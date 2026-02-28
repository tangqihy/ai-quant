import React, { useState, useEffect } from 'react';
import { Card, Row, Col, Statistic, Table, message, Spin, Tag } from 'antd';
import {
  StockOutlined,
  RiseOutlined,
  FallOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { getStocks, getRealtimeQuotes } from '../services/api';
import RevenueChart from '../components/charts/RevenueChart';

interface HoldingStock {
  key: string;
  symbol: string;
  name: string;
  price: number;
  change_pct: number;
}

const Dashboard: React.FC = () => {
  const [topStocks, setTopStocks] = useState<HoldingStock[]>([]);
  const [loading, setLoading] = useState(false);
  const [totalStocks, setTotalStocks] = useState(0);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const res = await getStocks(1, 10);
        if (res.success) {
          setTotalStocks(res.total);
          const symbols = res.data.map((s: any) => s.symbol);
          try {
            const quotesRes = await getRealtimeQuotes(symbols);
            if (quotesRes.success) {
              setTopStocks(
                quotesRes.data.map((q: any, i: number) => ({
                  key: String(i),
                  symbol: q.symbol,
                  name: q.name || res.data[i]?.name || '',
                  price: q.price,
                  change_pct: q.change_pct,
                }))
              );
            }
          } catch {
            setTopStocks(
              res.data.map((s: any, i: number) => ({
                key: String(i),
                symbol: s.symbol,
                name: s.name,
                price: 0,
                change_pct: 0,
              }))
            );
          }
        }
      } catch (e: any) {
        message.error('获取数据失败');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const stockColumns = [
    { title: '代码', dataIndex: 'symbol', key: 'symbol', width: 90,
      render: (v: string) => <span style={{ fontFamily: 'monospace', fontWeight: 500 }}>{v}</span>
    },
    { title: '名称', dataIndex: 'name', key: 'name', width: 100 },
    {
      title: '价格', dataIndex: 'price', key: 'price', width: 90,
      render: (val: number) => val > 0 ? <span style={{ fontWeight: 600 }}>{val.toFixed(2)}</span> : '-',
    },
    {
      title: '涨跌幅', dataIndex: 'change_pct', key: 'change_pct', width: 100,
      render: (val: number) => {
        if (!val) return '-';
        const color = val >= 0 ? '#ff4d4f' : '#52c41a';
        const icon = val >= 0 ? <RiseOutlined /> : <FallOutlined />;
        return (
          <Tag color={val >= 0 ? 'error' : 'success'} icon={icon} style={{ fontWeight: 600 }}>
            {val >= 0 ? '+' : ''}{val.toFixed(2)}%
          </Tag>
        );
      },
    },
  ];

  const cardStyle = {
    borderRadius: 12,
    boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
    transition: 'all 0.3s ease',
  };

  return (
    <div style={{ animation: 'fadeIn 0.5s ease' }}>
      <div style={{ marginBottom: 24, display: 'flex', alignItems: 'center', gap: 12 }}>
        <ThunderboltOutlined style={{ fontSize: 24, color: '#1890ff' }} />
        <h2 style={{ margin: 0, fontSize: 22, fontWeight: 600 }}>仪表盘概览</h2>
      </div>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} lg={8}>
          <Card style={cardStyle} hoverable>
            <Statistic
              title={<span style={{ fontSize: 14, color: '#8c8c8c' }}>A股总数</span>}
              value={totalStocks}
              prefix={<StockOutlined style={{ color: '#1890ff' }} />}
              suffix="只"
              valueStyle={{ fontSize: 32, fontWeight: 700, color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <Card style={cardStyle} hoverable>
            <Statistic
              title={<span style={{ fontSize: 14, color: '#8c8c8c' }}>系统状态</span>}
              value="运行中"
              valueStyle={{ fontSize: 32, fontWeight: 700, color: '#52c41a' }}
            />
            <div style={{ marginTop: 8 }}>
              <Tag color="success">后端正常</Tag>
              <Tag color="processing">数据源: 腾讯/东方财富</Tag>
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <Card style={cardStyle} hoverable>
            <Statistic
              title={<span style={{ fontSize: 14, color: '#8c8c8c' }}>支持策略</span>}
              value={3}
              suffix="种"
              valueStyle={{ fontSize: 32, fontWeight: 700, color: '#722ed1' }}
            />
            <div style={{ marginTop: 8 }}>
              <Tag color="purple">MA交叉</Tag>
              <Tag color="purple">RSI</Tag>
              <Tag color="purple">MACD</Tag>
            </div>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} lg={14}>
          <Card title="收益曲线（示例）" style={{ ...cardStyle, height: 420 }}
            headStyle={{ fontWeight: 600, borderBottom: '2px solid #f0f0f0' }}>
            <RevenueChart />
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card title="热门股票" style={{ ...cardStyle, height: 420 }}
            headStyle={{ fontWeight: 600, borderBottom: '2px solid #f0f0f0' }}>
            <Spin spinning={loading}>
              <Table
                columns={stockColumns}
                dataSource={topStocks}
                pagination={false}
                size="small"
                scroll={{ y: 300 }}
              />
            </Spin>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default Dashboard;
