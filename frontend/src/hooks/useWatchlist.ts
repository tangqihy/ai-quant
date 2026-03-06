import { useState, useEffect, useCallback } from 'react';
import {
  WatchlistData,
  WatchlistGroup,
  WatchlistItem,
  AddToWatchlistParams,
  CreateGroupParams,
  WATCHLIST_STORAGE_KEY,
  GROUP_COLORS,
} from '../types/watchlist';

// 生成唯一ID
const generateId = () => Math.random().toString(36).substring(2, 15);

// 获取默认数据
const getDefaultData = (): WatchlistData => ({
  groups: [
    { id: generateId(), name: '默认分组', color: GROUP_COLORS[0], createdAt: Date.now() },
  ],
  stocks: [],
  version: 1,
});

// 从 localStorage 读取数据
const loadFromStorage = (): WatchlistData => {
  try {
    const data = localStorage.getItem(WATCHLIST_STORAGE_KEY);
    if (data) {
      return JSON.parse(data);
    }
  } catch (e) {
    console.error('Failed to load watchlist from storage:', e);
  }
  return getDefaultData();
};

// 保存到 localStorage
const saveToStorage = (data: WatchlistData) => {
  try {
    localStorage.setItem(WATCHLIST_STORAGE_KEY, JSON.stringify(data));
  } catch (e) {
    console.error('Failed to save watchlist to storage:', e);
  }
};

export function useWatchlist() {
  const [data, setData] = useState<WatchlistData>(loadFromStorage);
  const [isLoaded, setIsLoaded] = useState(false);

  // 初始化加载
  useEffect(() => {
    setIsLoaded(true);
  }, []);

  // 数据变化时自动保存
  useEffect(() => {
    if (isLoaded) {
      saveToStorage(data);
    }
  }, [data, isLoaded]);

  // ========== 分组操作 ==========

  // 创建分组
  const createGroup = useCallback((params: CreateGroupParams): WatchlistGroup => {
    const newGroup: WatchlistGroup = {
      id: generateId(),
      name: params.name,
      color: params.color || GROUP_COLORS[data.groups.length % GROUP_COLORS.length],
      createdAt: Date.now(),
    };
    setData(prev => ({
      ...prev,
      groups: [...prev.groups, newGroup],
    }));
    return newGroup;
  }, [data.groups.length]);

  // 删除分组
  const deleteGroup = useCallback((groupId: string) => {
    setData(prev => ({
      ...prev,
      groups: prev.groups.filter(g => g.id !== groupId),
      stocks: prev.stocks.map(stock => ({
        ...stock,
        groupIds: stock.groupIds.filter(id => id !== groupId),
      })),
    }));
  }, []);

  // 重命名分组
  const renameGroup = useCallback((groupId: string, newName: string) => {
    setData(prev => ({
      ...prev,
      groups: prev.groups.map(g =>
        g.id === groupId ? { ...g, name: newName } : g
      ),
    }));
  }, []);

  // ========== 股票操作 ==========

  // 添加股票到自选
  const addStock = useCallback((params: AddToWatchlistParams): boolean => {
    setData(prev => {
      // 检查是否已存在
      const existingIndex = prev.stocks.findIndex(s => s.symbol === params.symbol);
      
      if (existingIndex >= 0) {
        // 已存在，更新分组和备注
        const updatedStocks = [...prev.stocks];
        const existing = updatedStocks[existingIndex];
        
        // 合并分组（去重）
        const mergedGroupIds = Array.from(new Set([...existing.groupIds, ...params.groupIds]));
        
        updatedStocks[existingIndex] = {
          ...existing,
          groupIds: mergedGroupIds,
          note: params.note || existing.note,
        };
        
        return { ...prev, stocks: updatedStocks };
      } else {
        // 新添加
        const newStock: WatchlistItem = {
          symbol: params.symbol,
          name: params.name,
          addedAt: Date.now(),
          note: params.note,
          groupIds: params.groupIds,
        };
        return { ...prev, stocks: [...prev.stocks, newStock] };
      }
    });
    return true;
  }, []);

  // 从自选移除
  const removeStock = useCallback((symbol: string) => {
    setData(prev => ({
      ...prev,
      stocks: prev.stocks.filter(s => s.symbol !== symbol),
    }));
  }, []);

  // 修改股票分组
  const updateStockGroups = useCallback((symbol: string, groupIds: string[]) => {
    setData(prev => ({
      ...prev,
      stocks: prev.stocks.map(stock =>
        stock.symbol === symbol ? { ...stock, groupIds } : stock
      ),
    }));
  }, []);

  // 修改股票备注
  const updateStockNote = useCallback((symbol: string, note: string) => {
    setData(prev => ({
      ...prev,
      stocks: prev.stocks.map(stock =>
        stock.symbol === symbol ? { ...stock, note } : stock
      ),
    }));
  }, []);

  // ========== 查询方法 ==========

  // 检查股票是否在自选中
  const isInWatchlist = useCallback((symbol: string): boolean => {
    return data.stocks.some(s => s.symbol === symbol);
  }, [data.stocks]);

  // 获取股票信息
  const getStock = useCallback((symbol: string): WatchlistItem | undefined => {
    return data.stocks.find(s => s.symbol === symbol);
  }, [data.stocks]);

  // 获取某分组下的所有股票
  const getStocksByGroup = useCallback((groupId: string): WatchlistItem[] => {
    return data.stocks.filter(s => s.groupIds.includes(groupId));
  }, [data.stocks]);

  // 获取股票所属的所有分组
  const getStockGroups = useCallback((symbol: string): WatchlistGroup[] => {
    const stock = data.stocks.find(s => s.symbol === symbol);
    if (!stock) return [];
    return data.groups.filter(g => stock.groupIds.includes(g.id));
  }, [data.stocks, data.groups]);

  // 获取未分组的股票
  const getUngroupedStocks = useCallback((): WatchlistItem[] => {
    return data.stocks.filter(s => s.groupIds.length === 0);
  }, [data.stocks]);

  return {
    // 数据
    groups: data.groups,
    stocks: data.stocks,
    isLoaded,
    
    // 分组操作
    createGroup,
    deleteGroup,
    renameGroup,
    
    // 股票操作
    addStock,
    removeStock,
    updateStockGroups,
    updateStockNote,
    
    // 查询
    isInWatchlist,
    getStock,
    getStocksByGroup,
    getStockGroups,
    getUngroupedStocks,
  };
}
