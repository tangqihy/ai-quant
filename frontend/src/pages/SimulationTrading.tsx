import React, { useEffect, useState } from 'react';
import {
  Card,
  Row,
  Col,
  Button,
  Input,
  InputNumber,
  Select,
  Table,
  Tag,
  Space,
  Statistic,
  Tabs,
  Form,
  message,
  Modal,
  Empty,
  Badge,
  Tooltip,
} from 'antd';
import {
  ReloadOutlined,
  ShoppingCartOutlined,
  DollarOutlined,
  HistoryOutlined,
  WalletOutlined,
  LineChartOutlined,
} from '@ant-design/icons';
import {
  getAccount,
  getPositions,
  getOrders,
  getTrades,
  createOrder,
  cancelOrder,
  resetAccount,
  matchOrders,
  Order,
  Trade,
  Position,
  Account,
} from '../services/simulationApi';
import { useWatchlist } from '../hooks/useWatchlist';

const { TabPane } = Tabs;
const { Option } = Select;

const SimulationTrading: React.FC = () => {
  const { stocks } = useWatchlist();
  const [account, setAccount] = useState<Account | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(false);
  const [orderForm] = Form.useForm();
  const [selectedSymbol, setSelectedSymbol] = useState<string>('');

  // 加载数据
  const loadData = async () => {
    setLoading(true);
    try {
      const [accountRes, positionsRes, ordersRes, tradesRes] = await Promise.all([
        getAccount(),
        getPositions(),
        getOrders(),
        getTrades(),
      ]);

      if (accountRes.data?.success) {
        setAccount(accountRes.data.data);
      }
      if (positionsRes.data?.success) {
        setPositions(positionsRes.data.data || []);
      }
      if (ordersRes.data?.success) {
        setOrders(ordersRes.data.data || []);
      }
      if (tradesRes.data?.success) {
        setTrades(tradesRes.data.data || []);
      }
    } catch (error) {
      message.error('加载数据失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    // 定时刷新
    const timer = setInterval(loadData, 5000);
    return () => clearInterval(timer);
  }, []);

  // 下单
  const handleSubmitOrder = async (values: any) => {
    try {
      const res = await createOrder({
        symbol: values.symbol,
        action: values.action,
        order_type: values.order_type,
        price: values.order_type === 'LIMIT' ? values.price : undefined,
        quantity: values.quantity,
      });

      if (res.data?.success) {
        message.success('下单成功');
        orderForm.resetFields();
        loadData();
      } else {
        message.error(res.data?.message || '下单失败');
      }
    } catch (error: any) {
      message.error(error.response?.data?.detail || '下单失败');
    }
  };

  // 撤单
  const handleCancelOrder = (orderId: string) => {
    Modal.confirm({
      title: '确认撤单',
      content: '确定要撤销该订单吗？',
      onOk: async () => {
        try {
          await cancelOrder(orderId);
          message.success('撤单成功');
          loadData();
        } catch (error) {
          message.error('撤单失败');
        }
      },
    });
  };

  // 重置账户
  const handleReset = () => {
    Modal.confirm({
      title: '重置账户',
      content: '确定要重置模拟账户吗？所有持仓和订单将被清空。',
      onOk: async () => {
        try {
          await resetAccount();
          message.success('账户已重置');
          loadData();
        } catch (error) {
          message.error('重置失败');
        }
      },
    });
  };

  // 手动撮合
  const handleMatch = async () => {
    try {
      const res = await matchOrders();
      if (res.data?.success) {
        message.success(res.data.message);
        loadData();
      }
    } catch (error) {
      message.error('撮合失败');
    }
  };

  // 持仓表格列
  const positionColumns = [
    {
      title: '股票代码',
      dataIndex: 'symbol',
      key: 'symbol',
      render: (text: string) => <span style={{ fontFamily: 'monospace' }}>{text}</span>,
    },
    {
      title: '持仓数量',
      dataIndex: 'quantity',
      key: 'quantity',
      align: 'right' as const,
      render: (val: number) => val.toLocaleString(),
    },
    {
      title: '成本价',
      dataIndex: 'avg_cost',
      key: 'avg_cost',
      align: 'right' as const,
      render: (val: number) => `¥${val.toFixed(2)}`,
    },
    {
      title: '市价',
      dataIndex: 'market_price',
      key: 'market_price',
      align: 'right' as const,
      render: (val: number) => `¥${val.toFixed(2)}`,
    },
    {
      title: '市值',
      dataIndex: 'market_value',
      key: 'market_value',
      align: 'right' as const,
      render: (val: number) => `¥${(val / 10000).toFixed(2)}万`,
    },
    {
      title: '浮动盈亏',
      dataIndex: 'unrealized_pnl',
      key: 'unrealized_pnl',
      align: 'right' as const,
      render: (val: number, record: Position) => (
        <span style={{ color: val >= 0 ? '#ff0040' : '#00ff41' }}>
          {val >= 0 ? '+' : ''}{val.toFixed(2)} ({record.unrealized_pnl_pct >= 0 ? '+' : ''}{record.unrealized_pnl_pct.toFixed(2)}%)
        </span>
      ),
    },
  ];

  // 订单表格列
  const orderColumns = [
    {
      title: '订单ID',
      dataIndex: 'id',
      key: 'id',
      render: (text: string) => <span style={{ fontSize: 12 }}>{text}</span>,
    },
    {
      title: '股票',
      dataIndex: 'symbol',
      key: 'symbol',
    },
    {
      title: '方向',
      dataIndex: 'action',
      key: 'action',
      render: (val: string) => (
        <Tag color={val === 'BUY' ? 'red' : 'green'}>{val === 'BUY' ? '买入' : '卖出'}</Tag>
      ),
    },
    {
      title: '类型',
      dataIndex: 'order_type',
      key: 'order_type',
      render: (val: string) => val === 'LIMIT' ? '限价' : '市价',
    },
    {
      title: '委托价',
      dataIndex: 'price',
      key: 'price',
      align: 'right' as const,
      render: (val?: number) => val ? `¥${val.toFixed(2)}` : '-',
    },
    {
      title: '数量',
      dataIndex: 'quantity',
      key: 'quantity',
      align: 'right' as const,
      render: (val: number, record: Order) => (
        <span>
          {record.filled_quantity}/{val}
        </span>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (val: string) => {
        const statusMap: Record<string, { color: string; text: string }> = {
          PENDING: { color: 'processing', text: '待成交' },
          PARTIAL_FILLED: { color: 'warning', text: '部分成交' },
          FILLED: { color: 'success', text: '已成交' },
          CANCELLED: { color: 'default', text: '已撤销' },
          REJECTED: { color: 'error', text: '已拒绝' },
        };
        const status = statusMap[val] || { color: 'default', text: val };
        return <Badge status={status.color as any} text={status.text} />;
      },
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: Order) => (
        record.status === 'PENDING' || record.status === 'PARTIAL_FILLED' ? (
          <Button type="link" size="small" danger onClick={() => handleCancelOrder(record.id)}>
            撤单
          </Button>
        ) : null
      ),
    },
  ];

  // 成交记录列
  const tradeColumns = [
    {
      title: '时间',
      dataIndex: 'timestamp',
      key: 'timestamp',
      render: (val: string) => new Date(val).toLocaleTimeString(),
    },
    {
      title: '股票',
      dataIndex: 'symbol',
      key: 'symbol',
    },
    {
      title: '方向',
      dataIndex: 'action',
      key: 'action',
      render: (val: string) => (
        <Tag color={val === 'BUY' ? 'red' : 'green'}>{val === 'BUY' ? '买入' : '卖出'}</Tag>
      ),
    },
    {
      title: '成交价',
      dataIndex: 'price',
      key: 'price',
      align: 'right' as const,
      render: (val: number) => `¥${val.toFixed(2)}`,
    },
    {
      title: '数量',
      dataIndex: 'quantity',
      key: 'quantity',
      align: 'right' as const,
    },
    {
      title: '手续费',
      dataIndex: 'total_fee',
      key: 'total_fee',
      align: 'right' as const,
      render: (val: number) => `¥${val.toFixed(2)}`,
    },
  ];

  const isUp = (account?.total_value || 0) >= (account?.initial_capital || 0);
  const pnl = (account?.total_value || 0) - (account?.initial_capital || 0);
  const pnlPct = account?.initial_capital ? (pnl / account.initial_capital) * 100 : 0;

  return (
    <div style={{ fontFamily: "'JetBrains Mono', monospace" }}>
      <h2 style={{ marginBottom: 24, color: '#00ff41' }}>
        <LineChartOutlined /> 模拟交易
      </h2>

      {/* 账户概览 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="总资产"
              value={account?.total_value || 0}
              prefix="¥"
              precision={2}
              valueStyle={{ color: isUp ? '#ff0040' : '#00ff41', fontSize: 24 }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="总盈亏"
              value={pnl}
              prefix={pnl >= 0 ? '+' : ''}
              suffix={`(${pnlPct >= 0 ? '+' : ''}${pnlPct.toFixed(2)}%)`}
              precision={2}
              valueStyle={{ color: pnl >= 0 ? '#ff0040' : '#00ff41' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="可用资金"
              value={account?.cash || 0}
              prefix="¥"
              precision={2}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="持仓市值"
              value={account?.positions_value || 0}
              prefix="¥"
              precision={2}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        {/* 下单面板 */}
        <Col xs={24} lg={8}>
          <Card
            title={<><ShoppingCartOutlined /> 下单</>}
            extra={
              <Space>
                <Button size="small" onClick={handleMatch}>撮合</Button>
                <Button size="small" danger onClick={handleReset}>重置</Button>
              </Space>
            }
          >
            <Form
              form={orderForm}
              layout="vertical"
              onFinish={handleSubmitOrder}
            >
              <Form.Item
                label="股票代码"
                name="symbol"
                rules={[{ required: true, message: '请选择股票' }]}
              >
                <Select
                  placeholder="选择股票"
                  showSearch
                  optionFilterProp="children"
                  onChange={(val) => setSelectedSymbol(val)}
                >
                  {stocks.map((s) => (
                    <Option key={s.symbol} value={s.symbol}>
                      {s.symbol} {s.name}
                    </Option>
                  ))}
                </Select>
              </Form.Item>

              <Form.Item
                label="买卖方向"
                name="action"
                initialValue="BUY"
                rules={[{ required: true }]}
              >
                <Select>
                  <Option value="BUY">买入</Option>
                  <Option value="SELL">卖出</Option>
                </Select>
              </Form.Item>

              <Form.Item
                label="订单类型"
                name="order_type"
                initialValue="LIMIT"
                rules={[{ required: true }]}
              >
                <Select>
                  <Option value="LIMIT">限价单</Option>
                  <Option value="MARKET">市价单</Option>
                </Select>
              </Form.Item>

              <Form.Item
                noStyle
                shouldUpdate={(prev, curr) => prev.order_type !== curr.order_type}
              >
                {({ getFieldValue }) =>
                  getFieldValue('order_type') === 'LIMIT' ? (
                    <Form.Item
                      label="委托价格"
                      name="price"
                      rules={[{ required: true, message: '请输入价格' }]}
                    >
                      <InputNumber
                        style={{ width: '100%' }}
                        min={0.01}
                        step={0.01}
                        prefix="¥"
                      />
                    </Form.Item>
                  ) : null
                }
              </Form.Item>

              <Form.Item
                label="数量"
                name="quantity"
                rules={[
                  { required: true, message: '请输入数量' },
                  { type: 'number', min: 100, message: '最小100股' },
                ]}
                tooltip="必须是100的整数倍"
              >
                <InputNumber
                  style={{ width: '100%' }}
                  min={100}
                  step={100}
                  placeholder="100"
                />
              </Form.Item>

              <Form.Item>
                <Button type="primary" htmlType="submit" block>
                  提交订单
                </Button>
              </Form.Item>
            </Form>
          </Card>
        </Col>

        {/* 持仓和订单 */}
        <Col xs={24} lg={16}>
          <Tabs defaultActiveKey="positions">
            <TabPane
              tab={<><WalletOutlined /> 持仓</>}
              key="positions"
            >
              <Table
                columns={positionColumns}
                dataSource={positions}
                rowKey="symbol"
                size="small"
                pagination={false}
                locale={{ emptyText: <Empty description="暂无持仓" /> }}
              />
            </TabPane>

            <TabPane
              tab={<><HistoryOutlined /> 当前订单</>}
              key="orders"
            >
              <Table
                columns={orderColumns}
                dataSource={orders}
                rowKey="id"
                size="small"
                pagination={{ pageSize: 10 }}
                locale={{ emptyText: <Empty description="暂无订单" /> }}
              />
            </TabPane>

            <TabPane
              tab={<><DollarOutlined /> 成交记录</>}
              key="trades"
            >
              <Table
                columns={tradeColumns}
                dataSource={trades}
                rowKey="id"
                size="small"
                pagination={{ pageSize: 10 }}
                locale={{ emptyText: <Empty description="暂无成交" /> }}
              />
            </TabPane>
          </Tabs>
        </Col>
      </Row>
    </div>
  );
};

export default SimulationTrading;
