import axios from 'axios';
import { setupAuthInterceptor } from './auth';

const request = axios.create({
  baseURL: '/api',
  timeout: 60000,
});

setupAuthInterceptor(request);

export interface ParamSchema {
  name: string;
  type: string;
  default?: number | string;
  description?: string;
  min?: number;
  max?: number;
  step?: number;
}

export interface StrategyMeta {
  id: string;
  name: string;
  description: string;
  params: string[];
  param_schema: ParamSchema[];
}

export interface SignalResult {
  symbol: string;
  strategy: string;
  strategy_name?: string;
  period: string;
  params: Record<string, number | string>;
  mode?: 'live' | 'replay';
  as_of: string;
  as_of_requested?: string | null;
  bar_index?: number;
  bar_total?: number;
  bars_used?: number;
  window_clock_note?: string | null;
  evaluated_at: string;
  action: 'BUY' | 'SELL' | 'HOLD';
  buy_signal: boolean;
  sell_signal: boolean;
  reason: string;
  in_trading_window: boolean;
  window_reason: string;
  snapshot: Record<string, number | null | undefined>;
  quote_price?: number | null;
  suggested_price?: number | null;
  executable: boolean;
  session_id?: string;
  session?: StrategySession;
}

export interface ReplayBar {
  index: number;
  step: number;
  date: string;
  action: 'BUY' | 'SELL' | 'HOLD';
  buy_signal: boolean;
  sell_signal: boolean;
  reason: string;
  close?: number | null;
  in_trading_window: boolean;
  window_reason: string;
  snapshot: Record<string, number | null | undefined>;
  executable: boolean;
}

export interface ReplayEvent {
  index: number;
  step: number;
  date: string;
  action: 'BUY' | 'SELL';
  reason: string;
  close?: number | null;
  in_trading_window: boolean;
}

export interface ReplayKLine {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface ReplayTimeline {
  symbol: string;
  strategy: string;
  strategy_name?: string;
  period: string;
  params: Record<string, number | string>;
  mode: 'replay';
  as_of_requested?: string | null;
  warm_up: number;
  bar_total: number;
  step_total: number;
  klines?: ReplayKLine[];
  bars: ReplayBar[];
  events: ReplayEvent[];
  window_clock_note?: string;
}

export interface StrategySession {
  id: string;
  name: string;
  symbol: string;
  strategy: string;
  params: Record<string, number | string>;
  period: string;
  position_pct: number;
  stop_loss_pct: number;
  stop_profit_pct: number;
  enabled: boolean;
  observe_factors?: string[];
  created_at?: string;
  updated_at?: string;
}

export async function getSignalStrategies(): Promise<StrategyMeta[]> {
  const { data } = await request.get('/signals/strategies');
  return data?.data ?? [];
}

export async function evaluateSignal(body: {
  symbol: string;
  strategy: string;
  params?: Record<string, number | string>;
  period?: string;
  as_of?: string | null;
  lookback_days?: number;
}): Promise<{ success: boolean; data?: SignalResult; error?: string; message?: string }> {
  const { data } = await request.post('/signals/evaluate', body);
  return data;
}

export async function loadReplayTimeline(body: {
  symbol: string;
  strategy: string;
  params?: Record<string, number | string>;
  period?: string;
  as_of?: string | null;
  lookback_days?: number;
  warm_up?: number;
}): Promise<{ success: boolean; data?: ReplayTimeline; error?: string; message?: string }> {
  const { data } = await request.post('/signals/replay', body);
  return data;
}

export async function listSessions(): Promise<StrategySession[]> {
  const { data } = await request.get('/signals/sessions');
  return data?.data ?? [];
}

export async function getActiveSession(): Promise<StrategySession | null> {
  const { data } = await request.get('/signals/sessions/active');
  return data?.data ?? null;
}

export async function saveSession(
  body: Partial<StrategySession> & { symbol: string; strategy: string; exclusive_enable?: boolean }
): Promise<StrategySession> {
  const { data } = await request.post('/signals/sessions', body);
  return data.data;
}

export async function enableSession(sessionId: string, enabled: boolean) {
  const { data } = await request.post(`/signals/sessions/${sessionId}/enable`, null, {
    params: { enabled },
  });
  return data;
}

export async function deleteSession(sessionId: string) {
  const { data } = await request.delete(`/signals/sessions/${sessionId}`);
  return data;
}

export async function evaluateSession(sessionId: string) {
  const { data } = await request.post(`/signals/sessions/${sessionId}/evaluate`);
  return data as { success: boolean; data?: SignalResult; error?: string; message?: string };
}

export async function executeSignal(body: {
  symbol: string;
  strategy: string;
  params?: Record<string, number | string>;
  period?: string;
  as_of?: string | null;
  position_pct?: number;
  order_type?: 'MARKET' | 'LIMIT';
  force?: boolean;
  stop_loss_pct?: number;
  stop_profit_pct?: number;
}) {
  const { data } = await request.post('/simulation/execute-signal', body);
  return data;
}

export async function checkStops() {
  const { data } = await request.post('/simulation/check-stops');
  return data;
}
