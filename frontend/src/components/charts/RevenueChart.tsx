import React from 'react';
import ReactECharts from 'echarts-for-react';
import { Empty } from 'antd';

interface RevenueChartProps {
  dailyValues?: { date: string; value: number }[];
  taskId?: string;
}

const RevenueChart: React.FC<RevenueChartProps> = ({ dailyValues }) => {
  // 如果没有数据，显示空状态
  if (!dailyValues || dailyValues.length === 0) {
    return (
      <Empty
        description="暂无回测数据"
        style={{ padding: '40px 0' }}
      />
    );
  }

  // 使用真实数据
  const dates = dailyValues.map(d => d.date);
  const revenueData = dailyValues.map(d => d.value);

  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      formatter: (params: any) => {
        let result = `${params[0].axisValue}<br/>`;
        params.forEach((item: any) => {
          const value = item.value.toFixed(2);
          const color = item.seriesName === '策略收益' ? '#1890ff' : '#faad14';
          result += `${item.marker} ${item.seriesName}: <span style="color:${color};font-weight:bold">${value}%</span><br/>`;
        });
        return result;
      },
    },
    legend: {
      data: ['策略收益', '基准收益 (沪深300)'],
      bottom: 0,
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
      axisLine: { lineStyle: { color: '#d9d9d9' } },
      axisLabel: { color: '#666' },
    },
    yAxis: {
      type: 'value',
      axisLine: { lineStyle: { color: '#d9d9d9' } },
      axisLabel: {
        color: '#666',
        formatter: '{value}%',
      },
      splitLine: {
        lineStyle: { color: '#f0f0f0' },
      },
    },
    dataZoom: [
      {
        type: 'inside',
        start: 0,
        end: 100,
      },
      {
        type: 'slider',
        start: 0,
        end: 100,
        bottom: 35,
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
          color: '#1890ff',
        },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(24, 144, 255, 0.3)' },
              { offset: 1, color: 'rgba(24, 144, 255, 0.05)' },
            ],
          },
        },
        markPoint: {
          data: [
            { type: 'max', name: '最大值' },
            { type: 'min', name: '最小值' },
          ],
        },
      },
    ],
  };

  return <ReactECharts option={option} style={{ height: '100%', width: '100%' }} />;
};

export default RevenueChart;
