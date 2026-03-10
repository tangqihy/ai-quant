import axios from 'axios';
import { setupAuthInterceptor } from './auth';

const request = axios.create({
  baseURL: '/api',
  timeout: 30000,
});

setupAuthInterceptor(request);

export interface WatchlistGroup {
  id: string;
  name: string;
  color: string;
  created_at: string;
  updated_at?: string;
}

export interface WatchlistItem {
  symbol: string;
  name: string;
  group_ids: string[];
  note: string;
  created_at: string;
  updated_at?: string;
}

export interface WatchlistData {
  groups: WatchlistGroup[];
  stocks: WatchlistItem[];
}

// 获取完整自选数据
export const getWatchlistData = () => {
  return request.get('/watchlist/data');
};

// 获取分组列表
export const getWatchlistGroups = () => {
  return request.get('/watchlist/groups');
};

// 创建分组
export const createWatchlistGroup = (name: string, color: string = '#1890ff') => {
  return request.post('/watchlist/groups', { name, color });
};

// 更新分组
export const updateWatchlistGroup = (groupId: string, name: string) => {
  return request.put(`/watchlist/groups/${groupId}`, { name });
};

// 删除分组
export const deleteWatchlistGroup = (groupId: string) => {
  return request.delete(`/watchlist/groups/${groupId}`);
};

// 获取自选股票列表
export const getWatchlistStocks = () => {
  return request.get('/watchlist/stocks');
};

// 添加自选股票
export const addWatchlistStock = (symbol: string, name: string = '', groupIds: string[] = [], note: string = '') => {
  return request.post('/watchlist/stocks', {
    symbol,
    name,
    group_ids: groupIds,
    note
  });
};

// 移除自选股票
export const removeWatchlistStock = (symbol: string) => {
  return request.delete(`/watchlist/stocks/${encodeURIComponent(symbol)}`);
};

// 更新股票分组
export const updateStockGroups = (symbol: string, groupIds: string[]) => {
  return request.put(`/watchlist/stocks/${encodeURIComponent(symbol)}/groups`, { group_ids: groupIds });
};

// 更新股票备注
export const updateStockNote = (symbol: string, note: string) => {
  return request.put(`/watchlist/stocks/${encodeURIComponent(symbol)}/note`, { note });
};
