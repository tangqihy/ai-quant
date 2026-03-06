// 自选股分组
export interface WatchlistGroup {
  id: string;
  name: string;
  color: string;
  createdAt: number;
}

// 自选股票项
export interface WatchlistItem {
  symbol: string;
  name: string;
  addedAt: number;
  note?: string;
  groupIds: string[]; // 所属分组ID列表，支持多分组
}

// 完整的自选数据
export interface WatchlistData {
  groups: WatchlistGroup[];
  stocks: WatchlistItem[];
  version: number;
}

// 添加到自选时的参数
export interface AddToWatchlistParams {
  symbol: string;
  name: string;
  groupIds: string[];
  note?: string;
}

// 创建分组参数
export interface CreateGroupParams {
  name: string;
  color?: string;
}

// 预设分组颜色
export const GROUP_COLORS = [
  '#1890ff', // 蓝色
  '#52c41a', // 绿色
  '#faad14', // 黄色
  '#f5222d', // 红色
  '#722ed1', // 紫色
  '#13c2c2', // 青色
  '#eb2f96', // 粉色
  '#fa541c', // 橙色
];

// localStorage key
export const WATCHLIST_STORAGE_KEY = 'ai-quant-watchlists-v1';
