import React, { useState, useEffect, useCallback } from 'react';
import { Table, Card, Input, Button, Tag, Space, message, Tooltip } from 'antd';
import { SearchOutlined, ReloadOutlined, StarOutlined, StarFilled } from '@ant-design/icons';
import { getStocks, getRealtimeQuotes } from '../services/api';
import { useWatchlist } from '../hooks/useWatchlist';
import { AddToWatchlistModal } from '../components/watchlist/AddToWatchlistModal';

interface StockData {
  key: string;
  symbol: string;
  name: string;
  market: string;
  price?: number;
  change_pct?: number;
  volume?: number;
  amount?: number;
  turnover?: number;
}

const StockList: React.FC = () => {
  const [searchText, setSearchText] = useState('');
  const [stocks, setStocks] = useState<StockData[]>([]);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [total, setTotal] = useState(0);

  const fetchStocks = useCallback(async (p: number, search: string) => {
    setLoading(true);
    try {
      const res = await getStocks(p, pageSize, search);
      if (res.success) {
        const list = res.data.map((s: any, i: number) => ({
          key: `${p}-${i}`,
          symbol: s.symbol,
          name: s.name,
          market: s.market,
        }));
        setStocks(list);
        setTotal(res.total);

        // 获取当前页股票的实时行情
        const symbols = res.data.map((s: any) => s.symbol);
        if (symbols.length > 0) {
          try {
            const quotesRes = await getRealtimeQuotes(symbols);
            if (quotesRes.success) {
              const quoteMap = new Map(
                quotesRes.data.map((q: any) => [q.symbol, q])
              );
              setStocks(prev =>
                prev.map(s => {
                  const q = quoteMap.get(s.symbol) as any;
                  return q && q.price > 0
                    ? { ...s, price: q.price, change_pct: q.change_pct, volume: q.volume, amount: q.amount, turnover: q.turnover }
                    : s;
                })
              );
            }
          } catch { /* 行情获取失败不影响列表 */ }
        }
      }
    } catch (e: any) {
      message.error('获取股票列表失败');
    } finally {
      setLoading(false);
    }
  }, [pageSize]);

  useEffect(() => {
    fetchStocks(page, searchText);
  }, [page, fetchStocks]);

  const handleSearch = () => {
    setPage(1);
    fetchStocks(1, searchText);
  };

  const columns = [
    { title: '股票代码', dataIndex: 'symbol', key: 'symbol', width: 100 },
    { title: '股票名称', dataIndex: 'name', key: 'name', width: 120 },
    {
      title: '当前价格', dataIndex: 'price', key: 'price', width: 100,
      render: (val?: number) => val && val > 0 ? val.toFixed(2) : '-',
    },
    {
      title: '涨跌幅', dataIndex: 'change_pct', key: 'change_pct', width: 100,
      render: (val?: number) =>
        val != null && val !== 0 ? (
          <Tag color={val >= 0 ? 'red' : 'green'}>{val >= 0 ? '+' : ''}{val.toFixed(2)}%</Tag>
        ) : '-',
    },
    {
      title: '成交量', dataIndex: 'volume', key: 'volume', width: 120,
      render: (val?: number) => val && val > 0 ? (val / 10000).toFixed(2) + '万' : '-',
    },
    {
      title: '成交额', dataIndex: 'amount', key: 'amount', width: 120,
      render: (val?: number) => val && val > 0 ? (val / 100000000).toFixed(2) + '亿' : '-',
    },
    {
      title: '换手率', dataIndex: 'turnover', key: 'turnover', width: 80,
      render: (val?: number) => val && val > 0 ? val.toFixed(2) + '%' : '-',
    },
  ];

  return (
    <div>
      <h2 style={{ marginBottom: 24 }}>股票列表</h2>
      <Card>
        <Space style={{ marginBottom: 16 }} wrap>
          <Input
            placeholder="搜索股票代码或名称"
            prefix={<SearchOutlined />}
            value={searchText}
            onChange={e => setSearchText(e.target.value)}
            onPressEnter={handleSearch}
            style={{ width: 250 }}
            allowClear
          />
          <Button type="primary" icon={<SearchOutlined />} onClick={handleSearch}>
            搜索
          </Button>
          <Button icon={<ReloadOutlined />} onClick={() => fetchStocks(page, searchText)} loading={loading}>
            刷新
          </Button>
        </Space>
        <Table
          columns={columns}
          dataSource={stocks}
          loading={loading}
          size="small"
          scroll={{ x: 800 }}
          pagination={{
            current: page,
            pageSize,
            total,
            showTotal: (t) => `共 ${t} 只股票`,
            showSizeChanger: false,
            onChange: (p) => setPage(p),
          }}
        />
      </Card>
    </div>
  );
};

export default StockList;
