import React, { useState, useEffect, useCallback } from 'react';
import { Table, Card, Input, Button, Tag, Space, message, Pagination } from 'antd';
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
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);
  const [total, setTotal] = useState(0);

  const fetchStocks = useCallback(async (pageNum: number = 1) => {
    setLoading(true);
    try {
      const res = await getStocks('沪深A股', pageNum, pageSize);
      if (res.success) {
        setTotal(res.total);
        const list = res.data.map((s: any, i: number) => ({
          key: `${pageNum}-${i}`,
          symbol: s.symbol,
          name: s.name,
          market: s.market,
        }));
        setStocks(list);
        setPage(pageNum);

        // 批量获取当前页前10只的实时行情（减少请求）
        const symbols = res.data.slice(0, 10).map((s: any) => s.symbol);
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
  }, [pageSize]);

  useEffect(() => {
    fetchStocks(1);
  }, [fetchStocks]);

  const handlePageChange = (newPage: number) => {
    fetchStocks(newPage);
  };

  const filteredStocks = stocks.filter(
    (s) => s.symbol.includes(searchText) || s.name.includes(searchText)
  );

  const columns = [
    { title: '股票代码', dataIndex: 'symbol', key: 'symbol', width: 100 },
    { title: '名称', dataIndex: 'name', key: 'name', ellipsis: true },
    { title: '实时价', dataIndex: 'price', key: 'price', width: 100,
      render: (val: number) => val ? val.toFixed(2) : '-'
    },
    { title: '涨跌幅', dataIndex: 'change_pct', key: 'change_pct', width: 100,
      render: (val: number) => {
        if (val === undefined) return '-';
        const color = val >= 0 ? '#ff4d4f' : '#52c41a';
        return <span style={{ color }}>{val >= 0 ? '+' : ''}{val.toFixed(2)}%</span>;
      }
    },
    { title: '成交量', dataIndex: 'volume', key: 'volume', width: 120,
      render: (val: number) => val ? (val / 100000000).toFixed(2) + '亿' : '-'
    },
    { title: '成交额', dataIndex: 'amount', key: 'amount', width: 120,
      render: (val: number) => val ? (val / 100000000).toFixed(2) + '亿' : '-'
    },
    { title: '换手率', dataIndex: 'turnover', key: 'turnover', width: 100,
      render: (val: number) => val ? val.toFixed(2) + '%' : '-'
    },
  ];

  return (
    <div>
      <h2 style={{ marginBottom: 16 }}>股票列表</h2>
      
      <Card>
        <Space style={{ marginBottom: 16 }}>
          <Input
            placeholder="搜索股票代码或名称"
            prefix={<SearchOutlined />}
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            style={{ width: 250 }}
            allowClear
          />
          <Button icon={<ReloadOutlined />} onClick={() => fetchStocks(page)}>
            刷新
          </Button>
        </Space>

        <Table
          columns={columns}
          dataSource={filteredStocks}
          loading={loading}
          pagination={false}
          size="small"
          scroll={{ x: 800 }}
        />
        
        <div style={{ marginTop: 16, textAlign: 'right' }}>
          <Pagination
            current={page}
            pageSize={pageSize}
            total={total}
            onChange={handlePageChange}
            showSizeChanger={false}
            showTotal={(t) => `共 ${t} 只`}
          />
        </div>
      </Card>
    </div>
  );
};

export default StockList;
