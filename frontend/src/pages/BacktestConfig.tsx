import React, { useState } from 'react';
import { Card, Form, Input, Select, InputNumber, DatePicker, Button, Space, Divider, Row, Col, message } from 'antd';
import { PlayCircleOutlined, SaveOutlined, UndoOutlined } from '@ant-design/icons';

const { Option } = Select;
const { RangePicker } = DatePicker;
const { TextArea } = Input;

interface BacktestConfig {
  stockCode: string;
  startDate: string;
  endDate: string;
  initialCapital: number;
  strategyType: string;
  buySignal: string;
  sellSignal: string;
  positionSize: number;
  stopLoss: number;
  commission: number;
  slippage: number;
}

const BacktestConfig: React.FC = () => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);

  const onFinish = (values: any) => {
    console.log('回测配置:', values);
    message.success('配置已保存');
    setLoading(true);
    // 模拟回测执行
    setTimeout(() => {
      setLoading(false);
      message.info('回测执行完成');
    }, 2000);
  };

  const onReset = () => {
    form.resetFields();
    message.info('表单已重置');
  };

  return (
    <div>
      <h2 style={{ marginBottom: 24 }}>回测配置</h2>
      
      <Form
        form={form}
        layout="vertical"
        onFinish={onFinish}
        initialValues={{
          stockCode: '600519',
          initialCapital: 1000000,
          strategyType: 'ma_cross',
          positionSize: 10,
          stopLoss: 5,
          commission: 0.0003,
          slippage: 0.001,
        }}
      >
        <Row gutter={[16, 0]}>
          {/* 基础配置 */}
          <Col xs={24} lg={12}>
            <Card title="基础配置" size="small">
              <Form.Item label="股票代码" name="stockCode" rules={[{ required: true, message: '请输入股票代码' }]}>
                <Input placeholder="例如: 600519" />
              </Form.Item>
              
              <Form.Item label="回测时间范围" name="dateRange" rules={[{ required: true, message: '请选择时间范围' }]}>
                <RangePicker style={{ width: '100%' }} />
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
                  <Option value="rsi">RSI 策略</Option>
                  <Option value="macd">MACD 策略</Option>
                  <Option value="bollinger">布林带策略</Option>
                  <Option value="custom">自定义策略</Option>
                </Select>
              </Form.Item>
            </Card>
          </Col>

          {/* 交易参数 */}
          <Col xs={24} lg={12}>
            <Card title="交易参数" size="small">
              <Form.Item label="仓位比例 (%)" name="positionSize">
                <InputNumber style={{ width: '100%' }} min={1} max={100} />
              </Form.Item>
              
              <Form.Item label="止损比例 (%)" name="stopLoss">
                <InputNumber style={{ width: '100%' }} min={1} max={50} step={0.5} />
              </Form.Item>
              
              <Form.Item label="手续费率" name="commission">
                <InputNumber
                  style={{ width: '100%' }}
                  min={0}
                  max={0.01}
                  step={0.0001}
                  precision={4}
                  formatter={value => `${(value! * 100).toFixed(2)}%`}
                  parser={value => parseFloat(value!.replace('%', '')) / 100}
                />
              </Form.Item>
              
              <Form.Item label="滑点" name="slippage">
                <InputNumber
                  style={{ width: '100%' }}
                  min={0}
                  max={0.01}
                  step={0.0001}
                  precision={4}
                  formatter={value => `${(value! * 100).toFixed(2)}%`}
                  parser={value => parseFloat(value!.replace('%', '')) / 100}
                />
              </Form.Item>
            </Card>
          </Col>

          {/* 策略参数 */}
          <Col xs={24}>
            <Card title="策略参数" size="small">
              <Row gutter={16}>
                <Col xs={24} lg={8}>
                  <Form.Item label="短期均线周期" name="shortPeriod">
                    <InputNumber style={{ width: '100%' }} min={1} max={100} defaultValue={5} />
                  </Form.Item>
                </Col>
                <Col xs={24} lg={8}>
                  <Form.Item label="长期均线周期" name="longPeriod">
                    <InputNumber style={{ width: '100%' }} min={1} max={200} defaultValue={20} />
                  </Form.Item>
                </Col>
                <Col xs={24} lg={8}>
                  <Form.Item label=" RSI 周期" name="rsiPeriod">
                    <InputNumber style={{ width: '100%' }} min={1} max={50} defaultValue={14} />
                  </Form.Item>
                </Col>
              </Row>
            </Card>
          </Col>

          {/* 自定义策略 */}
          <Col xs={24}>
            <Card title="自定义策略条件" size="small">
              <Form.Item label="买入条件" name="buySignal">
                <TextArea 
                  rows={3} 
                  placeholder="例如: MA5 > MA20 AND RSI < 30" 
                />
              </Form.Item>
              
              <Form.Item label="卖出条件" name="sellSignal">
                <TextArea 
                  rows={3} 
                  placeholder="例如: MA5 < MA20 OR RSI > 70" 
                />
              </Form.Item>
            </Card>
          </Col>
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
    </div>
  );
};

export default BacktestConfig;
