import React, { useState, useEffect } from 'react';
import { Card, Row, Col, Table, message, Spin, Tag } from 'antd';
import {
  StockOutlined,
  RiseOutlined,
  FallOutlined,
  ThunderboltOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons';
import { motion } from 'framer-motion';
import { getStocks, getRealtimeQuotes } from '../services/api';
import RevenueChart from '../components/charts/RevenueChart';
import { AnimatedCard, PulseIndicator } from '../components/common/AnimatedCard';
import { StaggerContainer, StaggerItem } from '../components/common/PageTransition';

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
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.5 }}
    >
      {/* 标题区域 */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        style={{ marginBottom: 24, display: 'flex', alignItems: 'center', gap: 12 }}
      >
        <motion.div
          animate={{ rotate: [0, 10, -10, 0] }}
          transition={{ duration: 0.5, delay: 0.5 }}
        >
          <ThunderboltOutlined style={{ fontSize: 24, color: '#1890ff' }} />
        </motion.div>
        <h2 style={{ margin: 0, fontSize: 22, fontWeight: 600 }}>仪表盘概览</h2>
      </motion.div>

      {/* 统计卡片区域 */}
      <StaggerContainer staggerDelay={0.1}>
        <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
          <Col xs={24} sm={12} lg={8}>
            <StaggerItem>
              <AnimatedCard
                title="A股总数"
                value={totalStocks}
                prefix={<StockOutlined style={{ marginRight: 8 }} />}
                suffix="只"
                color="#1890ff"
                delay={0}
              />
            </StaggerItem>
          </Col>
          <Col xs={24} sm={12} lg={8}>
            <StaggerItem>
              <AnimatedCard
                title="系统状态"
                value="运行中"
                prefix={<PulseIndicator color="#52c41a" size={10} />}
                color="#52c41a"
                delay={0.1}
              />
            </StaggerItem>
          </Col>
          <Col xs={24} sm={12} lg={8}>
            <StaggerItem>
              <AnimatedCard
                title="支持策略"
                value={3}
                suffix="种"
                color="#722ed1"
                delay={0.2}
              />
            </StaggerItem>
          </Col>
        </Row>
      </StaggerContainer>

      {/* 图表和表格区域 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} lg={14}>
          <motion.div
            initial={{ opacity: 0, x: -30 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5, delay: 0.3 }}
            whileHover={{ scale: 1.005 }}
          >
            <Card 
              title="收益曲线（示例）" 
              style={{ ...cardStyle, height: 420 }}
              headStyle={{ fontWeight: 600, borderBottom: '2px solid #f0f0f0' }}
            >
              <RevenueChart />
            </Card>
          </motion.div>
        </Col>
        <Col xs={24} lg={10}>
          <motion.div
            initial={{ opacity: 0, x: 30 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5, delay: 0.4 }}
            whileHover={{ scale: 1.005 }}
          >
            <Card 
              title="热门股票" 
              style={{ ...cardStyle, height: 420 }}
              headStyle={{ fontWeight: 600, borderBottom: '2px solid #f0f0f0' }}
            >
              <Spin spinning={loading}>
                <Table
                  columns={stockColumns}
                  dataSource={topStocks}
                  pagination={false}
                  size="small"
                  scroll={{ y: 300 }}
                  rowClassName={() => 'animated-row'}
                />
              </Spin>
            </Card>
          </motion.div>
        </Col>
      </Row>
    </motion.div>
  );
};

export default Dashboard;
