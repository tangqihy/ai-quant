import React, { useEffect, useState } from 'react';
import dayjs from 'dayjs';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Card,
  Row,
  Col,
  Tag,
  Space,
  Button,
  message,
  Spin,
  Statistic,
  Typography,
  Tabs,
  Empty,
} from 'antd';
import {
  ArrowLeftOutlined,
  StarFilled,
  StarOutlined,
  EditOutlined,
  LineChartOutlined,
} from '@ant-design/icons';
import { useWatchlist } from '../hooks/useWatchlist';
import AddToWatchlistModal from '../components/watchlist/AddToWatchlistModal';
import { getStockHistory, getRealtimeQuotes } from '../services/api';
import KLineChart from '../components/charts/KLineChart';

const { Title, Text } = Typography;

interface StockQuote {
  symbol: string;
  name: string;
  price: number;
  change_pct: number;
  volume?: number;
  amount?: number;
  turnover?: number;
}

export const StockDetail: React.FC = () => {
  const { symbol } = useParams<{ symbol: string }>();
  const navigate = useNavigate();
  const {
    isInWatchlist,
    getStock,
    removeStock,
    getStockGroups,
    groups,
  } = useWatchlist();

  const [loading, setLoading] = useState(true);
  const [quote, setQuote] = useState<StockQuote | null>(null);
  const [klineData, setKlineData] = useState<any[]>([]);
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const stockGroups = symbol ? getStockGroups(symbol) : [];

  // 检查是否在自选中
  const inWatchlist = symbol ? isInWatchlist(symbol) : false;

  useEffect(() => {
    if (!symbol) {
      navigate('/stocks');
      return;
    }

    // 如果不在自选中，提示并跳转
    if (!isInWatchlist(symbol)) {
      message.warning('该股票不在您的自选列表中，请先添加');
      navigate('/stocks');
      return;
    }

    // 加载数据
    loadStockData();
  }, [symbol, isInWatchlist, navigate]);

  const loadStockData = async () => {
    if (!symbol) return;
    setLoading(true);
    
    try {
      // 获取实时行情
      const quoteRes = await getRealtimeQuotes([symbol]);
      if (quoteRes.success && quoteRes.data.length > 0) {
        const q = quoteRes.data[0];
        setQuote({
          symbol: q.symbol,
          name: q.name || getStock(symbol)?.name || symbol,
          price: q.price,
          change_pct: q.change_pct,
          volume: q.volume,
          amount: q.amount,
          turnover: q.turnover,
        });
      }

      // 获取K线数据（最近一年）
      const endDate = dayjs().format('YYYYMMDD');
      const startDate = dayjs().subtract(1, 'year').format('YYYYMMDD');
      const historyRes = await getStockHistory(symbol, startDate, endDate);
      if (historyRes.success) {
        setKlineData(historyRes.data || []);
      }
    } catch (e) {
      message.error('加载股票数据失败');
    } finally {
      setLoading(false);
    }
  };

  // 从自选移除
  const handleRemoveFromWatchlist = () => {
    if (!symbol) return;
    Modal.confirm({
      title: '移除自选',
      content: `确定将 ${quote?.name || symbol} 从自选列表移除吗？`,
      onOk: () => {
        removeStock(symbol);
        message.success('已移除');
        navigate('/watchlist');
      },
    });
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 400 }}>
        <Spin size="large" tip="加载中..." />
      </div>
    );
  }

  if (!inWatchlist || !quote) {
    return (
      <Empty
        description="股票不在自选列表中"
        extra={
          <Button type="primary" onClick={() => navigate('/stocks')}>
            去添加自选
          </Button>
        }
      />
    );
  }

  const isUp = quote.change_pct >= 0;
  const color = isUp ? '#f5222d' : '#52c41a';

  return (
    <div>
      {/* 返回按钮 */}
      <Button
        icon={<ArrowLeftOutlined />}
        onClick={() => navigate(-1)}
        style={{ marginBottom: 16 }}
      >
        返回
      </Button>

      {/* 股票头部信息 */}
      <Card style={{ marginBottom: 24 }}>
        <Row gutter={[24, 16]} align="middle">
          <Col xs={24} md={12}>
            <Space direction="vertical" size={4}>
              <Space>
                <Title level={3} style={{ margin: 0 }}>{quote.name}</Title>
                <Text type="secondary" style={{ fontSize: 16, fontFamily: 'monospace' }}>
                  {quote.symbol}
                </Text>
                <Tag color="blue">{quote.symbol.startsWith('6') ? 'SH' : 'SZ'}</Tag>
              </Space>
              
              {/* 所属分组标签 */}
              <Space size={4} wrap>
                {stockGroups.map(g => (
                  <Tag key={g.id} color={g.color} size="small">
                    {g.name}
                  </Tag>
                ))}
                <Button
                  type="link"
                  size="small"
                  icon={<EditOutlined />}
                  onClick={() => setIsAddModalOpen(true)}
                >
                  调整分组
                </Button>
              </Space>
            </Space>
          </Col>
          
          <Col xs={24} md={12}>
            <Row gutter={16}>
              <Col span={8}>
                <Statistic
                  title="当前价格"
                  value={quote.price}
                  precision={2}
                  valueStyle={{ color, fontSize: 28, fontWeight: 'bold' }}
                />
              </Col>
              <Col span={8}>
                <Statistic
                  title="涨跌幅"
                  value={quote.change_pct}
                  precision={2}
                  suffix="%"
                  valueStyle={{ color, fontSize: 28, fontWeight: 'bold' }}
                  prefix={isUp ? '+' : ''}
                />
              </Col>
              <Col span={8} style={{ textAlign: 'right' }}>
                <Space direction="vertical">
                  <Button
                    type="primary"
                    danger
                    icon={<StarFilled />}
                    onClick={handleRemoveFromWatchlist}
                  >
                    移除自选
                  </Button>
                </Space>
              </Col>
            </Row>
          </Col>
        </Row>

        {/* 详细数据 */}
        <Row gutter={[48, 16]} style={{ marginTop: 24 }}>
          <Col xs={12} sm={8} md={6}>
            <div>
              <Text type="secondary">成交量</Text>
              <div style={{ fontSize: 16, fontWeight: 500 }}>
                {quote.volume ? (quote.volume / 10000).toFixed(2) + '万手' : '-'}
              </div>
            </div>
          </Col>
          <Col xs={12} sm={8} md={6}>
            <div>
              <Text type="secondary">成交额</Text>
              <div style={{ fontSize: 16, fontWeight: 500 }}>
                {quote.amount ? (quote.amount / 100000000).toFixed(2) + '亿' : '-'}
              </div>
            </div>
          </Col>
          <Col xs={12} sm={8} md={6}>
            <div>
              <Text type="secondary">换手率</Text>
              <div style={{ fontSize: 16, fontWeight: 500 }}>
                {quote.turnover ? quote.turnover.toFixed(2) + '%' : '-'}
              </div>
            </div>
          </Col>
        </Row>
      </Card>

      {/* K线图区域 */}
      <Card
        title={
          <Space>
            <LineChartOutlined />
            <span>K线走势</span>
          </Space>
        }
      >
        <KLineChart data={klineData} height={400} />
      </Card>

      {/* 添加到自选弹窗（用于调整分组） */}
      {symbol && quote && (
        <AddToWatchlistModal
          visible={isAddModalOpen}
          onCancel={() => setIsAddModalOpen(false)}
          stockSymbol={symbol}
          stockName={quote.name}
        />
      )}
    </div>
  );
};

// 简单的 Modal 确认对话框
const Modal = {
  confirm: ({ title, content, onOk }: { title: string; content: string; onOk: () => void }) => {
    if (window.confirm(`${title}\n${content}`)) {
      onOk();
    }
  },
};

export default StockDetail;
