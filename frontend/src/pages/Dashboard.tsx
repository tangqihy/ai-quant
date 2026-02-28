import React from 'react';
import { Card, Row, Col, Statistic, Table } from 'antd';
import { ArrowUpOutlined, ArrowDownOutlined, StockOutlined, DollarOutlined, PercentageOutlined, RiseOutlined } from '@ant-design/icons';
import RevenueChart from '../components/charts/RevenueChart';

const Dashboard: React.FC = () => {
  // 模拟数据
  const summaryData = [
    { title: '总资产', value: 1234567.89, prefix: <DollarOutlined />, suffix: '', precision: 2 },
    { title: '今日收益', value: 12345.67, prefix: <ArrowUpOutlined />, suffix: '', precision: 2, color: '#ff4d4f' },
    { title: '收益率', value: 2.35, prefix: <PercentageOutlined />, suffix: '%', precision: 2, color: '#ff4d4f' },
    { title: '持仓股票', value: 25, prefix: <StockOutlined />, suffix: '只', precision: 0 },
  ];

  const stockColumns = [
    { title: '股票代码', dataIndex: 'code', key: 'code' },
    { title: '股票名称', dataIndex: 'name', key: 'name' },
    { title: '当前价格', dataIndex: 'price', key: 'price', render: (val: number) => val.toFixed(2) },
    { title: '涨跌幅', dataIndex: 'change', key: 'change', render: (val: number) => (
      <span style={{ color: val >= 0 ? '#ff4d4f' : '#52c41a' }}>
        {val >= 0 ? '+' : ''}{val.toFixed(2)}%
      </span>
    )},
    { title: '持仓盈亏', dataIndex: 'pnl', key: 'pnl', render: (val: number) => (
      <span style={{ color: val >= 0 ? '#ff4d4f' : '#52c41a' }}>
        {val >= 0 ? '+' : ''}{val.toFixed(2)}
      </span>
    )},
  ];

  const stockData = [
    { key: '1', code: '600519', name: '贵州茅台', price: 1856.50, change: 2.35, pnl: 12500 },
    { key: '2', code: '000858', name: '五粮液', price: 168.30, change: 1.28, pnl: 3200 },
    { key: '3', code: '601318', name: '中国平安', price: 52.80, change: -0.56, pnl: -1800 },
    { key: '4', code: '600036', name: '招商银行', price: 38.90, change: 0.78, pnl: 2100 },
    { key: '5', code: '300750', name: '宁德时代', price: 425.60, change: 3.12, pnl: 8900 },
  ];

  const positionData = [
    { title: '股票仓位', value: 75.5, suffix: '%' },
    { title: '现金仓位', value: 24.5, suffix: '%' },
  ];

  return (
    <div>
      <h2 style={{ marginBottom: 24 }}>仪表盘概览</h2>
      
      {/* 统计卡片 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        {summaryData.map((item, index) => (
          <Col xs={24} sm={12} lg={6} key={index}>
            <Card>
              <Statistic
                title={item.title}
                value={item.value}
                precision={item.precision}
                prefix={item.prefix}
                suffix={item.suffix}
                valueStyle={{ color: item.color || '#3f8600' }}
              />
            </Card>
          </Col>
        ))}
      </Row>

      {/* 图表区域 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} lg={16}>
          <Card title="收益曲线" style={{ height: 400 }}>
            <RevenueChart />
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card title="仓位分布" style={{ height: 400 }}>
            <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', height: '100%', gap: 24 }}>
              {positionData.map((item, index) => (
                <div key={index} style={{ textAlign: 'center' }}>
                  <Statistic
                    title={item.title}
                    value={item.value}
                    suffix={item.suffix}
                    valueStyle={{ fontSize: 32, color: index === 0 ? '#1890ff' : '#52c41a' }}
                  />
                  <div style={{ 
                    width: '80%', 
                    height: 8, 
                    background: '#f0f0f0', 
                    borderRadius: 4, 
                    margin: '8px auto 0',
                    overflow: 'hidden'
                  }}>
                    <div style={{ 
                      width: `${item.value}%`, 
                      height: '100%', 
                      background: index === 0 ? '#1890ff' : '#52c41a',
                      borderRadius: 4
                    }} />
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </Col>
      </Row>

      {/* 持仓股票表格 */}
      <Card title="持仓明细">
        <Table 
          columns={stockColumns} 
          dataSource={stockData} 
          pagination={false}
          size="small"
        />
      </Card>
    </div>
  );
};

export default Dashboard;
