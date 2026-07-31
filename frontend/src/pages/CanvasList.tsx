import React, { useEffect, useState } from 'react';
import {
  Button,
  Card,
  Col,
  Empty,
  Form,
  Input,
  message,
  Modal,
  Popconfirm,
  Row,
  Spin,
  Tag,
  Typography,
} from 'antd';
import { DeleteOutlined, PlusOutlined, RightOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import {
  createCanvas,
  deleteCanvas,
  getCanvasList,
  type Canvas,
} from '../services/canvasApi';
import { CANVAS_STATUS_COLOR, CANVAS_STATUS_LABEL } from '../components/canvas/cardConfig';

const { Title, Text } = Typography;

export const CanvasList: React.FC = () => {
  const navigate = useNavigate();
  const [canvases, setCanvases] = useState<Canvas[]>([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [form] = Form.useForm();

  const load = async () => {
    setLoading(true);
    try {
      const r = await getCanvasList();
      setCanvases(r.data.data || []);
    } catch {
      message.error('加载画布列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleCreate = async () => {
    const values = await form.validateFields();
    try {
      await createCanvas(values.ts_code.trim(), values.name?.trim() || '');
      message.success('画布已创建');
      setCreateOpen(false);
      form.resetFields();
      load();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail || '创建失败');
    }
  };

  const handleDelete = async (tsCode: string) => {
    try {
      await deleteCanvas(tsCode);
      message.success('画布已删除');
      load();
    } catch {
      message.error('删除失败');
    }
  };

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0, color: '#e8f4ff' }}>
          研究画布
        </Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
          新建画布
        </Button>
      </div>

      <Spin spinning={loading}>
        {canvases.length === 0 && !loading ? (
          <Empty
            description={
              <span style={{ color: '#8899aa' }}>
                还没有研究画布。新建一个，或在 IM 里对 Hermes 说"为小米建画布"。
              </span>
            }
          />
        ) : (
          <Row gutter={[16, 16]}>
            {canvases.map((c) => (
              <Col xs={24} sm={12} md={8} key={c.ts_code}>
                <Card
                  hoverable
                  style={{ background: '#0a1020', border: '1px solid rgba(0,240,255,0.18)' }}
                  onClick={() => navigate(`/stock-canvas/${encodeURIComponent(c.ts_code)}`)}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div>
                      <Text strong style={{ color: '#e8f4ff', fontSize: 15 }}>
                        {c.name || c.ts_code}
                      </Text>
                      <div style={{ color: '#556677', fontSize: 12, marginTop: 2 }}>{c.ts_code}</div>
                    </div>
                    <Tag color={CANVAS_STATUS_COLOR[c.status]}>{CANVAS_STATUS_LABEL[c.status]}</Tag>
                  </div>
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      marginTop: 12,
                      color: '#556677',
                      fontSize: 11,
                    }}
                  >
                    <span>更新于 {(c.updated_at || c.created_at || '').slice(0, 10)}</span>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <Popconfirm
                        title="删除画布及其所有卡片？"
                        onConfirm={(e) => {
                          e?.stopPropagation();
                          handleDelete(c.ts_code);
                        }}
                        onCancel={(e) => e?.stopPropagation()}
                      >
                        <DeleteOutlined
                          style={{ color: '#f5222d' }}
                          onClick={(e) => e.stopPropagation()}
                        />
                      </Popconfirm>
                      <RightOutlined />
                    </span>
                  </div>
                </Card>
              </Col>
            ))}
          </Row>
        )}
      </Spin>

      <Modal
        title="新建研究画布"
        open={createOpen}
        onOk={handleCreate}
        onCancel={() => setCreateOpen(false)}
        okText="创建"
        cancelText="取消"
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="ts_code"
            label="股票代码"
            rules={[{ required: true, message: '请输入股票代码' }]}
            extra="如 002624.SZ / 01810.HK"
          >
            <Input placeholder="002624.SZ" />
          </Form.Item>
          <Form.Item name="name" label="股票名称">
            <Input placeholder="完美世界" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default CanvasList;
