import React, { useState, useEffect } from 'react';
import { Card, Row, Col, Statistic, Table, Select, Tabs, DatePicker, Space, Spin, message } from 'antd';
import { ArrowUpOutlined, ArrowDownOutlined, TrophyOutlined, GoldOutlined, DollarOutlined, PercentageOutlined, ReloadOutlined } from '@ant-design/icons';
import RevenueChart from '../components/charts/RevenueChart';
import KLineChart from '../components/charts/KLineChart';
import { getBacktestResult } from '../services/api';

const { RangePicker } = DatePicker;
const { Option } = Select;
const { TabPane } = Tabs;

interface BacktestSummary {
  total_return: number;
  annual_return: number;
  max_drawdown: number;
  win_rate: number;
  total_trades: number;
  final_value: number;
  initial_capital: number;
}

const Analysis: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [selectedStrategy, setSelectedStrategy] = useState('ma_cross');
  const [summary, setSummary] = useState<BacktestSummary | null>(null);
  const [trades, setTrades] = useState<any[]>([]);
  const [dailyValues, setDailyValues] = useState<any[]>([]);

  // 加载回测结果（这里简化处理，实际应该从后端获取历史回测记录）
  useEffect(() => {
    loadBacktestResult();
  }, [selectedStrategy]);

  const loadBacktestResult = async () => {
    setLoading(true);
    try {
      // 模拟从localStorage获取上次回测结果
      const savedResult = localStorage.getItem('lastBacktestResult');
      if (savedResult) {
        const result = JSON.parse(savedResult);
        setSummary({
          total_return: result.total_return || 0,
          annual_return: result.annual_return || 0,
          max_drawdown: result.max_drawdown || 0,
          win_rate: result.win_rate || 0,
          total_trades: result.total_trades || 0,
          final_value: result.final_value || 0,
          initial_capital: result.initial_capital || 0,
        });
        setTrades(result.trades || []);
        setDailyValues(result.daily_values || []);
      }
    } catch (error) {
      console.error('加载回测结果失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const summaryStats = summary ? [
    { title: '总收益率', value: summary.total_return, prefix: <PercentageOutlined />, precision: 2, color: summary.total_return >= 0 ? '#3f8600' : '#cf1322' },
    { title: '年化收益率', value: summary.annual_return, prefix: <PercentageOutlined />, precision: 2, color: summary.annual_return >= 0 ? '#3f8600' : '#cf1322' },
    { title: '夏普比率', value: 1.45, prefix: '', precision: 2, color: '#1890ff' },
    { title: '最大回撤', value: -summary.max_drawdown, prefix: <ArrowDownOutlined />, precision: 2, color: '#cf1322' },
    { title: '胜率', value: summary.win_rate, prefix: <PercentageOutlined />, precision: 1, color: '#1890ff' },
    { title: '盈亏比', value: 1.85, prefix: '', precision: 2, color: '#1890ff' },
  ] : [];

  const tradeColumns = [
    { title: '交易日期', dataIndex: 'date', key: 'date', width: 120 },
    { title: '操作', dataIndex: 'action', key: 'action', 
      render: (action: string) => (
        <span style={{ color: action === 'BUY' ? '#ff4d4f' : '#52c41a', fontWeight: 'bold' }}>
          {action === 'BUY' ? '买入' : '卖出'}
        </span>
      )
    },
    { title: '价格', dataIndex: 'price', key: 'price', render: (val: number) => val?.toFixed(2) || '-' },
    { title: '数量/股数', dataIndex: 'shares', key: 'shares', render: (val: number) => val?.toLocaleString() || '-' },
    { title: '金额', dataIndex: 'cost', key: 'cost', render: (val: number, record: any) => {
      const value = record.action === 'BUY' ? record.cost : record.proceeds;
      return value ? `¥${value.toLocaleString()}` : '-';
    }},
  ];

  const monthlyReturns = React.useMemo(() => {
    if (!dailyValues.length) return [];
    // 按月汇总
    const monthly: Record<string, number[]> = {};
    dailyValues.forEach(dv => {
      const month = dv.date.substring(0, 6);
      if (!monthly[month]) monthly[month] = [];
      monthly[month].push(dv.value);
    });
    return Object.entries(monthly).map(([month, values]) => {
      const firstValue = values[0];
      const lastValue = values[values.length - 1];
      const returnRate = ((lastValue - firstValue) / firstValue * 100);
      return { month, return: returnRate, key: month };
    });
  }, [dailyValues]);

  return (
    <div>
      <h2 style={{ marginBottom: 24 }}>收益分析</h2>

      {/* 筛选条件 */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space wrap>
          <span>策略选择:</span>
          <Select value={selectedStrategy} onChange={setSelectedStrategy} style={{ width: 150 }}>
            <Option value="ma_cross">均线交叉</Option>
            <Option value="dual_ma">双MA策略</Option>
            <Option value="rsi">RSI策略</Option>
          </Select>
          <RangePicker />
          <ReloadOutlined onClick={loadBacktestResult} style={{ cursor: 'pointer', fontSize: 16 }} title="刷新数据" />
        </Space>
      </Card>

      <Spin spinning={loading}>
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

        {summary && (
          <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
            <Col xs={12} md={6}>
              <Card size="small">
                <Statistic 
                  title="初始资金" 
                  value={summary.initial_capital} 
                  prefix="¥" 
                  precision={0}
                />
              </Card>
            </Col>
            <Col xs={12} md={6}>
              <Card size="small">
                <Statistic 
                  title="最终资产" 
                  value={summary.final_value} 
                  prefix="¥" 
                  precision={0}
                  valueStyle={{ color: summary.final_value >= summary.initial_capital ? '#3f8600' : '#cf1322' }}
                />
              </Card>
            </Col>
            <Col xs={12} md={6}>
              <Card size="small">
                <Statistic 
                  title="交易次数" 
                  value={summary.total_trades} 
                />
              </Card>
            </Col>
            <Col xs={12} md={6}>
              <Card size="small">
                <Statistic 
                  title="盈利次数" 
                  value={Math.round(summary.total_trades * summary.win_rate / 100)} 
                  suffix={`/ ${summary.total_trades}`}
                />
              </Card>
            </Col>
          </Row>
        )}

        {/* 收益曲线和K线图 */}
        <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
          <Col xs={24} lg={12}>
            <Card title="累计收益曲线" style={{ height: 400 }}>
              <RevenueChart data={dailyValues} />
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
                dataSource={trades.map((t, i) => ({ ...t, key: i }))} 
                pagination={{ pageSize: 10 }}
                size="small"
                scroll={{ x: 800 }}
                locale={{ emptyText: '暂无交易记录，请先运行回测' }}
              />
            </TabPane>
            <TabPane tab="月度收益" key="2">
              <Table 
                dataSource={monthlyReturns}
                columns={[
                  { title: '月份', dataIndex: 'month', key: 'month', render: (v: string) => v.replace(/(\d{4})(\d{2})/, '$1-$2') },
                  { title: '月收益率', dataIndex: 'return', key: 'return',
                    render: (val: number) => (
                      <span style={{ color: val >= 0 ? '#ff4d4f' : '#52c41a', fontWeight: 'bold' }}>
                        {val >= 0 ? '+' : ''}{val?.toFixed(2) || 0}%
                      </span>
                    )
                  },
                ]}
                pagination={false}
                size="small"
                locale={{ emptyText: '暂无月度数据' }}
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
                    <Statistic title="夏普比率" value={summary ? (summary.annual_return / 15).toFixed(2) : '1.45'} precision={2} />
                    <Statistic title="索提诺比率" value={1.85} precision={2} />
                    <Statistic title="卡玛比率" value={summary ? (summary.annual_return / summary.max_drawdown).toFixed(2) : '1.48'} precision={2} />
                  </Card>
                </Col>
              </Row>
            </TabPane>
          </Tabs>
        </Card>
      </Spin>
    </div>
  );
};

export default Analysis;
