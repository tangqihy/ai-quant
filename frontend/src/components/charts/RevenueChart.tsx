import React from 'react';
import ReactECharts from 'echarts-for-react';
import { Empty } from 'antd';

const NEON_GREEN = '#00ff41';
const NEON_AXIS = 'rgba(0, 255, 65, 0.5)';
const NEON_GRID = 'rgba(0, 255, 65, 0.08)';

interface RevenueChartProps {
  dailyValues?: { date: string; value: number }[];
  taskId?: string;
}

const RevenueChart: React.FC<RevenueChartProps> = ({ dailyValues }) => {
  if (!dailyValues || dailyValues.length === 0) {
    return (
      <Empty
        description="暂无回测数据"
        style={{ padding: '40px 0' }}
      />
    );
  }

  const dates = dailyValues.map(d => d.date);
  const revenueData = dailyValues.map(d => d.value);

  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: 'rgba(0, 10, 0, 0.9)',
      borderColor: NEON_GREEN,
      textStyle: { color: NEON_GREEN },
      formatter: (params: any) => {
        let result = `${params[0].axisValue}<br/>`;
        params.forEach((item: any) => {
          const value = item.value.toFixed(2);
          const color = item.seriesName === '策略收益' ? NEON_GREEN : 'rgba(255, 0, 64, 0.9)';
          result += `${item.marker} ${item.seriesName}: <span style="color:${color};font-weight:bold">${value}%</span><br/>`;
        });
        return result;
      },
    },
    legend: {
      data: ['策略收益', '基准收益 (沪深300)'],
      bottom: 0,
      textStyle: { color: NEON_AXIS },
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '15%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: dates,
      axisLine: { lineStyle: { color: NEON_AXIS } },
      axisLabel: { color: NEON_AXIS },
    },
    yAxis: {
      type: 'value',
      axisLine: { lineStyle: { color: NEON_AXIS } },
      axisLabel: {
        color: NEON_AXIS,
        formatter: '{value}%',
      },
      splitLine: { lineStyle: { color: NEON_GRID } },
    },
    dataZoom: [
      { type: 'inside', start: 0, end: 100 },
      {
        type: 'slider',
        start: 0,
        end: 100,
        bottom: 35,
        borderColor: NEON_AXIS,
        fillerColor: 'rgba(0, 255, 65, 0.2)',
        handleStyle: { color: NEON_GREEN },
        textStyle: { color: NEON_AXIS },
      },
    ],
    series: [
      {
        name: '策略收益',
        type: 'line',
        smooth: true,
        symbol: 'none',
        data: revenueData,
        lineStyle: {
          width: 2,
          color: NEON_GREEN,
        },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(0, 255, 65, 0.25)' },
              { offset: 1, color: 'rgba(0, 255, 65, 0.02)' },
            ],
          },
        },
        markPoint: {
          data: [
            { type: 'max', name: '最大值', itemStyle: { color: NEON_GREEN } },
            { type: 'min', name: '最小值', itemStyle: { color: '#ff0040' } },
          ],
        },
      },
    ],
  };

  return <ReactECharts option={option} style={{ height: '100%', width: '100%' }} />;
};

export default RevenueChart;
