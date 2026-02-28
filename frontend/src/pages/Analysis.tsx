import React, { useState } from 'react';
import { Card, Row, Col, Statistic, Table, Select, Tabs, DatePicker, Space } from 'antd';
import { ArrowUpOutlined, ArrowDownOutlined, TrophyOutlined, GoldOutlined, DollarOutlined, PercentageOutlined } from '@ant-design/icons';
import RevenueChart from '../components/charts/RevenueChart';
import KLineChart from '../components/charts/KLineChart';

const { RangePicker } = DatePicker;
const { Option } = Select;
const { TabPane } = Tabs;

const Analysis: React.FC = () => {
  const [selectedStrategy, setSelectedStrategy] = useState('all');

  // 模拟回测结果数据
  const summaryStats = [
    { title: '总收益率', value: 35.68, prefix: <PercentageOutlined />, precision: 2, color: '#3f8600' },
    { title: '年化收益率', value: 18.25, prefix: <PercentageOutlined />, precision: 2, color: '#3f8600' },
    { title: '夏普比率', value: 1.45, prefix: '', precision: 2, color: '#1890ff' },
    { title: '最大回撤', value: -12.35, prefix: <ArrowDownOutlined />, precision: 2, color: '#cf1322' },
    { title: '胜率', value: 58.5, prefix: <PercentageOutlined />, precision: 1, color: '#1890ff' },
    { title: '盈亏比', value: 1.85, prefix: '', precision: 2, color: '#1890ff' },
  ];

  const tradeColumns = [
    { title: '交易日期', dataIndex: 'date', key: 'date' },
    { title: '股票代码', dataIndex: 'code', key: 'code' },
    { title: '交易类型', dataIndex: 'type', key: 'type', 
      render: (type: string) => (
        <span style={{ color: type === '买入' ? '#ff4d4f' : '#52c41a', fontWeight: 'bold' }}>
          {type}
        </span>
      )
    },
    { title: '价格', dataIndex: 'price', key: 'price', render: (val: number) => val.toFixed(2) },
    { title: '数量', dataIndex: 'quantity', key: 'quantity' },
    { title: '金额', dataIndex: 'amount', key: 'amount', render: (val: number) => val.toFixed(2) },
    { title: '收益率', dataIndex: 'return', key: 'return', 
      render: (val: number) => (
        <span style={{ color: val >= 0 ? '#ff4d4f' : '#52c41a' }}>
          {val >= 0 ? '+' : ''}{val.toFixed(2)}%
        </span>
      )
    },
    { title: '持仓天数', dataIndex: 'holdDays', key: 'holdDays' },
  ];

  const tradeData = [
    { key: '1', date: '2024-01-15', code: '600519', type: '买入', price: 1680.50, quantity: 100, amount: 168050, return: 0, holdDays: 0 },
    { key: '2', date: '2024-01-20', code: '000858', type: '买入', price: 155.30, quantity: 1000, amount: 155300, return: 0, holdDays: 0 },
    { key: '3', date: '2024-02-05', code: '600519', type: '卖出', price: 1750.80, quantity: 100, amount: 175080, return: 4.18, holdDays: 21 },
    { key: '4', date: '2024-02-10', code: '601318', type: '买入', price: 48.60, quantity: 2000, amount: 97200, return: 0, holdDays: 0 },
    { key: '5', date: '2024-03-01', code: '000858', type: '卖出', price: 162.50, quantity: 1000, amount: 162500, return: 4.64, holdDays: 40 },
    { key: '6', date: '2024-03-15', code: '601318', type: '卖出', price: 51.20, quantity: 2000, amount: 102400, return: 5.35, holdDays: 34 },
    { key: '7', date: '2024-03-20', code: '300750', type: '买入', price: 385.60, quantity: 500, amount: 192800, return: 0, holdDays: 0 },
    { key: '8', date: '2024-04-10', code: '300750', type: '卖出', price: 398.50, quantity: 500, amount: 199250, return: 3.35, holdDays: 21 },
  ];

  const monthlyReturns = [
    { month: '2024-01', return: 3.25 },
    { month: '2024-02', return: 5.68 },
    { month: '2024-03', return: -2.15 },
    { month: '2024-04', return: 8.45 },
    { month: '2024-05', return: 4.32 },
    { month: '2024-06', return: -1.25 },
    { month: '2024-07', return: 6.85 },
    { month: '2024-08', return: 3.12 },
    { month: '2024-09', return: -3.56 },
    { month: '2024-10', return: 5.28 },
    { month: '2024-11', return: 4.85 },
    { month: '2024-12', return: 1.84 },
  ];

  return (
    <div>
      <h2 style={{ marginBottom: 24 }}>收益分析</h2>

      {/* 筛选条件 */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space wrap>
          <span>策略选择:</span>
          <Select value={selectedStrategy} onChange={setSelectedStrategy} style={{ width: 150 }}>
            <Option value="all">全部策略</Option>
            <Option value="ma_cross">均线交叉</Option>
            <Option value="rsi">RSI策略</Option>
            <Option value="macd">MACD策略</Option>
          </Select>
          <RangePicker />
        </Space>
      </Card>

      {/* 统计指标 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        {summaryStats.map((item, index) => (
          <Col xs={12} sm={8} lg={4} key={index}>
            <Card>
              <Statistic
                title={item.title}
                value={item.value}
                precision={item.precision}
                prefix={item.prefix}
                valueStyle={{ color: item.color }}
              />
            </Card>
          </Col>
        ))}
      </Row>

      {/* 收益曲线和K线图 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} lg={12}>
          <Card title="累计收益曲线" style={{ height: 400 }}>
            <RevenueChart />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="K线走势" style={{ height: 400 }}>
            <KLineChart />
          </Card>
        </Col>
      </Row>

      {/* 月度收益和交易记录 */}
      <Card>
        <Tabs defaultActiveKey="1">
          <TabPane tab="交易记录" key="1">
            <Table 
              columns={tradeColumns} 
              dataSource={tradeData} 
              pagination={{ pageSize: 5 }}
              size="small"
              scroll={{ x: 900 }}
            />
          </TabPane>
          <TabPane tab="月度收益" key="2">
            <Table 
              dataSource={monthlyReturns.map((item, i) => ({ ...item, key: i }))}
              columns={[
                { title: '月份', dataIndex: 'month', key: 'month' },
                { title: '月收益率', dataIndex: 'return', key: 'return',
                  render: (val: number) => (
                    <span style={{ color: val >= 0 ? '#ff4d4f' : '#52c41a', fontWeight: 'bold' }}>
                      {val >= 0 ? '+' : ''}{val.toFixed(2)}%
                    </span>
                  )
                },
              ]}
              pagination={false}
              size="small"
            />
          </TabPane>
          <TabPane tab="风险分析" key="3">
            <Row gutter={[16, 16]}>
              <Col xs={24} lg={12}>
                <Card title="风险指标" size="small">
                  <Statistic title="波动率" value={15.68} suffix="%" precision={2} />
                  <Statistic title="下行波动率" value={12.35} suffix="%" precision={2} />
                  <Statistic title="VaR (95%)" value={-5.25} suffix="%" precision={2} valueStyle={{ color: '#cf1322' }} />
                </Card>
              </Col>
              <Col xs={24} lg={12}>
                <Card title="风险调整收益" size="small">
                  <Statistic title="夏普比率" value={1.45} precision={2} />
                  <Statistic title="索提诺比率" value={1.85} precision={2} />
                  <Statistic title="卡玛比率" value={1.48} precision={2} />
                </Card>
              </Col>
            </Row>
          </TabPane>
        </Tabs>
      </Card>
    </div>
  );
};

export default Analysis;
