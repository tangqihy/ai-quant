import React, { useState, useEffect, useCallback } from 'react';
import { Card, Row, Col, Statistic, Table, Select, Tag, Spin, message, Empty } from 'antd';
import {
  CheckCircleOutlined,
  WarningOutlined,
  CloseCircleOutlined,
  BarChartOutlined,
  FundOutlined,
} from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
import type { ColumnsType } from 'antd/es/table';
import {
  getFactorIC,
  getFactorSummary,
  FactorICData,
  FactorItem,
  EventFactor,
  FactorSummary,
} from '../services/api';
import { GlitchText } from '../components/common/GlitchText';

const NEON_CYAN = '#00f0ff';
const NEON_PINK = '#ff00a0';
const NEON_GREEN = '#00ff41';
const CARD_BG = 'rgba(5, 8, 21, 0.85)';
const CARD_BORDER = 'rgba(0, 240, 255, 0.18)';

const verdictConfig: Record<string, { color: string; text: string }> = {
  effective: { color: '#00ff41', text: '有效' },
  weak: { color: '#faad14', text: '弱信号' },
  invalid: { color: '#ff4d4f', text: '无效' },
};

const categoryColors: Record<string, string> = {
  价值: '#00f0ff',
  动量: '#ff00a0',
  质量: '#7c3aed',
  波动率: '#faad14',
  流动性: '#00ff41',
  情绪: '#ff6b6b',
  技术: '#36cfc9',
  事件: '#f759ab',
  基本面: '#597ef7',
};

const FactorAnalysis: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [factorData, setFactorData] = useState<FactorICData | null>(null);
  const [summary, setSummary] = useState<FactorSummary | null>(null);
  const [selectedFactor, setSelectedFactor] = useState<string>('');

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [icData, summaryData] = await Promise.all([getFactorIC(), getFactorSummary()]);
      setFactorData(icData);
      setSummary(summaryData);
      // 默认选中第一个有效因子
      const firstEffective = icData.factors.find((f) => f.verdict === 'effective');
      if (firstEffective) {
        setSelectedFactor(firstEffective.name);
      } else if (icData.factors.length > 0) {
        setSelectedFactor(icData.factors[0].name);
      }
    } catch (e: any) {
      // 提取后端返回的真实错误信息，而非 generic 的 axios 文案
      const detail = e?.response?.data?.detail || e?.message || '';
      message.error('获取因子数据失败: ' + detail);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // ---------- 分组收益图 option ----------
  const currentFactor = factorData?.factors.find((f) => f.name === selectedFactor);

  const groupReturnOption =
    currentFactor && currentFactor.group_returns.length > 0
      ? {
          tooltip: {
            trigger: 'axis',
            backgroundColor: 'rgba(5, 8, 21, 0.92)',
            borderColor: NEON_CYAN,
            textStyle: { color: '#e0e0e0', fontFamily: "'JetBrains Mono', monospace", fontSize: 12 },
            axisPointer: { type: 'shadow' },
          },
          grid: { left: '3%', right: '4%', bottom: '8%', top: '12%', containLabel: true },
          xAxis: {
            type: 'category',
            data: currentFactor.group_labels.length > 0
              ? currentFactor.group_labels
              : currentFactor.group_returns.map((_, i) => `G${i + 1}`),
            axisLabel: { color: 'rgba(0, 240, 255, 0.6)', fontFamily: "'JetBrains Mono', monospace" },
            axisLine: { lineStyle: { color: 'rgba(0, 240, 255, 0.3)' } },
          },
          yAxis: {
            type: 'value',
            name: '收益率(%)',
            nameTextStyle: { color: 'rgba(0, 240, 255, 0.5)' },
            axisLabel: {
              color: 'rgba(0, 240, 255, 0.6)',
              formatter: (v: number) => v.toFixed(2) + '%',
            },
            axisLine: { lineStyle: { color: 'rgba(0, 240, 255, 0.3)' } },
            splitLine: { lineStyle: { color: 'rgba(0, 240, 255, 0.08)' } },
          },
          series: [
            {
              name: '分组收益',
              type: 'bar',
              barWidth: '55%',
              data: currentFactor.group_returns.map((v) => ({
                value: v,
                itemStyle: {
                  color: v >= 0
                    ? {
                        type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
                        colorStops: [
                          { offset: 0, color: 'rgba(0, 255, 65, 0.85)' },
                          { offset: 1, color: 'rgba(0, 255, 65, 0.15)' },
                        ],
                      }
                    : {
                        type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
                        colorStops: [
                          { offset: 0, color: 'rgba(255, 0, 64, 0.15)' },
                          { offset: 1, color: 'rgba(255, 0, 64, 0.85)' },
                        ],
                      },
                  borderRadius: v >= 0 ? [4, 4, 0, 0] : [0, 0, 4, 4],
                },
              })),
              label: {
                show: true,
                position: 'top',
                formatter: (p: any) => p.value.toFixed(2) + '%',
                color: 'rgba(0, 240, 255, 0.8)',
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 11,
              },
            },
          ],
        }
      : null;

  // ---------- IC表格列 ----------
  const icColumns: ColumnsType<FactorItem> = [
    {
      title: '因子名称',
      dataIndex: 'display_name',
      key: 'display_name',
      width: 140,
      render: (text: string, record: FactorItem) => (
        <span style={{ color: categoryColors[record.category] || NEON_CYAN, fontWeight: 600 }}>
          {text}
        </span>
      ),
    },
    {
      title: '类别',
      dataIndex: 'category',
      key: 'category',
      width: 80,
      filters: factorData
        ? [...new Set(factorData.factors.map((f) => f.category))].map((c) => ({ text: c, value: c }))
        : [],
      onFilter: (value, record) => record.category === value,
      render: (cat: string) => (
        <Tag
          style={{
            background: 'transparent',
            border: `1px solid ${categoryColors[cat] || NEON_CYAN}`,
            color: categoryColors[cat] || NEON_CYAN,
            fontFamily: "'JetBrains Mono', monospace",
          }}
        >
          {cat}
        </Tag>
      ),
    },
    {
      title: 'ICIR',
      dataIndex: 'icir',
      key: 'icir',
      width: 100,
      sorter: (a, b) => Math.abs(a.icir) - Math.abs(b.icir),
      defaultSortOrder: 'descend',
      render: (v: number) => {
        const absV = Math.abs(v);
        const ratio = Math.min(absV / 3, 1);
        const color = absV >= 2 ? NEON_GREEN : absV >= 1 ? '#faad14' : '#ff4d4f';
        return (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div
              style={{
                width: 48,
                height: 6,
                borderRadius: 3,
                background: 'rgba(255,255,255,0.06)',
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  width: `${ratio * 100}%`,
                  height: '100%',
                  borderRadius: 3,
                  background: `linear-gradient(90deg, ${color}80, ${color})`,
                  boxShadow: `0 0 6px ${color}60`,
                }}
              />
            </div>
            <span style={{ color, fontFamily: "'JetBrains Mono', monospace", fontSize: 12, fontWeight: 600 }}>
              {v.toFixed(3)}
            </span>
          </div>
        );
      },
    },
    {
      title: 'IC均值',
      dataIndex: 'ic_mean',
      key: 'ic_mean',
      width: 100,
      sorter: (a, b) => a.ic_mean - b.ic_mean,
      render: (v: number) => (
        <span
          style={{
            color: v >= 0 ? NEON_GREEN : '#ff0040',
            fontFamily: "'JetBrains Mono', monospace",
          }}
        >
          {v.toFixed(4)}
        </span>
      ),
    },
    {
      title: 'IC标准差',
      dataIndex: 'ic_std',
      key: 'ic_std',
      width: 100,
      render: (v: number) => (
        <span style={{ color: 'rgba(0, 240, 255, 0.6)', fontFamily: "'JetBrains Mono', monospace" }}>
          {v.toFixed(4)}
        </span>
      ),
    },
    {
      title: '有效性',
      dataIndex: 'verdict',
      key: 'verdict',
      width: 100,
      filters: [
        { text: '有效', value: 'effective' },
        { text: '弱信号', value: 'weak' },
        { text: '无效', value: 'invalid' },
      ],
      onFilter: (value, record) => record.verdict === value,
      render: (v: 'effective' | 'weak' | 'invalid') => {
        const cfg = verdictConfig[v] || verdictConfig.invalid;
        return (
          <Tag
            style={{
              background: 'transparent',
              border: `1px solid ${cfg.color}`,
              color: cfg.color,
              fontWeight: 600,
              fontFamily: "'JetBrains Mono', monospace",
            }}
          >
            {cfg.text}
          </Tag>
        );
      },
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
      render: (text: string) => (
        <span style={{ color: 'rgba(255,255,255,0.5)', fontSize: 12 }}>{text}</span>
      ),
    },
  ];

  // ---------- 事件因子表格列 ----------
  const eventColumns: ColumnsType<EventFactor> = [
    {
      title: '事件因子',
      dataIndex: 'display_name',
      key: 'display_name',
      width: 160,
      render: (text: string) => (
        <span style={{ color: NEON_PINK, fontWeight: 600 }}>{text}</span>
      ),
    },
    {
      title: 'ICIR',
      dataIndex: 'icir',
      key: 'icir',
      width: 100,
      sorter: (a, b) => Math.abs(a.icir) - Math.abs(b.icir),
      render: (v: number) => {
        const absV = Math.abs(v);
        const color = absV >= 2 ? NEON_GREEN : absV >= 1 ? '#faad14' : '#ff4d4f';
        return (
          <span style={{ color, fontFamily: "'JetBrains Mono', monospace", fontWeight: 600 }}>
            {v.toFixed(3)}
          </span>
        );
      },
    },
    {
      title: '判定',
      dataIndex: 'verdict',
      key: 'verdict',
      width: 90,
      render: (v: string) => {
        const color = v === 'effective' ? NEON_GREEN : v === 'weak' ? '#faad14' : '#ff4d4f';
        return (
          <Tag
            style={{
              background: 'transparent',
              border: `1px solid ${color}`,
              color,
              fontFamily: "'JetBrains Mono', monospace",
            }}
          >
            {v === 'effective' ? '有效' : v === 'weak' ? '弱信号' : '无效'}
          </Tag>
        );
      },
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
      render: (text: string) => (
        <span style={{ color: 'rgba(255,255,255,0.5)', fontSize: 12 }}>{text}</span>
      ),
    },
  ];

  // ---------- 卡片样式 ----------
  const cardStyle: React.CSSProperties = {
    background: CARD_BG,
    border: `1px solid ${CARD_BORDER}`,
    borderRadius: 8,
    backdropFilter: 'blur(12px)',
  };

  return (
    <div style={{ fontFamily: "'JetBrains Mono', monospace" }}>
      {/* 页面标题 */}
      <div style={{ marginBottom: 24, display: 'flex', alignItems: 'center', gap: 12 }}>
        <FundOutlined style={{ color: NEON_CYAN, fontSize: 24 }} />
        <GlitchText text="因子分析" />
        {factorData?.updated_at && (
          <span style={{ color: 'rgba(0, 240, 255, 0.4)', fontSize: 12, marginLeft: 'auto' }}>
            更新: {factorData.updated_at}
          </span>
        )}
      </div>

      <Spin spinning={loading}>
        {/* ========== 概览卡片 ========== */}
        <Row gutter={[16, 16]} style={{ marginBottom: 20 }}>
          <Col xs={12} sm={6}>
            <Card style={cardStyle} bodyStyle={{ padding: '16px 20px' }}>
              <Statistic
                title={<span style={{ color: 'rgba(0, 240, 255, 0.5)', fontSize: 12 }}>有效因子</span>}
                value={summary?.effective_count ?? 0}
                prefix={<CheckCircleOutlined style={{ color: NEON_GREEN }} />}
                valueStyle={{ color: NEON_GREEN, fontFamily: "'JetBrains Mono', monospace", fontSize: 28 }}
              />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card style={cardStyle} bodyStyle={{ padding: '16px 20px' }}>
              <Statistic
                title={<span style={{ color: 'rgba(0, 240, 255, 0.5)', fontSize: 12 }}>弱信号因子</span>}
                value={summary?.weak_count ?? 0}
                prefix={<WarningOutlined style={{ color: '#faad14' }} />}
                valueStyle={{ color: '#faad14', fontFamily: "'JetBrains Mono', monospace", fontSize: 28 }}
              />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card style={cardStyle} bodyStyle={{ padding: '16px 20px' }}>
              <Statistic
                title={<span style={{ color: 'rgba(0, 240, 255, 0.5)', fontSize: 12 }}>无效因子</span>}
                value={summary?.invalid_count ?? 0}
                prefix={<CloseCircleOutlined style={{ color: '#ff4d4f' }} />}
                valueStyle={{ color: '#ff4d4f', fontFamily: "'JetBrains Mono', monospace", fontSize: 28 }}
              />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card style={cardStyle} bodyStyle={{ padding: '16px 20px' }}>
              <Statistic
                title={<span style={{ color: 'rgba(0, 240, 255, 0.5)', fontSize: 12 }}>测试截面数</span>}
                value={summary?.cross_sections ?? 0}
                prefix={<BarChartOutlined style={{ color: NEON_CYAN }} />}
                valueStyle={{ color: NEON_CYAN, fontFamily: "'JetBrains Mono', monospace", fontSize: 28 }}
              />
            </Card>
          </Col>
        </Row>

        {/* 测试参数条 */}
        {summary && (
          <Card
            style={{ ...cardStyle, marginBottom: 20 }}
            bodyStyle={{ padding: '10px 20px', display: 'flex', gap: 32, flexWrap: 'wrap' }}
          >
            <span style={{ color: 'rgba(0, 240, 255, 0.45)', fontSize: 12 }}>
              测试周期: <span style={{ color: NEON_CYAN }}>{summary.test_period}</span>
            </span>
            <span style={{ color: 'rgba(0, 240, 255, 0.45)', fontSize: 12 }}>
              前瞻天数: <span style={{ color: NEON_CYAN }}>{summary.forward_days}日</span>
            </span>
            <span style={{ color: 'rgba(0, 240, 255, 0.45)', fontSize: 12 }}>
              中性化: <span style={{ color: NEON_CYAN }}>{summary.neutralization}</span>
            </span>
            <span style={{ color: 'rgba(0, 240, 255, 0.45)', fontSize: 12 }}>
              因子总数: <span style={{ color: NEON_CYAN }}>{summary.total_factors}</span>
            </span>
          </Card>
        )}

        {/* ========== 因子IC表格 ========== */}
        <Card
          title={
            <span style={{ color: NEON_CYAN, fontFamily: "'JetBrains Mono', monospace" }}>
              因子IC检验结果
            </span>
          }
          style={{ ...cardStyle, marginBottom: 20 }}
          bodyStyle={{ padding: 0 }}
        >
          {factorData && factorData.factors.length > 0 ? (
            <Table
              columns={icColumns}
              dataSource={factorData.factors.map((f) => ({ ...f, key: f.name }))}
              pagination={{ pageSize: 10, showSizeChanger: true, showTotal: (t) => `共 ${t} 个因子` }}
              size="small"
              scroll={{ x: 780 }}
              style={{ background: 'transparent' }}
            />
          ) : (
            <Empty
              description={<span style={{ color: 'rgba(0, 240, 255, 0.4)' }}>暂无因子数据</span>}
              style={{ padding: 40 }}
            />
          )}
        </Card>

        {/* ========== 分组收益图 ========== */}
        <Card
          title={
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
              <span style={{ color: NEON_CYAN, fontFamily: "'JetBrains Mono', monospace" }}>
                分组收益图
              </span>
              <Select
                value={selectedFactor}
                onChange={setSelectedFactor}
                style={{ width: 200 }}
                placeholder="选择因子"
                size="small"
                showSearch
                optionFilterProp="label"
                options={factorData?.factors.map((f) => ({
                  value: f.name,
                  label: `${f.display_name} (${f.category})`,
                }))}
              />
            </div>
          }
          style={{ ...cardStyle, marginBottom: 20 }}
          bodyStyle={{ padding: '12px 16px' }}
        >
          {groupReturnOption ? (
            <ReactECharts option={groupReturnOption} style={{ height: 360, width: '100%' }} />
          ) : (
            <div
              style={{
                height: 360,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'rgba(0, 240, 255, 0.3)',
              }}
            >
              请选择一个因子查看分组收益
            </div>
          )}
          {currentFactor && (
            <div style={{ textAlign: 'center', color: 'rgba(0, 240, 255, 0.45)', fontSize: 12, marginTop: 4 }}>
              {currentFactor.display_name} — {currentFactor.description}
            </div>
          )}
        </Card>

        {/* ========== 事件因子表格 ========== */}
        {factorData && factorData.event_factors && factorData.event_factors.length > 0 && (
          <Card
            title={
              <span style={{ color: NEON_PINK, fontFamily: "'JetBrains Mono', monospace" }}>
                事件因子
              </span>
            }
            style={cardStyle}
            bodyStyle={{ padding: 0 }}
          >
            <Table
              columns={eventColumns}
              dataSource={factorData.event_factors.map((f) => ({ ...f, key: f.name }))}
              pagination={false}
              size="small"
              scroll={{ x: 500 }}
              style={{ background: 'transparent' }}
            />
          </Card>
        )}

        {/* 无数据提示 */}
        {!loading && factorData && factorData.factors.length === 0 && (
          <Card style={{ ...cardStyle, textAlign: 'center', padding: 40 }}>
            <Empty
              description={
                <div style={{ color: 'rgba(0, 240, 255, 0.5)', fontSize: 14, lineHeight: 1.8 }}>
                  {factorData.needs_generation ? (
                    <>
                      <div>因子IC数据尚未生成</div>
                      <div style={{ fontSize: 12, marginTop: 8, color: 'rgba(0, 240, 255, 0.35)' }}>
                        请在后端运行 <code style={{ color: NEON_GREEN }}>python scripts/run_factor_ic.py</code>
                        <br />
                        该脚本会下载行情数据并计算各因子的IC/ICIR，生成 <code style={{ color: NEON_GREEN }}>data/factor_ic.json</code>
                      </div>
                    </>
                  ) : (
                    '暂无因子数据'
                  )}
                </div>
              }
            />
          </Card>
        )}
        {!loading && !factorData && (
          <Card style={{ ...cardStyle, textAlign: 'center', padding: 60 }}>
            <Empty
              description={
                <span style={{ color: 'rgba(0, 240, 255, 0.4)', fontSize: 14 }}>
                  未找到因子数据，请确认后端因子分析服务已运行
                </span>
              }
            />
          </Card>
        )}
      </Spin>
    </div>
  );
};

export default FactorAnalysis;
