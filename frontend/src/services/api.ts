import axios from 'axios';

const api = axios.create({
  baseURL: '/quant/api',
  timeout: 30000,
});

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
  adjust = 'qfq'
) {
  const { data } = await api.get(`/stocks/${symbol}/history`, {
    params: { start_date: startDate, end_date: endDate, adjust },
  });
  return data;
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
  initial_capital?: number;
}

// 运行回测
export async function runBacktest(config: BacktestConfig) {
  const { data } = await api.post('/backtest', config);
  return data as BacktestResult;
}

// 获取回测结果
export async function getBacktestResult(taskId: string) {
  const { data } = await api.get(`/backtest/${taskId}`);
  return data;
}

export default api;
