import React, { useState, useEffect } from 'react';
import { Card, Row, Col, Statistic, Table, message, Spin } from 'antd';
import {
  StockOutlined,
  DollarOutlined,
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
          const quotesRes = await getRealtimeQuotes(symbols);
          if (quotesRes.success) {
            setTopStocks(
              quotesRes.data.map((q: any, i: number) => ({
                key: String(i),
                symbol: q.symbol,
                name: q.name,
                price: q.price,
                change_pct: q.change_pct,
              }))
            );
          }
        }
      } catch (e: any) {
        message.error('获取数据失败: ' + (e.message || ''));
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const stockColumns = [
    { title: '股票代码', dataIndex: 'symbol', key: 'symbol' },
    { title: '股票名称', dataIndex: 'name', key: 'name' },
    {
      title: '当前价格',
      dataIndex: 'price',
      key: 'price',
      render: (val: number) => (val != null ? val.toFixed(2) : '-'),
    },
    {
      title: '涨跌幅',
      dataIndex: 'change_pct',
      key: 'change_pct',
      render: (val: number) => (
        <span style={{ color: val >= 0 ? '#ff4d4f' : '#52c41a' }}>
          {val >= 0 ? '+' : ''}
          {val?.toFixed(2)}%
        </span>
      ),
    },
  ];

  return (
    <div>
      <h2 style={{ marginBottom: 24 }}>仪表盘概览</h2>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="A股总数"
              value={totalStocks}
              prefix={<StockOutlined />}
              suffix="只"
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="系统状态"
              value="运行中"
              prefix={<DollarOutlined />}
              valueStyle={{ color: '#3f8600' }}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} lg={16}>
          <Card title="收益曲线（示例）" style={{ height: 400 }}>
            <RevenueChart />
          </Card>
        </Col>
      </Row>

      <Card title="热门股票实时行情">
        <Spin spinning={loading}>
          <Table
            columns={stockColumns}
            dataSource={topStocks}
            pagination={false}
            size="small"
          />
        </Spin>
      </Card>
    </div>
  );
};

export default Dashboard;
