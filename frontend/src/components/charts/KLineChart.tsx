import React, { useState, useEffect, useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import { getStockHistory, getIndicators } from '../../services/api';
import { cssVar } from '../../utils/chartTheme';

/** 单条 K 线（可能带指标字段） */
interface KLineData {
  date: string;
  open: number;
  close: number;
  high: number;
  low: number;
  volume: number;
  ma5?: number | null;
  ma10?: number | null;
  ma20?: number | null;
  boll_upper?: number | null;
  boll_mid?: number | null;
  boll_lower?: number | null;
  rsi?: number | null;
  dif?: number | null;
  dea?: number | null;
  macd?: number | null;
  support?: number | null;
  resistance?: number | null;
  grxy01?: number | null;
  strength?: number | null;
  buy_signal?: number | null;
  resist_cross?: number | null;
  trend?: number | null;
  prepare_cash?: number | null;
  buy_stock?: number | null;
  sell_edge?: number | null;
  [key: string]: number | string | null | undefined;
}

export type OverlayIndicator = 'ma' | 'boll' | 'rsi' | 'macd' | 'fenshi_t0' | 'capital_trend';

export type ChartSignalMark = {
  date: string;
  action: 'BUY' | 'SELL' | string;
  price?: number | null;
};

interface KLineChartProps {
  symbol?: string;
  data?: KLineData[];
  height?: number;
  startDate?: string;
  endDate?: string;
  /** K线周期: daily / 1min / 5min / 15min / 30min / 60min */
  period?: string;
  /** 叠加指标；不传则默认 MA5/10/20 */
  overlays?: OverlayIndicator[];
  /** 回放游标：当前 as_of 日期，画竖线 */
  cursorDate?: string | null;
  /** 策略买卖点标注 */
  signalMarks?: ChartSignalMark[];
  /** 数据缩放默认贴右（回放步进用） */
  zoomToEnd?: boolean;
}

function calcMA(data: number[], period: number): (number | null)[] {
  const result: (number | null)[] = [];
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) {
      result.push(null);
    } else {
      let sum = 0;
      for (let j = 0; j < period; j++) sum += data[i - j];
      result.push(+(sum / period).toFixed(2));
    }
  }
  return result;
}

function getOverlaySeries(
  rows: KLineData[],
  keys: { key: string; name: string }[]
): { name: string; data: (number | null)[] }[] {
  return keys.map(({ key, name }) => ({
    name,
    data: rows.map((r) => (r[key] != null ? Number(r[key]) : null)),
  }));
}

function buildMarkPoints(
  rows: KLineData[],
  flagKey: string,
  name: string,
  color: string,
  yKey: 'close' | 'support' | 'resistance' = 'close'
): { name: string; coord: [string, number]; value: string; itemStyle: { color: string } }[] {
  const points: { name: string; coord: [string, number]; value: string; itemStyle: { color: string } }[] = [];
  rows.forEach((r) => {
    if (Number(r[flagKey]) === 1) {
      const y = Number(r[yKey] ?? r.close);
      if (!Number.isFinite(y)) return;
      points.push({
        name,
        coord: [r.date, y],
        value: name,
        itemStyle: { color },
      });
    }
  });
  return points;
}

// cssVar 统一从工具引入：canvas 不认 CSS 变量，需渲染时取值

const SERIES_COLORS = {
  MA5: '#e8590c',
  MA20: '#7048a8',
  支撑: '#5F8F5F',
  阻力: '#C9B458',
  强弱: '#8a8578',
  快线: '#aa6666',
  趋势线: '#eab308',
};

/** 主色/涨跌色随主题解析，需在渲染期调用 */
const getLineColors = (): Record<string, string> => ({
  ...SERIES_COLORS,
  MA10: cssVar('--accent', '#2f5d8a'),
  布林上轨: cssVar('--up', '#c0392b'),
  布林中轨: cssVar('--accent', '#2f5d8a'),
  布林下轨: cssVar('--down', '#2f9e44'),
});

const KLineChart: React.FC<KLineChartProps> = ({
  symbol = '600519',
  data: propData,
  height = 400,
  startDate,
  endDate,
  period = 'daily',
  overlays,
  cursorDate,
  signalMarks,
  zoomToEnd = false,
}) => {
  const [dates, setDates] = useState<string[]>([]);
  const [ohlcData, setOhlcData] = useState<number[][]>([]);
  const [volumes, setVolumes] = useState<number[]>([]);
  const [indicatorRows, setIndicatorRows] = useState<KLineData[] | null>(null);
  const [loading, setLoading] = useState(false);

  const overlayKey = overlays?.join(',') ?? '';

  useEffect(() => {
    if (propData && propData.length > 0) {
      const d: string[] = [];
      const ohlc: number[][] = [];
      const vol: number[] = [];
      propData.forEach((item: KLineData) => {
        d.push(item.date);
        ohlc.push([item.open, item.close, item.low, item.high]);
        vol.push(item.volume);
      });
      setDates(d);
      setOhlcData(ohlc);
      setVolumes(vol);
      setIndicatorRows(propData);
      return;
    }

    let cancelled = false;
    const fetch = async () => {
      setLoading(true);
      try {
        if (overlays && overlays.length > 0) {
          const res = await getIndicators(symbol, overlays.join(','), startDate, endDate, period);
          if (cancelled) return;
          const rows: KLineData[] = res?.data?.klines ?? (Array.isArray(res?.data) ? res.data : []);
          if (res.success && rows.length > 0) {
            const d: string[] = [];
            const ohlc: number[][] = [];
            const vol: number[] = [];
            rows.forEach((item: KLineData) => {
              d.push(item.date);
              ohlc.push([item.open, item.close, item.low, item.high]);
              vol.push(item.volume);
            });
            setDates(d);
            setOhlcData(ohlc);
            setVolumes(vol);
            setIndicatorRows(rows);
          } else {
            setDates([]); setOhlcData([]); setVolumes([]); setIndicatorRows(null);
          }
        } else {
          const res = await getStockHistory(symbol, startDate, endDate, 'qfq', period);
          if (cancelled) return;
          const rows: KLineData[] = res?.data?.klines ?? (Array.isArray(res?.data) ? res.data : []);
          if (res.success && rows.length > 0) {
            const d: string[] = [];
            const ohlc: number[][] = [];
            const vol: number[] = [];
            rows.forEach((item: KLineData) => {
              d.push(item.date);
              ohlc.push([item.open, item.close, item.low, item.high]);
              vol.push(item.volume);
            });
            setDates(d);
            setOhlcData(ohlc);
            setVolumes(vol);
            setIndicatorRows(null);
          } else {
            setDates([]); setOhlcData([]); setVolumes([]); setIndicatorRows(null);
          }
        }
      } catch {
        if (!cancelled) {
          setDates([]); setOhlcData([]); setVolumes([]); setIndicatorRows(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetch();
    return () => { cancelled = true; };
  }, [symbol, propData, overlayKey, startDate, endDate, period]);

  const closeData = ohlcData.map((d) => d[1]);
  const hasCapitalTrend = overlays?.includes('capital_trend');
  const hasFenshi = overlays?.includes('fenshi_t0');

  const { overlayLineSeries, trendSeries, legendNames, markPoints } = useMemo(() => {
    const lines: { name: string; data: (number | null)[]; yAxisIndex?: number }[] = [];
    const legends: string[] = ['K线'];
    let trend: { name: string; data: (number | null)[] } | null = null;
    const marks: { name: string; coord: [string, number]; value: string; itemStyle: { color: string } }[] = [];

    if (indicatorRows && indicatorRows.length > 0) {
      if (overlays?.includes('ma') || (!overlays && indicatorRows[0].ma5 != null)) {
        const maSeries = getOverlaySeries(indicatorRows, [
          { key: 'ma5', name: 'MA5' },
          { key: 'ma10', name: 'MA10' },
          { key: 'ma20', name: 'MA20' },
        ]);
        lines.push(...maSeries);
        legends.push('MA5', 'MA10', 'MA20');
      }
      if (overlays?.includes('boll') && indicatorRows[0].boll_upper != null) {
        const bollSeries = getOverlaySeries(indicatorRows, [
          { key: 'boll_upper', name: '布林上轨' },
          { key: 'boll_mid', name: '布林中轨' },
          { key: 'boll_lower', name: '布林下轨' },
        ]);
        lines.push(...bollSeries);
        legends.push('布林上轨', '布林中轨', '布林下轨');
      }
      if (overlays?.includes('rsi') && indicatorRows[0].rsi != null) {
        lines.push(...getOverlaySeries(indicatorRows, [{ key: 'rsi', name: 'RSI' }]));
        legends.push('RSI');
      }
      if (overlays?.includes('macd') && indicatorRows[0].dif != null) {
        lines.push(
          ...getOverlaySeries(indicatorRows, [
            { key: 'dif', name: 'DIF' },
            { key: 'dea', name: 'DEA' },
            { key: 'macd', name: 'MACD' },
          ])
        );
        legends.push('DIF', 'DEA', 'MACD');
      }
      if (hasFenshi && indicatorRows[0].support != null) {
        lines.push(
          ...getOverlaySeries(indicatorRows, [
            { key: 'support', name: '支撑' },
            { key: 'resistance', name: '阻力' },
            { key: 'strength', name: '强弱' },
            { key: 'grxy01', name: '快线' },
          ])
        );
        legends.push('支撑', '阻力', '强弱', '快线');
        marks.push(
          ...buildMarkPoints(indicatorRows, 'buy_signal', '★B', '#C9B458', 'support'),
          ...buildMarkPoints(indicatorRows, 'resist_cross', '★', '#B35C5C', 'close')
        );
      }
      if (hasCapitalTrend && indicatorRows[0].trend != null) {
        trend = {
          name: '趋势线',
          data: indicatorRows.map((r) => (r.trend != null ? Number(r.trend) : null)),
        };
        legends.push('趋势线');
        marks.push(
          ...buildMarkPoints(indicatorRows, 'prepare_cash', '准备', '#CC9900', 'close'),
          ...buildMarkPoints(indicatorRows, 'buy_stock', '买入', '#0099FF', 'close'),
          ...buildMarkPoints(indicatorRows, 'sell_edge', '卖临界', '#FFFF00', 'close')
        );
      }
    }

    if (lines.length === 0 && !trend && closeData.length > 0 && !overlays?.length) {
      legends.push('MA5', 'MA10', 'MA20');
      lines.push(
        { name: 'MA5', data: calcMA(closeData, 5) },
        { name: 'MA10', data: calcMA(closeData, 10) },
        { name: 'MA20', data: calcMA(closeData, 20) }
      );
    }

    return { overlayLineSeries: lines, trendSeries: trend, legendNames: legends, markPoints: marks };
  }, [indicatorRows, overlays, hasFenshi, hasCapitalTrend, closeData]);

  const NEON_UP = cssVar('--up', '#c0392b');
  const NEON_DOWN = cssVar('--down', '#2f9e44');
  const NEON_AXIS = cssVar('--ink-faint', '#a39a89');
  const NEON_GRID = cssVar('--line', '#ddd5c3');
  const ACCENT = cssVar('--accent', '#2f5d8a');
  const ACCENT_RGB = cssVar('--accent-rgb', '47, 93, 138');
  const LINE_COLORS = getLineColors();

  const isMinute = period && period !== 'daily';
  const defaultEnd = 100;
  // 回放步进：默认显示最近约 60 根，贴右侧
  const defaultStart = zoomToEnd
    ? dates.length <= 60
      ? 0
      : Math.round((1 - 60 / dates.length) * 100)
    : isMinute
      ? 60
      : 0;
  const chartHeight = hasCapitalTrend ? Math.max(height, 480) : height;

  const signalMarkPoints = useMemo(() => {
    if (!signalMarks?.length || !dates.length) return [];
    const closeByDate = new Map(dates.map((d, i) => [d, ohlcData[i]?.[1]]));
    return signalMarks
      .filter((m) => m.action === 'BUY' || m.action === 'SELL')
      .map((m) => {
        const y = Number(m.price ?? closeByDate.get(m.date));
        if (!Number.isFinite(y)) return null;
        return {
          name: m.action === 'BUY' ? '买' : '卖',
          coord: [m.date, y] as [string, number],
          value: m.action === 'BUY' ? '买' : '卖',
          itemStyle: {
            color: m.action === 'BUY' ? cssVar('--up', '#c0392b') : cssVar('--down', '#2f9e44'),
          },
        };
      })
      .filter(Boolean) as {
      name: string;
      coord: [string, number];
      value: string;
      itemStyle: { color: string };
    }[];
  }, [signalMarks, dates, ohlcData]);

  const allMarkPoints = [...markPoints, ...signalMarkPoints];
  const cursorMarkLine =
    cursorDate && dates.includes(cursorDate)
      ? {
          symbol: 'none',
          label: {
            show: true,
            formatter: '当前',
            color: ACCENT,
            fontSize: 11,
          },
          lineStyle: { color: ACCENT, width: 1.5, type: 'dashed' },
          data: [{ xAxis: cursorDate }],
        }
      : undefined;

  const axisLabelFormatter = (val: string) => {
    if (!val) return '';
    if (isMinute) {
      const m = val.match(/^(\d{4})-(\d{2})-(\d{2}) (\d{2}:\d{2})/);
      return m ? `${m[2]}-${m[3]} ${m[4]}` : val.slice(5, 16);
    }
    return val.length >= 10 ? val.slice(5, 10) : val;
  };

  const priceGridHeight = hasCapitalTrend ? '42%' : '55%';
  const volTop = hasCapitalTrend ? '58%' : '72%';
  const trendTop = '78%';

  const series: any[] = [
    {
      name: 'K线',
      type: 'candlestick',
      data: ohlcData,
      itemStyle: {
        color: NEON_UP,
        color0: NEON_DOWN,
        borderColor: NEON_UP,
        borderColor0: NEON_DOWN,
      },
      markPoint:
        allMarkPoints.length > 0
          ? {
              symbol: 'pin',
              symbolSize: 36,
              label: { color: '#ffffff', fontSize: 10, fontWeight: 700 },
              data: allMarkPoints,
            }
          : undefined,
      markLine: cursorMarkLine,
    },
    ...overlayLineSeries.map((s) => ({
      name: s.name,
      type: 'line',
      data: s.data,
      smooth: true,
      lineStyle: { color: LINE_COLORS[s.name] || NEON_DOWN, opacity: 0.85, width: 1.5 },
      symbol: 'none',
    })),
    {
      name: 'Volume',
      type: 'bar',
      xAxisIndex: 1,
      yAxisIndex: 1,
      data: volumes,
      itemStyle: { color: `rgba(${ACCENT_RGB}, 0.35)` },
    },
  ];

  if (trendSeries) {
    series.push({
      name: trendSeries.name,
      type: 'line',
      xAxisIndex: 2,
      yAxisIndex: 2,
      data: trendSeries.data,
      smooth: true,
      lineStyle: { color: LINE_COLORS['趋势线'], width: 1.5 },
      symbol: 'none',
      areaStyle: { color: 'rgba(255, 204, 0, 0.08)' },
      markLine: {
        symbol: 'none',
        lineStyle: { type: 'dashed', color: NEON_AXIS },
        data: [{ yAxis: 13 }, { yAxis: 90 }],
      },
    });
  }

  const xAxes: any[] = [
    {
      type: 'category',
      data: dates,
      boundaryGap: false,
      axisLine: { lineStyle: { color: NEON_AXIS } },
      axisLabel: { color: NEON_AXIS, formatter: axisLabelFormatter },
      splitLine: { show: false },
      min: 'dataMin',
      max: 'dataMax',
    },
    {
      type: 'category',
      gridIndex: 1,
      data: dates,
      boundaryGap: false,
      axisLine: { onZero: false },
      axisTick: { show: false },
      axisLabel: { show: false },
      splitLine: { show: false },
      min: 'dataMin',
      max: 'dataMax',
    },
  ];

  const yAxes: any[] = [
    {
      scale: true,
      splitArea: { show: true, areaStyle: { color: [cssVar('--paper-elevated', '#faf7ee'), 'transparent'] } },
      axisLine: { show: true, lineStyle: { color: NEON_AXIS } },
      axisLabel: { color: NEON_AXIS },
      splitLine: { lineStyle: { color: NEON_GRID } },
    },
    {
      scale: true,
      gridIndex: 1,
      splitNumber: 2,
      axisLabel: { show: false },
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { show: false },
    },
  ];

  const grids: any[] = [
    { left: '10%', right: '10%', height: priceGridHeight },
    { left: '10%', right: '10%', top: volTop, height: hasCapitalTrend ? '12%' : '15%' },
  ];

  const zoomAxes = [0, 1];

  if (hasCapitalTrend) {
    grids.push({ left: '10%', right: '10%', top: trendTop, height: '12%' });
    xAxes.push({
      type: 'category',
      gridIndex: 2,
      data: dates,
      boundaryGap: false,
      axisLabel: { show: false },
      axisTick: { show: false },
      splitLine: { show: false },
      min: 'dataMin',
      max: 'dataMax',
    });
    yAxes.push({
      scale: true,
      gridIndex: 2,
      min: 0,
      max: 100,
      splitNumber: 2,
      axisLabel: { color: NEON_AXIS, fontSize: 10 },
      axisLine: { show: false },
      splitLine: { lineStyle: { color: NEON_GRID } },
    });
    zoomAxes.push(2);
  }

  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: cssVar('--paper-card', '#fffdf5'),
      borderColor: cssVar('--line-strong', '#b5ab94'),
      textStyle: { color: cssVar('--ink', '#2d2a26') },
    },
    legend: {
      data: legendNames,
      bottom: 0,
      textStyle: { color: NEON_AXIS },
    },
    grid: grids,
    xAxis: xAxes,
    yAxis: yAxes,
    dataZoom: [
      { type: 'inside', xAxisIndex: zoomAxes, start: defaultStart, end: defaultEnd },
      {
        show: true,
        xAxisIndex: zoomAxes,
        type: 'slider',
        bottom: 50,
        start: defaultStart,
        end: defaultEnd,
        borderColor: NEON_AXIS,
        fillerColor: `rgba(${ACCENT_RGB}, 0.15)`,
        handleStyle: { color: ACCENT },
        textStyle: { color: NEON_AXIS },
        labelFormatter: (val: string) => {
          if (!val) return '';
          const s = dates[val as unknown as number] || val;
          if (isMinute) return s ? s.slice(11, 16) : '';
          return s ? s.slice(5, 10) : '';
        },
      },
    ],
    series,
  };

  if (loading && !propData) {
    return <div style={{ textAlign: 'center', padding: 40 }}>加载中...</div>;
  }

  if (!propData && !loading && dates.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: 40, color: 'var(--ink-faint)' }}>
        暂无 K 线数据
      </div>
    );
  }

  return <ReactECharts option={option} style={{ height: chartHeight, width: '100%' }} notMerge />;
};

export default KLineChart;
