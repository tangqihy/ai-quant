import React, { useEffect, useState } from 'react';
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
  Modal,
  Empty,
  Radio,
  Checkbox,
} from 'antd';
import {
  ArrowLeftOutlined,
  StarFilled,
  EditOutlined,
  LineChartOutlined,
} from '@ant-design/icons';
import { useWatchlist } from '../hooks/useWatchlist';
import AddToWatchlistModal from '../components/watchlist/AddToWatchlistModal';
import { getRealtimeQuotes } from '../services/api';
import KLineChart, { OverlayIndicator } from '../components/charts/KLineChart';

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
    isLoaded,
    addStock,
  } = useWatchlist();

  const [loading, setLoading] = useState(true);
  const [quote, setQuote] = useState<StockQuote | null>(null);
  const [klinePeriod, setKlinePeriod] = useState<string>('daily');
  const [tdxOverlays, setTdxOverlays] = useState<OverlayIndicator[]>([
    'fenshi_t0',
    'capital_trend',
  ]);
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const stockGroups = symbol ? getStockGroups(symbol) : [];
  const isMinutePeriod = klinePeriod !== 'daily';
  const chartOverlays: OverlayIndicator[] | undefined = isMinutePeriod
    ? (tdxOverlays.length > 0 ? tdxOverlays : undefined)
    : ['ma'];

  // 检查是否在自选中
  const inWatchlist = symbol ? isInWatchlist(symbol) : false;

  useEffect(() => {
    if (!symbol) {
      navigate('/');
      return;
    }

    // 自选数据未就绪时不要误判「不在自选」
    if (!isLoaded) return;

    loadStockData();
  }, [symbol, isLoaded, isInWatchlist, navigate]);

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

      // K 线数据由 KLineChart 组件根据 symbol + period 自行拉取
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
      okText: '确定',
      cancelText: '取消',
      onOk: () => {
        removeStock(symbol);
        message.success('已移除');
        navigate('/');
      },
    });
  };

  if (!isLoaded || loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 400, color: 'var(--cyber-neon-cyan)' }}>
        <Spin size="large" description={isLoaded ? '加载中...' : '自选数据加载中...'} />
      </div>
    );
  }

  if (!quote) {
    return (
      <Empty
        description="暂无股票数据"
        extra={
          <Button type="primary" onClick={() => navigate('/')}>
            返回首页
          </Button>
        }
      />
    );
  }

  const isUp = quote.change_pct >= 0;
  const color = isUp ? 'var(--up)' : 'var(--down)';
  const neonBorder = '1.5px solid var(--line)';

  return (
    <div style={{ fontFamily: 'var(--mono-font)' }}>
      <Button
        icon={<ArrowLeftOutlined />}
        onClick={() => navigate(-1)}
        style={{ marginBottom: 16 }}
      >
        返回
      </Button>

      <Card
        style={{
          marginBottom: 24,
          background: 'var(--paper-card)',
          border: neonBorder,
          boxShadow: '0 0 12px rgba(var(--accent-rgb), 0.06)',
        }}
      >
        <Row gutter={[24, 16]} align="middle">
          <Col xs={24} md={12}>
            <Space orientation="vertical" size={4}>
              <Space>
                <Title level={3} style={{ margin: 0 }}>{quote.name}</Title>
                <Text type="secondary" style={{ fontSize: 16, fontFamily: 'monospace' }}>
                  {quote.symbol}
                </Text>
                <Tag color="green">{quote.symbol.startsWith('6') ? 'SH' : 'SZ'}</Tag>
              </Space>
              
              {/* 所属分组标签 */}
              <Space size={4} wrap>
                {stockGroups.map(g => (
                  <Tag key={g.id} color={g.color} size="small">
                    {g.name}
                  </Tag>
                ))}
                {inWatchlist ? (
                  <Button
                    type="link"
                    size="small"
                    icon={<EditOutlined />}
                    onClick={() => setIsAddModalOpen(true)}
                  >
                    调整分组
                  </Button>
                ) : (
                  <Button
                    type="link"
                    size="small"
                    icon={<StarFilled />}
                    onClick={async () => {
                      if (!symbol) return;
                      const ok = await addStock({ symbol, name: quote.name, groupIds: [] });
                      if (ok) message.success('已加入自选');
                    }}
                  >
                    加入自选
                  </Button>
                )}
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
                  styles={{ content: { color, fontSize: 28, fontWeight: 'bold' } }}
                />
              </Col>
              <Col span={8}>
                <Statistic
                  title="涨跌幅"
                  value={quote.change_pct}
                  precision={2}
                  suffix="%"
                  styles={{ content: { color, fontSize: 28, fontWeight: 'bold' } }}
                  prefix={isUp ? '+' : ''}
                />
              </Col>
              <Col span={8} style={{ textAlign: 'right' }}>
                {inWatchlist && (
                  <Space orientation="vertical">
                    <Button
                      type="primary"
                      danger
                      icon={<StarFilled />}
                      onClick={handleRemoveFromWatchlist}
                    >
                      移除自选
                    </Button>
                  </Space>
                )}
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

      <Card
        title={
          <Space>
            <LineChartOutlined style={{ color: 'var(--cyber-neon-cyan)' }} />
            <span style={{ color: 'var(--cyber-neon-cyan)' }}>K线走势</span>
          </Space>
        }
        extra={
          <Space wrap>
            {isMinutePeriod && (
              <Checkbox.Group
                value={tdxOverlays}
                onChange={(vals) => setTdxOverlays(vals as OverlayIndicator[])}
                options={[
                  { label: '分时T加0', value: 'fenshi_t0' },
                  { label: '主力/趋势', value: 'capital_trend' },
                ]}
              />
            )}
            <Radio.Group
              size="small"
              value={klinePeriod}
              onChange={(e) => setKlinePeriod(e.target.value)}
              optionType="button"
              buttonStyle="solid"
            >
              <Radio.Button value="daily">日线</Radio.Button>
              <Radio.Button value="60min">60分</Radio.Button>
              <Radio.Button value="30min">30分</Radio.Button>
              <Radio.Button value="15min">15分</Radio.Button>
              <Radio.Button value="5min">5分</Radio.Button>
            </Radio.Group>
          </Space>
        }
        style={{
          background: 'var(--paper-card)',
          border: neonBorder,
          boxShadow: '0 0 12px rgba(var(--accent-rgb), 0.06)',
        }}
        styles={{ header: { borderBottom: neonBorder, color: 'var(--cyber-neon-cyan)' } }}
      >
        <KLineChart
          symbol={symbol}
          period={klinePeriod}
          overlays={chartOverlays}
          height={isMinutePeriod ? 480 : 400}
        />
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

export default StockDetail;
