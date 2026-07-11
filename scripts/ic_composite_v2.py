"""
多因子组合 v2 - 多种加权方案对比

测试：
1. 等权组合 (EW)
2. IC加权 (ICW) - 用滚动IC作为权重
3. 单因子分别测试
4. 不同前瞻天数 (5d, 10d, 20d)
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
               b.turnover_rate, b.turnover_rate_f, b.total_mv
        FROM daily d
        JOIN daily_basic b ON d.ts_code = b.ts_code AND d.trade_date = b.trade_date
        WHERE d.trade_date = ? AND d.open IS NOT NULL AND b.total_mv IS NOT NULL
    """
    return client.query(sql, [date])

def get_history(client, ts_codes, end_date, lookback=25):
    client._ensure_view("daily")
    placeholders = ", ".join("?" for _ in ts_codes)
    sql = f"SELECT ts_code, trade_date, close, pct_chg, vol, high, low FROM daily WHERE ts_code IN ({placeholders}) AND trade_date <= ? ORDER BY trade_date"
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
    df = pd.DataFrame({'val': series, 'ind': industry}).dropna()
    ranked = df.groupby('ind', group_keys=False)['val'].rank(pct=True)
    return ranked.reindex(series.index)

def compute_ic(a, b):
    merged = pd.DataFrame({'a': a, 'b': b}).dropna()
    if len(merged) < 30:
        return np.nan
    corr, _ = sp_stats.spearmanr(merged['a'], merged['b'])
    return corr

def run_factor_test(client, industry_map, trading_days, START_DATE, END_DATE, FORWARD_DAYS, N_GROUPS=5):
    """Run factor test for given forward days, return group_returns dict and IC dict"""
    CORE_FACTORS = ['turnover_rate', 'turnover_rate_f', 'volatility_20d']
    
    group_returns_ew = {g: [] for g in range(1, N_GROUPS + 1)}
    group_returns_icw = {g: [] for g in range(1, N_GROUPS + 1)}
    single_ics = {f: [] for f in CORE_FACTORS}
    composite_ics_ew = []
    composite_ics_icw = []
    ic_history = {f: [] for f in CORE_FACTORS}  # rolling IC for weighting
    
    valid_days = 0
    
    for i in range(len(trading_days) - FORWARD_DAYS - 1):
        date = trading_days[i]
        t_plus_1 = trading_days[i + 1]
        t_plus_n1 = trading_days[i + FORWARD_DAYS + 1]
        
        cs = get_data_for_date(client, date)
        if cs.empty or len(cs) < 200:
            continue
        
        cs['industry'] = cs['ts_code'].map(industry_map)
        cs = cs.dropna(subset=['industry'])
        if len(cs) < 200:
            continue
        
        history = get_history(client, cs['ts_code'].tolist(), date, lookback=25)
        idx = trading_days.index(date)
        
        if idx >= 20:
            recent = trading_days[max(0, idx-19):idx+1]
            hist_sub = history[history['trade_date'].isin(recent)]
            vol20 = hist_sub.groupby('ts_code')['pct_chg'].std()
            cs['volatility_20d'] = cs['ts_code'].map(vol20).values
        else:
            continue
        
        fwd_ret = get_forward_returns(client, cs['ts_code'].tolist(), t_plus_1, t_plus_n1)
        if fwd_ret.empty:
            continue
        
        merged = cs.merge(fwd_ret, on='ts_code', how='inner').dropna(subset=['forward_return'])
        if len(merged) < 200:
            continue
        
        valid_days += 1
        
        # Industry-neutral rank (higher = better)
        for f in CORE_FACTORS:
            if f not in merged.columns:
                continue
            raw_rank = industry_rank(merged[f], merged['industry'])
            merged[f'{f}_rank'] = 1 - raw_rank  # lower original value → higher rank
            ic = compute_ic(merged[f'{f}_rank'], merged['forward_return'])
            single_ics[f].append(ic)
            ic_history[f].append(ic)
        
        # Equal-weight composite
        rank_cols = [f'{f}_rank' for f in CORE_FACTORS if f'{f}_rank' in merged.columns]
        merged['composite_ew'] = merged[rank_cols].mean(axis=1)
        ew_ic = compute_ic(merged['composite_ew'], merged['forward_return'])
        composite_ics_ew.append(ew_ic)
        
        # IC-weighted composite (use rolling 20-period IC as weight)
        if valid_days >= 20:
            weights = {}
            for f in CORE_FACTORS:
                recent_ics = [x for x in ic_history[f][-20:] if not np.isnan(x)]
                weights[f] = abs(np.mean(recent_ics)) if recent_ics else 0
            total_w = sum(weights.values())
            if total_w > 0:
                for f in weights:
                    weights[f] /= total_w
            merged['composite_icw'] = sum(
                merged[f'{f}_rank'] * weights.get(f, 0) 
                for f in CORE_FACTORS if f'{f}_rank' in merged.columns
            )
            icw_ic = compute_ic(merged['composite_icw'], merged['forward_return'])
            composite_ics_icw.append(icw_ic)
        else:
            merged['composite_icw'] = merged['composite_ew']
            composite_ics_icw.append(ew_ic)
        
        # Quintile portfolios for both composites
        for comp_name, group_returns in [('composite_ew', group_returns_ew), ('composite_icw', group_returns_icw)]:
            try:
                merged['group'] = pd.qcut(merged[comp_name], N_GROUPS, labels=False, duplicates='drop') + 1
            except ValueError:
                continue
            for g in range(1, N_GROUPS + 1):
                grp = merged[merged['group'] == g]
                if len(grp) > 0:
                    group_returns[g].append(grp['forward_return'].mean())
    
    return {
        'valid_days': valid_days,
        'single_ics': single_ics,
        'composite_ics_ew': composite_ics_ew,
        'composite_ics_icw': composite_ics_icw,
        'group_returns_ew': group_returns_ew,
        'group_returns_icw': group_returns_icw,
    }

def print_results(results, forward_days, n_groups=5):
    """Print formatted results"""
    print(f"\n{'='*80}")
    print(f"前瞻 {forward_days} 天 | 有效截面: {results['valid_days']}")
    print(f"{'='*80}")
    
    # IC
    print(f"\n{'因子':<25} {'IC均值':>8} {'ICIR':>8} {'IC>0%':>8}")
    print("-" * 55)
    
    all_items = []
    for f, ics in results['single_ics'].items():
        clean = [x for x in ics if not np.isnan(x)]
        if clean:
            m, s = np.mean(clean), np.std(clean)
            all_items.append((f, m, s, m/s if s>0 else 0, np.mean([1 for x in clean if x>0])*100))
    
    for name, ics_key in [('EW composite', 'composite_ics_ew'), ('ICW composite', 'composite_ics_icw')]:
        clean = [x for x in results[ics_key] if not np.isnan(x)]
        if clean:
            m, s = np.mean(clean), np.std(clean)
            all_items.append((f'★ {name}', m, s, m/s if s>0 else 0, np.mean([1 for x in clean if x>0])*100))
    
    all_items.sort(key=lambda x: abs(x[3]), reverse=True)
    for name, m, s, ir, pct in all_items:
        judge = "✅" if abs(ir) >= 0.5 else ("⚠️" if abs(ir) >= 0.3 else "❌")
        print(f"{name:<25} {m:>8.4f} {ir:>8.3f} {pct:>7.1f}% {judge}")
    
    # Group returns
    for comp_name, group_returns in [('等权(EW)', results['group_returns_ew']), ('IC加权(ICW)', results['group_returns_icw'])]:
        print(f"\n{comp_name} 分组收益:")
        print(f"{'组别':<8} {'期均收益':>8} {'年化':>8} {'累计':>8}")
        print("-" * 36)
        
        periods_per_year = 252 / forward_days
        
        for g in range(1, n_groups + 1):
            rets = group_returns[g]
            if not rets:
                continue
            mean_r = np.mean(rets)
            ann_r = mean_r * periods_per_year
            cum = 1.0
            for r in rets:
                cum *= (1 + r)
            label = '最差' if g==1 else ('最好' if g==n_groups else '')
            print(f"G{g} {label:<4} {mean_r:>8.4f} {ann_r:>7.1%} {cum-1:>7.1%}")
        
        # Long-short
        if group_returns[n_groups] and group_returns[1]:
            ls = [r5 - r1 for r5, r1 in zip(group_returns[n_groups], group_returns[1])]
            ls_mean = np.mean(ls)
            ls_ann = ls_mean * periods_per_year
            ls_sharpe = ls_mean / np.std(ls) * np.sqrt(periods_per_year) if np.std(ls) > 0 else 0
            ls_cum = 1.0
            for r in ls:
                ls_cum *= (1 + r)
            print(f"  多空(G{n_groups}-G1): 年化{ls_ann:>7.1%} | Sharpe {ls_sharpe:>5.2f} | 累计{ls_cum-1:>7.1%}")

def main():
    print("=" * 80)
    print("多因子组合 v2 - 多前瞻天数 + 多加权方案")
    print("=" * 80)
    
    client = DuckDBClient("data/normalized")
    industry_map = get_industry_map()
    
    START_DATE = "2025-07-10"
    END_DATE = "2026-07-10"
    
    trading_days = get_trading_days(client, START_DATE, END_DATE)
    print(f"交易日: {len(trading_days)} 天")
    
    # Test multiple forward days
    for fwd in [5, 10, 20]:
        results = run_factor_test(client, industry_map, trading_days, START_DATE, END_DATE, fwd)
        print_results(results, fwd)

if __name__ == "__main__":
    main()
