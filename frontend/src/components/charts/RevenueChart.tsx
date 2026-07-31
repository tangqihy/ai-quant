import React from 'react';
import ReactECharts from 'echarts-for-react';
import { Empty } from 'antd';
import { accentRgba, chartColors } from '../../utils/chartTheme';

interface RevenueChartProps {
  dailyValues?: { date: string; value: number }[];
  taskId?: string;
}

const RevenueChart: React.FC<RevenueChartProps> = ({ dailyValues }) => {
  // 渲染期解析主题色：canvas 不认 CSS 变量
  const C = chartColors();

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
      backgroundColor: C.paperCard,
      borderColor: C.lineStrong,
      textStyle: { color: C.ink },
      formatter: (params: any) => {
        let result = `${params[0].axisValue}<br/>`;
        params.forEach((item: any) => {
          const value = item.value.toFixed(2);
          const color = item.seriesName === '策略收益' ? C.accent : C.accentWarm;
          result += `${item.marker} ${item.seriesName}: <span style="color:${color};font-weight:bold">${value}%</span><br/>`;
        });
        return result;
      },
    },
    legend: {
      data: ['策略收益', '基准收益 (沪深300)'],
      bottom: 0,
      textStyle: { color: C.inkFaint },
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
      axisLine: { lineStyle: { color: C.inkFaint } },
      axisLabel: { color: C.inkFaint },
    },
    yAxis: {
      type: 'value',
      axisLine: { lineStyle: { color: C.inkFaint } },
      axisLabel: {
        color: C.inkFaint,
        formatter: '{value}%',
      },
      splitLine: { lineStyle: { color: C.line } },
    },
    dataZoom: [
      { type: 'inside', start: 0, end: 100 },
      {
        type: 'slider',
        start: 0,
        end: 100,
        bottom: 35,
        borderColor: C.inkFaint,
        fillerColor: accentRgba(0.15),
        handleStyle: { color: C.accent },
        textStyle: { color: C.inkFaint },
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
          color: C.accent,
        },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: accentRgba(0.25) },
              { offset: 1, color: accentRgba(0.02) },
            ],
          },
        },
        markPoint: {
          data: [
            { type: 'max', name: '最大值', itemStyle: { color: C.accent } },
            { type: 'min', name: '最小值', itemStyle: { color: C.accentWarm } },
          ],
        },
      },
    ],
  };

  return <ReactECharts option={option} style={{ height: '100%', width: '100%' }} />;
};

export default RevenueChart;
