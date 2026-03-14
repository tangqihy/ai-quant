import React, { useState, useMemo } from 'react';
import {
  Card,
  Row,
  Col,
  Button,
  Table,
  Tag,
  Space,
  Modal,
  Form,
  Input,
  ColorPicker,
  message,
  Typography,
  Tooltip,
  Popconfirm,
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  StarFilled,
  EyeOutlined,
  FolderAddOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useWatchlist } from '../hooks/useWatchlist';
import { GroupCard } from '../components/watchlist/GroupCard';
import { WatchlistGroup, GROUP_COLORS } from '../types/watchlist';

const { Title, Text } = Typography;

export const WatchlistManager: React.FC = () => {
  const navigate = useNavigate();
  const {
    groups,
    stocks,
    createGroup,
    deleteGroup,
    renameGroup,
    removeStock,
    updateStockGroups,
    getStocksByGroup,
  } = useWatchlist();

  const [selectedGroupId, setSelectedGroupId] = useState<string | 'all'>('all');
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editingGroup, setEditingGroup] = useState<WatchlistGroup | null>(null);
  const [createForm] = Form.useForm();
  const [editForm] = Form.useForm();

  // 根据选择的分组过滤股票
  const displayedStocks = useMemo(() => {
    if (selectedGroupId === 'all') return stocks;
    return getStocksByGroup(selectedGroupId);
  }, [stocks, selectedGroupId, getStocksByGroup]);

  // 处理创建分组
  const handleCreateGroup = async () => {
    try {
      const values = await createForm.validateFields();
      await createGroup({
        name: values.name,
        color: typeof values.color === 'string' ? values.color : values.color?.toHexString(),
      });
      message.success('分组创建成功');
      setIsCreateModalOpen(false);
      createForm.resetFields();
    } catch (e) {
      // validation failed
    }
  };

  // 处理编辑分组
  const handleEditGroup = async () => {
    if (!editingGroup) return;
    try {
      const values = await editForm.validateFields();
      await renameGroup(editingGroup.id, values.name);
      message.success('分组重命名成功');
      setIsEditModalOpen(false);
      setEditingGroup(null);
    } catch (e) {
      // validation failed
    }
  };

  // 打开编辑弹窗
  const openEditModal = (group: WatchlistGroup) => {
    setEditingGroup(group);
    editForm.setFieldsValue({ name: group.name });
    setIsEditModalOpen(true);
  };

  // 表格列定义
  const columns = [
    {
      title: '股票代码',
      dataIndex: 'symbol',
      key: 'symbol',
      width: 100,
      render: (symbol: string) => (
        <Text strong style={{ fontFamily: 'monospace' }}>{symbol}</Text>
      ),
    },
    {
      title: '股票名称',
      dataIndex: 'name',
      key: 'name',
      width: 120,
    },
    {
      title: '所属分组',
      key: 'groups',
      render: (_: any, record: any) => {
        const stockGroups = groups.filter(g => record.groupIds.includes(g.id));
        return (
          <Space size={4} wrap>
            {stockGroups.map(g => (
              <Tag key={g.id} color={g.color} size="small">
                {g.name}
              </Tag>
            ))}
            {record.groupIds.length === 0 && <Text type="secondary">未分组</Text>}
          </Space>
        );
      },
    },
    {
      title: '备注',
      dataIndex: 'note',
      key: 'note',
      ellipsis: true,
      render: (note?: string) => note || '-',
    },
    {
      title: '操作',
      key: 'action',
      width: 150,
      render: (_: any, record: any) => (
        <Space>
          <Tooltip title="查看详情">
            <Button
              type="text"
              icon={<EyeOutlined />}
              onClick={() => navigate(`/stocks/${record.symbol}`)}
            />
          </Tooltip>
          <Tooltip title="调整分组">
            <Button
              type="text"
              icon={<FolderAddOutlined />}
              onClick={() => handleAdjustGroups(record)}
            />
          </Tooltip>
          <Popconfirm
            title="确定移除这只股票？"
            onConfirm={async () => {
              await removeStock(record.symbol);
              message.success('已移除');
            }}
          >
            <Button type="text" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  // 调整股票分组
  const handleAdjustGroups = (stock: any) => {
    Modal.confirm({
      title: `调整 ${stock.name} 的分组`,
      content: (
        <Space direction="vertical" style={{ width: '100%', marginTop: 16 }}>
          {groups.map(group => (
            <label
              key={group.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '8px 12px',
                borderRadius: 6,
                cursor: 'pointer',
                backgroundColor: stock.groupIds.includes(group.id) ? `${group.color}15` : 'transparent',
              }}
            >
              <input
                type="checkbox"
                defaultChecked={stock.groupIds.includes(group.id)}
                onChange={async (e) => {
                  const newGroupIds = e.target.checked
                    ? [...stock.groupIds, group.id]
                    : stock.groupIds.filter((id: string) => id !== group.id);
                  await updateStockGroups(stock.symbol, newGroupIds);
                }}
              />
              <Tag color={group.color}>{group.name}</Tag>
            </label>
          ))}
        </Space>
      ),
      onOk: () => message.success('分组已更新'),
    });
  };

  return (
    <div>
      <div style={{ marginBottom: 24, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Space>
          <StarFilled style={{ fontSize: 24, color: '#00ff41' }} />
          <Title level={3} style={{ margin: 0, color: '#00ff41' }}>我的自选</Title>
        </Space>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setIsCreateModalOpen(true)}
        >
          新建分组
        </Button>
      </div>

      {/* 分组卡片区域 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} lg={8} xl={6}>
          <Card
            hoverable
            onClick={() => setSelectedGroupId('all')}
            style={{
              borderRadius: 4,
              borderColor: selectedGroupId === 'all' ? '#00ff41' : undefined,
              boxShadow: selectedGroupId === 'all' ? '0 0 12px rgba(0, 255, 65, 0.25)' : undefined,
            }}
            bodyStyle={{ padding: 16 }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div
                style={{
                  width: 48,
                  height: 48,
                  borderRadius: 4,
                  backgroundColor: 'rgba(0, 255, 65, 0.12)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <StarFilled style={{ fontSize: 24, color: '#00ff41' }} />
              </div>
              <div>
                <Text strong style={{ fontSize: 16, display: 'block' }}>
                  全部自选
                </Text>
                <Text type="secondary" style={{ fontSize: 13 }}>
                  {stocks.length} 只股票
                </Text>
              </div>
            </div>
          </Card>
        </Col>
        
        {groups.map(group => (
          <Col xs={24} sm={12} lg={8} xl={6} key={group.id}>
            <GroupCard
              group={group}
              stocks={getStocksByGroup(group.id)}
              isActive={selectedGroupId === group.id}
              onClick={() => setSelectedGroupId(group.id)}
              onEdit={() => openEditModal(group)}
              onDelete={() => {
                Modal.confirm({
                  title: '删除分组',
                  content: `确定删除分组 "${group.name}" 吗？其中的股票不会被删除。`,
                  onOk: async () => {
                    await deleteGroup(group.id);
                    if (selectedGroupId === group.id) {
                      setSelectedGroupId('all');
                    }
                    message.success('分组已删除');
                  },
                });
              }}
            />
          </Col>
        ))}
      </Row>

      {/* 股票列表 */}
      <Card
        title={
          <Space>
            <span>{selectedGroupId === 'all' ? '全部自选股票' : groups.find(g => g.id === selectedGroupId)?.name}</span>
            <Tag>{displayedStocks.length} 只</Tag>
          </Space>
        }
      >
        <Table
          columns={columns}
          dataSource={displayedStocks.map(s => ({ ...s, key: s.symbol }))}
          pagination={{ pageSize: 10 }}
          size="small"
          locale={{ emptyText: '暂无自选股票，请使用顶部搜索添加' }}
        />
      </Card>

      {/* 创建分组弹窗 */}
      <Modal
        title="新建分组"
        open={isCreateModalOpen}
        onOk={handleCreateGroup}
        onCancel={() => {
          setIsCreateModalOpen(false);
          createForm.resetFields();
        }}
      >
        <Form form={createForm} layout="vertical">
          <Form.Item
            name="name"
            label="分组名称"
            rules={[{ required: true, message: '请输入分组名称' }]}
          >
            <Input placeholder="例如：科技股" maxLength={20} showCount />
          </Form.Item>
          <Form.Item
            name="color"
            label="分组颜色"
            initialValue={GROUP_COLORS[groups.length % GROUP_COLORS.length]}
          >
            <ColorPicker presets={[{ label: '推荐', colors: GROUP_COLORS }]} />
          </Form.Item>
        </Form>
      </Modal>

      {/* 编辑分组弹窗 */}
      <Modal
        title="重命名分组"
        open={isEditModalOpen}
        onOk={handleEditGroup}
        onCancel={() => {
          setIsEditModalOpen(false);
          setEditingGroup(null);
        }}
      >
        <Form form={editForm} layout="vertical">
          <Form.Item
            name="name"
            label="分组名称"
            rules={[{ required: true, message: '请输入分组名称' }]}
          >
            <Input placeholder="例如：科技股" maxLength={20} showCount />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default WatchlistManager;
