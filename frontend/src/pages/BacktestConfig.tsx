import React, { useState } from 'react';
import { Card, Form, Input, Select, InputNumber, DatePicker, Button, Space, Divider, Row, Col, message, Spin, Dropdown } from 'antd';
import { PlayCircleOutlined, SaveOutlined, UndoOutlined, DownOutlined } from '@ant-design/icons';
import { runBacktest, BacktestResult } from '../services/api';
import { useWatchlist } from '../hooks/useWatchlist';
import dayjs from 'dayjs';

const { Option } = Select;
const { RangePicker } = DatePicker;
const { TextArea } = Input;

interface BacktestConfig {
  stockCode: string;
  startDate: string;
  endDate: string;
  initialCapital: number;
  strategyType: string;
  shortWindow: number;
  longWindow: number;
}

const BacktestConfig: React.FC = () => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const { stocks } = useWatchlist();

  const onFinish = async (values: any) => {
    console.log('回测配置:', values);
    
    // 解析日期范围
    const dateRange = values.dateRange;
    const startDate = dateRange?.[0]?.format('YYYYMMDD') || '20230101';
    const endDate = dateRange?.[1]?.format('YYYYMMDD') || '20231231';
    
    setLoading(true);
    message.info('回测执行中，请稍候...');
    
    try {
      const backtestResult = await runBacktest({
        symbol: values.stockCode,
        start_date: startDate,
        end_date: endDate,
        strategy: values.strategyType,
        short_window: values.shortWindow || 5,
        long_window: values.longWindow || 20,
        initial_capital: values.initialCapital || 1000000
      });
      
      if (backtestResult.success) {
        setResult(backtestResult);
        // 保存到localStorage，供Analysis页面展示
        localStorage.setItem('lastBacktestResult', JSON.stringify(backtestResult));
        message.success('回测执行完成！');
      } else {
        message.error(backtestResult.error || '回测失败');
      }
    } catch (error: any) {
      console.error('回测错误:', error);
      message.error(error.message || '回测执行失败');
    } finally {
      setLoading(false);
    }
  };

  const onReset = () => {
    form.resetFields();
    setResult(null);
    message.info('表单已重置');
  };

  return (
    <div>
      <h2 style={{ marginBottom: 24 }}>回测配置</h2>
      
      <Spin spinning={loading}>
        <Form
          form={form}
          layout="vertical"
          onFinish={onFinish}
          initialValues={{
            stockCode: stocks[0]?.symbol ?? '600519',
            dateRange: [dayjs('20241201'), dayjs('20250228')],
            initialCapital: 1000000,
            strategyType: 'ma_cross',
            shortWindow: 5,
            longWindow: 20,
          }}
        >
          <Row gutter={[16, 0]}>
            {/* 基础配置 */}
            <Col xs={24} lg={12}>
              <Card title="基础配置" size="small">
                <Form.Item
                  label="股票代码"
                  name="stockCode"
                  rules={[{ required: true, message: '请输入或选择股票代码' }]}
                >
                  <Space.Compact style={{ width: '100%' }}>
                    <Input placeholder="例如 600519，或从自选选择" style={{ flex: 1 }} />
                    <Dropdown
                      menu={{
                        items: stocks.map((s) => ({ 
                          key: s.symbol, 
                          label: `${s.symbol} ${s.name}`,
                          onClick: () => {
                            console.log('Selected stock:', s.symbol);
                            form.setFieldValue('stockCode', s.symbol);
                          }
                        })),
                      }}
                      disabled={stocks.length === 0}
                    >
                      <Button>
                        从自选 <DownOutlined />
                      </Button>
                    </Dropdown>
                  </Space.Compact>
                </Form.Item>
                
                <Form.Item label="回测时间范围" name="dateRange" rules={[{ required: true, message: '请选择时间范围' }]}>
                  <RangePicker style={{ width: '100%' }} format="YYYY-MM-DD" />
                </Form.Item>
                
                <Form.Item label="初始资金" name="initialCapital" rules={[{ required: true, message: '请输入初始资金' }]}>
                  <InputNumber
                    style={{ width: '100%' }}
                    min={10000}
                    max={100000000}
                    formatter={value => `${value}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}
                    parser={value => value!.replace(/\$\s?|(,*)/g, '')}
                  />
                </Form.Item>
                
                <Form.Item label="策略类型" name="strategyType" rules={[{ required: true, message: '请选择策略类型' }]}>
                  <Select>
                    <Option value="ma_cross">均线交叉策略</Option>
                    <Option value="dual_ma">双MA策略</Option>
                  </Select>
                </Form.Item>
              </Card>
            </Col>

            {/* 策略参数 */}
            <Col xs={24} lg={12}>
              <Card title="策略参数" size="small">
                <Form.Item label="短期均线周期" name="shortWindow">
                  <InputNumber style={{ width: '100%' }} min={1} max={100} />
                </Form.Item>
                
                <Form.Item label="长期均线周期" name="longWindow">
                  <InputNumber style={{ width: '100%' }} min={1} max={200} />
                </Form.Item>
              </Card>
            </Col>

            {/* 回测结果 */}
            {result && (
              <Col xs={24}>
                <Card title="回测结果" size="small" style={{ marginTop: 16 }}>
                  <Row gutter={[16, 16]}>
                    <Col xs={12} md={6}>
                      <div style={{ textAlign: 'center' }}>
                        <div style={{ color: '#888', fontSize: 12 }}>总收益率</div>
                        <div style={{ 
                          color: result.total_return > 0 ? '#f50' : '#52c41a', 
                          fontSize: 24, 
                          fontWeight: 'bold' 
                        }}>
                          {result.total_return}%
                        </div>
                      </div>
                    </Col>
                    <Col xs={12} md={6}>
                      <div style={{ textAlign: 'center' }}>
                        <div style={{ color: '#888', fontSize: 12 }}>年化收益率</div>
                        <div style={{ 
                          color: result.annual_return > 0 ? '#f50' : '#52c41a', 
                          fontSize: 24, 
                          fontWeight: 'bold' 
                        }}>
                          {result.annual_return}%
                        </div>
                      </div>
                    </Col>
                    <Col xs={12} md={6}>
                      <div style={{ textAlign: 'center' }}>
                        <div style={{ color: '#888', fontSize: 12 }}>最大回撤</div>
                        <div style={{ color: '#ff4d4f', fontSize: 24, fontWeight: 'bold' }}>
                          {result.max_drawdown}%
                        </div>
                      </div>
                    </Col>
                    <Col xs={12} md={6}>
                      <div style={{ textAlign: 'center' }}>
                        <div style={{ color: '#888', fontSize: 12 }}>胜率</div>
                        <div style={{ fontSize: 24, fontWeight: 'bold' }}>
                          {result.win_rate}%
                        </div>
                      </div>
                    </Col>
                  </Row>
                  <Divider />
                  <div style={{ color: '#888', fontSize: 12 }}>
                    交易次数: {result.total_trades} | 
                    初始资金: {result.initial_capital.toLocaleString()} | 
                    最终资产: {result.final_value.toLocaleString()}
                  </div>
                </Card>
              </Col>
            )}
          </Row>

          <Divider />

          <Space>
            <Button type="primary" htmlType="submit" icon={<PlayCircleOutlined />} loading={loading}>
              开始回测
            </Button>
            <Button icon={<SaveOutlined />}>
              保存配置
            </Button>
            <Button icon={<UndoOutlined />} onClick={onReset}>
              重置
            </Button>
          </Space>
        </Form>
      </Spin>
    </div>
  );
};

export default BacktestConfig;
