import React, { createContext, useState, useEffect, useCallback, useMemo } from 'react';
import {
  WatchlistData,
  WatchlistGroup,
  WatchlistItem,
  AddToWatchlistParams,
  CreateGroupParams,
  WATCHLIST_STORAGE_KEY,
  GROUP_COLORS,
} from '../types/watchlist';

const generateId = () => Math.random().toString(36).substring(2, 15);

const getDefaultData = (): WatchlistData => ({
  groups: [
    { id: generateId(), name: '默认分组', color: GROUP_COLORS[0], createdAt: Date.now() },
  ],
  stocks: [],
  version: 1,
});

const loadFromStorage = (): WatchlistData => {
  try {
    const data = localStorage.getItem(WATCHLIST_STORAGE_KEY);
    if (data) return JSON.parse(data);
  } catch (e) {
    console.error('Failed to load watchlist from storage:', e);
  }
  return getDefaultData();
};

const saveToStorage = (data: WatchlistData) => {
  try {
    localStorage.setItem(WATCHLIST_STORAGE_KEY, JSON.stringify(data));
  } catch (e) {
    console.error('Failed to save watchlist to storage:', e);
  }
};

export interface WatchlistContextValue {
  groups: WatchlistGroup[];
  stocks: WatchlistItem[];
  isLoaded: boolean;
  createGroup: (params: CreateGroupParams) => WatchlistGroup;
  deleteGroup: (groupId: string) => void;
  renameGroup: (groupId: string, newName: string) => void;
  addStock: (params: AddToWatchlistParams) => boolean;
  removeStock: (symbol: string) => void;
  updateStockGroups: (symbol: string, groupIds: string[]) => void;
  updateStockNote: (symbol: string, note: string) => void;
  isInWatchlist: (symbol: string) => boolean;
  getStock: (symbol: string) => WatchlistItem | undefined;
  getStocksByGroup: (groupId: string) => WatchlistItem[];
  getStockGroups: (symbol: string) => WatchlistGroup[];
  getUngroupedStocks: () => WatchlistItem[];
}

const WatchlistContext = createContext<WatchlistContextValue | null>(null);

export const WatchlistProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [data, setData] = useState<WatchlistData>(loadFromStorage);
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    setIsLoaded(true);
  }, []);

  useEffect(() => {
    if (isLoaded) saveToStorage(data);
  }, [data, isLoaded]);

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

  const renameGroup = useCallback((groupId: string, newName: string) => {
    setData(prev => ({
      ...prev,
      groups: prev.groups.map(g =>
        g.id === groupId ? { ...g, name: newName } : g
      ),
    }));
  }, []);

  const addStock = useCallback((params: AddToWatchlistParams): boolean => {
    setData(prev => {
      const existingIndex = prev.stocks.findIndex(s => s.symbol === params.symbol);
      if (existingIndex >= 0) {
        const updatedStocks = [...prev.stocks];
        const existing = updatedStocks[existingIndex];
        const mergedGroupIds = Array.from(new Set([...existing.groupIds, ...(params.groupIds || [])]));
        updatedStocks[existingIndex] = {
          ...existing,
          groupIds: mergedGroupIds,
          note: params.note ?? existing.note,
        };
        return { ...prev, stocks: updatedStocks };
      }
      const newStock: WatchlistItem = {
        symbol: params.symbol,
        name: params.name,
        addedAt: Date.now(),
        note: params.note,
        groupIds: params.groupIds || [],
      };
      return { ...prev, stocks: [...prev.stocks, newStock] };
    });
    return true;
  }, []);

  const removeStock = useCallback((symbol: string) => {
    setData(prev => ({
      ...prev,
      stocks: prev.stocks.filter(s => s.symbol !== symbol),
    }));
  }, []);

  const updateStockGroups = useCallback((symbol: string, groupIds: string[]) => {
    setData(prev => ({
      ...prev,
      stocks: prev.stocks.map(stock =>
        stock.symbol === symbol ? { ...stock, groupIds } : stock
      ),
    }));
  }, []);

  const updateStockNote = useCallback((symbol: string, note: string) => {
    setData(prev => ({
      ...prev,
      stocks: prev.stocks.map(stock =>
        stock.symbol === symbol ? { ...stock, note } : stock
      ),
    }));
  }, []);

  const isInWatchlist = useCallback((symbol: string): boolean => {
    return data.stocks.some(s => s.symbol === symbol);
  }, [data.stocks]);

  const getStock = useCallback((symbol: string): WatchlistItem | undefined => {
    return data.stocks.find(s => s.symbol === symbol);
  }, [data.stocks]);

  const getStocksByGroup = useCallback((groupId: string): WatchlistItem[] => {
    return data.stocks.filter(s => s.groupIds.includes(groupId));
  }, [data.stocks]);

  const getStockGroups = useCallback((symbol: string): WatchlistGroup[] => {
    const stock = data.stocks.find(s => s.symbol === symbol);
    if (!stock) return [];
    return data.groups.filter(g => stock.groupIds.includes(g.id));
  }, [data.stocks, data.groups]);

  const getUngroupedStocks = useCallback((): WatchlistItem[] => {
    return data.stocks.filter(s => s.groupIds.length === 0);
  }, [data.stocks]);

  const value = useMemo<WatchlistContextValue>(() => ({
    groups: data.groups,
    stocks: data.stocks,
    isLoaded,
    createGroup,
    deleteGroup,
    renameGroup,
    addStock,
    removeStock,
    updateStockGroups,
    updateStockNote,
    isInWatchlist,
    getStock,
    getStocksByGroup,
    getStockGroups,
    getUngroupedStocks,
  }), [
    data,
    isLoaded,
    createGroup,
    deleteGroup,
    renameGroup,
    addStock,
    removeStock,
    updateStockGroups,
    updateStockNote,
    isInWatchlist,
    getStock,
    getStocksByGroup,
    getStockGroups,
    getUngroupedStocks,
  ]);

  return (
    <WatchlistContext.Provider value={value}>
      {children}
    </WatchlistContext.Provider>
  );
};

export default WatchlistContext;
