import React, { useCallback, useEffect, useState } from 'react';
import { Button, Empty, Spin, Tooltip } from 'antd';
import { ReloadOutlined, LinkOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import 'dayjs/locale/zh-cn';
import { getNews, NewsItem } from '../services/api';

dayjs.extend(relativeTime);
dayjs.locale('zh-cn');

interface NewsFeedProps {
  limit?: number;
  maxHeight?: number | string;
}

function formatTime(value: string): string {
  if (!value) return '';
  const d = dayjs(value);
  if (!d.isValid()) return value;
  const diffHours = dayjs().diff(d, 'hour');
  if (diffHours < 24) return d.fromNow();
  return d.format('MM-DD HH:mm');
}

const NewsFeed: React.FC<NewsFeedProps> = ({ limit = 20, maxHeight = 420 }) => {
  const [items, setItems] = useState<NewsItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (showLoading = true) => {
    if (showLoading) setLoading(true);
    setError(null);
    try {
      const res = await getNews(limit);
      if (res.success && res.data?.items) {
        setItems(res.data.items);
      } else {
        setItems([]);
        setError(res.message || '暂无新闻');
      }
    } catch (e: any) {
      setItems([]);
      setError(e?.response?.data?.detail || e?.message || '加载失败');
    } finally {
      if (showLoading) setLoading(false);
    }
  }, [limit]);

  useEffect(() => {
    load(true);
    const timer = setInterval(() => load(false), 3 * 60 * 1000);
    return () => clearInterval(timer);
  }, [load]);

  return (
    <div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'flex-end',
          marginBottom: 8,
        }}
      >
        <Button
          type="text"
          size="small"
          icon={<ReloadOutlined />}
          loading={loading}
          onClick={() => load(true)}
          style={{ color: 'rgba(var(--accent-rgb), 0.65)' }}
        >
          刷新
        </Button>
      </div>

      <Spin spinning={loading && items.length === 0}>
        <div
          style={{
            maxHeight,
            overflowY: 'auto',
            paddingRight: 4,
          }}
        >
          {items.length === 0 && !loading ? (
            <Empty
              description={error || '暂无新闻'}
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              style={{ padding: '24px 0' }}
            />
          ) : (
            items.map((item, idx) => {
              const content = (
                <div
                  key={`${item.title}-${idx}`}
                  style={{
                    padding: '10px 8px',
                    marginBottom: 6,
                    borderRadius: 8,
                    border: '1px solid rgba(var(--accent-rgb), 0.12)',
                    background: 'rgba(var(--accent-rgb), 0.03)',
                    cursor: item.url ? 'pointer' : 'default',
                    transition: 'border-color 0.2s',
                  }}
                  onClick={() => {
                    if (item.url) window.open(item.url, '_blank', 'noopener,noreferrer');
                  }}
                  onMouseEnter={(e) => {
                    (e.currentTarget as HTMLDivElement).style.borderColor = 'rgba(var(--accent-rgb), 0.4)';
                  }}
                  onMouseLeave={(e) => {
                    (e.currentTarget as HTMLDivElement).style.borderColor = 'rgba(var(--accent-rgb), 0.12)';
                  }}
                >
                  <div
                    style={{
                      color: 'rgba(var(--accent-rgb), 0.92)',
                      fontSize: 13,
                      fontWeight: 500,
                      lineHeight: 1.45,
                      marginBottom: 4,
                      fontFamily: "'JetBrains Mono', system-ui, sans-serif",
                    }}
                  >
                    {item.url && (
                      <LinkOutlined style={{ marginRight: 6, fontSize: 11, opacity: 0.7 }} />
                    )}
                    {item.title}
                  </div>
                  {item.summary && item.summary !== item.title && (
                    <div
                      style={{
                        color: 'rgba(var(--accent-rgb), 0.5)',
                        fontSize: 11,
                        lineHeight: 1.4,
                        marginBottom: 6,
                        display: '-webkit-box',
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: 'vertical',
                        overflow: 'hidden',
                      }}
                    >
                      {item.summary}
                    </div>
                  )}
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      gap: 8,
                      color: 'rgba(var(--accent-rgb), 0.4)',
                      fontSize: 11,
                      fontFamily: 'var(--mono-font)',
                    }}
                  >
                    <span>{item.source || '财经'}</span>
                    <Tooltip title={item.published_at}>
                      <span>{formatTime(item.published_at)}</span>
                    </Tooltip>
                  </div>
                </div>
              );
              return content;
            })
          )}
        </div>
      </Spin>
    </div>
  );
};

export default NewsFeed;
