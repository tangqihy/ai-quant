import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Card, Table, Tag, Spin, Empty, Button, message, Select, Space } from 'antd';
import { RiseOutlined, FallOutlined, ReloadOutlined, PlusOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { getRealtimeQuotes } from '../services/api';
import { useWatchlist } from '../hooks/useWatchlist';
import RevenueChart from '../components/charts/RevenueChart';

interface QuoteRow {
  key: string;
  symbol: string;
  name: string;
  price: number;
  change_pct: number;
  volume?: number;
  amount?: number;
}

const REFRESH_INTERVAL_MS = 15000;

const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const { stocks, getStocksByGroup, groups } = useWatchlist();
  const [selectedGroupId, setSelectedGroupId] = useState<string | 'all'>('all');
  const [quoteRows, setQuoteRows] = useState<QuoteRow[]>([]);
  const [loading, setLoading] = useState(false);

  const symbols = useMemo(() => {
    const list = selectedGroupId === 'all' ? stocks : getStocksByGroup(selectedGroupId);
    return list.map((s) => s.symbol);
  }, [stocks, selectedGroupId, getStocksByGroup]);

  const fetchQuotes = useCallback(async () => {
    if (symbols.length === 0) {
      setQuoteRows([]);
      return;
    }
    setLoading(true);
    try {
      const res = await getRealtimeQuotes(symbols);
      if (res.success && res.data?.length) {
        const map = new Map(
          res.data.map((q: any) => [q.symbol, q])
        );
        const list = selectedGroupId === 'all' ? stocks : getStocksByGroup(selectedGroupId);
        setQuoteRows(
          list.map((s) => {
            const q = map.get(s.symbol);
            return {
              key: s.symbol,
              symbol: s.symbol,
              name: s.name,
              price: q?.price ?? 0,
              change_pct: q?.change_pct ?? 0,
              volume: q?.volume,
              amount: q?.amount,
            };
          })
        );
      } else {
        const list = selectedGroupId === 'all' ? stocks : getStocksByGroup(selectedGroupId);
        setQuoteRows(
          list.map((s) => ({
            key: s.symbol,
            symbol: s.symbol,
            name: s.name,
            price: 0,
            change_pct: 0,
            volume: undefined,
            amount: undefined,
          }))
        );
      }
    } catch {
      message.error('获取行情失败');
    } finally {
      setLoading(false);
    }
  }, [symbols.join(','), stocks, selectedGroupId, getStocksByGroup]);

  useEffect(() => {
    fetchQuotes();
  }, [fetchQuotes]);

  useEffect(() => {
    const timer = setInterval(fetchQuotes, REFRESH_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [fetchQuotes]);

  const columns = [
    {
      title: '代码',
      dataIndex: 'symbol',
      key: 'symbol',
      width: 96,
      render: (v: string) => (
        <span style={{ fontFamily: 'monospace', fontWeight: 600, color: '#fff' }}>
          {v}
        </span>
      ),
    },
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      width: 100,
      render: (v: string) => <span style={{ color: 'rgba(255,255,255,0.9)' }}>{v}</span>,
    },
    {
      title: '最新价',
      dataIndex: 'price',
      key: 'price',
      width: 100,
      render: (val: number, row: QuoteRow) => {
        const isUp = row.change_pct >= 0;
        const color = isUp ? '#f23645' : '#00c087';
        return (
          <span style={{ fontWeight: 600, color }}>
            {val > 0 ? val.toFixed(2) : '-'}
          </span>
        );
      },
    },
    {
      title: '涨跌幅',
      dataIndex: 'change_pct',
      key: 'change_pct',
      width: 100,
      render: (val: number) => {
        const isUp = val >= 0;
        const color = isUp ? '#f23645' : '#00c087';
        const icon = isUp ? <RiseOutlined /> : <FallOutlined />;
        return (
          <Tag
            color={isUp ? 'red' : 'green'}
            icon={icon}
            style={{
              margin: 0,
              fontWeight: 600,
              background: isUp ? 'rgba(242,54,69,0.15)' : 'rgba(0,192,135,0.15)',
              border: 'none',
            }}
          >
            {isUp ? '+' : ''}{val.toFixed(2)}%
          </Tag>
        );
      },
    },
    {
      title: '成交量',
      dataIndex: 'volume',
      key: 'volume',
      width: 110,
      render: (val?: number) => (
        <span style={{ color: 'rgba(255,255,255,0.65)' }}>
          {val && val > 0 ? (val / 10000).toFixed(2) + '万' : '-'}
        </span>
      ),
    },
    {
      title: '成交额',
      dataIndex: 'amount',
      key: 'amount',
      width: 110,
      render: (val?: number) => (
        <span style={{ color: 'rgba(255,255,255,0.65)' }}>
          {val && val > 0 ? (val / 100000000).toFixed(2) + '亿' : '-'}
        </span>
      ),
    },
  ];

  const tableWrapStyle: React.CSSProperties = {
    background: '#141414',
    borderRadius: 8,
    border: '1px solid rgba(255,255,255,0.06)',
    overflow: 'hidden',
  };

  return (
    <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
      {/* 左侧：自选分组 + 行情表格 */}
      <div style={{ flex: '1 1 520px', minWidth: 0 }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: 12,
            flexWrap: 'wrap',
            gap: 8,
          }}
        >
          <Space>
            <Select
              value={selectedGroupId}
              onChange={setSelectedGroupId}
              style={{ width: 160 }}
              options={[
                { value: 'all', label: '全部自选' },
                ...groups.map((g) => ({ value: g.id, label: `${g.name} (${getStocksByGroup(g.id).length})` })),
              ]}
            />
            <Button
              type="text"
              icon={<ReloadOutlined />}
              onClick={fetchQuotes}
              loading={loading}
              style={{ color: 'rgba(255,255,255,0.65)' }}
            >
              刷新
            </Button>
          </Space>
          <span style={{ color: 'rgba(255,255,255,0.45)', fontSize: 12 }}>
            共 {quoteRows.length} 只
          </span>
        </div>
        <div style={tableWrapStyle}>
          <Spin spinning={loading}>
            {symbols.length === 0 ? (
              <Empty
                description="暂无自选股票，请使用顶部搜索添加"
                style={{ padding: 48 }}
              >
                <Button
                  type="primary"
                  icon={<PlusOutlined />}
                  onClick={() => navigate('/watchlist')}
                >
                  去分组管理
                </Button>
              </Empty>
            ) : (
              <Table
                columns={columns}
                dataSource={quoteRows}
                pagination={false}
                size="small"
                scroll={{ y: 420 }}
                onRow={(record) => ({
                  onClick: () => navigate(`/stocks/${record.symbol}`),
                  style: { cursor: 'pointer' },
                })}
                style={{
                  background: '#141414',
                }}
                className="futu-table"
              />
            )}
          </Spin>
        </div>
      </div>

      {/* 右侧：收益曲线 + 预留 */}
      <div style={{ width: 400, flexShrink: 0 }}>
        <Card
          title="收益曲线（示例）"
          size="small"
          style={{
            background: '#141414',
            border: '1px solid rgba(255,255,255,0.06)',
            marginBottom: 16,
          }}
          headStyle={{
            borderBottom: '1px solid rgba(255,255,255,0.06)',
            color: 'rgba(255,255,255,0.85)',
          }}
        >
          <RevenueChart />
        </Card>
        <Card
          title="新闻 / 快讯"
          size="small"
          style={{
            background: '#141414',
            border: '1px solid rgba(255,255,255,0.06)',
          }}
          headStyle={{
            borderBottom: '1px solid rgba(255,255,255,0.06)',
            color: 'rgba(255,255,255,0.85)',
          }}
        >
          <div style={{ color: 'rgba(255,255,255,0.45)', fontSize: 12, textAlign: 'center', padding: 24 }}>
            预留
          </div>
        </Card>
      </div>
    </div>
  );
};

export default Dashboard;
