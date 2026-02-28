import React from 'react';
import ReactECharts from 'echarts-for-react';

const RevenueChart: React.FC = () => {
  // 模拟收益数据
  const dates = [];
  const baseDate = new Date('2024-01-01');
  for (let i = 0; i < 365; i++) {
    const date = new Date(baseDate);
    date.setDate(date.getDate() + i);
    dates.push(date.toISOString().slice(0, 10));
  }

  // 生成模拟的累计收益曲线
  const generateRevenueData = () => {
    const data = [];
    let value = 0;
    for (let i = 0; i < dates.length; i++) {
      // 模拟收益率波动
      const randomReturn = (Math.random() - 0.45) * 3; // 略微偏向正收益
      value = value + randomReturn;
      data.push(value);
    }
    return data;
  };

  const revenueData = generateRevenueData();
  
  // 基准收益（沪深300）
  const benchmarkData = revenueData.map((_, i) => {
    return (Math.random() - 0.48) * 2 + (i * 0.01);
  });

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
      {
        name: '基准收益 (沪深300)',
        type: 'line',
        smooth: true,
        symbol: 'none',
        data: benchmarkData,
        lineStyle: {
          width: 2,
          color: '#faad14',
          type: 'dashed',
        },
      },
    ],
  };

  return <ReactECharts option={option} style={{ height: '100%', width: '100%' }} />;
};

export default RevenueChart;
