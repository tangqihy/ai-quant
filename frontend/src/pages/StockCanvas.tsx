import React, { useCallback, useEffect, useState } from 'react';
import {
  Button,
  message,
  Popover,
  Select,
  Space,
  Spin,
  Tabs,
  Tag,
  Timeline,
  Typography,
} from 'antd';
import { ArrowLeftOutlined, ReloadOutlined } from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';
import {
  getCanvasDetail,
  getDecisions,
  getTimeline,
  updateCanvas,
  type CanvasCard,
  type CanvasDetail,
  type CanvasStatus,
  type TimelineEvent,
} from '../services/canvasApi';
import { CANVAS_STATUS_COLOR, CANVAS_STATUS_LABEL, CARD_TYPE_COLOR, CARD_TYPE_LABEL } from '../components/canvas/cardConfig';
import { CanvasBoard } from '../components/canvas/CanvasBoard';
import { CanvasSidebar } from '../components/canvas/CanvasSidebar';

const { Title, Text } = Typography;

const STATUS_OPTIONS: CanvasStatus[] = ['watching', 'holding', 'sold', 'archived'];

export const StockCanvas: React.FC = () => {
  const { ts_code: tsCode = '' } = useParams<{ ts_code: string }>();
  const navigate = useNavigate();

  const [detail, setDetail] = useState<CanvasDetail | null>(null);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [decisions, setDecisions] = useState<CanvasCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState('board');

  const load = useCallback(async () => {
    if (!tsCode) return;
    setLoading(true);
    try {
      const [d, t, dec] = await Promise.all([
        getCanvasDetail(tsCode),
        getTimeline(tsCode),
        getDecisions(tsCode),
      ]);
      setDetail(d.data.data);
      setTimeline(t.data.data || []);
      setDecisions(dec.data.data || []);
    } catch {
      message.error('加载画布失败');
    } finally {
      setLoading(false);
    }
  }, [tsCode]);

  useEffect(() => {
    load();
  }, [load]);

  const handleStatusChange = async (status: CanvasStatus) => {
    try {
      await updateCanvas(tsCode, { status });
      message.success(`状态已更新为 ${CANVAS_STATUS_LABEL[status]}`);
      load();
    } catch {
      message.error('状态更新失败');
    }
  };

  if (loading && !detail) {
    return (
      <div style={{ height: '60vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!detail) {
    return (
      <div style={{ padding: 24 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/stock-canvas')}>
          返回列表
        </Button>
        <div style={{ color: '#8899aa', marginTop: 16 }}>画布不存在或加载失败</div>
      </div>
    );
  }

  const { canvas, cards, edges } = detail;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 56px - 80px)' }}>
      {/* 顶部栏 */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px 4px 12px',
          flexWrap: 'wrap',
          gap: 8,
        }}
      >
        <Space size={12} wrap>
          <Button icon={<ArrowLeftOutlined />} type="text" onClick={() => navigate('/stock-canvas')} style={{ color: '#8899aa' }} />
          <Title level={4} style={{ margin: 0, color: '#e8f4ff' }}>
            {canvas.name || canvas.ts_code}
          </Title>
          <Text style={{ color: '#556677', fontSize: 12 }}>{canvas.ts_code}</Text>
          <Tag color={CANVAS_STATUS_COLOR[canvas.status]}>{CANVAS_STATUS_LABEL[canvas.status]}</Tag>
          <Select
            size="small"
            value={canvas.status}
            style={{ width: 100 }}
            onChange={handleStatusChange}
            options={STATUS_OPTIONS.map((s) => ({ value: s, label: CANVAS_STATUS_LABEL[s] }))}
          />
        </Space>
        <Space>
          <Text style={{ color: '#556677', fontSize: 11 }}>
            {cards.length} 张卡片 · {edges.length} 条关联 · 更新于 {(canvas.updated_at || canvas.created_at || '').slice(0, 16).replace('T', ' ')}
          </Text>
          <Button size="small" icon={<ReloadOutlined />} onClick={load} loading={loading}>
            刷新
          </Button>
        </Space>
      </div>

      <Tabs
        activeKey={tab}
        onChange={setTab}
        style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}
        items={[
          {
            key: 'board',
            label: '画布',
            children: (
              <div style={{ display: 'flex', height: 'calc(100vh - 56px - 170px)', border: '1px solid rgba(0,240,255,0.12)', borderRadius: 8, overflow: 'hidden' }}>
                <div style={{ width: 220, borderRight: '1px solid rgba(0,240,255,0.12)', background: '#050815', flexShrink: 0 }}>
                  <CanvasSidebar cards={cards} />
                </div>
                <div style={{ flex: 1 }}>
                  <CanvasBoard cards={cards} edges={edges} />
                </div>
              </div>
            ),
          },
          {
            key: 'timeline',
            label: '时间线',
            children: (
              <div style={{ padding: 16, maxWidth: 640, overflow: 'auto', maxHeight: 'calc(100vh - 56px - 190px)' }}>
                {timeline.length === 0 ? (
                  <Text style={{ color: '#556677' }}>暂无时间线事件</Text>
                ) : (
                  <Timeline
                    items={[...timeline].reverse().map((e) => ({
                      key: e.card_id,
                      color: e.card_type === 'catalyst' ? 'orange' : e.card_type === 'trade_record' ? 'gold' : 'blue',
                      children: (
                        <div>
                          <Text style={{ color: '#8899aa', fontSize: 11 }}>{(e.date || '').slice(0, 10)}</Text>
                          <div>
                            <Tag color={CARD_TYPE_COLOR[e.card_type]} style={{ marginRight: 6 }}>
                              {CARD_TYPE_LABEL[e.card_type]}
                            </Tag>
                            <Text style={{ color: '#ccd6e0' }}>{e.title}</Text>
                          </div>
                        </div>
                      ),
                    }))}
                  />
                )}
              </div>
            ),
          },
          {
            key: 'decisions',
            label: `决策清单 (${decisions.length})`,
            children: (
              <div style={{ padding: 16, maxWidth: 720, overflow: 'auto', maxHeight: 'calc(100vh - 56px - 190px)' }}>
                {decisions.length === 0 ? (
                  <Text style={{ color: '#556677' }}>
                    还没有入场/出场计划。在 IM 里对 Hermes 说"小米入场计划：28买20%仓位"。
                  </Text>
                ) : (
                  decisions.map((c) => <DecisionCard key={c.id} card={c} />)
                )}
              </div>
            ),
          },
        ]}
      />
    </div>
  );
};

const DecisionCard: React.FC<{ card: CanvasCard }> = ({ card }) => {
  const d = card.structured_data || {};
  return (
    <div
      style={{
        background: '#0a1020',
        border: '1px solid rgba(0,240,255,0.18)',
        borderRadius: 8,
        padding: '10px 14px',
        marginBottom: 10,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
        <Tag color={CARD_TYPE_COLOR[card.card_type]}>{CARD_TYPE_LABEL[card.card_type]}</Tag>
        <Text strong style={{ color: '#e8f4ff' }}>{card.title}</Text>
        {d.status != null && <Tag>{String(d.status)}</Tag>}
      </div>
      <div style={{ color: '#8899aa', fontSize: 12 }}>
        {d.trigger_price != null && <span style={{ marginRight: 12 }}>触发价 {String(d.trigger_price)}</span>}
        {d.position_pct != null && <span style={{ marginRight: 12 }}>仓位 {((d.position_pct as number) * 100).toFixed(0)}%</span>}
        {d.price != null && <span style={{ marginRight: 12 }}>成交价 {String(d.price)}</span>}
      </div>
      {Array.isArray(d.conditions) && d.conditions.length > 0 && (
        <div style={{ color: '#9fb3c8', fontSize: 12, marginTop: 4 }}>
          条件：{(d.conditions as string[]).join('；')}
        </div>
      )}
      {card.content && (
        <Popover content={card.content} trigger="hover">
          <div
            style={{
              color: '#9fb3c8',
              fontSize: 12,
              marginTop: 4,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              cursor: 'default',
            }}
          >
            {card.content}
          </div>
        </Popover>
      )}
    </div>
  );
};

export default StockCanvas;
