import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Input, List, Spin, Empty, message } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import { getStocks } from '../services/api';
import { useWatchlist } from '../hooks/useWatchlist';
import AddToWatchlistModal from './watchlist/AddToWatchlistModal';

const SEARCH_DEBOUNCE_MS = 300;

export const SearchBar: React.FC = () => {
  const [keyword, setKeyword] = useState('');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<{ symbol: string; name: string }[]>([]);
  const [dropdownVisible, setDropdownVisible] = useState(false);
  const [selectedStock, setSelectedStock] = useState<{ symbol: string; name: string } | null>(null);
  const [modalVisible, setModalVisible] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();
  const wrapperRef = useRef<HTMLDivElement>(null);
  const { isInWatchlist, groups } = useWatchlist();

  const doSearch = useCallback(async (q: string) => {
    const term = (q || '').trim();
    if (!term || term.length < 1) {
      setResults([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const res = await getStocks(1, 20, term);
      if (res.success && res.data?.length) {
        setResults(
          res.data.map((s: any) => ({ symbol: s.symbol, name: s.name || s.symbol }))
        );
        setDropdownVisible(true);
      } else {
        setResults([]);
        setDropdownVisible(true);
      }
    } catch {
      setResults([]);
      message.error('搜索失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!keyword.trim()) {
      setResults([]);
      setDropdownVisible(false);
      setLoading(false);
      return;
    }
    setLoading(true);
    debounceRef.current = setTimeout(() => {
      doSearch(keyword);
    }, SEARCH_DEBOUNCE_MS);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [keyword, doSearch]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setDropdownVisible(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelectStock = (item: { symbol: string; name: string }) => {
    setSelectedStock(item);
    setModalVisible(true);
    setDropdownVisible(false);
    setKeyword('');
    setResults([]);
  };

  const handleModalSuccess = () => {
    setModalVisible(false);
    setSelectedStock(null);
  };

  return (
    <div ref={wrapperRef} className="search-bar-wrap" style={{ position: 'relative', width: 320, maxWidth: '100%', minWidth: 0, flex: '1 1 auto' }}>
      <Input
        placeholder="搜索股票代码 / 名称，添加自选"
        prefix={<SearchOutlined style={{ color: 'rgba(255,255,255,0.45)' }} />}
        value={keyword}
        onChange={(e) => setKeyword(e.target.value)}
        onFocus={() => keyword.trim() && results.length >= 0 && setDropdownVisible(true)}
        allowClear
        style={{
          borderRadius: 6,
          background: 'rgba(255,255,255,0.08)',
          border: '1px solid rgba(255,255,255,0.15)',
          color: '#fff',
        }}
        styles={{
          input: { background: 'transparent', color: '#fff' },
        }}
      />
      {dropdownVisible && (
        <div
          style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            right: 0,
            marginTop: 4,
            background: '#1f1f1f',
            borderRadius: 8,
            boxShadow: '0 6px 16px rgba(0,0,0,0.4)',
            border: '1px solid rgba(255,255,255,0.1)',
            zIndex: 1050,
            maxHeight: 320,
            overflow: 'hidden',
          }}
        >
          {loading ? (
            <div style={{ padding: 24, textAlign: 'center' }}>
              <Spin size="small" />
            </div>
          ) : results.length === 0 ? (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description="无匹配股票"
              style={{ padding: 16, margin: 0 }}
            />
          ) : (
            <List
              size="small"
              dataSource={results}
              style={{ maxHeight: 300, overflow: 'auto' }}
              renderItem={(item) => {
                const inList = isInWatchlist(item.symbol);
                return (
                  <List.Item
                    style={{
                      cursor: 'pointer',
                      padding: '10px 12px',
                      borderBottom: '1px solid rgba(255,255,255,0.06)',
                    }}
                    onClick={() => handleSelectStock(item)}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = 'rgba(24, 144, 255, 0.15)';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = 'transparent';
                    }}
                  >
                    <span style={{ fontFamily: 'monospace', fontWeight: 600, marginRight: 8 }}>
                      {item.symbol}
                    </span>
                    <span style={{ color: 'rgba(255,255,255,0.85)' }}>{item.name}</span>
                    {inList && (
                      <span
                        style={{
                          marginLeft: 'auto',
                          fontSize: 12,
                          color: 'rgba(255,255,255,0.45)',
                        }}
                      >
                        已在自选
                      </span>
                    )}
                  </List.Item>
                );
              }}
            />
          )}
        </div>
      )}
      {selectedStock && (
        <AddToWatchlistModal
          visible={modalVisible}
          onCancel={() => {
            setModalVisible(false);
            setSelectedStock(null);
          }}
          onSuccess={handleModalSuccess}
          stockSymbol={selectedStock.symbol}
          stockName={selectedStock.name}
        />
      )}
    </div>
  );
};

export default SearchBar;
