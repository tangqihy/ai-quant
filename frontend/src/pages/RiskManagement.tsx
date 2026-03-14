import React, { useEffect, useState } from 'react';
import {
  Card,
  Tabs,
  Table,
  Button,
  Switch,
  Input,
  InputNumber,
  Form,
  Modal,
  message,
  Tag,
  Space,
  Empty,
  Badge,
  Tooltip,
  Popconfirm,
} from 'antd';
import {
  SafetyOutlined,
  StopOutlined,
  WarningOutlined,
  BellOutlined,
  DeleteOutlined,
  CheckOutlined,
} from '@ant-design/icons';
import {
  getRiskRules,
  updateRiskRule,
  getBlacklist,
  addToBlacklist,
  removeFromBlacklist,
  getRiskAlerts,
  acknowledgeAlert,
  clearAlerts,
  RiskRule,
  RiskAlert,
  BlacklistItem,
} from '../services/riskApi';

const { TabPane } = Tabs;

const RiskManagement: React.FC = () => {
  const [rules, setRules] = useState<RiskRule[]>([]);
  const [blacklist, setBlacklist] = useState<BlacklistItem[]>([]);
  const [alerts, setAlerts] = useState<RiskAlert[]>([]);
  const [loading, setLoading] = useState(false);
  const [blacklistForm] = Form.useForm();
  const [blacklistModalVisible, setBlacklistModalVisible] = useState(false);

  // 加载数据
  const loadData = async () => {
    setLoading(true);
    try {
      const [rulesRes, blacklistRes, alertsRes] = await Promise.all([
        getRiskRules(),
        getBlacklist(),
        getRiskAlerts(),
      ]);

      if (rulesRes.data?.success) {
        setRules(rulesRes.data.data || []);
      }
      if (blacklistRes.data?.success) {
        setBlacklist(blacklistRes.data.data || []);
      }
      if (alertsRes.data?.success) {
        setAlerts(alertsRes.data.data || []);
      }
    } catch (error) {
      message.error('加载数据失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // 更新规则
  const handleUpdateRule = async (ruleId: string, enabled: boolean) => {
    try {
      await updateRiskRule(ruleId, enabled);
      message.success('规则更新成功');
      loadData();
    } catch (error) {
      message.error('规则更新失败');
    }
  };

  // 添加到黑名单
  const handleAddToBlacklist = async (values: any) => {
    try {
      await addToBlacklist(values);
      message.success('已添加到黑名单');
      setBlacklistModalVisible(false);
      blacklistForm.resetFields();
      loadData();
    } catch (error) {
      message.error('添加失败');
    }
  };

  // 从黑名单移除
  const handleRemoveFromBlacklist = async (symbol: string) => {
    try {
      await removeFromBlacklist(symbol);
      message.success('已从黑名单移除');
      loadData();
    } catch (error) {
      message.error('移除失败');
    }
  };

  // 确认告警
  const handleAcknowledgeAlert = async (alertId: string) => {
    try {
      await acknowledgeAlert(alertId);
      message.success('告警已确认');
      loadData();
    } catch (error) {
      message.error('确认失败');
    }
  };

  // 清空告警
  const handleClearAlerts = async () => {
    try {
      await clearAlerts();
      message.success('告警已清空');
      loadData();
    } catch (error) {
      message.error('清空失败');
    }
  };

  // 规则表格列
  const ruleColumns = [
    {
      title: '规则名称',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '类型',
      dataIndex: 'rule_type',
      key: 'rule_type',
      render: (type: string) => {
        const typeMap: Record<string, string> = {
          POSITION_LIMIT: '仓位限制',
          STOP_LOSS: '止损止盈',
          BLACKLIST: '黑名单',
          TRADE_LIMIT: '交易限制',
        };
        return typeMap[type] || type;
      },
    },
    {
      title: '状态',
      dataIndex: 'enabled',
      key: 'enabled',
      render: (enabled: boolean, record: RiskRule) => (
        <Switch
          checked={enabled}
          onChange={(checked) => handleUpdateRule(record.id, checked)}
        />
      ),
    },
    {
      title: '配置',
      dataIndex: 'params',
      key: 'params',
      render: (params: Record<string, any>) => (
        <div style={{ fontSize: 12 }}>
          {Object.entries(params).map(([key, value]) => (
            <div key={key}>
              {key}: {value}
            </div>
          ))}
        </div>
      ),
    },
  ];

  // 黑名单表格列
  const blacklistColumns = [
    {
      title: '股票代码',
      dataIndex: 'symbol',
      key: 'symbol',
    },
    {
      title: '原因',
      dataIndex: 'reason',
      key: 'reason',
      render: (reason: string) => {
        const reasonMap: Record<string, { color: string; text: string }> = {
          ST: { color: 'orange', text: 'ST股' },
          DELISTING: { color: 'red', text: '退市' },
          SUSPENDED: { color: 'gray', text: '停牌' },
          LIMIT_UP: { color: 'green', text: '涨停' },
          LIMIT_DOWN: { color: 'red', text: '跌停' },
          MANUAL: { color: 'blue', text: '手动' },
        };
        const { color, text } = reasonMap[reason] || { color: 'default', text: reason };
        return <Tag color={color}>{text}</Tag>;
      },
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
    },
    {
      title: '过期时间',
      dataIndex: 'expires_at',
      key: 'expires_at',
      render: (expires: string) => expires ? new Date(expires).toLocaleString() : '永久',
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: BlacklistItem) => (
        <Popconfirm
          title="确认移除"
          description={`确定要从黑名单移除 ${record.symbol} 吗？`}
          onConfirm={() => handleRemoveFromBlacklist(record.symbol)}
        >
          <Button type="link" danger size="small">
            移除
          </Button>
        </Popconfirm>
      ),
    },
  ];

  // 告警表格列
  const alertColumns = [
    {
      title: '时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (time: string) => new Date(time).toLocaleString(),
    },
    {
      title: '级别',
      dataIndex: 'alert_type',
      key: 'alert_type',
      render: (type: string) => {
        const typeMap: Record<string, { color: string; text: string }> = {
          WARNING: { color: 'warning', text: '警告' },
          ERROR: { color: 'error', text: '错误' },
          BLOCK: { color: 'red', text: '阻止' },
        };
        const { color, text } = typeMap[type] || { color: 'default', text: type };
        return <Badge status={color as any} text={text} />;
      },
    },
    {
      title: '规则',
      dataIndex: 'rule_name',
      key: 'rule_name',
    },
    {
      title: '股票',
      dataIndex: 'symbol',
      key: 'symbol',
      render: (symbol: string) => symbol || '-',
    },
    {
      title: '消息',
      dataIndex: 'message',
      key: 'message',
    },
    {
      title: '状态',
      dataIndex: 'acknowledged',
      key: 'acknowledged',
      render: (ack: boolean) => ack ? <Tag color="success">已确认</Tag> : <Tag color="warning">未确认</Tag>,
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: RiskAlert) => (
        !record.acknowledged && (
          <Button
            type="link"
            size="small"
            icon={<CheckOutlined />}
            onClick={() => handleAcknowledgeAlert(record.id)}
          >
            确认
          </Button>
        )
      ),
    },
  ];

  return (
    <div style={{ fontFamily: "'JetBrains Mono', monospace" }}>
      <h2 style={{ marginBottom: 24, color: '#00ff41' }}>
        <SafetyOutlined /> 风控管理
      </h2>

      <Tabs defaultActiveKey="rules">
        <TabPane
          tab={<><SafetyOutlined /> 风控规则</>}
          key="rules"
        >
          <Card>
            <Table
              columns={ruleColumns}
              dataSource={rules}
              rowKey="id"
              loading={loading}
              pagination={false}
              size="small"
            />
          </Card>
        </TabPane>

        <TabPane
          tab={<><StopOutlined /> 黑名单</>}
          key="blacklist"
        >
          <Card
            extra={
              <Button type="primary" onClick={() => setBlacklistModalVisible(true)}>
                添加黑名单
              </Button>
            }
          >
            <Table
              columns={blacklistColumns}
              dataSource={blacklist}
              rowKey="symbol"
              loading={loading}
              pagination={false}
              size="small"
              locale={{ emptyText: <Empty description="暂无黑名单" /> }}
            />
          </Card>
        </TabPane>

        <TabPane
          tab={<><BellOutlined /> 风控告警 {alerts.filter(a => !a.acknowledged).length > 0 && (
            <Badge count={alerts.filter(a => !a.acknowledged).length} />
          )}</>}
          key="alerts"
        >
          <Card
            extra={
              <Button danger onClick={handleClearAlerts} disabled={alerts.length === 0}>
                <DeleteOutlined /> 清空告警
              </Button>
            }
          >
            <Table
              columns={alertColumns}
              dataSource={alerts}
              rowKey="id"
              loading={loading}
              pagination={{ pageSize: 10 }}
              size="small"
              locale={{ emptyText: <Empty description="暂无告警" /> }}
            />
          </Card>
        </TabPane>
      </Tabs>

      {/* 添加黑名单弹窗 */}
      <Modal
        title="添加黑名单"
        open={blacklistModalVisible}
        onCancel={() => setBlacklistModalVisible(false)}
        footer={null}
      >
        <Form
          form={blacklistForm}
          layout="vertical"
          onFinish={handleAddToBlacklist}
        >
          <Form.Item
            label="股票代码"
            name="symbol"
            rules={[{ required: true, message: '请输入股票代码' }]}
          >
            <Input placeholder="如: 000001" />
          </Form.Item>

          <Form.Item
            label="原因"
            name="reason"
            rules={[{ required: true, message: '请选择原因' }]}
          >
            <Input.TextArea placeholder="可选" />
          </Form.Item>

          <Form.Item
            label="过期时间（小时）"
            name="expires_in_hours"
            tooltip="留空表示永久"
          >
            <InputNumber min={1} style={{ width: '100%' }} placeholder="留空表示永久" />
          </Form.Item>

          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">
                添加
              </Button>
              <Button onClick={() => setBlacklistModalVisible(false)}>
                取消
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default RiskManagement;
