import React, { createContext, useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
  WatchlistData,
  WatchlistGroup,
  WatchlistItem,
  AddToWatchlistParams,
  CreateGroupParams,
} from '../types/watchlist';
import {
  getWatchlistData,
  createWatchlistGroup,
  updateWatchlistGroup,
  deleteWatchlistGroup,
  addWatchlistStock,
  removeWatchlistStock,
  updateStockGroups as updateStockGroupsApi,
  updateStockNote as updateStockNoteApi,
} from '../services/watchlistApi';
import { getToken } from '../services/auth';
import { message } from 'antd';

const emptyData = (): WatchlistData => ({
  groups: [],
  stocks: [],
  version: 1,
});

function mapServerData(serverData: any): WatchlistData {
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
  return { groups, stocks, version: 1 };
}

export interface WatchlistContextValue {
  groups: WatchlistGroup[];
  stocks: WatchlistItem[];
  /** 首次加载是否完成（未完成前禁止写操作） */
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
  getStocksByGroup: (groupId: string) => WatchlistItem[];
  getStock: (symbol: string) => WatchlistItem | undefined;
  getStockGroups: (symbol: string) => { id: string; name: string; color: string }[];
  refresh: () => Promise<void>;
}

const WatchlistContext = createContext<WatchlistContextValue | null>(null);

export const WatchlistProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [data, setData] = useState<WatchlistData>(emptyData);
  const [isLoaded, setIsLoaded] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const isLoadedRef = useRef(false);
  // 加载序号：写操作会递增，使进行中的拉取结果失效，避免覆盖本地已提交的变更
  const loadSeqRef = useRef(0);

  const ensureReady = useCallback((): boolean => {
    if (!isLoadedRef.current) {
      message.warning('自选数据加载中，请稍候再操作');
      return false;
    }
    return true;
  }, []);

  /** 本地写成功后作废进行中的拉取，防止旧快照盖掉新数据 */
  const invalidateInflightLoads = useCallback(() => {
    loadSeqRef.current += 1;
  }, []);

  const loadFromServer = useCallback(async () => {
    if (!getToken()) {
      setData(emptyData());
      setIsLoading(false);
      isLoadedRef.current = true;
      setIsLoaded(true);
      return;
    }

    const seq = ++loadSeqRef.current;
    setIsLoading(true);

    try {
      const res = await getWatchlistData();
      if (seq !== loadSeqRef.current) return;

      if (res.data?.success && res.data.data) {
        setData(mapServerData(res.data.data));
      } else {
        setData(emptyData());
      }
      isLoadedRef.current = true;
      setIsLoaded(true);
    } catch (error) {
      if (seq !== loadSeqRef.current) return;
      console.error('Failed to load watchlist from server:', error);
      if (getToken()) {
        message.error('加载自选数据失败');
      }
      // 失败也标记 loaded，避免永久锁死写操作；保留已有本地数据
      isLoadedRef.current = true;
      setIsLoaded(true);
    } finally {
      if (seq === loadSeqRef.current) {
        setIsLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    loadFromServer();
  }, [loadFromServer]);

  const createGroup = useCallback(async (params: CreateGroupParams): Promise<WatchlistGroup | null> => {
    if (!ensureReady()) return null;
    try {
      const res = await createWatchlistGroup(params.name, params.color);
      if (res.data?.success) {
        invalidateInflightLoads();
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
    } catch {
      message.error('创建分组失败');
    }
    return null;
  }, [ensureReady, invalidateInflightLoads]);

  const deleteGroup = useCallback(async (groupId: string) => {
    if (!ensureReady()) return;
    try {
      await deleteWatchlistGroup(groupId);
      invalidateInflightLoads();
      setData(prev => ({
        ...prev,
        groups: prev.groups.filter(g => g.id !== groupId),
        stocks: prev.stocks.map(s => ({
          ...s,
          groupIds: s.groupIds.filter(id => id !== groupId),
        })),
      }));
    } catch {
      message.error('删除分组失败');
    }
  }, [ensureReady, invalidateInflightLoads]);

  const renameGroup = useCallback(async (groupId: string, newName: string) => {
    if (!ensureReady()) return;
    try {
      await updateWatchlistGroup(groupId, newName);
      invalidateInflightLoads();
      setData(prev => ({
        ...prev,
        groups: prev.groups.map(g =>
          g.id === groupId ? { ...g, name: newName } : g
        ),
      }));
    } catch {
      message.error('重命名分组失败');
    }
  }, [ensureReady, invalidateInflightLoads]);

  const addStock = useCallback(async (params: AddToWatchlistParams): Promise<boolean> => {
    if (!ensureReady()) return false;
    try {
      const res = await addWatchlistStock(
        params.symbol,
        params.name,
        params.groupIds,
        params.note
      );
      if (res.data?.success) {
        invalidateInflightLoads();
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
            ? prev.stocks.map(s => (s.symbol === newStock.symbol ? newStock : s))
            : [...prev.stocks, newStock],
        }));
        return true;
      }
    } catch {
      message.error('添加自选失败');
    }
    return false;
  }, [ensureReady, invalidateInflightLoads]);

  const removeStock = useCallback(async (symbol: string) => {
    if (!ensureReady()) return;
    try {
      await removeWatchlistStock(symbol);
      invalidateInflightLoads();
      setData(prev => ({
        ...prev,
        stocks: prev.stocks.filter(s => s.symbol !== symbol),
      }));
    } catch {
      message.error('移除自选失败');
    }
  }, [ensureReady, invalidateInflightLoads]);

  const updateStockGroups = useCallback(async (symbol: string, groupIds: string[]) => {
    if (!ensureReady()) return;
    try {
      await updateStockGroupsApi(symbol, groupIds);
      invalidateInflightLoads();
      setData(prev => ({
        ...prev,
        stocks: prev.stocks.map(s =>
          s.symbol === symbol ? { ...s, groupIds } : s
        ),
      }));
    } catch {
      message.error('更新分组失败');
    }
  }, [ensureReady, invalidateInflightLoads]);

  const updateStockNote = useCallback(async (symbol: string, note: string) => {
    if (!ensureReady()) return;
    try {
      await updateStockNoteApi(symbol, note);
      invalidateInflightLoads();
      setData(prev => ({
        ...prev,
        stocks: prev.stocks.map(s =>
          s.symbol === symbol ? { ...s, note } : s
        ),
      }));
    } catch {
      message.error('更新备注失败');
    }
  }, [ensureReady, invalidateInflightLoads]);

  const isInWatchlist = useCallback((symbol: string) => {
    return data.stocks.some(s => s.symbol === symbol);
  }, [data.stocks]);

  const getStocksByGroup = useCallback((groupId: string) => {
    if (groupId === 'all') return data.stocks;
    return data.stocks.filter(s => s.groupIds.includes(groupId));
  }, [data.stocks]);

  const getStock = useCallback((symbol: string) => {
    return data.stocks.find(s => s.symbol === symbol);
  }, [data.stocks]);

  const getStockGroups = useCallback((symbol: string) => {
    const stock = data.stocks.find(s => s.symbol === symbol);
    if (!stock) return [];
    return data.groups.filter(g => stock.groupIds.includes(g.id));
  }, [data.stocks, data.groups]);

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
      getStocksByGroup,
      getStock,
      getStockGroups,
      refresh,
    }),
    [
      data,
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
      getStocksByGroup,
      getStock,
      getStockGroups,
      refresh,
    ]
  );

  return <WatchlistContext.Provider value={value}>{children}</WatchlistContext.Provider>;
};

export default WatchlistContext;
