import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Card, Table, Spin, Empty, Button, message, Select, Space, Tabs, Grid } from 'antd';
import { ReloadOutlined, PlusOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { getRealtimeQuotes } from '../services/api';
import { useWatchlist } from '../hooks/useWatchlist';
import RevenueChart from '../components/charts/RevenueChart';
import Sparkline from '../components/Sparkline';
import { formatPrice, formatChangePct, formatChangeAmount, formatVolume } from '../lib/utils';

const { useBreakpoint } = Grid;

interface QuoteRow {
  key: string;
  symbol: string;
  name: string;
  price: number;
  change_amount: number;
  change_pct: number;
  volume?: number;
  amount?: number;
}

const REFRESH_INTERVAL_MS = 15000;

/** A 股红涨绿跌 - 赛博朋克霓虹色 */
const COLOR_UP = '#ff0040';
const COLOR_DOWN = '#00ff41';

const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const screens = useBreakpoint();
  const isMobile = !screens.md;
  const { stocks, getStocksByGroup, groups } = useWatchlist();
  const [marketTab, setMarketTab] = useState<'cn' | 'hk' | 'us'>('cn');
  const [selectedGroupId, setSelectedGroupId] = useState<string | 'all'>('all');
  const [quoteRows, setQuoteRows] = useState<QuoteRow[]>([]);
  const [loading, setLoading] = useState(false);

  const symbols = useMemo(() => {
    const list = selectedGroupId === 'all' ? stocks : getStocksByGroup(selectedGroupId);
    return list.map((s) => s.symbol);
  }, [stocks, selectedGroupId, getStocksByGroup]);

  const fetchQuotes = useCallback(async (showLoading = false) => {
    if (symbols.length === 0) {
      setQuoteRows([]);
      return;
    }
    if (showLoading) setLoading(true);
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
              change_amount: q?.change_amount ?? 0,
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
            change_amount: 0,
            change_pct: 0,
            volume: undefined,
            amount: undefined,
          }))
        );
      }
    } catch {
      message.error('获取行情失败');
    } finally {
      if (showLoading) setLoading(false);
    }
  }, [symbols, stocks, selectedGroupId, getStocksByGroup]);

  useEffect(() => {
    fetchQuotes(true);
  }, []);

  useEffect(() => {
    const timer = setInterval(() => fetchQuotes(false), REFRESH_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [fetchQuotes]);

  const columns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      width: 120,
      render: (_: string, row: QuoteRow) => (
        <div>
          <div style={{ color: 'rgba(0, 255, 65, 0.9)', fontWeight: 500 }}>
            {row.name || '-'}
          </div>
          <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: 'rgba(0, 255, 65, 0.5)' }}>
            {row.symbol}
          </div>
        </div>
      ),
    },
    {
      title: '走势',
      key: 'sparkline',
      width: 72,
      render: (_: unknown, row: QuoteRow) => (
        <Sparkline
          symbol={row.symbol}
          days={5}
          width={64}
          height={28}
          isUp={row.change_pct >= 0}
        />
      ),
    },
    {
      title: '最新价',
      dataIndex: 'price',
      key: 'price',
      width: 88,
      align: 'right' as const,
      render: (val: number, row: QuoteRow) => {
        const isUp = row.change_pct >= 0;
        const color = isUp ? COLOR_UP : COLOR_DOWN;
        return (
          <span style={{ fontWeight: 600, color }}>
            {formatPrice(val)}
          </span>
        );
      },
    },
    {
      title: '涨跌额',
      dataIndex: 'change_amount',
      key: 'change_amount',
      width: 88,
      align: 'right' as const,
      render: (val: number, row: QuoteRow) => {
        const isUp = row.change_pct >= 0;
        const color = isUp ? COLOR_UP : COLOR_DOWN;
        return (
          <span style={{ fontWeight: 500, color }}>
            {formatChangeAmount(val)}
          </span>
        );
      },
    },
    {
      title: '涨跌幅',
      dataIndex: 'change_pct',
      key: 'change_pct',
      width: 88,
      align: 'right' as const,
      render: (val: number) => {
        const isUp = val >= 0;
        const color = isUp ? COLOR_UP : COLOR_DOWN;
        return (
          <span style={{ fontWeight: 600, color }}>
            {formatChangePct(val)}
          </span>
        );
      },
    },
    {
      title: '成交量',
      dataIndex: 'volume',
      key: 'volume',
      width: 90,
      align: 'right' as const,
      render: (val?: number) => (
        <span style={{ color: 'rgba(0, 255, 65, 0.65)', fontSize: 12 }}>
          {formatVolume(val)}
        </span>
      ),
    },
  ];

  const tableWrapStyle: React.CSSProperties = {
    background: '#0a0a0a',
    borderRadius: 4,
    border: '1px solid rgba(0, 255, 65, 0.25)',
    overflow: 'hidden',
    boxShadow: '0 0 12px rgba(0, 255, 65, 0.06)',
  };

  const renderQuoteList = () => {
    if (symbols.length === 0) {
      return (
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
      );
    }
    if (isMobile) {
      return (
        <div className="futu-quote-cards" style={{ padding: 12 }}>
          {quoteRows.map((row) => {
            const isUp = row.change_pct >= 0;
            const color = isUp ? COLOR_UP : COLOR_DOWN;
            return (
              <div
                key={row.key}
                role="button"
                tabIndex={0}
                onClick={() => navigate(`/stocks/${row.symbol}`)}
                onKeyDown={(e) => e.key === 'Enter' && navigate(`/stocks/${row.symbol}`)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '12px 10px',
                  marginBottom: 8,
                  background: 'rgba(0, 255, 65, 0.04)',
                  borderRadius: 4,
                  border: '1px solid rgba(0, 255, 65, 0.2)',
                  cursor: 'pointer',
                  fontFamily: "'JetBrains Mono', monospace",
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0, flex: 1 }}>
                  <Sparkline
                    symbol={row.symbol}
                    days={5}
                    width={48}
                    height={24}
                    isUp={isUp}
                  />
                  <div style={{ minWidth: 0 }}>
                    <div style={{ color: 'rgba(0, 255, 65, 0.9)', fontWeight: 500, fontSize: 13 }}>
                      {row.name || '-'}
                    </div>
                    <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: 'rgba(0, 255, 65, 0.5)' }}>
                      {row.symbol}
                    </div>
                  </div>
                </div>
                <div style={{ textAlign: 'right', flexShrink: 0 }}>
                  <div style={{ fontWeight: 600, color, fontSize: 14 }}>
                    {formatPrice(row.price)}
                  </div>
                  <div style={{ fontWeight: 500, color, fontSize: 12 }}>
                    {formatChangePct(row.change_pct)}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      );
    }
    return (
      <Table
        columns={columns}
        dataSource={quoteRows}
        pagination={false}
        size="small"
        scroll={{ y: 420, x: 'max-content' }}
        onRow={(record) => ({
          onClick: () => navigate(`/stocks/${record.symbol}`),
          style: { cursor: 'pointer' },
        })}
        style={{ background: '#0a0a0a' }}
        className="futu-table futu-table-compact"
      />
    );
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* 顶部市场切换：沪深 / 港股 / 美股，预留扩展 */}
      <Tabs
        activeKey={marketTab}
        onChange={(k) => setMarketTab(k as 'cn' | 'hk' | 'us')}
        size="small"
        className="futu-market-tabs"
        items={[
          { key: 'cn', label: '沪深' },
          { key: 'hk', label: '港股', disabled: true },
          { key: 'us', label: '美股', disabled: true },
        ]}
      />

      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
        <div style={{ flex: '1 1 520px', minWidth: 0 }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: 8,
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
                style={{ color: 'rgba(0, 255, 65, 0.65)' }}
              >
                刷新
              </Button>
            </Space>
            <span style={{ color: 'rgba(0, 255, 65, 0.45)', fontSize: 12, fontFamily: "'JetBrains Mono', monospace" }}>
              共 {quoteRows.length} 只
            </span>
          </div>
          <div style={tableWrapStyle}>
            <Spin spinning={loading}>
              {renderQuoteList()}
            </Spin>
          </div>
        </div>

        <div className="futu-dashboard-sidebar" style={{ width: 400, flexShrink: 0 }}>
          <Card
            title="收益曲线（示例）"
            size="small"
            style={{
              background: '#0a0a0a',
              border: '1px solid rgba(0, 255, 65, 0.25)',
              marginBottom: 16,
              boxShadow: '0 0 12px rgba(0, 255, 65, 0.06)',
            }}
            headStyle={{
              borderBottom: '1px solid rgba(0, 255, 65, 0.25)',
              color: '#00ff41',
            }}
          >
            <RevenueChart />
          </Card>
          <Card
            title="新闻 / 快讯"
            size="small"
            style={{
              background: '#0a0a0a',
              border: '1px solid rgba(0, 255, 65, 0.25)',
              boxShadow: '0 0 12px rgba(0, 255, 65, 0.06)',
            }}
            headStyle={{
              borderBottom: '1px solid rgba(0, 255, 65, 0.25)',
              color: '#00ff41',
            }}
          >
            <div style={{ color: 'rgba(0, 255, 65, 0.55)', fontSize: 12, textAlign: 'center', padding: 24, fontFamily: "'JetBrains Mono', monospace" }}>
              预留
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
