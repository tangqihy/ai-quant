import React, { useState, useEffect } from 'react';
import { getStockHistory } from '../services/api';

export interface SparklinePoint {
  date: string;
  close: number;
}

interface SparklineProps {
  symbol: string;
  /** 最近 N 个交易日（默认 5） */
  days?: number;
  width?: number;
  height?: number;
  /** 涨用红色，跌用绿色；不传则根据首尾 close 判断 */
  isUp?: boolean;
  className?: string;
}

/** 迷你走势图：最近几日收盘价折线，A 股红涨绿跌 */
const Sparkline: React.FC<SparklineProps> = ({
  symbol,
  days = 5,
  width = 64,
  height = 28,
  isUp,
  className,
}) => {
  const [points, setPoints] = useState<SparklinePoint[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const end = new Date();
    const start = new Date();
    start.setDate(start.getDate() - Math.min(days + 10, 30)); // 多取几天以防非交易日
    const fmt = (d: Date) =>
      `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}`;

    const fetchData = async () => {
      setLoading(true);
      try {
        const res = await getStockHistory(
          symbol,
          fmt(start),
          fmt(end)
        );
        if (cancelled) return;
        if (res?.success && Array.isArray(res.data) && res.data.length > 0) {
          const list = (res.data as { date: string; close: number }[])
            .map((d) => ({ date: d.date, close: Number(d.close) }))
            .filter((d) => !Number.isNaN(d.close))
            .slice(-days);
          setPoints(list);
        } else {
          setPoints([]);
        }
      } catch {
        if (!cancelled) setPoints([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchData();
    return () => { cancelled = true; };
  }, [symbol, days]);

  if (loading || points.length < 2) {
    return (
      <div
        className={className}
        style={{
          width,
          height,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'rgba(255,255,255,0.03)',
          borderRadius: 4,
          color: 'rgba(255,255,255,0.35)',
          fontSize: 10,
        }}
      >
        {loading ? '…' : '-'}
      </div>
    );
  }

  const closes = points.map((p) => p.close);
  const min = Math.min(...closes);
  const max = Math.max(...closes);
  const range = max - min || 1;
  const padding = 2;
  const w = width - padding * 2;
  const h = height - padding * 2;

  const pathD = points
    .map((p, i) => {
      const x = padding + (i / (points.length - 1)) * w;
      const y = padding + h - ((p.close - min) / range) * h;
      return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
    })
    .join(' ');

  const direction = isUp ?? closes[closes.length - 1] >= closes[0];
  const strokeColor = direction ? '#ef232a' : '#00c087'; // A 股红涨绿跌

  return (
    <svg
      width={width}
      height={height}
      className={className}
      style={{ display: 'block', overflow: 'visible' }}
    >
      <path
        d={pathD}
        fill="none"
        stroke={strokeColor}
        strokeWidth="1.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
};

export default Sparkline;
