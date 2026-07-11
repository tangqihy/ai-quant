"""
行业中性化因子IC分析

方法：
1. 获取 stock_basic 的 industry 分类
2. 每个截面日期，按行业分组计算因子百分位排名
3. 中性化因子值 = 行业内百分位排名（0-1）
4. 比较原始IC vs 中性化IC
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from scipy import stats as sp_stats
from app.data.duckdb_client import DuckDBClient
from app.data.pit import PITQuery

def get_industry_map():
    """获取股票-行业映射"""
    import tushare as ts
    pro = ts.pro_api()
    df = pro.stock_basic(exchange='', list_status='L', fields='ts_code,industry')
    return df.dropna(subset=['industry']).set_index('ts_code')['industry'].to_dict()

def get_trading_days(pit_query, start, end):
    """获取交易日列表（从daily表中提取）"""
    client = pit_query.client
    client._ensure_view("daily")
    sql = """
        SELECT DISTINCT trade_date FROM daily
        WHERE trade_date >= ? AND trade_date <= ?
        ORDER BY trade_date
    """
    df = client.query(sql, [start, end])
    return [str(d)[:10] for d in df['trade_date'].tolist()]

def get_cross_section(client, date):
    """获取某日的全市场截面数据"""
    client._ensure_view("daily")
    client._ensure_view("daily_basic")
    
    sql = """
        SELECT d.ts_code, d.open as open_price,
               b.total_mv, b.pe_ttm, b.pb, b.turnover_rate, b.dv_ttm
        FROM daily d
        JOIN daily_basic b ON d.ts_code = b.ts_code AND d.trade_date = b.trade_date
        WHERE d.trade_date = ?
          AND d.open IS NOT NULL
          AND b.total_mv IS NOT NULL
    """
    return client.query(sql, [date])

def get_forward_returns(client, ts_codes, start_date, end_date):
    """获取前瞻收益 (T+1 open → T+N+1 open)"""
    client._ensure_view("daily")
    placeholders = ", ".join("?" for _ in ts_codes)
    sql = f"""
        SELECT ts_code, trade_date, open FROM daily
        WHERE ts_code IN ({placeholders}) AND trade_date IN (?, ?)
    """
    params = list(ts_codes) + [start_date, end_date]
    df = client.query(sql, params)
    if df.empty:
        return pd.DataFrame(columns=['ts_code', 'forward_return'])
    pivot = df.pivot(index='ts_code', columns='trade_date', values='open')
    dates = sorted(pivot.columns)
    if len(dates) < 2:
        return pd.DataFrame(columns=['ts_code', 'forward_return'])
    ret = ((pivot[dates[-1]] / pivot[dates[0]]) - 1).dropna()
    ret.name = 'forward_return'
    return ret.reset_index()

def industry_neutralize(factor_series, industry_series):
    """
    行业中性化：在每个行业内计算百分位排名
    返回 0-1 的值，表示该股票在其行业内的相对位置
    """
    df = pd.DataFrame({'factor': factor_series, 'industry': industry_series})
    df = df.dropna()
    
    def rank_within_group(group):
        if len(group) < 3:
            return pd.Series(np.nan, index=group.index)
        return group['factor'].rank(pct=True)
    
    neutralized = df.groupby('industry').apply(rank_within_group)
    # flatten multi-index
    if isinstance(neutralized.index, pd.MultiIndex):
        neutralized = neutralized.droplevel(0)
    return neutralized

def compute_ic(factor_values, forward_returns, method='spearman'):
    """计算Spearman rank IC"""
    merged = pd.DataFrame({
        'factor': factor_values,
        'return': forward_returns
    }).dropna()
    if len(merged) < 30:
        return np.nan
    corr, _ = sp_stats.spearmanr(merged['factor'], merged['return'])
    return corr

def main():
    print("=" * 80)
    print("行业中性化因子IC分析")
    print("=" * 80)
    
    # 初始化
    client = DuckDBClient("data/normalized")
    pit_query = PITQuery(client)
    
    # 获取行业映射
    print("\n获取行业映射...")
    industry_map = get_industry_map()
    print(f"  有效行业映射: {len(industry_map)} 只股票")
    
    # 参数
    START_DATE = "2025-07-10"
    END_DATE = "2026-07-10"
    FORWARD_DAYS = 10  # 10个交易日前瞻
    
    # 因子列表
    FACTORS = {
        'total_mv': {'col': 'total_mv', 'direction': -1},
        'pe_ttm': {'col': 'pe_ttm', 'direction': -1},
        'pb': {'col': 'pb', 'direction': -1},
        'turnover_rate': {'col': 'turnover_rate', 'direction': -1},
        'dv_ttm': {'col': 'dv_ttm', 'direction': 1},
    }
    
    # 获取交易日
    trading_days = get_trading_days(pit_query, START_DATE, END_DATE)
    print(f"  交易日: {len(trading_days)} 天")
    print(f"  前瞻天数: {FORWARD_DAYS} 天")
    
    # 存储结果
    results = {f: {'raw_ic': [], 'neutral_ic': []} for f in FACTORS}
    
    print(f"\n逐日计算IC（共 {len(trading_days) - FORWARD_DAYS - 1} 个截面）...")
    
    valid_days = 0
    for i in range(len(trading_days) - FORWARD_DAYS - 1):
        date = trading_days[i]
        t_plus_1 = trading_days[i + 1]
        t_plus_n1 = trading_days[i + FORWARD_DAYS + 1]
        
        # 获取截面数据
        cs = get_cross_section(client, date)
        if cs.empty or len(cs) < 100:
            continue
        
        # 添加行业
        cs['industry'] = cs['ts_code'].map(industry_map)
        cs = cs.dropna(subset=['industry'])
        if len(cs) < 100:
            continue
        
        # 获取前瞻收益
        fwd_ret = get_forward_returns(client, cs['ts_code'].tolist(), t_plus_1, t_plus_n1)
        if fwd_ret.empty:
            continue
        
        merged = cs.merge(fwd_ret, on='ts_code', how='inner')
        if len(merged) < 100:
            continue
        
        valid_days += 1
        
        # 对每个因子计算原始IC和中性化IC
        for fname, finfo in FACTORS.items():
            col = finfo['col']
            direction = finfo['direction']
            
            if col not in merged.columns:
                continue
            
            raw_factor = merged[col] * direction
            
            # 原始IC
            raw_ic = compute_ic(raw_factor, merged['forward_return'])
            
            # 行业中性化
            neutral_factor = industry_neutralize(raw_factor, merged['industry'])
            
            # 中性化IC
            neutral_ic = compute_ic(neutral_factor, merged['forward_return'])
            
            results[fname]['raw_ic'].append(raw_ic)
            results[fname]['neutral_ic'].append(neutral_ic)
        
        if (i + 1) % 20 == 0:
            print(f"  已处理 {i+1}/{len(trading_days) - FORWARD_DAYS - 1} 个截面")
    
    print(f"\n有效截面数: {valid_days}")
    
    # 输出结果
    print("\n" + "=" * 80)
    print("因子IC对比：原始 vs 行业中性化")
    print("=" * 80)
    print(f"{'因子':<18} {'原始IC均值':>10} {'原始ICIR':>10} {'中性IC均值':>10} {'中性ICIR':>10} {'IC变化':>8}")
    print("-" * 80)
    
    for fname in FACTORS:
        raw_ics = [x for x in results[fname]['raw_ic'] if not np.isnan(x)]
        neu_ics = [x for x in results[fname]['neutral_ic'] if not np.isnan(x)]
        
        if not raw_ics or not neu_ics:
            print(f"{fname:<18} {'N/A':>10} {'N/A':>10} {'N/A':>10} {'N/A':>10} {'N/A':>8}")
            continue
        
        raw_mean = np.mean(raw_ics)
        raw_std = np.std(raw_ics)
        raw_ir = raw_mean / raw_std if raw_std > 0 else 0
        
        neu_mean = np.mean(neu_ics)
        neu_std = np.std(neu_ics)
        neu_ir = neu_mean / neu_std if neu_std > 0 else 0
        
        # IC变化：中性化后ICIR的绝对值 vs 原始
        ir_change = abs(neu_ir) - abs(raw_ir)
        change_str = f"{'↑' if ir_change > 0 else '↓'}{abs(ir_change):.3f}"
        
        print(f"{fname:<18} {raw_mean:>10.4f} {raw_ir:>10.3f} {neu_mean:>10.4f} {neu_ir:>10.3f} {change_str:>8}")
    
    print("-" * 80)
    print("判断标准: |ICIR| > 0.5 有效, > 0.3 弱信号")
    print("行业中性化 = 行业内百分位排名，消除行业间差异")
    print()

if __name__ == "__main__":
    main()
