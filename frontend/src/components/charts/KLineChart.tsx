import React, { useState, useEffect } from 'react';
import ReactECharts from 'echarts-for-react';
import { getStockHistory, getIndicators } from '../../services/api';

/** 单条 K 线（可能带指标字段） */
interface KLineData {
  date: string;
  open: number;
  close: number;
  high: number;
  low: number;
  volume: number;
  /** 叠加指标字段（由后端 /indicators 返回） */
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
  [key: string]: number | string | null | undefined;
}

export type OverlayIndicator = 'ma' | 'boll' | 'rsi' | 'macd';

interface KLineChartProps {
  symbol?: string;
  data?: KLineData[];
  height?: number;
  /** 要在 K 线上叠加的指标，如 ['ma', 'boll']；不传则使用 data 或历史接口并默认画 MA5/10/20 */
  overlays?: OverlayIndicator[];
}

/** 客户端计算 MA（无 overlays 或仅用 history 数据时兼容使用） */
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

/** 从数据行中提取指标序列，用于 ECharts series */
function getOverlaySeries(
  rows: KLineData[],
  keys: { key: string; name: string }[]
): { name: string; data: (number | null)[] }[] {
  return keys.map(({ key, name }) => ({
    name,
    data: rows.map((r) => (r[key] != null ? Number(r[key]) : null)),
  }));
}

const KLineChart: React.FC<KLineChartProps> = ({
  symbol = '600519',
  data: propData,
  height = 400,
  overlays,
}) => {
  const [dates, setDates] = useState<string[]>([]);
  const [ohlcData, setOhlcData] = useState<number[][]>([]);
  const [volumes, setVolumes] = useState<number[]>([]);
  const [indicatorRows, setIndicatorRows] = useState<KLineData[] | null>(null);
  const [loading, setLoading] = useState(false);

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

    const fetch = async () => {
      setLoading(true);
      try {
        if (overlays && overlays.length > 0) {
          const res = await getIndicators(symbol, overlays.join(','));
          if (res.success && res.data?.length > 0) {
            const d: string[] = [];
            const ohlc: number[][] = [];
            const vol: number[] = [];
            res.data.forEach((item: KLineData) => {
              d.push(item.date);
              ohlc.push([item.open, item.close, item.low, item.high]);
              vol.push(item.volume);
            });
            setDates(d);
            setOhlcData(ohlc);
            setVolumes(vol);
            setIndicatorRows(res.data);
          }
        } else {
          const res = await getStockHistory(symbol);
          if (res.success && res.data?.length > 0) {
            const d: string[] = [];
            const ohlc: number[][] = [];
            const vol: number[] = [];
            res.data.forEach((item: KLineData) => {
              d.push(item.date);
              ohlc.push([item.open, item.close, item.low, item.high]);
              vol.push(item.volume);
            });
            setDates(d);
            setOhlcData(ohlc);
            setVolumes(vol);
            setIndicatorRows(null);
          }
        }
      } catch {
        // 静默失败
      } finally {
        setLoading(false);
      }
    };
    fetch();
  }, [symbol, propData, overlays?.join(',')]);

  const closeData = ohlcData.map((d) => d[1]);

  // 叠加线：优先用后端返回的指标数据，否则用客户端 MA
  const overlayLineSeries: { name: string; data: (number | null)[] }[] = [];
  const legendNames: string[] = ['K线'];

  if (indicatorRows && indicatorRows.length > 0) {
    if (overlays?.includes('ma') || (!overlays && indicatorRows[0].ma5 != null)) {
      const maSeries = getOverlaySeries(indicatorRows, [
        { key: 'ma5', name: 'MA5' },
        { key: 'ma10', name: 'MA10' },
        { key: 'ma20', name: 'MA20' },
      ]);
      overlayLineSeries.push(...maSeries);
      legendNames.push('MA5', 'MA10', 'MA20');
    }
    if (overlays?.includes('boll') && indicatorRows[0].boll_upper != null) {
      const bollSeries = getOverlaySeries(indicatorRows, [
        { key: 'boll_upper', name: '布林上轨' },
        { key: 'boll_mid', name: '布林中轨' },
        { key: 'boll_lower', name: '布林下轨' },
      ]);
      overlayLineSeries.push(...bollSeries);
      legendNames.push('布林上轨', '布林中轨', '布林下轨');
    }
    if (overlays?.includes('rsi') && indicatorRows[0].rsi != null) {
      const rsiSeries = getOverlaySeries(indicatorRows, [{ key: 'rsi', name: 'RSI' }]);
      overlayLineSeries.push(...rsiSeries);
      legendNames.push('RSI');
    }
    if (overlays?.includes('macd') && indicatorRows[0].dif != null) {
      const macdSeries = getOverlaySeries(indicatorRows, [
        { key: 'dif', name: 'DIF' },
        { key: 'dea', name: 'DEA' },
        { key: 'macd', name: 'MACD' },
      ]);
      overlayLineSeries.push(...macdSeries);
      legendNames.push('DIF', 'DEA', 'MACD');
    }
  }

  if (overlayLineSeries.length === 0 && closeData.length > 0) {
    legendNames.push('MA5', 'MA10', 'MA20');
    overlayLineSeries.push(
      { name: 'MA5', data: calcMA(closeData, 5) },
      { name: 'MA10', data: calcMA(closeData, 10) },
      { name: 'MA20', data: calcMA(closeData, 20) }
    );
  }

  const NEON_UP = '#ff0040';
  const NEON_DOWN = '#00ff41';
  const NEON_AXIS = 'rgba(0, 255, 65, 0.5)';
  const NEON_GRID = 'rgba(0, 255, 65, 0.08)';

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
    },
    ...overlayLineSeries.map((s) => ({
      name: s.name,
      type: 'line',
      data: s.data,
      smooth: true,
      lineStyle: { color: NEON_DOWN, opacity: 0.7 },
      symbol: 'none',
    })),
    {
      name: 'Volume',
      type: 'bar',
      xAxisIndex: 1,
      yAxisIndex: 1,
      data: volumes,
      itemStyle: { color: 'rgba(0, 255, 65, 0.35)' },
    },
  ];

  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: 'rgba(0, 10, 0, 0.9)',
      borderColor: NEON_DOWN,
      textStyle: { color: NEON_DOWN },
    },
    legend: {
      data: legendNames,
      bottom: 0,
      textStyle: { color: NEON_AXIS },
    },
    grid: [
      { left: '10%', right: '10%', height: '55%' },
      { left: '10%', right: '10%', top: '72%', height: '15%' },
    ],
    xAxis: [
      {
        type: 'category',
        data: dates,
        boundaryGap: false,
        axisLine: { lineStyle: { color: NEON_AXIS } },
        axisLabel: { color: NEON_AXIS },
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
    ],
    yAxis: [
      {
        scale: true,
        splitArea: { show: true, areaStyle: { color: [NEON_GRID, 'transparent'] } },
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
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: 70, end: 100 },
      {
        show: true,
        xAxisIndex: [0, 1],
        type: 'slider',
        bottom: 60,
        start: 70,
        end: 100,
        borderColor: NEON_AXIS,
        fillerColor: 'rgba(0, 255, 65, 0.2)',
        handleStyle: { color: NEON_DOWN },
        textStyle: { color: NEON_AXIS },
      },
    ],
    series,
  };

  if (loading && !propData) {
    return <div style={{ textAlign: 'center', padding: 40 }}>加载中...</div>;
  }

  return <ReactECharts option={option} style={{ height, width: '100%' }} />;
};

export default KLineChart;
