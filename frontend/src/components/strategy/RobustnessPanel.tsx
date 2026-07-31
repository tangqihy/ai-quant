import React, { useMemo, useState } from 'react';
import {
  Button,
  Card,
  Checkbox,
  Col,
  InputNumber,
  Radio,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
  message,
} from 'antd';
import { ExperimentOutlined } from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
import {
  runRobustness,
  RobustnessRequest,
  RobustnessResult,
} from '../../services/api';
import { useWatchlist } from '../../hooks/useWatchlist';

const { Text } = Typography;

const CLASS_COLOR: Record<string, string> = {
  robust: 'success',
  moderate: 'warning',
  sensitive: 'error',
};

const CLASS_LABEL: Record<string, string> = {
  robust: '稳健',
  moderate: '中等',
  sensitive: '敏感（易过拟合）',
};

export interface RobustnessPanelProps {
  strategy: string;
  baselineParams: Record<string, number>;
  /** 当前页主标的，默认并入标的池 */
  primarySymbol?: string;
  startDate?: string;
  endDate?: string;
  compact?: boolean;
}

const RobustnessPanel: React.FC<RobustnessPanelProps> = ({
  strategy,
  baselineParams,
  primarySymbol,
  startDate,
  endDate,
  compact = false,
}) => {
  const { stocks, isLoaded } = useWatchlist();
  const [mode, setMode] = useState<'neighborhood' | 'monte_carlo'>('neighborhood');
  const [includeWatchlist, setIncludeWatchlist] = useState(true);
  const [extraSymbols, setExtraSymbols] = useState<string[]>([]);
  const [perturbationPct, setPerturbationPct] = useState(25);
  const [nSteps, setNSteps] = useState(5);
  const [nSamples, setNSamples] = useState(20);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<RobustnessResult | null>(null);

  const watchlistCodes = useMemo(() => stocks.map((s) => s.symbol), [stocks]);

  const symbols = useMemo(() => {
    const set = new Set<string>();
    if (primarySymbol?.trim()) set.add(primarySymbol.trim());
    if (includeWatchlist) watchlistCodes.forEach((c) => set.add(c));
    extraSymbols.forEach((c) => {
      const t = c.trim();
      if (t) set.add(t);
    });
    return Array.from(set);
  }, [primarySymbol, includeWatchlist, watchlistCodes, extraSymbols]);

  const handleRun = async () => {
    if (symbols.length === 0) {
      message.warning('请至少选择一个研究标的（当前股票或自选）');
      return;
    }
    setLoading(true);
    try {
      const body: RobustnessRequest = {
        symbols,
        strategy,
        baseline_params: baselineParams,
        start_date: startDate,
        end_date: endDate,
        mode,
        perturbation_pct: perturbationPct / 100,
        n_steps: nSteps,
        n_samples: nSamples,
        max_runs: 200,
      };
      const res = await runRobustness(body);
      if (!res.success) {
        message.error(res.error || '稳健性检验失败');
        return;
      }
      setResult(res);
      if (res.truncated) {
        message.warning('已达最大回测次数上限，结果为截断采样');
      } else {
        message.success(`完成 ${res.n_runs} 次回测`);
      }
    } catch (e: any) {
      message.error(e?.message || '稳健性检验失败');
    } finally {
      setLoading(false);
    }
  };

  const summary = result?.summary;
  const histOption = useMemo(() => {
    if (!result?.runs?.length) return null;
    const returns = result.runs
      .filter((r) => r.success && r.total_return != null)
      .map((r) => Number(r.total_return));
    if (!returns.length) return null;

    const min = Math.min(...returns);
    const max = Math.max(...returns);
    const bins = 12;
    const width = max === min ? 1 : (max - min) / bins;
    const counts = new Array(bins).fill(0);
    const labels: string[] = [];
    for (let i = 0; i < bins; i++) {
      const a = min + i * width;
      const b = a + width;
      labels.push(`${a.toFixed(1)}`);
      returns.forEach((v) => {
        if (v >= a && (i === bins - 1 ? v <= b : v < b)) counts[i] += 1;
      });
    }
    const baselineRet = summary?.baseline_metrics?.total_return;
    let baselineLabel: string | undefined;
    if (baselineRet != null && labels.length) {
      let bestIdx = 0;
      let bestDist = Infinity;
      for (let i = 0; i < bins; i++) {
        const center = min + (i + 0.5) * width;
        const d = Math.abs(center - baselineRet);
        if (d < bestDist) {
          bestDist = d;
          bestIdx = i;
        }
      }
      baselineLabel = labels[bestIdx];
    }

    return {
      tooltip: { trigger: 'axis' },
      grid: { left: 40, right: 16, top: 28, bottom: 40 },
      xAxis: {
        type: 'category',
        data: labels,
        name: '收益%',
        axisLabel: { color: 'rgba(0,255,65,0.55)', fontSize: 10 },
      },
      yAxis: {
        type: 'value',
        name: '次数',
        axisLabel: { color: 'rgba(0,255,65,0.55)' },
        splitLine: { lineStyle: { color: 'rgba(0,255,65,0.08)' } },
      },
      series: [
        {
          type: 'bar',
          data: counts,
          itemStyle: { color: 'rgba(0,240,255,0.65)' },
          markLine:
            baselineLabel != null
              ? {
                  symbol: 'none',
                  label: { formatter: `baseline ${baselineRet?.toFixed(1)}%`, color: '#ffcc00' },
                  data: [
                    {
                      xAxis: baselineLabel,
                      lineStyle: { color: '#ffcc00', type: 'dashed' },
                    },
                  ],
                }
              : undefined,
        },
      ],
    };
  }, [result, summary]);

  const runColumns = [
    {
      title: '标的',
      dataIndex: 'symbol',
      width: 90,
    },
    {
      title: '基准',
      dataIndex: 'is_baseline',
      width: 60,
      render: (v: boolean) => (v ? <Tag color="gold">是</Tag> : '—'),
    },
    {
      title: '参数',
      dataIndex: 'params',
      ellipsis: true,
      render: (p: Record<string, number>) =>
        Object.entries(p || {})
          .map(([k, v]) => `${k}=${v}`)
          .join(', '),
    },
    {
      title: '收益%',
      dataIndex: 'total_return',
      width: 80,
      sorter: (a: any, b: any) => (a.total_return ?? 0) - (b.total_return ?? 0),
      render: (v: number | null) => (v == null ? '—' : v.toFixed(2)),
    },
    {
      title: 'Sharpe',
      dataIndex: 'sharpe',
      width: 80,
      sorter: (a: any, b: any) => (a.sharpe ?? 0) - (b.sharpe ?? 0),
      render: (v: number | null) => (v == null ? '—' : Number(v).toFixed(3)),
    },
    {
      title: '回撤%',
      dataIndex: 'max_drawdown',
      width: 80,
      render: (v: number | null) => (v == null ? '—' : v.toFixed(2)),
    },
  ];

  const symbolColumns = [
    { title: '标的', dataIndex: 'symbol', width: 90 },
    {
      title: 'Baseline收益%',
      dataIndex: 'baseline_return',
      render: (v: number | null) => (v == null ? '—' : v.toFixed(2)),
    },
    {
      title: '扰动中位收益%',
      dataIndex: 'median_return',
      render: (v: number | null) => (v == null ? '—' : v.toFixed(2)),
    },
    {
      title: '稳定',
      dataIndex: 'stable',
      width: 70,
      render: (v: boolean) => (v ? <Tag color="green">是</Tag> : <Tag>否</Tag>),
    },
    { title: '次数', dataIndex: 'n_runs', width: 60 },
  ];

  return (
    <Card
      size="small"
      title={
        <Space>
          <ExperimentOutlined style={{ color: '#00f0ff' }} />
          <span style={{ color: '#00f0ff' }}>参数稳健性检验</span>
        </Space>
      }
      style={{ marginBottom: 16 }}
      extra={
        summary ? (
          <Tag color={CLASS_COLOR[summary.classification] || 'default'}>
            {CLASS_LABEL[summary.classification] || summary.classification}
          </Tag>
        ) : null
      }
    >
      <Space direction="vertical" style={{ width: '100%' }} size="middle">
        <Space wrap align="center">
          <span>模式</span>
          <Radio.Group
            value={mode}
            onChange={(e) => setMode(e.target.value)}
            optionType="button"
            buttonStyle="solid"
            size="small"
          >
            <Radio.Button value="neighborhood">邻域扫描</Radio.Button>
            <Radio.Button value="monte_carlo">Monte Carlo</Radio.Button>
          </Radio.Group>
          <span>±%</span>
          <InputNumber
            size="small"
            min={5}
            max={100}
            value={perturbationPct}
            onChange={(v) => setPerturbationPct(Number(v) || 25)}
          />
          {mode === 'neighborhood' ? (
            <>
              <span>每参数点数</span>
              <InputNumber
                size="small"
                min={2}
                max={21}
                value={nSteps}
                onChange={(v) => setNSteps(Number(v) || 5)}
              />
            </>
          ) : (
            <>
              <span>采样组数</span>
              <InputNumber
                size="small"
                min={5}
                max={100}
                value={nSamples}
                onChange={(v) => setNSamples(Number(v) || 20)}
              />
            </>
          )}
          <Checkbox
            checked={includeWatchlist}
            disabled={!isLoaded}
            onChange={(e) => setIncludeWatchlist(e.target.checked)}
          >
            并入自选（{watchlistCodes.length}）
          </Checkbox>
          <Select
            mode="tags"
            size="small"
            style={{ minWidth: compact ? 140 : 200 }}
            placeholder="额外代码"
            value={extraSymbols}
            onChange={setExtraSymbols}
            tokenSeparators={[',', ' ']}
          />
          <Button type="primary" size="small" loading={loading} onClick={handleRun}>
            运行检验
          </Button>
        </Space>
        <Text type="secondary" style={{ fontSize: 12 }}>
          标的池 {symbols.length} 只
          {primarySymbol ? `（含当前 ${primarySymbol}）` : ''}
          ；围绕当前参数做扰动后批跑回测，看收益分布与跨标的稳定性。
        </Text>

        {summary && (
          <>
            <Row gutter={[12, 12]}>
              <Col xs={12} sm={8} md={4}>
                <Statistic
                  title="平台区占比"
                  value={(summary.stability_score ?? 0) * 100}
                  precision={1}
                  suffix="%"
                  styles={{ content: { color: '#00f0ff', fontSize: 20 } }}
                />
              </Col>
              <Col xs={12} sm={8} md={4}>
                <Statistic
                  title="Baseline Sharpe 分位"
                  value={summary.baseline_sharpe_percentile ?? '—'}
                  suffix={summary.baseline_sharpe_percentile != null ? '%' : undefined}
                  styles={{ content: { color: '#ffcc00', fontSize: 20 } }}
                />
              </Col>
              <Col xs={12} sm={8} md={4}>
                <Statistic
                  title="跨标的稳定比"
                  value={(summary.cross_symbol?.stability_ratio ?? 0) * 100}
                  precision={1}
                  suffix="%"
                  styles={{ content: { color: '#00ff41', fontSize: 20 } }}
                />
              </Col>
              <Col xs={12} sm={8} md={4}>
                <Statistic
                  title="收益中位%"
                  value={summary.distribution?.total_return?.p50 ?? '—'}
                  styles={{ content: { fontSize: 20 } }}
                />
              </Col>
              <Col xs={12} sm={8} md={4}>
                <Statistic
                  title="收益 P5 / P95"
                  value={
                    summary.distribution?.total_return?.p5 != null
                      ? `${summary.distribution.total_return.p5} / ${summary.distribution.total_return.p95}`
                      : '—'
                  }
                  styles={{ content: { fontSize: 16 } }}
                />
              </Col>
              <Col xs={12} sm={8} md={4}>
                <Statistic
                  title="有效回测"
                  value={`${summary.n_ok}/${result?.n_runs ?? 0}`}
                  styles={{ content: { fontSize: 20 } }}
                />
              </Col>
            </Row>
            <Text type="secondary" style={{ fontSize: 12 }}>
              Baseline 分位偏高（如 ≥90%）且平台区窄，通常意味着参数落在尖峰，实盘更易失效。
            </Text>
            <Row gutter={[16, 16]}>
              <Col xs={24} lg={12}>
                <Card size="small" title="收益分布（相对 baseline）" style={{ height: 280 }}>
                  {histOption ? (
                    <ReactECharts option={histOption} style={{ height: 220 }} />
                  ) : (
                    <div style={{ textAlign: 'center', padding: 40, opacity: 0.5 }}>暂无分布</div>
                  )}
                </Card>
              </Col>
              <Col xs={24} lg={12}>
                <Card size="small" title="跨标的稳定性" style={{ height: 280 }}>
                  <Table
                    size="small"
                    pagination={false}
                    scroll={{ y: 180 }}
                    columns={symbolColumns}
                    dataSource={(summary.cross_symbol?.symbols || []).map((r) => ({
                      ...r,
                      key: r.symbol,
                    }))}
                  />
                </Card>
              </Col>
            </Row>
            <Card size="small" title="全部扰动结果">
              <Table
                size="small"
                columns={runColumns}
                dataSource={(result?.runs || []).map((r, i) => ({ ...r, key: i }))}
                pagination={{ pageSize: 8 }}
                scroll={{ x: 640 }}
              />
            </Card>
          </>
        )}
      </Space>
    </Card>
  );
};

export default RobustnessPanel;
