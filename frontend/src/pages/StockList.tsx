import React, { useState } from 'react';
import { Table, Card, Input, Select, Button, Tag, Space } from 'antd';
import { SearchOutlined, StarOutlined, StarFilled } from '@ant-design/icons';

const { Option } = Select;

interface StockData {
  key: string;
  code: string;
  name: string;
  price: number;
  change: number;
  volume: number;
  amount: number;
  turnover: number;
  pe: number;
  marketCap: number;
  industry: string;
  favorite: boolean;
}

const StockList: React.FC = () => {
  const [searchText, setSearchText] = useState('');
  const [industryFilter, setIndustryFilter] = useState<string | null>(null);

  // 模拟数据
  const allStocks: StockData[] = [
    { key: '1', code: '600519', name: '贵州茅台', price: 1856.50, change: 2.35, volume: 1234567, amount: 2289567890, turnover: 1.28, pe: 42.5, marketCap: 2334000000000, industry: '食品饮料', favorite: true },
    { key: '2', code: '000858', name: '五粮液', price: 168.30, change: 1.28, volume: 2345678, amount: 3946789012, turnover: 2.15, pe: 28.3, marketCap: 654000000000, industry: '食品饮料', favorite: false },
    { key: '3', code: '601318', name: '中国平安', price: 52.80, change: -0.56, volume: 3456789, amount: 1824567890, turnover: 1.05, pe: 12.8, marketCap: 965000000000, industry: '非银金融', favorite: true },
    { key: '4', code: '600036', name: '招商银行', price: 38.90, change: 0.78, volume: 4567890, amount: 1776123456, turnover: 1.32, pe: 6.5, marketCap: 980000000000, industry: '银行', favorite: false },
    { key: '5', code: '300750', name: '宁德时代', price: 425.60, change: 3.12, volume: 5678901, amount: 2415678901, turnover: 2.45, pe: 65.2, marketCap: 1980000000000, industry: '电力设备', favorite: true },
    { key: '6', code: '000001', name: '平安银行', price: 12.45, change: -1.25, volume: 6789012, amount: 845123456, turnover: 3.21, pe: 5.8, marketCap: 242000000000, industry: '银行', favorite: false },
    { key: '7', code: '600900', name: '长江电力', price: 23.80, change: 0.85, volume: 7890123, amount: 1878345678, turnover: 1.56, pe: 18.9, marketCap: 538000000000, industry: '电力', favorite: false },
    { key: '8', code: '601888', name: '中国中免', price: 68.50, change: 4.25, volume: 8901234, amount: 6097234567, turnover: 4.12, pe: 35.6, marketCap: 1340000000000, industry: '商贸零售', favorite: true },
    { key: '9', code: '002594', name: '比亚迪', price: 256.80, change: 2.68, volume: 9012345, amount: 2314567890, turnover: 2.89, pe: 78.5, marketCap: 747000000000, industry: '汽车', favorite: false },
    { key: '10', code: '600276', name: '恒瑞医药', price: 52.30, change: -2.15, volume: 12345678, amount: 645678901, turnover: 3.65, pe: 45.2, marketCap: 334000000000, industry: '医药生物', favorite: true },
  ];

  const filteredStocks = allStocks.filter(stock => {
    const matchesSearch = stock.code.includes(searchText) || stock.name.includes(searchText);
    const matchesIndustry = !industryFilter || stock.industry === industryFilter;
    return matchesSearch && matchesIndustry;
  });

  const industries = [...new Set(allStocks.map(s => s.industry))];

  const columns = [
    { title: '关注', dataIndex: 'favorite', key: 'favorite', width: 60,
      render: (_: any, record: StockData) => (
        record.favorite ? 
          <StarFilled style={{ color: '#faad14' }} /> : 
          <StarOutlined style={{ color: '#d9d9d9' }} />
      )
    },
    { title: '股票代码', dataIndex: 'code', key: 'code', width: 100 },
    { title: '股票名称', dataIndex: 'name', key: 'name', width: 100 },
    { title: '当前价格', dataIndex: 'price', key: 'price', width: 100,
      render: (val: number) => val.toFixed(2)
    },
    { title: '涨跌幅', dataIndex: 'change', key: 'change', width: 100,
      render: (val: number) => (
        <Tag color={val >= 0 ? 'red' : 'green'}>
          {val >= 0 ? '+' : ''}{val.toFixed(2)}%
        </Tag>
      )
    },
    { title: '成交量', dataIndex: 'volume', key: 'volume', width: 120,
      render: (val: number) => (val / 10000).toFixed(2) + '万'
    },
    { title: '成交额', dataIndex: 'amount', key: 'amount', width: 120,
      render: (val: number) => (val / 100000000).toFixed(2) + '亿'
    },
    { title: '换手率', dataIndex: 'turnover', key: 'turnover', width: 80,
      render: (val: number) => val.toFixed(2) + '%'
    },
    { title: '市盈率', dataIndex: 'pe', key: 'pe', width: 80,
      render: (val: number) => val.toFixed(1)
    },
    { title: '总市值', dataIndex: 'marketCap', key: 'marketCap', width: 120,
      render: (val: number) => (val / 1000000000000).toFixed(2) + '万亿'
    },
    { title: '所属行业', dataIndex: 'industry', key: 'industry', width: 100 },
    {
      title: '操作',
      key: 'action',
      width: 120,
      render: (_: any, record: StockData) => (
        <Space>
          <Button type="link" size="small">详情</Button>
          <Button type="link" size="small">交易</Button>
        </Space>
      )
    },
  ];

  return (
    <div>
      <h2 style={{ marginBottom: 24 }}>股票列表</h2>
      
      <Card>
        <Space style={{ marginBottom: 16 }} wrap>
          <Input
            placeholder="搜索股票代码或名称"
            prefix={<SearchOutlined />}
            value={searchText}
            onChange={e => setSearchText(e.target.value)}
            style={{ width: 250 }}
            allowClear
          />
          <Select
            placeholder="所属行业"
            allowClear
            style={{ width: 150 }}
            onChange={value => setIndustryFilter(value)}
          >
            {industries.map(ind => (
              <Option key={ind} value={ind}>{ind}</Option>
            ))}
          </Select>
          <Button type="primary">刷新数据</Button>
        </Space>

        <Table
          columns={columns}
          dataSource={filteredStocks}
          pagination={{ pageSize: 10 }}
          scroll={{ x: 1200 }}
          size="small"
        />
      </Card>
    </div>
  );
};

export default StockList;
