import type { CardType, CanvasStatus } from '../../services/canvasApi';

export const CARD_TYPE_LABEL: Record<CardType, string> = {
  note: '笔记',
  thesis: '论点',
  catalyst: '催化剂',
  risk: '风险',
  financial: '财务',
  valuation: '估值',
  sentiment: '情绪',
  entry_plan: '入场计划',
  exit_plan: '出场计划',
  trade_record: '交易记录',
};

export const CARD_TYPE_COLOR: Record<CardType, string> = {
  note: 'default',
  thesis: 'blue',
  catalyst: 'orange',
  risk: 'red',
  financial: 'cyan',
  valuation: 'geekblue',
  sentiment: 'purple',
  entry_plan: 'green',
  exit_plan: 'volcano',
  trade_record: 'gold',
};

export const CANVAS_STATUS_LABEL: Record<CanvasStatus, string> = {
  watching: '观察中',
  holding: '持仓中',
  sold: '已卖出',
  archived: '已归档',
};

export const CANVAS_STATUS_COLOR: Record<CanvasStatus, string> = {
  watching: 'blue',
  holding: 'green',
  sold: 'gold',
  archived: 'default',
};

export const DIRECTION_LABEL: Record<string, { label: string; color: string }> = {
  bullish: { label: '看多', color: 'red' },
  bearish: { label: '看空', color: 'green' },
  neutral: { label: '中性', color: 'default' },
};
