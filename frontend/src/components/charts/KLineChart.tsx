import React, { useState, useEffect } from 'react';
import ReactECharts from 'echarts-for-react';
import { getStockHistory } from '../../services/api';

interface KLineData {
  date: string;
  open: number;
  close: number;
  high: number;
  low: number;
  volume: number;
}

interface KLineChartProps {
  symbol?: string;
  data?: KLineData[];
  height?: number;
}

function calcMA(data: number[], period: number) {
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

const KLineChart: React.FC<KLineChartProps> = ({ symbol = '600519', data: propData, height = 400 }) => {
  const [dates, setDates] = useState<string[]>([]);
  const [ohlcData, setOhlcData] = useState<number[][]>([]);
  const [volumes, setVolumes] = useState<number[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // 如果提供了 data prop，直接使用
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
      return;
    }

    // 否则通过 symbol 获取数据
    const fetch = async () => {
      setLoading(true);
      try {
        const res = await getStockHistory(symbol);
        if (res.success && res.data.length > 0) {
          const d: string[] = [];
          const ohlc: number[][] = [];
          const vol: number[] = [];
          res.data.forEach((item: any) => {
            d.push(item.date);
            ohlc.push([item.open, item.close, item.low, item.high]);
            vol.push(item.volume);
          });
          setDates(d);
          setOhlcData(ohlc);
          setVolumes(vol);
        }
      } catch {
        // 静默失败，保持空图
      } finally {
        setLoading(false);
      }
    };
    fetch();
  }, [symbol, propData]);

  const closeData = ohlcData.map((d) => d[1]);
  const ma5 = calcMA(closeData, 5);
  const ma10 = calcMA(closeData, 10);
  const ma20 = calcMA(closeData, 20);

  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
    },
    legend: {
      data: ['K线', 'MA5', 'MA10', 'MA20'],
      bottom: 0,
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
        axisLine: { onZero: false },
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
      { scale: true, splitArea: { show: true } },
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
      { show: true, xAxisIndex: [0, 1], type: 'slider', bottom: 60, start: 70, end: 100 },
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: ohlcData,
        itemStyle: {
          color: '#ef232a',
          color0: '#14c143',
          borderColor: '#ef232a',
          borderColor0: '#14c143',
        },
      },
      { name: 'MA5', type: 'line', data: ma5, smooth: true, lineStyle: { opacity: 0.5 }, symbol: 'none' },
      { name: 'MA10', type: 'line', data: ma10, smooth: true, lineStyle: { opacity: 0.5 }, symbol: 'none' },
      { name: 'MA20', type: 'line', data: ma20, smooth: true, lineStyle: { opacity: 0.5 }, symbol: 'none' },
      {
        name: 'Volume',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: volumes,
        itemStyle: { color: '#7f8c8d' },
      },
    ],
  };

  if (loading && !propData) {
    return <div style={{ textAlign: 'center', padding: 40 }}>加载中...</div>;
  }

  return <ReactECharts option={option} style={{ height, width: '100%' }} />;
};

export default KLineChart;
