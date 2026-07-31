import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Card, Row, Col, Statistic, Table, Select, Button, Space, Tabs, message, Spin, DatePicker, Radio, Switch, Typography } from 'antd';
import { ArrowDownOutlined, PlayCircleOutlined } from '@ant-design/icons';
import dayjs, { Dayjs } from 'dayjs';
import ReactECharts from 'echarts-for-react';
import { runBacktest, BacktestResult, getBacktestStrategies, StrategyMeta } from '../services/api';
import KLineChart from '../components/charts/KLineChart';
import StrategyParamTuner from '../components/strategy/StrategyParamTuner';
import RobustnessPanel from '../components/strategy/RobustnessPanel';
import SymbolInput from '../components/common/SymbolInput';

const { Text } = Typography;

const { RangePicker } = DatePicker;

type RangeKey = '1m' | '3m' | '6m' | '1y' | 'all';

function rangeToDates(key: RangeKey): { start?: string; end?: string } {
  const fmt = (d: Dayjs) => d.format('YYYYMMDD');
  const end = dayjs();
  switch (key) {
    case '1m':
      return { start: fmt(end.subtract(1, 'month')), end: fmt(end) };
    case '3m':
      return { start: fmt(end.subtract(3, 'month')), end: fmt(end) };
    case '6m':
      return { start: fmt(end.subtract(6, 'month')), end: fmt(end) };
    case '1y':
      return { start: fmt(end.subtract(1, 'year')), end: fmt(end) };
    case 'all':
    default:
      return { start: undefined, end: undefined };
  }
}

const Analysis: React.FC = () => {
  const [symbol, setSymbol] = useState('600519');
  const [strategy, setStrategy] = useState('ma_cross');
  const [strategies, setStrategies] = useState<StrategyMeta[]>([]);
  const [strategyParams, setStrategyParams] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [rangeKey, setRangeKey] = useState<RangeKey>('6m');
  const [dateRange, setDateRange] = useState<[Dayjs | null, Dayjs | null] | null>(null);
  const [klinePeriod, setKlinePeriod] = useState<string>('daily');
  const [liveTune, setLiveTune] = useState(true);
  const tuneReadyRef = useRef(false);

  const currentMeta = useMemo(
    () => strategies.find((s) => s.id === strategy),
    [strategies, strategy]
  );

  const applyStrategyDefaults = (meta?: StrategyMeta) => {
    if (!meta) return;
    const next: Record<string, number> = {};
    (meta.param_schema || []).forEach((p) => {
      if (p.default != null) next[p.name] = Number(p.default);
    });
    setStrategyParams(next);
  };

  useEffect(() => {
    getBacktestStrategies()
      .then((list) => {
        setStrategies(list);
        const initial = list.find((s) => s.id === strategy) || list[0];
        if (initial) {
          setStrategy(initial.id);
          applyStrategyDefaults(initial);
        }
      })
      .catch(() => {
        /* 回退硬编码选项 */
      });
  }, []);

  // K 线与回测使用的日期范围：优先自定义 dateRange，否则用快捷区间
  const activeRange = dateRange && dateRange[0] && dateRange[1]
    ? {
        start: dateRange[0].format('YYYYMMDD'),
        end: dateRange[1].format('YYYYMMDD'),
      }
    : rangeToDates(rangeKey);

  const handleRunBacktest = useCallback(
    async (opts?: { silent?: boolean }) => {
      setLoading(true);
      try {
        const res = await runBacktest({
          symbol,
          strategy,
          initial_capital: 1000000,
          start_date: activeRange.start,
          end_date: activeRange.end,
          engine: 'v2',
          ...strategyParams,
        });
        if (res.success) {
          setResult(res);
          if (!opts?.silent) message.success('回测完成');
        } else if (!opts?.silent) {
          message.error(res.error || '回测失败');
        }
      } catch (e: any) {
        if (!opts?.silent) message.error('回测失败: ' + (e.message || ''));
      } finally {
        setLoading(false);
      }
    },
    [symbol, strategy, activeRange.start, activeRange.end, strategyParams]
  );

  const paramsKey = JSON.stringify(strategyParams);

  /** 调参后防抖自动回测，净值/交易点即时更新 */
  useEffect(() => {
    if (!tuneReadyRef.current) {
      tuneReadyRef.current = true;
      return;
    }
    if (!liveTune || !result) return;
    const timer = window.setTimeout(() => {
      handleRunBacktest({ silent: true });
    }, 500);
    return () => window.clearTimeout(timer);
    // 仅在参数/策略/区间变化时重跑；result 存在才开启
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [liveTune, strategy, paramsKey, activeRange.start, activeRange.end, symbol]);

  // 收益曲线 option
  const revenueOption = result?.daily_values
    ? {
        tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
        grid: { left: '3%', right: '4%', bottom: '10%', containLabel: true },
        xAxis: {
          type: 'category',
          data: result.daily_values.map((d: any) => d.date),
          axisLabel: { color: 'rgba(0, 255, 65, 0.6)' },
          axisLine: { lineStyle: { color: 'rgba(0, 255, 65, 0.4)' } },
        },
        yAxis: {
          type: 'value',
          axisLabel: {
            color: 'rgba(0, 255, 65, 0.6)',
            formatter: (v: number) => (v / 10000).toFixed(0) + '万',
          },
          axisLine: { lineStyle: { color: 'rgba(0, 255, 65, 0.4)' } },
          splitLine: { lineStyle: { color: 'rgba(0, 255, 65, 0.1)' } },
        },
        dataZoom: [
          { type: 'inside', start: 0, end: 100 },
          { type: 'slider', start: 0, end: 100 },
        ],
        series: [
          {
            name: '资产净值',
            type: 'line',
            smooth: true,
            symbol: 'none',
            data: result.daily_values.map((d: any) => d.value),
            lineStyle: { width: 2, color: '#00ff41' },
            areaStyle: {
              color: {
                type: 'linear',
                x: 0, y: 0, x2: 0, y2: 1,
                colorStops: [
                  { offset: 0, color: 'rgba(0, 255, 65, 0.25)' },
                  { offset: 1, color: 'rgba(0, 255, 65, 0.02)' },
                ],
              },
            },
            markPoint: {
              data: [
                { type: 'max', name: '最高' },
                { type: 'min', name: '最低' },
              ],
            },
          },
        ],
      }
    : null;

  const tradeColumns = [
    { title: '日期', dataIndex: 'date', key: 'date' },
    {
      title: '操作',
      dataIndex: 'action',
      key: 'action',
      render: (v: string) => (
        <span style={{ color: v === 'BUY' ? '#ff0040' : '#00ff41', fontWeight: 'bold' }}>
          {v === 'BUY' ? '买入' : '卖出'}
        </span>
      ),
    },
    { title: '价格', dataIndex: 'price', key: 'price', render: (v: number) => v?.toFixed(2) },
    { title: '数量', dataIndex: 'shares', key: 'shares' },
    {
      title: '金额',
      key: 'amount',
      render: (_: any, r: any) => ((r.cost || r.proceeds || 0) / 10000).toFixed(2) + '万',
    },
  ];

  useEffect(() => {
    const raw = localStorage.getItem('lastBacktestResult');
    if (!raw) return;
    try {
      const parsed = JSON.parse(raw);
      if (parsed?.success && parsed?.daily_values) {
        setResult(parsed);
        if (parsed.symbol) setSymbol(parsed.symbol);
        if (parsed.strategy) setStrategy(parsed.strategy);
      }
    } catch {
      // ignore invalid cache
    }
  }, []);

  return (
    <div style={{ fontFamily: "'JetBrains Mono', monospace" }}>
      <h2 style={{ marginBottom: 24, color: '#00ff41' }}>收益分析</h2>

      <Card size="small" style={{ marginBottom: 16 }}>
        <Space wrap>
          <span>股票代码:</span>
          <SymbolInput
            value={symbol}
            onChange={setSymbol}
            style={{ width: 220 }}
            size="small"
            compact
            placeholder="600519"
          />
          <span>策略:</span>
          <Select
            value={strategy}
            onChange={(id) => {
              setStrategy(id);
              applyStrategyDefaults(strategies.find((s) => s.id === id));
            }}
            style={{ width: 150 }}
            options={
              strategies.length
                ? strategies.map((s) => ({ value: s.id, label: s.name }))
                : [
                    { value: 'ma_cross', label: '均线交叉' },
                    { value: 'rsi', label: 'RSI策略' },
                  ]
            }
          />
          <Space size={4}>
            <Text type="secondary" style={{ fontSize: 12 }}>
              拖参即回测
            </Text>
            <Switch size="small" checked={liveTune} onChange={setLiveTune} />
          </Space>
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            onClick={() => handleRunBacktest()}
            loading={loading}
          >
            运行回测
          </Button>
        </Space>
      </Card>

      <Card
        size="small"
        title={<span style={{ color: '#00f0ff' }}>策略参数微调</span>}
        style={{ marginBottom: 16 }}
        extra={
          liveTune && result ? (
            <Text type="secondary" style={{ fontSize: 12 }}>
              拖动滑条后约 0.5s 自动刷新结果
            </Text>
          ) : (
            <Text type="secondary" style={{ fontSize: 12 }}>
              先运行一次回测后，开启「拖参即回测」可所见即所得
            </Text>
          )
        }
      >
        <StrategyParamTuner
          strategyId={strategy}
          schema={currentMeta?.param_schema || []}
          value={strategyParams}
          onChange={setStrategyParams}
          disabled={loading}
          compact
        />
      </Card>

      <RobustnessPanel
        strategy={strategy}
        baselineParams={strategyParams}
        primarySymbol={symbol}
        startDate={activeRange.start}
        endDate={activeRange.end}
      />

      <Card size="small" style={{ marginBottom: 16 }}>
        <Space wrap>
          <span>时间范围:</span>
          <Radio.Group
            value={rangeKey}
            onChange={(e) => {
              setRangeKey(e.target.value);
              setDateRange(null);
            }}
            optionType="button"
            buttonStyle="solid"
            size="small"
          >
            <Radio.Button value="1m">近1月</Radio.Button>
            <Radio.Button value="3m">近3月</Radio.Button>
            <Radio.Button value="6m">近6月</Radio.Button>
            <Radio.Button value="1y">近1年</Radio.Button>
            <Radio.Button value="all">全部</Radio.Button>
          </Radio.Group>
          <RangePicker
            size="small"
            value={dateRange as [Dayjs | null, Dayjs | null] | null}
            onChange={(v) => {
              setDateRange(v as [Dayjs | null, Dayjs | null] | null);
              if (v && v[0] && v[1]) setRangeKey('all');
            }}
            allowClear
            placeholder={['开始日期', '结束日期']}
          />
        </Space>
      </Card>

      <Card
        title={`${symbol} K线走势`}
        size="small"
        style={{ marginBottom: 16, height: 440 }}
        extra={
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
        }
      >
        <KLineChart
          symbol={symbol}
          startDate={activeRange.start}
          endDate={activeRange.end}
          period={klinePeriod}
          height={360}
        />
      </Card>

      <Spin spinning={loading}>
        {result && (
          <>
            <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
              <Col xs={12} sm={8} lg={4}>
                <Card>
                  <Statistic
                    title="总收益率"
                    value={result.total_return}
                    precision={2}
                    suffix="%"
                    styles={{ content: { color: result.total_return >= 0 ? '#00ff41' : '#ff0040' } }}
                  />
                </Card>
              </Col>
              <Col xs={12} sm={8} lg={4}>
                <Card>
                  <Statistic
                    title="年化收益率"
                    value={result.annual_return}
                    precision={2}
                    suffix="%"
                    styles={{ content: { color: result.annual_return >= 0 ? '#00ff41' : '#ff0040' } }}
                  />
                </Card>
              </Col>
              <Col xs={12} sm={8} lg={4}>
                <Card>
                  <Statistic
                    title="最大回撤"
                    value={result.max_drawdown}
                    precision={2}
                    prefix={<ArrowDownOutlined />}
                    suffix="%"
                    styles={{ content: { color: '#ff0040' } }}
                  />
                </Card>
              </Col>
              <Col xs={12} sm={8} lg={4}>
                <Card>
                  <Statistic title="胜率" value={result.win_rate} precision={1} suffix="%" styles={{ content: { color: '#00ff41' } }} />
                </Card>
              </Col>
              <Col xs={12} sm={8} lg={4}>
                <Card>
                  <Statistic title="交易次数" value={result.total_trades} styles={{ content: { color: '#00ff41' } }} />
                </Card>
              </Col>
              <Col xs={12} sm={8} lg={4}>
                <Card>
                  <Statistic
                    title="最终资产"
                    value={result.final_value}
                    precision={0}
                    prefix="¥"
                    styles={{ content: { color: result.final_value >= result.initial_capital ? '#00ff41' : '#ff0040' } }}
                  />
                </Card>
              </Col>
            </Row>

            <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
              <Col xs={24} lg={24}>
                <Card title="资产净值曲线" style={{ height: 400 }}>
                  {revenueOption ? (
                    <ReactECharts option={revenueOption} style={{ height: '100%', width: '100%' }} />
                  ) : (
                    <div style={{ textAlign: 'center', padding: 40, color: 'rgba(0, 255, 65, 0.5)' }}>暂无数据</div>
                  )}
                </Card>
              </Col>
            </Row>

            <Card>
              <Tabs
                defaultActiveKey="1"
                items={[
                  {
                    key: '1',
                    label: '交易记录',
                    children: (
                      <Table
                        columns={tradeColumns}
                        dataSource={result.trades.map((t: any, i: number) => ({ ...t, key: i }))}
                        pagination={{ pageSize: 10 }}
                        size="small"
                        scroll={{ x: 600 }}
                      />
                    ),
                  },
                  {
                    key: '2',
                    label: '风险指标',
                    children: (
                      <Row gutter={[16, 16]}>
                        <Col xs={24} lg={12}>
                          <Card title="回测概要" size="small">
                            <Statistic title="初始资金" value={result.initial_capital} prefix="¥" />
                            <Statistic title="最终资产" value={result.final_value} prefix="¥" precision={2} />
                            <Statistic title="总收益率" value={result.total_return} suffix="%" precision={2} />
                          </Card>
                        </Col>
                        <Col xs={24} lg={12}>
                          <Card title="风险指标" size="small">
                            <Statistic title="最大回撤" value={result.max_drawdown} suffix="%" precision={2} styles={{ content: { color: '#ff0040' } }} />
                            <Statistic title="胜率" value={result.win_rate} suffix="%" precision={1} />
                            <Statistic title="交易次数" value={result.total_trades} />
                          </Card>
                        </Col>
                      </Row>
                    ),
                  },
                ]}
              />
            </Card>
          </>
        )}

        {!result && !loading && (
          <Card style={{ textAlign: 'center', padding: 40 }}>
            <p style={{ color: 'rgba(0, 255, 65, 0.5)', fontSize: 16 }}>选择股票和策略，点击"运行回测"查看分析结果</p>
          </Card>
        )}
      </Spin>
    </div>
  );
};

export default Analysis;
