import React from 'react';
import ReactECharts from 'echarts-for-react';

const KLineChart: React.FC = () => {
  // 模拟K线数据
  const dates = ['2024-01-02', '2024-01-03', '2024-01-04', '2024-01-05', '2024-01-08', 
                 '2024-01-09', '2024-01-10', '2024-01-11', '2024-01-12', '2024-01-15',
                 '2024-01-16', '2024-01-17', '2024-01-18', '2024-01-19', '2024-01-22'];
  
  // [open, close, lowest, highest]
  const klineData = [
    [1680, 1720, 1675, 1735],
    [1720, 1685, 1670, 1730],
    [1685, 1705, 1675, 1720],
    [1705, 1750, 1695, 1760],
    [1750, 1735, 1720, 1765],
    [1735, 1710, 1700, 1745],
    [1710, 1685, 1675, 1720],
    [1685, 1695, 1670, 1705],
    [1695, 1720, 1685, 1735],
    [1720, 1700, 1690, 1735],
    [1700, 1680, 1665, 1710],
    [1680, 1695, 1670, 1705],
    [1695, 1715, 1685, 1725],
    [1715, 1740, 1705, 1750],
    [1740, 1755, 1730, 1765],
  ];

  const categoryData = dates;
  const ohlcData = klineData.map(item => [item[0], item[3], item[2], item[1]]);
  
  // 模拟MA5, MA10, MA20数据
  const ma5Data = [null, null, null, null, 1712, 1713, 1704, 1698, 1705, 1711, 1701, 1697, 1706, 1719, 1732];
  const ma10Data = [null, null, null, null, null, null, null, null, 1702, 1705, 1700, 1696, 1701, 1710, 1721];
  const ma20Data = [null, null, null, null, null, null, null, null, null, null, null, null, null, null, null];

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
      {
        left: '10%',
        right: '10%',
        height: '60%',
      },
      {
        left: '10%',
        right: '10%',
        top: '75%',
        height: '15%',
      },
    ],
    xAxis: [
      {
        type: 'category',
        data: categoryData,
        boundaryGap: false,
        axisLine: { onZero: false },
        splitLine: { show: false },
        min: 'dataMin',
        max: 'dataMax',
      },
      {
        type: 'category',
        gridIndex: 1,
        data: categoryData,
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
        splitArea: { show: true },
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
      {
        type: 'inside',
        xAxisIndex: [0, 1],
        start: 50,
        end: 100,
      },
      {
        show: true,
        xAxisIndex: [0, 1],
        type: 'slider',
        bottom: 60,
        start: 50,
        end: 100,
      },
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
      {
        name: 'MA5',
        type: 'line',
        data: ma5Data,
        smooth: true,
        lineStyle: { opacity: 0.5 },
        symbol: 'none',
      },
      {
        name: 'MA10',
        type: 'line',
        data: ma10Data,
        smooth: true,
        lineStyle: { opacity: 0.5 },
        symbol: 'none',
      },
      {
        name: 'MA20',
        type: 'line',
        data: ma20Data,
        smooth: true,
        lineStyle: { opacity: 0.5 },
        symbol: 'none',
      },
      {
        name: 'Volume',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: [12500, 15800, 13200, 16800, 18200, 14500, 12800, 11500, 13800, 14200, 13500, 12500, 14800, 16200, 17500],
        itemStyle: {
          color: '#7f8c8d',
        },
      },
    ],
  };

  return <ReactECharts option={option} style={{ height: '100%', width: '100%' }} />;
};

export default KLineChart;
