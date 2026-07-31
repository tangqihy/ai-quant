import React, { useState, useEffect } from 'react';
import {
  Modal,
  Form,
  Input,
  Space,
  Tag,
  Button,
  message,
  Empty,
  Spin,
} from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { useWatchlist } from '../../hooks/useWatchlist';

interface AddToWatchlistModalProps {
  visible: boolean;
  onCancel: () => void;
  onSuccess?: () => void;
  stockSymbol: string;
  stockName: string;
}

const AddToWatchlistModal: React.FC<AddToWatchlistModalProps> = ({
  visible,
  onCancel,
  onSuccess,
  stockSymbol,
  stockName,
}) => {
  const [form] = Form.useForm();
  const { groups, addStock, createGroup, getStock, isLoaded } = useWatchlist();
  const [selectedGroups, setSelectedGroups] = useState<string[]>([]);
  const [isNewGroupVisible, setIsNewGroupVisible] = useState(false);
  const [newGroupName, setNewGroupName] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [existingStock, setExistingStock] = useState<ReturnType<typeof getStock>>(undefined);

  // 当弹窗打开且数据就绪时，同步已有自选信息
  useEffect(() => {
    if (visible && isLoaded) {
      const stock = getStock(stockSymbol);
      setExistingStock(stock);
      if (stock) {
        setSelectedGroups(stock.groupIds);
        form.setFieldsValue({
          note: stock.note || '',
        });
      } else {
        setSelectedGroups([]);
        form.resetFields();
      }
    }
  }, [visible, isLoaded, stockSymbol, getStock, form]);

  const handleOk = async () => {
    if (!isLoaded) {
      message.warning('自选数据加载中，请稍候再操作');
      return;
    }
    try {
      const values = await form.validateFields();
      setSubmitting(true);
      const ok = await addStock({
        symbol: stockSymbol,
        name: stockName,
        groupIds: selectedGroups,
        note: values.note,
      });
      if (!ok) return;

      message.success(existingStock ? '已更新自选信息' : '成功添加到自选');
      onSuccess?.();
      onCancel();
    } catch (e) {
      console.error(e);
    } finally {
      setSubmitting(false);
    }
  };

  const handleCreateGroup = async () => {
    if (!isLoaded) {
      message.warning('自选数据加载中，请稍候再操作');
      return;
    }
    if (!newGroupName.trim()) {
      message.warning('请输入分组名称');
      return;
    }
    const newGroup = await createGroup({ name: newGroupName.trim() });
    if (newGroup) {
      setSelectedGroups(prev => [...prev, newGroup.id]);
      setNewGroupName('');
      setIsNewGroupVisible(false);
      message.success('分组创建成功');
    }
  };

  const toggleGroup = (groupId: string) => {
    setSelectedGroups(prev =>
      prev.includes(groupId)
        ? prev.filter(id => id !== groupId)
        : [...prev, groupId]
    );
  };

  return (
    <Modal
      title={existingStock ? '管理自选' : '添加到自选'}
      open={visible}
      onOk={handleOk}
      onCancel={onCancel}
      okText={existingStock ? '更新' : '添加'}
      okButtonProps={{ disabled: !isLoaded, loading: submitting }}
      width={480}
    >
      <div style={{ marginBottom: 16 }}>
        <span style={{ color: 'rgba(var(--accent-rgb), 0.6)' }}>股票：</span>
        <Tag color="green">{stockSymbol}</Tag>
        <span>{stockName}</span>
      </div>

      {!isLoaded ? (
        <div style={{ textAlign: 'center', padding: 32 }}>
          <Spin description="自选数据加载中..." />
        </div>
      ) : (
      <Form form={form} layout="vertical">
        <Form.Item label="选择分组（可选）">
          {groups.length === 0 ? (
            <Empty description="暂无分组，请先创建" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          ) : (
            <Space wrap size={[8, 8]}>
              {groups.map(group => (
                <Tag
                  key={group.id}
                  color={selectedGroups.includes(group.id) ? group.color : undefined}
                  style={{
                    cursor: 'pointer',
                    borderColor: group.color,
                    backgroundColor: selectedGroups.includes(group.id) ? undefined : 'transparent',
                    opacity: selectedGroups.includes(group.id) ? 1 : 0.6,
                  }}
                  onClick={() => toggleGroup(group.id)}
                >
                  {selectedGroups.includes(group.id) && '✓ '}
                  {group.name}
                </Tag>
              ))}
            </Space>
          )}
        </Form.Item>

        {!isNewGroupVisible ? (
          <Button
            type="dashed"
            size="small"
            icon={<PlusOutlined />}
            onClick={() => setIsNewGroupVisible(true)}
            style={{ marginBottom: 16 }}
          >
            新建分组
          </Button>
        ) : (
          <Space style={{ marginBottom: 16 }}>
            <Input
              placeholder="分组名称"
              value={newGroupName}
              onChange={e => setNewGroupName(e.target.value)}
              onPressEnter={handleCreateGroup}
              autoFocus
              style={{ width: 150 }}
            />
            <Button type="primary" size="small" onClick={handleCreateGroup}>
              创建
            </Button>
            <Button size="small" onClick={() => setIsNewGroupVisible(false)}>
              取消
            </Button>
          </Space>
        )}

        <Form.Item label="备注" name="note">
          <Input.TextArea
            placeholder="添加备注（可选）"
            rows={2}
            maxLength={100}
            showCount
          />
        </Form.Item>
      </Form>
      )}
    </Modal>
  );
};

export default AddToWatchlistModal;
