import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
});

// 股票列表
export async function getStocks(market = '沪深A股', limit = 100) {
  const { data } = await api.get('/stocks', { params: { market, limit } });
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

// 运行回测
export async function runBacktest(config: Record<string, unknown>) {
  const { data } = await api.post('/backtest', config);
  return data;
}

// 获取回测结果
export async function getBacktestResult(taskId: string) {
  const { data } = await api.get(`/backtest/${taskId}`);
  return data;
}

export default api;
