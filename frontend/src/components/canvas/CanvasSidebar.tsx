import React, { useMemo, useState } from 'react';
import { Input, List, Tag, Typography, Empty } from 'antd';
import type { CanvasCard, CardType } from '../../services/canvasApi';
import { CARD_TYPE_COLOR, CARD_TYPE_LABEL } from './cardConfig';

const { Text } = Typography;

interface CanvasSidebarProps {
  cards: CanvasCard[];
  onFocusCard?: (cardId: string) => void;
}

const FILTER_ORDER: (CardType | 'all')[] = [
  'all', 'thesis', 'catalyst', 'risk', 'note', 'entry_plan', 'exit_plan', 'trade_record',
];

/** 侧边栏：按类型筛选 + 关键字过滤的卡片列表 */
export const CanvasSidebar: React.FC<CanvasSidebarProps> = ({ cards, onFocusCard }) => {
  const [filter, setFilter] = useState<CardType | 'all'>('all');
  const [keyword, setKeyword] = useState('');

  const filtered = useMemo(() => {
    let list = filter === 'all' ? cards : cards.filter((c) => c.card_type === filter);
    if (keyword.trim()) {
      const kw = keyword.trim().toLowerCase();
      list = list.filter(
        (c) =>
          c.title.toLowerCase().includes(kw) ||
          c.content.toLowerCase().includes(kw) ||
          c.tags.some((t) => t.toLowerCase().includes(kw)),
      );
    }
    return list;
  }, [cards, filter, keyword]);

  const countByType = useMemo(() => {
    const map: Record<string, number> = { all: cards.length };
    cards.forEach((c) => {
      map[c.card_type] = (map[c.card_type] || 0) + 1;
    });
    return map;
  }, [cards]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <div style={{ padding: '8px 8px 4px' }}>
        <Input.Search
          size="small"
          placeholder="筛选卡片..."
          allowClear
          onChange={(e) => setKeyword(e.target.value)}
          style={{ marginBottom: 6 }}
        />
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
          {FILTER_ORDER.map((t) => {
            const count = countByType[t] || 0;
            if (t !== 'all' && count === 0) return null;
            return (
              <Tag
                key={t}
                color={filter === t ? (t === 'all' ? 'processing' : CARD_TYPE_COLOR[t as CardType]) : 'default'}
                style={{ cursor: 'pointer', marginRight: 0, fontSize: 11 }}
                onClick={() => setFilter(t)}
              >
                {t === 'all' ? '全部' : CARD_TYPE_LABEL[t as CardType]} {count}
              </Tag>
            );
          })}
        </div>
      </div>
      <div style={{ flex: 1, overflow: 'auto', padding: '0 8px 8px' }}>
        {filtered.length === 0 ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={<Text style={{ color: 'var(--cyber-text-faint)', fontSize: 12 }}>无匹配卡片</Text>} />
        ) : (
          <List
            size="small"
            dataSource={filtered}
            renderItem={(card) => (
              <List.Item
                style={{ padding: '6px 4px', cursor: 'pointer', borderBottom: '1px solid rgba(var(--accent-rgb),0.08)' }}
                onClick={() => onFocusCard?.(card.id)}
              >
                <div style={{ width: '100%', overflow: 'hidden' }}>
                  <Text
                    style={{
                      color: 'var(--cyber-text)',
                      fontSize: 12,
                      display: 'block',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {card.title}
                  </Text>
                  <Tag color={CARD_TYPE_COLOR[card.card_type]} style={{ fontSize: 10, marginTop: 2 }}>
                    {CARD_TYPE_LABEL[card.card_type]}
                  </Tag>
                </div>
              </List.Item>
            )}
          />
        )}
      </div>
    </div>
  );
};
