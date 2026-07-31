import React from 'react';
import { Tag, Typography } from 'antd';
import type { CanvasCard } from '../../services/canvasApi';
import { CARD_TYPE_COLOR, CARD_TYPE_LABEL, DIRECTION_LABEL } from './cardConfig';

const { Text } = Typography;

interface CardShellProps {
  card: CanvasCard;
}

/** 通用卡片壳：标题 + 类型标签 + 按类型渲染正文 + 底部元信息 */
export const CardShell: React.FC<CardShellProps> = ({ card }) => {
  return (
    <div
      style={{
        width: 300,
        background: '#0a1020',
        border: `1px solid ${borderColorByType(card)}`,
        borderRadius: 8,
        padding: '10px 12px 8px',
        fontSize: 12,
        color: '#ccd6e0',
        boxShadow: '0 2px 10px rgba(0,0,0,0.4)',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
        <Text strong style={{ color: '#e8f4ff', fontSize: 13, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {card.title}
        </Text>
        <Tag color={CARD_TYPE_COLOR[card.card_type]} style={{ marginRight: 0, fontSize: 11 }}>
          {CARD_TYPE_LABEL[card.card_type]}
        </Tag>
      </div>

      <CardBody card={card} />

      {(card.tags.length > 0 || card.importance >= 4) && (
        <div style={{ marginTop: 6, display: 'flex', gap: 4, flexWrap: 'wrap', alignItems: 'center' }}>
          {card.tags.map((t) => (
            <Tag key={t} style={{ fontSize: 10, marginRight: 0 }}>{t}</Tag>
          ))}
          {card.importance >= 4 && (
            <Tag color="red" style={{ fontSize: 10, marginRight: 0, marginLeft: 'auto' }}>
              重要
            </Tag>
          )}
        </div>
      )}
    </div>
  );
};

function borderColorByType(card: CanvasCard): string {
  if (card.card_type === 'risk') return 'rgba(245,34,45,0.6)';
  if (card.card_type === 'thesis') {
    const dir = card.structured_data?.direction as string | undefined;
    if (dir === 'bullish') return 'rgba(245,34,45,0.55)';
    if (dir === 'bearish') return 'rgba(82,196,26,0.55)';
    return 'rgba(0,144,255,0.5)';
  }
  return 'rgba(0,240,255,0.28)';
}

/** 按卡片类型渲染正文 */
const CardBody: React.FC<{ card: CanvasCard }> = ({ card }) => {
  const d = card.structured_data || {};

  switch (card.card_type) {
    case 'thesis': {
      const dir = DIRECTION_LABEL[(d.direction as string) || 'neutral'];
      return (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
            <Tag color={dir.color} style={{ marginRight: 0 }}>{dir.label}</Tag>
            {typeof d.confidence === 'number' && (
              <Text style={{ color: '#8899aa', fontSize: 11 }}>置信度 {(d.confidence * 100).toFixed(0)}%</Text>
            )}
          </div>
          <div style={{ color: '#8899aa', fontSize: 11 }}>
            {d.target_price != null && <span style={{ marginRight: 8 }}>目标价 {String(d.target_price)}</span>}
            {d.stop_loss != null && <span>止损 {String(d.stop_loss)}</span>}
          </div>
          {card.content && <ContentSnippet content={card.content} />}
        </div>
      );
    }
    case 'catalyst':
      return (
        <div>
          {d.event_date != null && (
            <Text style={{ color: '#ffa940', fontSize: 11, display: 'block', marginBottom: 2 }}>
              {String(d.event_date)}
              {d.event_type != null && ` · ${String(d.event_type)}`}
            </Text>
          )}
          {card.content && <ContentSnippet content={card.content} />}
        </div>
      );
    case 'risk':
      return (
        <div>
          {d.severity != null && (
            <Tag color={d.severity === 'high' ? 'red' : d.severity === 'medium' ? 'orange' : 'default'} style={{ marginBottom: 4 }}>
              {d.severity === 'high' ? '高风险' : d.severity === 'medium' ? '中风险' : '低风险'}
            </Tag>
          )}
          {card.content ? <ContentSnippet content={card.content} /> : null}
        </div>
      );
    case 'entry_plan':
    case 'exit_plan':
      return (
        <div style={{ fontSize: 11, color: '#8899aa' }}>
          {d.trigger_price != null && <div>触发价 {String(d.trigger_price)}</div>}
          {d.position_pct != null && <div>仓位 {((d.position_pct as number) * 100).toFixed(0)}%</div>}
          {Array.isArray(d.conditions) && d.conditions.length > 0 && (
            <div style={{ marginTop: 2 }}>{(d.conditions as string[]).join('；')}</div>
          )}
          {d.status != null && <Tag style={{ marginTop: 4 }}>{String(d.status)}</Tag>}
        </div>
      );
    case 'trade_record':
      return (
        <div style={{ fontSize: 11, color: '#8899aa' }}>
          {d.direction != null && (
            <Tag color={d.direction === 'buy' ? 'red' : 'green'}>
              {d.direction === 'buy' ? '买入' : '卖出'}
            </Tag>
          )}
          {d.price != null && <span style={{ marginLeft: 4 }}>{String(d.price)}</span>}
          {d.shares != null && <span style={{ marginLeft: 4 }}>x{String(d.shares)}</span>}
        </div>
      );
    case 'financial':
      return (
        <div style={{ fontSize: 11, color: '#8899aa', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2 }}>
          {d.period != null && <span>期间 {String(d.period)}</span>}
          {d.pe_ttm != null && <span>PE {String(d.pe_ttm)}</span>}
          {d.pb != null && <span>PB {String(d.pb)}</span>}
          {d.revenue != null && <span>营收 {formatAmount(d.revenue as number)}</span>}
        </div>
      );
    default:
      return card.content ? <ContentSnippet content={card.content} /> : null;
  }
};

const ContentSnippet: React.FC<{ content: string }> = ({ content }) => (
  <div
    style={{
      color: '#9fb3c8',
      fontSize: 11,
      lineHeight: 1.5,
      display: '-webkit-box',
      WebkitLineClamp: 3,
      WebkitBoxOrient: 'vertical',
      overflow: 'hidden',
    }}
  >
    {content}
  </div>
);

function formatAmount(v: number): string {
  if (v >= 1e8) return `${(v / 1e8).toFixed(1)}亿`;
  if (v >= 1e4) return `${(v / 1e4).toFixed(1)}万`;
  return String(v);
}
