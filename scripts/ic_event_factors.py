"""
事件/消息因子IC分析

因子：
1. forecast_surprise: 业绩预告惊喜度 (p_change 取中值)
2. express_surprise: 业绩快报净利润增速
3. dividend_yield_event: 分红事件 (现金分红/股价)
4. repurchase_signal: 回购信号 (近期是否有回购公告)
5. share_float_pressure: 解禁压力 (未来30天解禁比例)
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

def compute_ic(a, b):
    merged = pd.DataFrame({'a': a, 'b': b}).dropna()
    if len(merged) < 30:
        return np.nan
    corr, _ = sp_stats.spearmanr(merged['a'], merged['b'])
    return corr

def industry_rank(series, industry):
    df = pd.DataFrame({'val': series, 'ind': industry}).dropna()
    ranked = df.groupby('ind', group_keys=False)['val'].rank(pct=True)
    return ranked.reindex(series.index)

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

def main():
    print("=" * 90)
    print("事件/消息因子IC分析（行业中性化）")
    print("=" * 90)
    
    client = DuckDBClient("data/normalized")
    industry_map = get_industry_map()
    
    START_DATE = "2025-07-10"
    END_DATE = "2026-07-10"
    FORWARD_DAYS = 10
    
    trading_days = get_trading_days(client, START_DATE, END_DATE)
    print(f"交易日: {len(trading_days)} 天")
    
    # Pre-load event data
    client._ensure_view("forecast")
    client._ensure_view("express")
    client._ensure_view("dividend")
    client._ensure_view("repurchase")
    client._ensure_view("share_float")
    
    # Load all event data into memory for fast lookup
    print("加载事件数据...")
    forecast_all = client.query("SELECT ts_code, ann_date, p_change_min, p_change_max FROM forecast WHERE ann_date IS NOT NULL")
    express_all = client.query("SELECT ts_code, ann_date, revenue, n_income, total_assets FROM express WHERE ann_date IS NOT NULL")
    dividend_all = client.query("SELECT ts_code, ann_date, cash_div, record_date FROM dividend WHERE ann_date IS NOT NULL AND cash_div > 0")
    repurchase_all = client.query("SELECT ts_code, ann_date, vol, amount FROM repurchase WHERE ann_date IS NOT NULL")
    share_float_all = client.query("SELECT ts_code, ann_date, float_date, float_share, float_ratio FROM share_float WHERE float_date IS NOT NULL")
    
    print(f"  forecast: {len(forecast_all)} records")
    print(f"  express: {len(express_all)} records")
    print(f"  dividend: {len(dividend_all)} records")
    print(f"  repurchase: {len(repurchase_all)} records")
    print(f"  share_float: {len(share_float_all)} records")
    
    # Normalize dates
    for df in [forecast_all, express_all, dividend_all, repurchase_all]:
        if 'ann_date' in df.columns:
            df['ann_date'] = pd.to_datetime(df['ann_date'], errors='coerce').dt.strftime('%Y-%m-%d')
    if not share_float_all.empty:
        share_float_all['float_date'] = pd.to_datetime(share_float_all['float_date'], errors='coerce').dt.strftime('%Y-%m-%d')
        share_float_all['ann_date'] = pd.to_datetime(share_float_all['ann_date'], errors='coerce').dt.strftime('%Y-%m-%d')
    
    # Get daily_basic for price data
    client._ensure_view("daily_basic")
    client._ensure_view("daily")
    
    FACTORS = {
        'forecast_surprise': {'direction': 1, 'category': '业绩'},
        'express_growth': {'direction': 1, 'category': '业绩'},
        'dividend_event': {'direction': 1, 'category': '分红'},
        'repurchase_signal': {'direction': 1, 'category': '回购'},
        'float_pressure': {'direction': -1, 'category': '解禁'},
        # Composite with market factors
        'turnover_rate': {'direction': -1, 'category': '换手'},
    }
    
    results = {f: {'raw_ic': [], 'neutral_ic': []} for f in FACTORS}
    valid_days = 0
    
    print(f"\n逐日计算事件因子（{len(trading_days) - FORWARD_DAYS - 1} 个截面）...")
    
    for i in range(len(trading_days) - FORWARD_DAYS - 1):
        date = trading_days[i]
        t_plus_1 = trading_days[i + 1]
        t_plus_n1 = trading_days[i + FORWARD_DAYS + 1]
        
        # Get cross-section with daily_basic
        client._ensure_view("daily")
        client._ensure_view("daily_basic")
        cs = client.query("""
            SELECT d.ts_code, d.close, b.turnover_rate, b.total_mv
            FROM daily d
            JOIN daily_basic b ON d.ts_code = b.ts_code AND d.trade_date = b.trade_date
            WHERE d.trade_date = ? AND d.open IS NOT NULL AND b.total_mv IS NOT NULL
        """, [date])
        
        if cs.empty or len(cs) < 200:
            continue
        
        cs['industry'] = cs['ts_code'].map(industry_map)
        cs = cs.dropna(subset=['industry'])
        if len(cs) < 200:
            continue
        
        # === Build event factors ===
        
        # 1. Forecast surprise: p_change midpoint, look at announcements in last 30 days
        cs['forecast_surprise'] = np.nan
        if not forecast_all.empty:
            idx = trading_days.index(date)
            lookback_30 = trading_days[max(0, idx-29):idx+1]
            recent_fc = forecast_all[forecast_all['ann_date'].isin(lookback_30)]
            if not recent_fc.empty:
                recent_fc = recent_fc.copy()
                recent_fc['p_change_mid'] = (recent_fc['p_change_min'].astype(float) + recent_fc['p_change_max'].astype(float)) / 2
                # Latest per stock
                latest_fc = recent_fc.sort_values('ann_date').groupby('ts_code')['p_change_mid'].last()
                cs['forecast_surprise'] = cs['ts_code'].map(latest_fc).values
        
        # 2. Express growth: n_income growth, look at announcements in last 60 days
        cs['express_growth'] = np.nan
        if not express_all.empty:
            lookback_60 = trading_days[max(0, idx-59):idx+1]
            recent_ex = express_all[express_all['ann_date'].isin(lookback_60)]
            if not recent_ex.empty:
                recent_ex = recent_ex.copy()
                recent_ex['n_income'] = pd.to_numeric(recent_ex['n_income'], errors='coerce')
                latest_ex = recent_ex.sort_values('ann_date').groupby('ts_code')['n_income'].last()
                # Normalize by total_mv
                cs['express_growth'] = cs['ts_code'].map(latest_ex).values
                # Use n_income / close as a yield proxy
                cs['express_growth'] = cs['express_growth'] / cs['close'].replace(0, np.nan)
        
        # 3. Dividend event: cash dividends announced in last 30 days
        cs['dividend_event'] = 0.0
        if not dividend_all.empty:
            lookback_30 = trading_days[max(0, idx-29):idx+1]
            recent_div = dividend_all[dividend_all['ann_date'].isin(lookback_30)]
            if not recent_div.empty:
                recent_div = recent_div.copy()
                recent_div['cash_div'] = pd.to_numeric(recent_div['cash_div'], errors='coerce')
                total_div = recent_div.groupby('ts_code')['cash_div'].sum()
                cs['dividend_event'] = cs['ts_code'].map(total_div).fillna(0).values
                # Normalize by price
                cs['dividend_event'] = cs['dividend_event'] / cs['close'].replace(0, np.nan)
        
        # 4. Repurchase signal: any repurchase announced in last 30 days
        cs['repurchase_signal'] = 0.0
        if not repurchase_all.empty:
            lookback_30 = trading_days[max(0, idx-29):idx+1]
            recent_rp = repurchase_all[repurchase_all['ann_date'].isin(lookback_30)]
            if not recent_rp.empty:
                has_rp = recent_rp.groupby('ts_code').size()
                cs['repurchase_signal'] = cs['ts_code'].map(has_rp).fillna(0).values
                cs['repurchase_signal'] = (cs['repurchase_signal'] > 0).astype(float)
        
        # 5. Float pressure: upcoming float in next 30 days / total_mv
        cs['float_pressure'] = 0.0
        if not share_float_all.empty:
            future_30 = trading_days[idx:min(len(trading_days), idx+30)]
            upcoming = share_float_all[share_float_all['float_date'].isin(future_30)]
            if not upcoming.empty:
                upcoming = upcoming.copy()
                upcoming['float_share'] = pd.to_numeric(upcoming['float_share'], errors='coerce')
                total_float = upcoming.groupby('ts_code')['float_share'].sum()
                cs['float_pressure'] = cs['ts_code'].map(total_float).fillna(0).values
                # Normalize by total_mv
                cs['float_pressure'] = cs['float_pressure'] / (cs['total_mv'].replace(0, np.nan) / 10000)  # total_mv in 万元
        
        # 6. Turnover rate (benchmark)
        cs['turnover_rate'] = cs['turnover_rate']
        
        # Forward returns
        fwd_ret = get_forward_returns(client, cs['ts_code'].tolist(), t_plus_1, t_plus_n1)
        if fwd_ret.empty:
            continue
        
        merged = cs.merge(fwd_ret, on='ts_code', how='inner').dropna(subset=['forward_return'])
        if len(merged) < 100:
            continue
        
        valid_days += 1
        
        # Compute IC for each factor
        for fname, finfo in FACTORS.items():
            if fname not in merged.columns:
                continue
            
            # Drop NaN for this factor
            sub = merged.dropna(subset=[fname])
            if len(sub) < 50:
                continue
            
            direction = finfo['direction']
            raw_factor = sub[fname] * direction
            
            raw_ic = compute_ic(raw_factor, sub['forward_return'])
            
            # Industry neutralize
            neutral_factor = industry_rank(raw_factor, sub['industry'])
            neutral_ic = compute_ic(neutral_factor, sub['forward_return'])
            
            results[fname]['raw_ic'].append(raw_ic)
            results[fname]['neutral_ic'].append(neutral_ic)
        
        if (i + 1) % 30 == 0:
            print(f"  已处理 {i+1}/{len(trading_days) - FORWARD_DAYS - 1}")
    
    print(f"\n有效截面数: {valid_days}")
    
    # Output
    print("\n" + "=" * 90)
    print("事件/消息因子IC分析结果")
    print("=" * 90)
    print(f"{'因子':<22} {'类别':<6} {'原始IC均值':>10} {'原始ICIR':>8} {'中性IC均值':>10} {'中性ICIR':>8} {'判断':>6}")
    print("-" * 80)
    
    sorted_f = []
    for fname in FACTORS:
        raw = [x for x in results[fname]['raw_ic'] if not np.isnan(x)]
        neu = [x for x in results[fname]['neutral_ic'] if not np.isnan(x)]
        if not raw or not neu:
            continue
        rm, rs = np.mean(raw), np.std(raw)
        nm, ns = np.mean(neu), np.std(neu)
        sorted_f.append((fname, FACTORS[fname]['category'], rm, rm/rs if rs>0 else 0, nm, nm/ns if ns>0 else 0))
    
    sorted_f.sort(key=lambda x: abs(x[5]), reverse=True)
    
    for fname, cat, rm, ri, nm, ni in sorted_f:
        judge = "✅" if abs(ni) >= 0.5 else ("⚠️" if abs(ni) >= 0.3 else "❌")
        print(f"{fname:<22} {cat:<6} {rm:>10.4f} {ri:>8.3f} {nm:>10.4f} {ni:>8.3f} {judge:>6}")
    
    print("-" * 80)
    print("判断标准: |ICIR| > 0.5 有效, > 0.3 弱信号")
    
    # Also check event coverage
    print(f"\n事件覆盖率（有事件数据的股票占比）:")
    print(f"  forecast: {len(forecast_all['ts_code'].unique())} 只股票有业绩预告")
    print(f"  express: {len(express_all['ts_code'].unique())} 只股票有业绩快报")
    print(f"  dividend: {len(dividend_all['ts_code'].unique())} 只股票有分红")
    print(f"  repurchase: {len(repurchase_all['ts_code'].unique())} 只股票有回购")
    print(f"  share_float: {len(share_float_all['ts_code'].unique())} 只股票有解禁")

if __name__ == "__main__":
    main()
