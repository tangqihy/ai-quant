import React, { useState, useEffect, useCallback } from 'react';
import { Table, Card, Input, Button, Tag, Space, message } from 'antd';
import { SearchOutlined, ReloadOutlined } from '@ant-design/icons';
import { getStocks, getRealtimeQuotes } from '../services/api';

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

  const fetchStocks = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getStocks('沪深A股', 50);
      if (res.success) {
        const list = res.data.map((s: any, i: number) => ({
          key: String(i),
          symbol: s.symbol,
          name: s.name,
          market: s.market,
        }));
        setStocks(list);

        // 批量获取前20只的实时行情
        const symbols = res.data.slice(0, 20).map((s: any) => s.symbol);
        try {
          const quotesRes = await getRealtimeQuotes(symbols);
          if (quotesRes.success) {
            const quoteMap = new Map(
              quotesRes.data.map((q: any) => [q.symbol, q])
            );
            setStocks((prev) =>
              prev.map((s) => {
                const q = quoteMap.get(s.symbol) as any;
                return q
                  ? {
                      ...s,
                      price: q.price,
                      change_pct: q.change_pct,
                      volume: q.volume,
                      amount: q.amount,
                      turnover: q.turnover,
                    }
                  : s;
              })
            );
          }
        } catch {
          // 实时行情获取失败不影响列表展示
        }
      }
    } catch (e: any) {
      message.error('获取股票列表失败: ' + (e.message || '未知错误'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStocks();
  }, [fetchStocks]);

  const filteredStocks = stocks.filter(
    (s) => s.symbol.includes(searchText) || s.name.includes(searchText)
  );

  const columns = [
    { title: '股票代码', dataIndex: 'symbol', key: 'symbol', width: 100 },
    { title: '股票名称', dataIndex: 'name', key: 'name', width: 100 },
    {
      title: '当前价格',
      dataIndex: 'price',
      key: 'price',
      width: 100,
      render: (val?: number) => (val != null ? val.toFixed(2) : '-'),
    },
    {
      title: '涨跌幅',
      dataIndex: 'change_pct',
      key: 'change_pct',
      width: 100,
      render: (val?: number) =>
        val != null ? (
          <Tag color={val >= 0 ? 'red' : 'green'}>
            {val >= 0 ? '+' : ''}
            {val.toFixed(2)}%
          </Tag>
        ) : (
          '-'
        ),
    },
    {
      title: '成交量',
      dataIndex: 'volume',
      key: 'volume',
      width: 120,
      render: (val?: number) =>
        val != null ? (val / 10000).toFixed(2) + '万' : '-',
    },
    {
      title: '成交额',
      dataIndex: 'amount',
      key: 'amount',
      width: 120,
      render: (val?: number) =>
        val != null ? (val / 100000000).toFixed(2) + '亿' : '-',
    },
    {
      title: '换手率',
      dataIndex: 'turnover',
      key: 'turnover',
      width: 80,
      render: (val?: number) => (val != null ? val.toFixed(2) + '%' : '-'),
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
            onChange={(e) => setSearchText(e.target.value)}
            style={{ width: 250 }}
            allowClear
          />
          <Button
            type="primary"
            icon={<ReloadOutlined />}
            onClick={fetchStocks}
            loading={loading}
          >
            刷新数据
          </Button>
        </Space>
        <Table
          columns={columns}
          dataSource={filteredStocks}
          pagination={{ pageSize: 20 }}
          scroll={{ x: 800 }}
          size="small"
          loading={loading}
        />
      </Card>
    </div>
  );
};

export default StockList;
