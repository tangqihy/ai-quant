"""
多因子组合IC分析 + 分组回测

核心因子：turnover_rate, turnover_rate_f, volatility_20d
方法：行业内百分位排名 → 等权/IC加权组合 → 分组收益
"""
import sys, os, warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from scipy import stats as sp_stats
from app.data.duckdb_client import DuckDBClient

def get_industry_map():
    import tushare as ts
    pro = ts.pro_api()
    df = pro.stock_basic(exchange='', list_status='L', fields='ts_code,industry')
    return df.dropna(subset=['industry']).set_index('ts_code')['industry'].to_dict()

def get_trading_days(client, start, end):
    client._ensure_view("daily")
    sql = "SELECT DISTINCT trade_date FROM daily WHERE trade_date >= ? AND trade_date <= ? ORDER BY trade_date"
    df = client.query(sql, [start, end])
    return [str(d)[:10] for d in df['trade_date'].tolist()]

def get_data_for_date(client, date):
    client._ensure_view("daily")
    client._ensure_view("daily_basic")
    sql = """
        SELECT d.ts_code, d.close, d.pct_chg, d.vol, d.high, d.low, d.open,
               b.turnover_rate, b.turnover_rate_f, b.volume_ratio, b.total_mv
        FROM daily d
        JOIN daily_basic b ON d.ts_code = b.ts_code AND d.trade_date = b.trade_date
        WHERE d.trade_date = ? AND d.open IS NOT NULL AND b.total_mv IS NOT NULL
    """
    return client.query(sql, [date])

def get_history(client, ts_codes, end_date, lookback=30):
    client._ensure_view("daily")
    placeholders = ", ".join("?" for _ in ts_codes)
    sql = f"""
        SELECT ts_code, trade_date, close, pct_chg, vol, high, low
        FROM daily WHERE ts_code IN ({placeholders}) AND trade_date <= ?
        ORDER BY trade_date
    """
    return client.query(sql, list(ts_codes) + [end_date])

def get_forward_returns(client, ts_codes, start_date, end_date):
    client._ensure_view("daily")
    placeholders = ", ".join("?" for _ in ts_codes)
    sql = f"SELECT ts_code, trade_date, open FROM daily WHERE ts_code IN ({placeholders}) AND trade_date IN (?, ?)"
    df = client.query(sql, list(ts_codes) + [start_date, end_date])
    if df.empty:
        return pd.DataFrame(columns=['ts_code', 'forward_return'])
    pivot = df.pivot(index='ts_code', columns='trade_date', values='open')
    dates = sorted(pivot.columns)
    if len(dates) < 2:
        return pd.DataFrame(columns=['ts_code', 'forward_return'])
    ret = ((pivot[dates[-1]] / pivot[dates[0]]) - 1).dropna()
    ret.name = 'forward_return'
    return ret.reset_index()

def industry_rank(series, industry):
    """行业内百分位排名 (0-1)"""
    df = pd.DataFrame({'val': series, 'ind': industry}).dropna()
    ranked = df.groupby('ind', group_keys=False)['val'].rank(pct=True)
    return ranked.reindex(series.index)

def compute_ic(a, b):
    merged = pd.DataFrame({'a': a, 'b': b}).dropna()
    if len(merged) < 30:
        return np.nan
    corr, _ = sp_stats.spearmanr(merged['a'], merged['b'])
    return corr

def main():
    print("=" * 90)
    print("多因子组合分析（行业中性化，1年数据）")
    print("=" * 90)
    
    client = DuckDBClient("data/normalized")
    industry_map = get_industry_map()
    
    START_DATE = "2025-07-10"
    END_DATE = "2026-07-10"
    FORWARD_DAYS = 10
    N_GROUPS = 5
    
    trading_days = get_trading_days(client, START_DATE, END_DATE)
    print(f"交易日: {len(trading_days)} 天, 前瞻: {FORWARD_DAYS}天, 分组: {N_GROUPS}组")
    
    # Core factors (direction: all "lower is better" → rank as-is, higher rank = lower value)
    CORE_FACTORS = ['turnover_rate', 'turnover_rate_f', 'volatility_20d']
    
    # Storage for group returns and IC
    group_returns = {g: [] for g in range(1, N_GROUPS + 1)}
    composite_ics = []
    single_ics = {f: [] for f in CORE_FACTORS}
    
    valid_days = 0
    
    for i in range(len(trading_days) - FORWARD_DAYS - 1):
        date = trading_days[i]
        t_plus_1 = trading_days[i + 1]
        t_plus_n1 = trading_days[i + FORWARD_DAYS + 1]
        
        # Get data
        cs = get_data_for_date(client, date)
        if cs.empty or len(cs) < 200:
            continue
        
        cs['industry'] = cs['ts_code'].map(industry_map)
        cs = cs.dropna(subset=['industry'])
        if len(cs) < 200:
            continue
        
        # History for volatility
        history = get_history(client, cs['ts_code'].tolist(), date, lookback=25)
        idx = trading_days.index(date)
        
        # Compute 20d volatility
        if idx >= 20:
            recent = trading_days[max(0, idx-19):idx+1]
            hist_sub = history[history['trade_date'].isin(recent)]
            vol20 = hist_sub.groupby('ts_code')['pct_chg'].std()
            cs['volatility_20d'] = cs['ts_code'].map(vol20).values
        else:
            continue
        
        # Forward returns
        fwd_ret = get_forward_returns(client, cs['ts_code'].tolist(), t_plus_1, t_plus_n1)
        if fwd_ret.empty:
            continue
        
        merged = cs.merge(fwd_ret, on='ts_code', how='inner').dropna(subset=['forward_return'])
        if len(merged) < 200:
            continue
        
        valid_days += 1
        
        # Industry-neutral rank for each factor (higher = better, so for "lower is better" we use 1-rank)
        for f in CORE_FACTORS:
            if f not in merged.columns:
                continue
            # rank within industry: higher raw rank = higher value
            # Since "lower is better", we want: neutral_rank = 1 - industry_rank
            raw_rank = industry_rank(merged[f], merged['industry'])
            merged[f'{f}_rank'] = 1 - raw_rank  # flip: now higher = better (lower original value)
        
        # Composite: equal-weight of neutralized ranks
        rank_cols = [f'{f}_rank' for f in CORE_FACTORS if f'{f}_rank' in merged.columns]
        if len(rank_cols) < 3:
            continue
        
        merged['composite'] = merged[rank_cols].mean(axis=1)
        
        # IC analysis
        for f in CORE_FACTORS:
            ic = compute_ic(merged[f'{f}_rank'], merged['forward_return'])
            single_ics[f].append(ic)
        
        composite_ic = compute_ic(merged['composite'], merged['forward_return'])
        composite_ics.append(composite_ic)
        
        # Quintile portfolios
        try:
            merged['group'] = pd.qcut(merged['composite'], N_GROUPS, labels=False, duplicates='drop') + 1
        except ValueError:
            continue
        
        for g in range(1, N_GROUPS + 1):
            grp = merged[merged['group'] == g]
            if len(grp) > 0:
                group_returns[g].append(grp['forward_return'].mean())
        
        if (i + 1) % 30 == 0:
            print(f"  已处理 {i+1}/{len(trading_days) - FORWARD_DAYS - 1}")
    
    print(f"\n有效截面数: {valid_days}")
    
    # ========== IC Summary ==========
    print("\n" + "=" * 90)
    print("因子IC对比")
    print("=" * 90)
    print(f"{'因子':<25} {'IC均值':>10} {'IC标准差':>10} {'ICIR':>10} {'IC>0%':>8} {'判断':>6}")
    print("-" * 75)
    
    all_items = list(single_ics.items()) + [('composite_equal_weight', composite_ics)]
    all_items.sort(key=lambda x: abs(np.mean([v for v in x[1] if not np.isnan(v)]) / max(np.std([v for v in x[1] if not np.isnan(v)]), 1e-6)), reverse=True)
    
    for name, ics in all_items:
        clean = [x for x in ics if not np.isnan(x)]
        if not clean:
            continue
        mean = np.mean(clean)
        std = np.std(clean)
        ir = mean / std if std > 0 else 0
        pct_pos = np.mean([1 for x in clean if x > 0]) * 100
        judge = "✅" if abs(ir) >= 0.5 else ("⚠️" if abs(ir) >= 0.3 else "❌")
        label = name.replace('_rank', '').replace('composite_equal_weight', '★ composite')
        print(f"{label:<25} {mean:>10.4f} {std:>10.4f} {ir:>10.3f} {pct_pos:>7.1f}% {judge:>6}")
    
    # ========== Group Returns ==========
    print("\n" + "=" * 90)
    print(f"分组收益（{N_GROUPS}组，每组等权，每{FORWARD_DAYS}天调仓）")
    print("=" * 90)
    
    # Per-period stats
    print(f"\n{'组别':<8} {'期均收益':>10} {'年化收益':>10} {'胜率':>8} {'累计收益':>10}")
    print("-" * 55)
    
    periods_per_year = 252 / FORWARD_DAYS
    cumulative = {g: 1.0 for g in range(1, N_GROUPS + 1)}
    
    for g in range(1, N_GROUPS + 1):
        rets = group_returns[g]
        if not rets:
            continue
        mean_ret = np.mean(rets)
        ann_ret = mean_ret * periods_per_year
        win_rate = np.mean([1 for r in rets if r > 0]) * 100
        for r in rets:
            cumulative[g] *= (1 + r)
        total_ret = cumulative[g] - 1
        print(f"G{g} ({'最差' if g==1 else '最好' if g==N_GROUPS else '中间':<4}) {mean_ret:>10.4f} {ann_ret:>10.2%} {win_rate:>7.1f}% {total_ret:>10.2%}")
    
    # Long-short
    if group_returns[N_GROUPS] and group_returns[1]:
        ls_rets = [r5 - r1 for r5, r1 in zip(group_returns[N_GROUPS], group_returns[1])]
        ls_mean = np.mean(ls_rets)
        ls_ann = ls_mean * periods_per_year
        ls_sharpe = ls_mean / np.std(ls_rets) * np.sqrt(periods_per_year) if np.std(ls_rets) > 0 else 0
        ls_cum = 1.0
        for r in ls_rets:
            ls_cum *= (1 + r)
        ls_dd = 0
        peak = 1.0
        cum = 1.0
        for r in ls_rets:
            cum *= (1 + r)
            peak = max(peak, cum)
            dd = (peak - cum) / peak
            ls_dd = max(ls_dd, dd)
        
        print(f"\n多空组合（G{N_GROUPS} - G1）:")
        print(f"  期均收益: {ls_mean:.4f}")
        print(f"  年化收益: {ls_ann:.2%}")
        print(f"  年化Sharpe: {ls_sharpe:.2f}")
        print(f"  累计收益: {ls_cum - 1:.2%}")
        print(f"  最大回撤: {ls_dd:.2%}")
    
    # ========== Buy-and-hold cumulative ==========
    print("\n" + "=" * 90)
    print("各组净值曲线（累计）")
    print("=" * 90)
    
    nav = {g: [1.0] for g in range(1, N_GROUPS + 1)}
    for t in range(len(group_returns[1])):
        for g in range(1, N_GROUPS + 1):
            if t < len(group_returns[g]):
                nav[g].append(nav[g][-1] * (1 + group_returns[g][t]))
            else:
                nav[g].append(nav[g][-1])
    
    print(f"\n{'调仓期':<8}", end="")
    for g in range(1, N_GROUPS + 1):
        print(f"{'G'+str(g):>10}", end="")
    print(f"{'G5-G1':>10}")
    print("-" * (8 + 10 * (N_GROUPS + 1)))
    
    # Show every 10th period
    for t in range(0, len(nav[1]), 10):
        print(f"T+{t*FORWARD_DAYS:<5}", end="")
        for g in range(1, N_GROUPS + 1):
            print(f"{nav[g][t]:>10.4f}", end="")
        if t < len(group_returns[N_GROUPS]) and t < len(group_returns[1]):
            ls_nav = nav[N_GROUPS][t] / nav[1][t]
            print(f"{ls_nav:>10.4f}", end="")
        print()
    
    # Final
    print(f"\n最终", end="")
    for g in range(1, N_GROUPS + 1):
        print(f"{nav[g][-1]:>10.4f}", end="")
    print(f"{nav[N_GROUPS][-1] / nav[1][-1]:>10.4f}")

if __name__ == "__main__":
    main()
