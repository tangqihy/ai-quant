import React, { createContext, useState, useEffect, useCallback, useMemo } from 'react';
import {
  WatchlistData,
  WatchlistGroup,
  WatchlistItem,
  AddToWatchlistParams,
  CreateGroupParams,
  GROUP_COLORS,
} from '../types/watchlist';
import {
  getWatchlistData,
  createWatchlistGroup,
  updateWatchlistGroup,
  deleteWatchlistGroup,
  addWatchlistStock,
  removeWatchlistStock,
  updateStockGroups,
  updateStockNote,
} from '../services/watchlistApi';
import { message } from 'antd';

const generateId = () => Math.random().toString(36).substring(2, 15);

const getDefaultData = (): WatchlistData => ({
  groups: [
    { id: generateId(), name: '默认分组', color: GROUP_COLORS[0], createdAt: Date.now() },
  ],
  stocks: [],
  version: 1,
});

export interface WatchlistContextValue {
  groups: WatchlistGroup[];
  stocks: WatchlistItem[];
  isLoaded: boolean;
  isLoading: boolean;
  createGroup: (params: CreateGroupParams) => Promise<WatchlistGroup | null>;
  deleteGroup: (groupId: string) => Promise<void>;
  renameGroup: (groupId: string, newName: string) => Promise<void>;
  addStock: (params: AddToWatchlistParams) => Promise<boolean>;
  removeStock: (symbol: string) => Promise<void>;
  updateStockGroups: (symbol: string, groupIds: string[]) => Promise<void>;
  updateStockNote: (symbol: string, note: string) => Promise<void>;
  isInWatchlist: (symbol: string) => boolean;
  refresh: () => Promise<void>;
}

const WatchlistContext = createContext<WatchlistContextValue | null>(null);

export const WatchlistProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [data, setData] = useState<WatchlistData>(getDefaultData());
  const [isLoaded, setIsLoaded] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  // 从服务器加载数据
  const loadFromServer = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await getWatchlistData();
      if (res.data?.success && res.data.data) {
        const serverData = res.data.data;
        // 转换服务器数据格式
        const groups: WatchlistGroup[] = (serverData.groups || []).map((g: any) => ({
          id: g.id,
          name: g.name,
          color: g.color,
          createdAt: new Date(g.created_at).getTime(),
          updatedAt: g.updated_at ? new Date(g.updated_at).getTime() : undefined,
        }));
        const stocks: WatchlistItem[] = (serverData.stocks || []).map((s: any) => ({
          symbol: s.symbol,
          name: s.name,
          groupIds: s.group_ids || [],
          note: s.note,
          addedAt: new Date(s.created_at).getTime(),
          updatedAt: s.updated_at ? new Date(s.updated_at).getTime() : undefined,
        }));
        setData({
          groups: groups.length > 0 ? groups : getDefaultData().groups,
          stocks,
          version: 1,
        });
      }
    } catch (error) {
      console.error('Failed to load watchlist from server:', error);
      message.error('加载自选数据失败');
    } finally {
      setIsLoading(false);
      setIsLoaded(true);
    }
  }, []);

  // 初始加载
  useEffect(() => {
    loadFromServer();
  }, [loadFromServer]);

  // 创建分组
  const createGroup = useCallback(async (params: CreateGroupParams): Promise<WatchlistGroup | null> => {
    try {
      const res = await createWatchlistGroup(params.name, params.color);
      if (res.data?.success) {
        const newGroup = res.data.data;
        const group: WatchlistGroup = {
          id: newGroup.id,
          name: newGroup.name,
          color: newGroup.color,
          createdAt: new Date(newGroup.created_at).getTime(),
          updatedAt: newGroup.updated_at ? new Date(newGroup.updated_at).getTime() : undefined,
        };
        setData(prev => ({
          ...prev,
          groups: [...prev.groups, group],
        }));
        return group;
      }
    } catch (error) {
      message.error('创建分组失败');
    }
    return null;
  }, []);

  // 删除分组
  const deleteGroup = useCallback(async (groupId: string) => {
    try {
      await deleteWatchlistGroup(groupId);
      setData(prev => ({
        ...prev,
        groups: prev.groups.filter(g => g.id !== groupId),
        stocks: prev.stocks.map(s => ({
          ...s,
          groupIds: s.groupIds.filter(id => id !== groupId),
        })),
      }));
    } catch (error) {
      message.error('删除分组失败');
    }
  }, []);

  // 重命名分组
  const renameGroup = useCallback(async (groupId: string, newName: string) => {
    try {
      await updateWatchlistGroup(groupId, newName);
      setData(prev => ({
        ...prev,
        groups: prev.groups.map(g =>
          g.id === groupId ? { ...g, name: newName } : g
        ),
      }));
    } catch (error) {
      message.error('重命名分组失败');
    }
  }, []);

  // 添加股票
  const addStock = useCallback(async (params: AddToWatchlistParams): Promise<boolean> => {
    try {
      const res = await addWatchlistStock(
        params.symbol,
        params.name,
        params.groupIds,
        params.note
      );
      if (res.data?.success) {
        const stock = res.data.data;
        const newStock: WatchlistItem = {
          symbol: stock.symbol,
          name: stock.name,
          groupIds: stock.group_ids || [],
          note: stock.note,
          addedAt: new Date(stock.created_at).getTime(),
          updatedAt: stock.updated_at ? new Date(stock.updated_at).getTime() : undefined,
        };
        setData(prev => ({
          ...prev,
          stocks: prev.stocks.some(s => s.symbol === newStock.symbol)
            ? prev.stocks.map(s => s.symbol === newStock.symbol ? newStock : s)
            : [...prev.stocks, newStock],
        }));
        return true;
      }
    } catch (error) {
      message.error('添加自选失败');
    }
    return false;
  }, []);

  // 移除股票
  const removeStock = useCallback(async (symbol: string) => {
    try {
      await removeWatchlistStock(symbol);
      setData(prev => ({
        ...prev,
        stocks: prev.stocks.filter(s => s.symbol !== symbol),
      }));
    } catch (error) {
      message.error('移除自选失败');
    }
  }, []);

  // 更新股票分组
  const updateStockGroups = useCallback(async (symbol: string, groupIds: string[]) => {
    try {
      await updateStockGroups(symbol, groupIds);
      setData(prev => ({
        ...prev,
        stocks: prev.stocks.map(s =>
          s.symbol === symbol ? { ...s, groupIds } : s
        ),
      }));
    } catch (error) {
      message.error('更新分组失败');
    }
  }, []);

  // 更新股票备注
  const updateStockNote = useCallback(async (symbol: string, note: string) => {
    try {
      await updateStockNote(symbol, note);
      setData(prev => ({
        ...prev,
        stocks: prev.stocks.map(s =>
          s.symbol === symbol ? { ...s, note } : s
        ),
      }));
    } catch (error) {
      message.error('更新备注失败');
    }
  }, []);

  // 检查是否在自选
  const isInWatchlist = useCallback((symbol: string) => {
    return data.stocks.some(s => s.symbol === symbol);
  }, [data.stocks]);

  // 刷新数据
  const refresh = useCallback(async () => {
    await loadFromServer();
  }, [loadFromServer]);

  const value = useMemo(
    () => ({
      groups: data.groups,
      stocks: data.stocks,
      isLoaded,
      isLoading,
      createGroup,
      deleteGroup,
      renameGroup,
      addStock,
      removeStock,
      updateStockGroups,
      updateStockNote,
      isInWatchlist,
      refresh,
    }),
    [data, isLoaded, isLoading, createGroup, deleteGroup, renameGroup, addStock, removeStock, updateStockGroups, updateStockNote, isInWatchlist, refresh]
  );

  return <WatchlistContext.Provider value={value}>{children}</WatchlistContext.Provider>;
};

export default WatchlistContext;
