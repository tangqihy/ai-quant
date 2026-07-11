"""
扩展因子IC分析 - 行业中性化

新增因子：
动量类: momentum_5d/10d/20d/60d
反转类: reversal_5d
波动类: volatility_20d, idio_vol_20d
换手类: abnormal_turnover_20d, turnover_rate_f
估值类: ps_ttm, circ_mv
技术类: price_pos_20d (20日高点位置), volume_ratio_20d (量比)
"""
import sys, os, warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from scipy import stats as sp_stats
from app.data.duckdb_client import DuckDBClient
from app.data.pit import PITQuery

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

def get_cross_section_with_history(client, date, history_days=60):
    """获取截面数据 + 历史数据用于计算技术因子"""
    client._ensure_view("daily")
    client._ensure_view("daily_basic")
    
    # Get all stocks that have data on this date
    sql = """
        SELECT d.ts_code, d.trade_date, d.open, d.high, d.low, d.close, d.pct_chg, d.vol, d.amount,
               b.turnover_rate, b.turnover_rate_f, b.volume_ratio, 
               b.pe_ttm, b.pb, b.ps_ttm, b.dv_ttm, b.total_mv, b.circ_mv
        FROM daily d
        JOIN daily_basic b ON d.ts_code = b.ts_code AND d.trade_date = b.trade_date
        WHERE d.trade_date = ?
          AND d.open IS NOT NULL AND b.total_mv IS NOT NULL
    """
    cs = client.query(sql, [date])
    return cs

def get_history(client, ts_codes, end_date, lookback=60):
    """获取历史行情数据用于计算动量/波动等"""
    client._ensure_view("daily")
    placeholders = ", ".join("?" for _ in ts_codes)
    sql = f"""
        SELECT ts_code, trade_date, close, pct_chg, vol, high, low
        FROM daily
        WHERE ts_code IN ({placeholders})
          AND trade_date <= ?
        ORDER BY trade_date
    """
    return client.query(sql, list(ts_codes) + [end_date])

def compute_technical_factors(cs, history, date, trading_days):
    """从截面+历史数据计算技术因子"""
    result = pd.DataFrame({'ts_code': cs['ts_code']})
    
    # 1. Momentum factors
    for lookback in [5, 10, 20, 60]:
        # Get the date N days ago
        idx = trading_days.index(date) if date in trading_days else -1
        if idx >= lookback:
            start_d = trading_days[idx - lookback]
            # Compute return from start_d to date
            hist_pivot = history.pivot(index='ts_code', columns='trade_date', values='close')
            if start_d in hist_pivot.columns and date in hist_pivot.columns:
                ret = (hist_pivot[date] / hist_pivot[start_d] - 1)
                result[f'momentum_{lookback}d'] = ret.values
    
    # 2. Reversal (negative 5d momentum)
    if 'momentum_5d' in result.columns:
        result['reversal_5d'] = -result['momentum_5d']
    
    # 3. Volatility (20d std of pct_chg)
    idx = trading_days.index(date) if date in trading_days else -1
    if idx >= 20:
        recent_days = trading_days[max(0, idx-19):idx+1]
        hist_subset = history[history['trade_date'].isin(recent_days)]
        vol_stats = hist_subset.groupby('ts_code')['pct_chg'].std()
        result['volatility_20d'] = result['ts_code'].map(vol_stats).values
    
    # 4. Abnormal turnover (current / 20d average)
    if idx >= 20:
        recent_days = trading_days[max(0, idx-19):idx+1]
        hist_subset = history[history['trade_date'].isin(recent_days)]
        avg_vol = hist_subset.groupby('ts_code')['vol'].mean()
        current_vol = cs.set_index('ts_code')['vol']
        abnorm = (current_vol / avg_vol).replace([np.inf, -np.inf], np.nan)
        result['abnormal_vol_20d'] = result['ts_code'].map(abnorm).values
    
    # 5. Price position relative to 20d high-low range
    if idx >= 20:
        recent_days = trading_days[max(0, idx-19):idx+1]
        hist_subset = history[history['trade_date'].isin(recent_days)]
        high_20d = hist_subset.groupby('ts_code')['high'].max()
        low_20d = hist_subset.groupby('ts_code')['low'].min()
        current_close = cs.set_index('ts_code')['close']
        range_20d = high_20d - low_20d
        pos = ((current_close - low_20d) / range_20d).replace([np.inf, -np.inf], np.nan)
        result['price_pos_20d'] = result['ts_code'].map(pos).values
    
    # 6. 60d volatility
    if idx >= 60:
        recent_days = trading_days[max(0, idx-59):idx+1]
        hist_subset = history[history['trade_date'].isin(recent_days)]
        vol60 = hist_subset.groupby('ts_code')['pct_chg'].std()
        result['volatility_60d'] = result['ts_code'].map(vol60).values
    
    # Merge daily_basic factors
    for col in ['turnover_rate', 'turnover_rate_f', 'volume_ratio', 'ps_ttm', 'circ_mv']:
        if col in cs.columns:
            result[col] = cs[col].values
    
    return result

def industry_neutralize(factor_series, industry_series):
    """行业中性化：行业内百分位排名"""
    df = pd.DataFrame({'factor': factor_series, 'industry': industry_series}).dropna()
    if len(df) < 10:
        return pd.Series(np.nan, index=factor_series.index)
    neutralized = df.groupby('industry', group_keys=False)['factor'].rank(pct=True)
    return neutralized.reindex(factor_series.index)

def compute_ic(factor_values, forward_returns):
    """Spearman rank IC"""
    merged = pd.DataFrame({'factor': factor_values, 'return': forward_returns}).dropna()
    if len(merged) < 30:
        return np.nan
    corr, _ = sp_stats.spearmanr(merged['factor'], merged['return'])
    return corr

def get_forward_returns(client, ts_codes, start_date, end_date):
    """T+1 open → T+N+1 open"""
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

def main():
    print("=" * 90)
    print("扩展因子IC分析（行业中性化，1年数据）")
    print("=" * 90)
    
    client = DuckDBClient("data/normalized")
    industry_map = get_industry_map()
    print(f"行业映射: {len(industry_map)} 只股票")
    
    START_DATE = "2025-07-10"
    END_DATE = "2026-07-10"
    FORWARD_DAYS = 10
    
    trading_days = get_trading_days(client, START_DATE, END_DATE)
    print(f"交易日: {len(trading_days)} 天")
    
    # Extended factor definitions
    FACTORS = {
        # 原始5个
        'total_mv':         {'direction': -1, 'category': '市值'},
        'pe_ttm':           {'direction': -1, 'category': '估值'},
        'pb':               {'direction': -1, 'category': '估值'},
        'turnover_rate':    {'direction': -1, 'category': '换手'},
        'dv_ttm':           {'direction':  1, 'category': '估值'},
        # 新增动量
        'momentum_5d':      {'direction':  1, 'category': '动量'},
        'momentum_10d':     {'direction':  1, 'category': '动量'},
        'momentum_20d':     {'direction':  1, 'category': '动量'},
        'momentum_60d':     {'direction':  1, 'category': '动量'},
        # 新增反转
        'reversal_5d':      {'direction':  1, 'category': '反转'},
        # 新增波动
        'volatility_20d':   {'direction': -1, 'category': '波动'},
        'volatility_60d':   {'direction': -1, 'category': '波动'},
        # 新增换手
        'abnormal_vol_20d': {'direction': -1, 'category': '换手'},
        'turnover_rate_f':  {'direction': -1, 'category': '换手'},
        # 新增估值
        'ps_ttm':           {'direction': -1, 'category': '估值'},
        'circ_mv':          {'direction': -1, 'category': '市值'},
        # 技术
        'price_pos_20d':    {'direction': -1, 'category': '技术'},
        'volume_ratio':     {'direction': -1, 'category': '技术'},
    }
    
    results = {f: {'raw_ic': [], 'neutral_ic': []} for f in FACTORS}
    valid_days = 0
    
    print(f"\n逐日计算 {len(FACTORS)} 个因子（共 {len(trading_days) - FORWARD_DAYS - 1} 个截面）...")
    
    for i in range(len(trading_days) - FORWARD_DAYS - 1):
        date = trading_days[i]
        t_plus_1 = trading_days[i + 1]
        t_plus_n1 = trading_days[i + FORWARD_DAYS + 1]
        
        # Get cross-section
        cs = get_cross_section_with_history(client, date)
        if cs.empty or len(cs) < 100:
            continue
        
        # Add industry
        cs['industry'] = cs['ts_code'].map(industry_map)
        cs = cs.dropna(subset=['industry'])
        if len(cs) < 100:
            continue
        
        # Get history for technical factors
        history = get_history(client, cs['ts_code'].tolist(), date, lookback=60)
        
        # Compute technical factors
        tech = compute_technical_factors(cs, history, date, trading_days)
        
        # Get forward returns
        fwd_ret = get_forward_returns(client, cs['ts_code'].tolist(), t_plus_1, t_plus_n1)
        if fwd_ret.empty:
            continue
        
        # Merge all
        merged = tech.merge(fwd_ret, on='ts_code', how='inner')
        merged['industry'] = merged['ts_code'].map(industry_map)
        
        if len(merged) < 100:
            continue
        
        valid_days += 1
        
        # Compute IC for each factor
        for fname, finfo in FACTORS.items():
            if fname not in merged.columns:
                continue
            
            direction = finfo['direction']
            raw_factor = merged[fname] * direction
            
            # Raw IC
            raw_ic = compute_ic(raw_factor, merged['forward_return'])
            
            # Neutralized IC
            neutral_factor = industry_neutralize(raw_factor, merged['industry'])
            neutral_ic = compute_ic(neutral_factor, merged['forward_return'])
            
            results[fname]['raw_ic'].append(raw_ic)
            results[fname]['neutral_ic'].append(neutral_ic)
        
        if (i + 1) % 30 == 0:
            print(f"  已处理 {i+1}/{len(trading_days) - FORWARD_DAYS - 1} 个截面")
    
    print(f"\n有效截面数: {valid_days}")
    
    # Output results
    print("\n" + "=" * 90)
    print("因子IC对比：原始 vs 行业中性化（1年，232截面）")
    print("=" * 90)
    print(f"{'因子':<20} {'类别':<6} {'原始IC均值':>10} {'原始ICIR':>10} {'中性IC均值':>10} {'中性ICIR':>10} {'IC变化':>8} {'判断':>6}")
    print("-" * 90)
    
    # Sort by neutral ICIR absolute value
    sorted_factors = []
    for fname in FACTORS:
        raw_ics = [x for x in results[fname]['raw_ic'] if not np.isnan(x)]
        neu_ics = [x for x in results[fname]['neutral_ic'] if not np.isnan(x)]
        if not raw_ics or not neu_ics:
            continue
        raw_mean = np.mean(raw_ics)
        raw_std = np.std(raw_ics)
        raw_ir = raw_mean / raw_std if raw_std > 0 else 0
        neu_mean = np.mean(neu_ics)
        neu_std = np.std(neu_ics)
        neu_ir = neu_mean / neu_std if neu_std > 0 else 0
        sorted_factors.append((fname, FACTORS[fname]['category'], raw_mean, raw_ir, neu_mean, neu_ir))
    
    sorted_factors.sort(key=lambda x: abs(x[5]), reverse=True)
    
    for fname, cat, raw_mean, raw_ir, neu_mean, neu_ir in sorted_factors:
        ir_change = abs(neu_ir) - abs(raw_ir)
        change_str = f"{'↑' if ir_change > 0 else '↓'}{abs(ir_change):.3f}"
        
        # Judgment
        abs_ir = abs(neu_ir)
        if abs_ir >= 0.5:
            judge = "✅有效"
        elif abs_ir >= 0.3:
            judge = "⚠️弱"
        else:
            judge = "❌"
        
        print(f"{fname:<20} {cat:<6} {raw_mean:>10.4f} {raw_ir:>10.3f} {neu_mean:>10.4f} {neu_ir:>10.3f} {change_str:>8} {judge:>6}")
    
    print("-" * 90)
    print("判断标准: |ICIR| > 0.5 有效, > 0.3 弱信号")
    print("方向: 动量/反转=正相关, 波动/换手/市值=负相关（低X更好）")

if __name__ == "__main__":
    main()
