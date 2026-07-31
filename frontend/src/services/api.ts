import axios from 'axios';
import { setupAuthInterceptor } from './auth';

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
});

setupAuthInterceptor(api);

// 股票列表（分页）
export async function getStocks(page = 1, pageSize = 20, search = '') {
  const { data } = await api.get('/stocks', { params: { page, page_size: pageSize, search } });
  return data;
}

// 单个股票信息
export async function getStockInfo(symbol: string) {
  const { data } = await api.get(`/stocks/${symbol}`);
  return data;
}

// 股票历史K线
export async function getStockHistory(
  symbol: string,
  startDate?: string,
  endDate?: string,
  adjust = 'qfq',
  period = 'daily'
) {
  const { data } = await api.get(`/stocks/${symbol}/history`, {
    params: { start_date: startDate, end_date: endDate, adjust, period },
  });
  return data;
}

// K 线 + 叠加指标（MA、布林带、通达信分时T等），供 K 线图使用
export async function getIndicators(
  symbol: string,
  indicators: string = 'ma',
  startDate?: string,
  endDate?: string,
  period: string = 'daily',
  indexSymbol: string = '000001.SH'
) {
  const { data } = await api.get(`/indicators/${symbol}`, {
    params: {
      indicators,
      start_date: startDate,
      end_date: endDate,
      period,
      index_symbol: indexSymbol,
    },
  });
  return data;
}

// 财经新闻 / 快讯
export interface NewsItem {
  title: string;
  summary: string;
  source: string;
  published_at: string;
  url: string;
  provider: string;
}

export async function getNews(limit = 20, src = 'auto') {
  const { data } = await api.get('/news', { params: { limit, src } });
  return data as {
    success: boolean;
    data?: { items: NewsItem[]; total: number };
    message?: string;
  };
}

// 单个股票实时行情
export async function getRealtimeQuote(symbol: string) {
  const { data } = await api.get(`/stocks/${symbol}/realtime`);
  return data;
}

// 批量实时行情
export async function getRealtimeQuotes(symbols: string[]) {
  const { data } = await api.get('/quotes/realtime', {
    params: { symbols: symbols.join(',') },
  });
  return data;
}

// 回测结果类型
export interface BacktestResult {
  success: boolean;
  symbol: string;
  strategy: string;
  initial_capital: number;
  final_value: number;
  total_return: number;
  annual_return: number;
  max_drawdown: number;
  total_trades: number;
  win_rate: number;
  trades: any[];
  daily_values: any[];
  error?: string;
}

// 回测配置类型
export interface BacktestConfig {
  symbol: string;
  start_date?: string;
  end_date?: string;
  strategy?: string;
  short_window?: number;
  long_window?: number;
  period?: number;
  oversold?: number;
  overbought?: number;
  initial_capital?: number;
  engine?: 'v1' | 'v2';
}

export interface StrategyMeta {
  id: string;
  name: string;
  description: string;
  params: string[];
  param_schema: {
    name: string;
    type: string;
    default?: number | string;
    description?: string;
    min?: number;
    max?: number;
    step?: number;
  }[];
}

export async function getBacktestStrategies(): Promise<StrategyMeta[]> {
  const { data } = await api.get('/backtest/strategies');
  return data?.data ?? [];
}

// 运行回测
export async function runBacktest(config: BacktestConfig) {
  const { data } = await api.post('/backtest', config);
  return data as BacktestResult;
}

/** 稳健性检验：参数邻域 / Monte Carlo + 多标的批跑 */
export interface RobustnessRequest {
  symbols: string[];
  strategy: string;
  baseline_params?: Record<string, number | string>;
  start_date?: string;
  end_date?: string;
  initial_capital?: number;
  mode?: 'neighborhood' | 'monte_carlo';
  perturbation_pct?: number;
  n_steps?: number;
  n_samples?: number;
  seed?: number;
  max_runs?: number;
  plateau_threshold?: number;
}

export interface RobustnessRunRow {
  symbol: string;
  params: Record<string, number>;
  is_baseline: boolean;
  success: boolean;
  error?: string;
  total_return?: number | null;
  annual_return?: number | null;
  max_drawdown?: number | null;
  sharpe?: number | null;
  win_rate?: number | null;
  total_trades?: number | null;
  final_value?: number | null;
}

export interface RobustnessResult {
  success: boolean;
  error?: string;
  mode?: string;
  strategy?: string;
  symbols?: string[];
  n_variants?: number;
  n_runs?: number;
  truncated?: boolean;
  summary?: {
    baseline_params: Record<string, number>;
    baseline_metrics: {
      total_return: number;
      sharpe: number;
      max_drawdown: number;
      win_rate: number;
      n_symbols: number;
    } | null;
    distribution: Record<
      string,
      {
        count: number;
        mean: number | null;
        p5: number | null;
        p50: number | null;
        p95: number | null;
        min: number | null;
        max: number | null;
      }
    >;
    stability_score: number;
    plateau_fraction: number;
    baseline_sharpe_percentile: number | null;
    baseline_return_percentile: number | null;
    classification: 'robust' | 'moderate' | 'sensitive' | string;
    cross_symbol: {
      n_symbols: number;
      profitable_baseline_count: number;
      stable_count: number;
      stability_ratio: number;
      symbols: {
        symbol: string;
        baseline_return: number | null;
        baseline_sharpe: number | null;
        median_return: number | null;
        n_runs: number;
        stable: boolean;
      }[];
    };
    n_ok: number;
    n_failed: number;
  };
  runs?: RobustnessRunRow[];
}

export async function runRobustness(config: RobustnessRequest) {
  const { data } = await api.post('/backtest/robustness', config, { timeout: 180000 });
  // ok() 包装：{ success, data: RobustnessResult }
  if (data?.data && typeof data.data === 'object') {
    return { ...data.data, success: data.success !== false, error: data.error } as RobustnessResult;
  }
  return data as RobustnessResult;
}

// 获取回测结果
export async function getBacktestResult(taskId: string) {
  const { data } = await api.get(`/backtest/${taskId}`);
  return data;
}

// ---------- 鉴权 ----------
export async function loginApi(password: string) {
  const { data } = await api.post<{ success: boolean; token?: string }>('/auth/login', {
    password,
  });
  return data;
}

export async function verifyAuthApi() {
  const { data } = await api.get<{ success: boolean; valid?: boolean }>('/auth/verify');
  return data;
}

export async function logoutApi() {
  const { data } = await api.post<{ success: boolean; message?: string }>('/auth/logout');
  return data;
}

// ---------- 因子分析 ----------
export interface FactorICData {
  updated_at: string;
  test_period: string;
  cross_sections: number;
  forward_days: number;
  neutralization: string;
  factors: FactorItem[];
  event_factors: EventFactor[];
  /** 数据未生成时为 true，前端展示引导 */
  needs_generation?: boolean;
  message?: string;
}

export interface FactorItem {
  name: string;
  display_name: string;
  category: string;
  direction: number;
  icir: number;
  ic_mean: number;
  ic_std: number;
  verdict: 'effective' | 'weak' | 'invalid';
  description: string;
  group_returns: number[];
  group_labels: string[];
}

export interface EventFactor {
  name: string;
  display_name: string;
  icir: number;
  verdict: string;
  description: string;
}

export interface FactorSummary {
  total_factors: number;
  effective_count: number;
  weak_count: number;
  invalid_count: number;
  test_period: string;
  cross_sections: number;
  forward_days: number;
  neutralization: string;
  updated_at: string;
  top_factors: { name: string; display_name: string; icir: number }[];
  needs_generation?: boolean;
  message?: string;
}

export async function getFactorIC() {
  const { data } = await api.get('/factors/ic');
  return data as FactorICData;
}

export async function getFactorSummary() {
  const { data } = await api.get('/factors/summary');
  return data as FactorSummary;
}

export async function getFactorDistribution(factorName: string) {
  const { data } = await api.get(`/factors/${factorName}/distribution`);
  return data;
}

export async function refreshFactorIC(params?: {
  start?: string;
  end?: string;
  forward_days?: number;
  skip_download?: boolean;
}) {
  const { data } = await api.post('/factors/refresh', null, { params });
  return data as { success: boolean; message?: string; output?: string[] };
}

export default api;
