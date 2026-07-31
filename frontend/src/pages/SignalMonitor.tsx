import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Col,
  DatePicker,
  Form,
  InputNumber,
  Row,
  Select,
  Slider,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
  message,
  Spin,
  Segmented,
} from 'antd';
import {
  RadarChartOutlined,
  ReloadOutlined,
  PlayCircleOutlined,
  SaveOutlined,
  ShoppingCartOutlined,
  SafetyOutlined,
  StepBackwardOutlined,
  StepForwardOutlined,
  FastForwardOutlined,
  VerticalAlignTopOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import dayjs, { Dayjs } from 'dayjs';
import {
  StrategyMeta,
  StrategySession,
  SignalResult,
  ReplayTimeline,
  ReplayBar,
  getSignalStrategies,
  evaluateSignal,
  loadReplayTimeline,
  listSessions,
  saveSession,
  enableSession,
  deleteSession,
  executeSignal,
  checkStops,
} from '../services/signalApi';
import KLineChart from '../components/charts/KLineChart';
import StrategyParamTuner from '../components/strategy/StrategyParamTuner';
import RobustnessPanel from '../components/strategy/RobustnessPanel';
import SymbolInput from '../components/common/SymbolInput';

const { Text, Title } = Typography;

const NEON = '#00f0ff';
const cardStyle: React.CSSProperties = {
  background: 'rgba(5, 12, 24, 0.85)',
  border: '1px solid rgba(0, 240, 255, 0.28)',
};

function actionColor(action?: string) {
  if (action === 'BUY') return '#ff0040';
  if (action === 'SELL') return '#00ff41';
  return 'rgba(0, 240, 255, 0.7)';
}

function barToSignal(
  bar: ReplayBar,
  meta: { symbol: string; strategy: string; period: string; params: Record<string, number | string> }
): SignalResult {
  return {
    symbol: meta.symbol,
    strategy: meta.strategy,
    period: meta.period,
    params: meta.params,
    mode: 'replay',
    as_of: bar.date,
    bar_index: bar.index,
    bar_total: undefined,
    evaluated_at: new Date().toISOString(),
    action: bar.action,
    buy_signal: bar.buy_signal,
    sell_signal: bar.sell_signal,
    reason: bar.reason,
    in_trading_window: bar.in_trading_window,
    window_reason: bar.window_reason,
    snapshot: bar.snapshot,
    suggested_price: bar.close ?? null,
    quote_price: null,
    executable: bar.executable,
  };
}

const SignalMonitor: React.FC = () => {
  const navigate = useNavigate();
  const [strategies, setStrategies] = useState<StrategyMeta[]>([]);
  const [sessions, setSessions] = useState<StrategySession[]>([]);
  const [loading, setLoading] = useState(false);
  const [signal, setSignal] = useState<SignalResult | null>(null);
  const [mode, setMode] = useState<'live' | 'replay'>('live');
  const [replayEnd, setReplayEnd] = useState<Dayjs | null>(dayjs().subtract(1, 'day'));
  const [timeline, setTimeline] = useState<ReplayTimeline | null>(null);
  const [step, setStep] = useState(0);
  /** 拖参后自动重算（所见即所得） */
  const [liveTune, setLiveTune] = useState(true);
  /** 全区间预览：调参时看全部买卖点；步进截断：只看截至当前根 */
  const [chartScope, setChartScope] = useState<'full' | 'asof'>('full');
  const [form] = Form.useForm();
  const strategyId = Form.useWatch('strategy', form) || 'rsi';
  const paramsWatch = Form.useWatch('params', form);
  const symbolWatch = Form.useWatch('symbol', form);
  const periodWatch = Form.useWatch('period', form) || 'daily';
  const stepRatioRef = useRef(1);
  const tuneReadyRef = useRef(false);
  const stepRef = useRef(0);
  const timelineRef = useRef<ReplayTimeline | null>(null);

  useEffect(() => {
    stepRef.current = step;
  }, [step]);
  useEffect(() => {
    timelineRef.current = timeline;
  }, [timeline]);

  const currentMeta = useMemo(
    () => strategies.find((s) => s.id === strategyId),
    [strategies, strategyId]
  );

  const currentBar = timeline?.bars[step] ?? null;

  const eventStats = useMemo(() => {
    const events = timeline?.events || [];
    return {
      total: events.length,
      buy: events.filter((e) => e.action === 'BUY').length,
      sell: events.filter((e) => e.action === 'SELL').length,
    };
  }, [timeline]);

  /** 全区间预览看完整 K 线；步进截断只到当前 as_of */
  const replayChartData = useMemo(() => {
    if (!timeline?.klines?.length) return [];
    if (chartScope === 'full' || !currentBar) return timeline.klines;
    return timeline.klines.slice(0, currentBar.index + 1);
  }, [timeline, currentBar, chartScope]);

  const replaySignalMarks = useMemo(() => {
    if (!timeline?.events?.length) return [];
    const events =
      chartScope === 'full' ? timeline.events : timeline.events.filter((e) => e.step <= step);
    return events.map((e) => ({ date: e.date, action: e.action, price: e.close }));
  }, [timeline, step, chartScope]);

  const applyBarStep = useCallback(
    (nextStep: number, tl: ReplayTimeline | null = timeline) => {
      if (!tl?.bars.length) return;
      const clamped = Math.max(0, Math.min(nextStep, tl.bars.length - 1));
      setStep(clamped);
      const bar = tl.bars[clamped];
      setSignal(
        barToSignal(bar, {
          symbol: tl.symbol,
          strategy: tl.strategy,
          period: tl.period,
          params: tl.params,
        })
      );
    },
    [timeline]
  );

  const loadMeta = useCallback(async () => {
    try {
      const [list, sess] = await Promise.all([getSignalStrategies(), listSessions()]);
      setStrategies(list);
      setSessions(sess);
      if (!form.getFieldValue('strategy') && list.length) {
        form.setFieldsValue({ strategy: list[0].id });
        applyDefaults(list[0]);
      }
    } catch (e: any) {
      message.error('加载策略失败: ' + (e.message || ''));
    }
  }, [form]);

  const applyDefaults = (meta?: StrategyMeta) => {
    if (!meta) return;
    const params: Record<string, number> = {};
    (meta.param_schema || []).forEach((p) => {
      if (p.default != null) params[p.name] = Number(p.default);
    });
    form.setFieldsValue({
      params,
      period: form.getFieldValue('period') || 'daily',
      position_pct: form.getFieldValue('position_pct') ?? 5,
      stop_loss_pct: form.getFieldValue('stop_loss_pct') ?? 2,
      stop_profit_pct: form.getFieldValue('stop_profit_pct') ?? 4,
    });
  };

  useEffect(() => {
    form.setFieldsValue({
      symbol: '600036',
      strategy: 'rsi',
      period: 'daily',
      position_pct: 5,
      stop_loss_pct: 2,
      stop_profit_pct: 4,
      force: false,
      params: { period: 14, oversold: 30, overbought: 70 },
    });
    loadMeta();
  }, [loadMeta, form]);

  const collectBody = () => {
    const v = form.getFieldsValue(true);
    const asOf =
      mode === 'replay'
        ? currentBar?.date || (replayEnd ? replayEnd.format('YYYY-MM-DD') : undefined)
        : undefined;
    return {
      symbol: String(v.symbol || '').trim(),
      strategy: v.strategy,
      params: v.params || {},
      period: v.period || 'daily',
      position_pct: v.position_pct,
      stop_loss_pct: v.stop_loss_pct,
      stop_profit_pct: v.stop_profit_pct,
      force: !!v.force,
      as_of: asOf,
    };
  };

  const handleEvaluate = async () => {
    const body = collectBody();
    if (!body.symbol) {
      message.warning('请填写股票代码');
      return;
    }
    setLoading(true);
    try {
      const res = await evaluateSignal({
        symbol: body.symbol,
        strategy: body.strategy,
        params: body.params,
        period: body.period,
        as_of: mode === 'replay' ? body.as_of : undefined,
      });
      if (res.success && res.data) {
        setSignal(res.data);
        message.success(`信号: ${res.data.action}${res.data.mode === 'replay' ? '（回放）' : ''}`);
      } else {
        message.error(res.error || res.message || '评估失败');
      }
    } catch (e: any) {
      message.error(e?.response?.data?.detail || e.message || '评估失败');
    } finally {
      setLoading(false);
    }
  };

  const handleLoadReplay = useCallback(
    async (opts?: { silent?: boolean; preserveStep?: boolean }) => {
      const v = form.getFieldsValue(true);
      const symbol = String(v.symbol || '').trim();
      if (!symbol) {
        if (!opts?.silent) message.warning('请填写股票代码');
        return;
      }
      const tl = timelineRef.current;
      const st = stepRef.current;
      if (tl && tl.step_total > 1) {
        stepRatioRef.current = st / (tl.step_total - 1);
      }
      setLoading(true);
      try {
        const res = await loadReplayTimeline({
          symbol,
          strategy: v.strategy,
          params: v.params || {},
          period: v.period || 'daily',
          as_of: replayEnd ? replayEnd.format('YYYY-MM-DD') : undefined,
          lookback_days: 120,
          warm_up: 30,
        });
        if (res.success && res.data?.bars?.length) {
          setTimeline(res.data);
          const last = res.data.bars.length - 1;
          const nextStep = opts?.preserveStep
            ? Math.max(0, Math.min(last, Math.round(stepRatioRef.current * last)))
            : last;
          setStep(nextStep);
          setSignal(
            barToSignal(res.data.bars[nextStep], {
              symbol: res.data.symbol,
              strategy: res.data.strategy,
              period: res.data.period,
              params: res.data.params,
            })
          );
          if (!opts?.silent) {
            message.success(
              `回放就绪：${res.data.step_total} 根可步进，买卖点 ${res.data.events.length} 处`
            );
          }
        } else if (!opts?.silent) {
          message.error(res.error || res.message || '加载回放失败');
        }
      } catch (e: any) {
        if (!opts?.silent) {
          message.error(e?.response?.data?.detail || e.message || '加载回放失败');
        }
      } finally {
        setLoading(false);
      }
    },
    [form, replayEnd]
  );

  const paramsKey = JSON.stringify(paramsWatch || {});

  /** 参数/策略变更后防抖重算时间轴，图表买卖点即时更新 */
  useEffect(() => {
    if (!tuneReadyRef.current) {
      tuneReadyRef.current = true;
      return;
    }
    if (mode !== 'replay' || !liveTune) return;
    if (!String(symbolWatch || '').trim()) return;
    const timer = window.setTimeout(() => {
      handleLoadReplay({ silent: true, preserveStep: true });
    }, 420);
    return () => window.clearTimeout(timer);
  }, [
    mode,
    liveTune,
    symbolWatch,
    strategyId,
    periodWatch,
    replayEnd,
    paramsKey,
    handleLoadReplay,
  ]);

  const jumpNextEvent = (direction: 1 | -1) => {
    if (!timeline?.events.length) {
      message.info('当前区间无买卖信号');
      return;
    }
    const events = timeline.events;
    let target: number | null = null;
    if (direction > 0) {
      const found = events.find((e) => e.step > step);
      target = found ? found.step : events[0].step;
    } else {
      const before = [...events].reverse().find((e) => e.step < step);
      target = before ? before.step : events[events.length - 1].step;
    }
    if (target != null) applyBarStep(target);
  };

  const handleSaveSession = async () => {
    const body = collectBody();
    if (!body.symbol) return;
    try {
      const session = await saveSession({
        name: `${body.strategy}@${body.symbol}`,
        symbol: body.symbol,
        strategy: body.strategy,
        params: body.params,
        period: body.period,
        position_pct: body.position_pct,
        stop_loss_pct: body.stop_loss_pct,
        stop_profit_pct: body.stop_profit_pct,
        enabled: true,
        exclusive_enable: true,
      });
      message.success('会话已保存并启用');
      setSessions(await listSessions());
      form.setFieldsValue({ session_id: session.id });
    } catch (e: any) {
      message.error(e.message || '保存失败');
    }
  };

  const handleExecute = async () => {
    const body = collectBody();
    setLoading(true);
    try {
      const res = await executeSignal({
        ...body,
        order_type: 'MARKET',
        as_of: mode === 'replay' ? body.as_of : undefined,
      });
      if (res.success) {
        setSignal(res.data?.signal || null);
        message.success(res.message || '已提交模拟单');
      } else {
        if (res.data?.signal) setSignal(res.data.signal);
        message.warning(res.message || res.error || '未下单');
      }
    } catch (e: any) {
      message.error(e?.response?.data?.detail || e.message || '下单失败');
    } finally {
      setLoading(false);
    }
  };

  const handleCheckStops = async () => {
    setLoading(true);
    try {
      const res = await checkStops();
      message.info(res.message || '止损扫描完成');
    } catch (e: any) {
      message.error(e.message || '扫描失败');
    } finally {
      setLoading(false);
    }
  };

  const loadSession = (s: StrategySession) => {
    form.setFieldsValue({
      symbol: s.symbol,
      strategy: s.strategy,
      params: s.params,
      period: s.period,
      position_pct: s.position_pct,
      stop_loss_pct: s.stop_loss_pct,
      stop_profit_pct: s.stop_profit_pct,
    });
    message.success(`已加载会话 ${s.name}`);
  };

  const sessionColumns = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '标的', dataIndex: 'symbol', key: 'symbol', width: 90 },
    { title: '策略', dataIndex: 'strategy', key: 'strategy', width: 90 },
    {
      title: '仓位%',
      dataIndex: 'position_pct',
      key: 'position_pct',
      width: 70,
    },
    {
      title: '启用',
      dataIndex: 'enabled',
      key: 'enabled',
      width: 70,
      render: (v: boolean, r: StrategySession) => (
        <Switch
          size="small"
          checked={v}
          onChange={async (checked) => {
            await enableSession(r.id, checked);
            setSessions(await listSessions());
          }}
        />
      ),
    },
    {
      title: '操作',
      key: 'ops',
      width: 160,
      render: (_: unknown, r: StrategySession) => (
        <Space size="small">
          <Button size="small" type="link" onClick={() => loadSession(r)}>
            加载
          </Button>
          <Button
            size="small"
            type="link"
            danger
            onClick={async () => {
              await deleteSession(r.id);
              setSessions(await listSessions());
            }}
          >
            删除
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ fontFamily: "'JetBrains Mono', monospace" }}>
      <Space style={{ marginBottom: 16 }} align="center">
        <RadarChartOutlined style={{ color: NEON, fontSize: 22 }} />
        <Title level={3} style={{ margin: 0, color: NEON }}>
          信号监控
        </Title>
        <Text type="secondary">盘中评估 · 历史回放步进 · 模拟半自动</Text>
      </Space>

      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16, background: 'rgba(0,240,255,0.06)', borderColor: 'rgba(0,240,255,0.25)' }}
        message="允许下单时段：09:35-10:30 / 13:30-14:30。盘后请切「历史回放」加载时间轴后逐根步进自测；日线默认按 10:00 判时段。"
      />

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={10}>
          <Card title={<span style={{ color: NEON }}>评估参数</span>} style={cardStyle}>
            <Form form={form} layout="vertical">
              <Form.Item label="模式">
                <Segmented
                  block
                  value={mode}
                  options={[
                    { label: '实时', value: 'live' },
                    { label: '历史回放', value: 'replay' },
                  ]}
                  onChange={(v) => {
                    setMode(v as 'live' | 'replay');
                    if (v === 'live') setTimeline(null);
                  }}
                />
              </Form.Item>

              <Form.Item label="股票代码" name="symbol" rules={[{ required: true, message: '请输入或从自选选择' }]}>
                <SymbolInput placeholder="600036" />
              </Form.Item>
              <Form.Item label="策略" name="strategy">
                <Select
                  options={strategies.map((s) => ({ value: s.id, label: s.name }))}
                  onChange={(id) => applyDefaults(strategies.find((s) => s.id === id))}
                />
              </Form.Item>
              <Form.Item label="K线周期" name="period">
                <Select
                  options={[
                    { value: 'daily', label: '日线' },
                    { value: '60min', label: '60分' },
                    { value: '30min', label: '30分' },
                    { value: '15min', label: '15分' },
                    { value: '5min', label: '5分' },
                  ]}
                />
              </Form.Item>

              {mode === 'replay' && (
                <Form.Item label="回放截止日">
                  <DatePicker
                    style={{ width: '100%' }}
                    value={replayEnd}
                    onChange={(d) => setReplayEnd(d)}
                    allowClear
                  />
                </Form.Item>
              )}

              <Form.Item
                label={
                  <Space size="middle">
                    <span>策略参数</span>
                    {mode === 'replay' && (
                      <Space size={4}>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          拖动即刷新
                        </Text>
                        <Switch size="small" checked={liveTune} onChange={setLiveTune} />
                      </Space>
                    )}
                  </Space>
                }
                name="params"
                trigger="onChange"
                valuePropName="value"
              >
                <StrategyParamTuner
                  strategyId={strategyId}
                  schema={currentMeta?.param_schema || []}
                  disabled={loading}
                />
              </Form.Item>

              <Row gutter={12}>
                <Col span={8}>
                  <Form.Item label="仓位%" name="position_pct">
                    <InputNumber min={0.1} max={100} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item label="止损%" name="stop_loss_pct">
                    <InputNumber min={0.1} max={50} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item label="止盈%" name="stop_profit_pct">
                    <InputNumber min={0.1} max={100} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
              </Row>

              <Form.Item label="忽略时段强制下单" name="force" valuePropName="checked">
                <Switch />
              </Form.Item>

              <Space wrap>
                {mode === 'live' ? (
                  <Button type="primary" icon={<ReloadOutlined />} loading={loading} onClick={handleEvaluate}>
                    刷新信号
                  </Button>
                ) : (
                  <Button
                    type="primary"
                    icon={<PlayCircleOutlined />}
                    loading={loading}
                    onClick={() => handleLoadReplay()}
                  >
                    {liveTune ? '重新加载回放' : '加载回放时间轴'}
                  </Button>
                )}
                <Button icon={<SaveOutlined />} onClick={handleSaveSession}>
                  保存为本周会话
                </Button>
                <Button
                  icon={<ShoppingCartOutlined />}
                  loading={loading}
                  onClick={handleExecute}
                  disabled={!signal || signal.action === 'HOLD'}
                >
                  一键模拟下单
                </Button>
                <Button icon={<SafetyOutlined />} loading={loading} onClick={handleCheckStops}>
                  扫描止损
                </Button>
                <Button type="link" onClick={() => navigate('/simulation')}>
                  打开模拟交易
                </Button>
              </Space>
            </Form>
          </Card>
        </Col>

        <Col xs={24} lg={14}>
          {mode === 'replay' && (
            <Card
              title={<span style={{ color: NEON }}>逐根步进 · 参数预览</span>}
              style={{ ...cardStyle, marginBottom: 16 }}
              extra={
                <Segmented
                  size="small"
                  value={chartScope}
                  onChange={(v) => setChartScope(v as 'full' | 'asof')}
                  options={[
                    { label: '全区间预览', value: 'full' },
                    { label: '步进截断', value: 'asof' },
                  ]}
                />
              }
            >
              {timeline?.bars.length ? (
                <Space direction="vertical" style={{ width: '100%' }} size="middle">
                  <Text style={{ color: '#fff' }}>
                    第 {step + 1} / {timeline.step_total} 根 · {currentBar?.date}
                    {currentBar ? ` · 收盘 ${currentBar.close ?? '-'}` : ''}
                  </Text>
                  <Slider
                    min={0}
                    max={Math.max(timeline.step_total - 1, 0)}
                    value={step}
                    onChange={(v) => applyBarStep(v)}
                    tooltip={{ formatter: (v) => timeline.bars[v ?? 0]?.date }}
                  />
                  <Space wrap>
                    <Button
                      icon={<VerticalAlignTopOutlined />}
                      disabled={step <= 0}
                      onClick={() => applyBarStep(0)}
                    >
                      开头
                    </Button>
                    <Button
                      icon={<StepBackwardOutlined />}
                      disabled={step <= 0}
                      onClick={() => applyBarStep(step - 1)}
                    >
                      上一根
                    </Button>
                    <Button
                      type="primary"
                      icon={<StepForwardOutlined />}
                      disabled={step >= timeline.step_total - 1}
                      onClick={() => applyBarStep(step + 1)}
                    >
                      下一根
                    </Button>
                    <Button icon={<FastForwardOutlined />} onClick={() => jumpNextEvent(1)}>
                      下一买卖点
                    </Button>
                    <Button onClick={() => jumpNextEvent(-1)}>上一买卖点</Button>
                    <Button
                      onClick={() => applyBarStep(timeline.step_total - 1)}
                      disabled={step >= timeline.step_total - 1}
                    >
                      末根
                    </Button>
                  </Space>
                  <Space wrap size={[8, 8]}>
                    <Tag color="magenta">买 {eventStats.buy}</Tag>
                    <Tag color="green">卖 {eventStats.sell}</Tag>
                    <Tag color="cyan">合计 {eventStats.total}</Tag>
                    {liveTune && (
                      <Tag color="processing">拖参自动刷新</Tag>
                    )}
                    <Text type="secondary">
                      {timeline.window_clock_note || ''}
                    </Text>
                  </Space>
                  {replayChartData.length > 0 && (
                    <div
                      style={{
                        border: '1px solid rgba(0,240,255,0.2)',
                        borderRadius: 4,
                        padding: '8px 0 0',
                        background: 'rgba(0,0,0,0.25)',
                      }}
                    >
                      <KLineChart
                        key={`${timeline.symbol}-${periodWatch}-${chartScope}-replay`}
                        data={replayChartData}
                        height={360}
                        period={periodWatch}
                        cursorDate={currentBar?.date}
                        signalMarks={replaySignalMarks}
                        zoomToEnd={chartScope === 'asof'}
                      />
                    </div>
                  )}
                </Space>
              ) : (
                <Text type="secondary">
                  {liveTune
                    ? '填写代码后拖动左侧参数，将自动加载时间轴与买卖点'
                    : '选择截止日并点击「加载回放时间轴」后可逐根步进'}
                </Text>
              )}
            </Card>
          )}

          <Card title={<span style={{ color: NEON }}>当前信号</span>} style={{ ...cardStyle, marginBottom: 16 }}>
            <Spin spinning={loading}>
              {signal ? (
                <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                  <div>
                    <Tag color={actionColor(signal.action)} style={{ fontSize: 18, padding: '4px 12px' }}>
                      {signal.action}
                    </Tag>
                    <Tag color={signal.mode === 'replay' ? 'purple' : 'blue'}>
                      {signal.mode === 'replay' ? '回放' : '实时'}
                    </Tag>
                    <Tag color={signal.in_trading_window ? 'green' : 'default'}>
                      {signal.in_trading_window ? '时段内' : '时段外'}
                    </Tag>
                    <Tag>{signal.executable ? '可执行' : '暂不可执行'}</Tag>
                  </div>
                  <Text style={{ color: '#fff' }}>{signal.reason}</Text>
                  <Text type="secondary">{signal.window_reason}</Text>
                  <Text type="secondary">
                    数据截至 {signal.as_of}
                    {signal.bar_index != null ? ` · bar#${signal.bar_index}` : ''}
                    {signal.evaluated_at ? ` · 评估于 ${signal.evaluated_at}` : ''}
                  </Text>
                  <Text type="secondary">
                    建议价 {signal.suggested_price ?? '-'} · 行情价 {signal.quote_price ?? '-'}
                  </Text>
                  {signal.window_clock_note && (
                    <Text type="secondary">{signal.window_clock_note}</Text>
                  )}
                  <pre
                    style={{
                      margin: 0,
                      padding: 12,
                      background: 'rgba(0,0,0,0.35)',
                      color: 'rgba(0,240,255,0.85)',
                      fontSize: 12,
                      overflow: 'auto',
                    }}
                  >
                    {JSON.stringify(signal.snapshot, null, 2)}
                  </pre>
                </Space>
              ) : (
                <Text type="secondary">
                  {mode === 'replay' ? '加载回放时间轴后开始步进' : '点击「刷新信号」开始评估'}
                </Text>
              )}
            </Spin>
          </Card>

          <Card
            title={<span style={{ color: NEON }}>本周策略会话</span>}
            style={cardStyle}
            extra={
              <Button size="small" icon={<PlayCircleOutlined />} onClick={loadMeta}>
                刷新列表
              </Button>
            }
          >
            <Table
              size="small"
              rowKey="id"
              columns={sessionColumns}
              dataSource={sessions}
              pagination={false}
              locale={{ emptyText: '暂无会话，评估后点「保存为本周会话」' }}
            />
          </Card>
        </Col>
      </Row>

      <div style={{ marginTop: 16 }}>
        <RobustnessPanel
          strategy={strategyId}
          baselineParams={(paramsWatch as Record<string, number>) || {}}
          primarySymbol={symbolWatch}
          compact
        />
      </div>
    </div>
  );
};

export default SignalMonitor;
