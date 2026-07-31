import React, { useMemo } from 'react';
import { Button, Col, InputNumber, Row, Slider, Space, Tag, Typography } from 'antd';
import type { ParamSchema } from '../../services/signalApi';

const { Text } = Typography;

const FALLBACK_RANGE: Record<string, { min: number; max: number; step: number }> = {
  period: { min: 5, max: 30, step: 1 },
  oversold: { min: 10, max: 40, step: 1 },
  overbought: { min: 60, max: 90, step: 1 },
  short_window: { min: 2, max: 30, step: 1 },
  long_window: { min: 5, max: 120, step: 1 },
};

const PRESETS: Record<string, { label: string; params: Record<string, number> }[]> = {
  rsi: [
    { label: '默认', params: { period: 14, oversold: 30, overbought: 70 } },
    { label: '敏感', params: { period: 9, oversold: 25, overbought: 75 } },
    { label: '保守', params: { period: 21, oversold: 20, overbought: 80 } },
  ],
  ma_cross: [
    { label: '5/20', params: { short_window: 5, long_window: 20 } },
    { label: '3/10', params: { short_window: 3, long_window: 10 } },
    { label: '10/30', params: { short_window: 10, long_window: 30 } },
  ],
};

function resolveRange(p: ParamSchema) {
  const fb = FALLBACK_RANGE[p.name] || { min: 1, max: 100, step: 1 };
  return {
    min: p.min ?? fb.min,
    max: p.max ?? fb.max,
    step: (p as ParamSchema & { step?: number }).step ?? fb.step,
  };
}

export interface StrategyParamTunerProps {
  strategyId?: string;
  schema: ParamSchema[];
  /** Form.Item 注入；也可受控使用 */
  value?: Record<string, number>;
  onChange?: (next: Record<string, number>) => void;
  disabled?: boolean;
  /** 紧凑模式（分析页工具条） */
  compact?: boolean;
}

const StrategyParamTuner: React.FC<StrategyParamTunerProps> = ({
  strategyId,
  schema,
  value,
  onChange,
  disabled,
  compact = false,
}) => {
  const params = value || {};
  const presets = useMemo(() => (strategyId ? PRESETS[strategyId] || [] : []), [strategyId]);

  const setParam = (name: string, raw: number | null) => {
    const meta = schema.find((p) => p.name === name);
    const { min, max } = meta ? resolveRange(meta) : { min: 1, max: 999 };
    const nextVal = Math.min(max, Math.max(min, Number(raw ?? params[name] ?? min)));
    const next = { ...params, [name]: nextVal };

    // 均线交叉：短期不能大于等于长期
    if (name === 'short_window' && next.long_window != null && nextVal >= next.long_window) {
      next.long_window = Math.min(resolveRange({ name: 'long_window', type: 'int' }).max, nextVal + 1);
    }
    if (name === 'long_window' && next.short_window != null && nextVal <= next.short_window) {
      next.short_window = Math.max(2, nextVal - 1);
    }
    // RSI：超卖应小于超买
    if (name === 'oversold' && next.overbought != null && nextVal >= next.overbought) {
      next.overbought = Math.min(90, nextVal + 10);
    }
    if (name === 'overbought' && next.oversold != null && nextVal <= next.oversold) {
      next.oversold = Math.max(10, nextVal - 10);
    }
    onChange?.(next);
  };

  const activePreset = presets.find((p) =>
    Object.entries(p.params).every(([k, v]) => Number(params[k]) === v)
  );

  if (!schema.length) {
    return <Text type="secondary">该策略无可调参数</Text>;
  }

  return (
    <div>
      {presets.length > 0 && (
        <Space wrap size={[8, 8]} style={{ marginBottom: compact ? 8 : 12 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            预设
          </Text>
          {presets.map((p) => (
            <Button
              key={p.label}
              size="small"
              type={activePreset?.label === p.label ? 'primary' : 'default'}
              disabled={disabled}
              onClick={() => onChange?.({ ...params, ...p.params })}
            >
              {p.label}
            </Button>
          ))}
          {activePreset && (
            <Tag color="cyan" style={{ marginInlineEnd: 0 }}>
              {activePreset.label}
            </Tag>
          )}
        </Space>
      )}

      <Space direction="vertical" size={compact ? 8 : 14} style={{ width: '100%' }}>
        {schema.map((p) => {
          const { min, max, step } = resolveRange(p);
          const current = Number(params[p.name] ?? p.default ?? min);
          return (
            <div key={p.name}>
              <Row justify="space-between" align="middle" style={{ marginBottom: 4 }}>
                <Col>
                  <Text style={{ color: 'rgba(var(--accent-rgb),0.85)', fontSize: compact ? 12 : 13 }}>
                    {p.description || p.name}
                  </Text>
                </Col>
                <Col>
                  <InputNumber
                    size="small"
                    min={min}
                    max={max}
                    step={step}
                    value={current}
                    disabled={disabled}
                    onChange={(v) => setParam(p.name, v)}
                    style={{ width: 72 }}
                  />
                </Col>
              </Row>
              <Slider
                min={min}
                max={max}
                step={step}
                value={current}
                disabled={disabled}
                onChange={(v) => setParam(p.name, v)}
                tooltip={{ formatter: (v) => `${v}` }}
                styles={{
                  track: { background: 'rgba(var(--accent-rgb),0.55)' },
                  rail: { background: 'rgba(var(--accent-rgb),0.12)' },
                }}
              />
              <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: -6 }}>
                <Text type="secondary" style={{ fontSize: 11 }}>
                  {min}
                </Text>
                <Text type="secondary" style={{ fontSize: 11 }}>
                  {max}
                </Text>
              </div>
            </div>
          );
        })}
      </Space>
    </div>
  );
};

export default StrategyParamTuner;
