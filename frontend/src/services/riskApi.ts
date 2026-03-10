import axios from 'axios';
import { setupAuthInterceptor } from './auth';

const request = axios.create({
  baseURL: '/api',
  timeout: 30000,
});

setupAuthInterceptor(request);

export interface RiskRule {
  id: string;
  name: string;
  rule_type: string;
  enabled: boolean;
  params: Record<string, any>;
  created_at: string;
  updated_at?: string;
}

export interface RiskAlert {
  id: string;
  rule_id: string;
  rule_name: string;
  alert_type: 'WARNING' | 'ERROR' | 'BLOCK';
  symbol?: string;
  message: string;
  details: Record<string, any>;
  created_at: string;
  acknowledged: boolean;
}

export interface StopLossConfig {
  symbol: string;
  position_id: string;
  stop_loss_price: number;
  stop_loss_pct: number;
  stop_profit_price?: number;
  stop_profit_pct?: number;
  trailing_stop: boolean;
  trailing_stop_pct?: number;
  highest_price?: number;
  created_at: string;
  updated_at?: string;
}

export interface BlacklistItem {
  symbol: string;
  reason: string;
  description: string;
  expires_at?: string;
  created_at: string;
}

// 获取风控规则列表
export const getRiskRules = () => {
  return request.get('/risk/rules');
};

// 更新风控规则
export const updateRiskRule = (ruleId: string, enabled: boolean, params?: Record<string, any>) => {
  return request.put(`/risk/rules/${ruleId}`, { enabled, params });
};

// 设置止损止盈
export const setStopLoss = (data: {
  symbol: string;
  position_id: string;
  stop_loss_pct: number;
  stop_profit_pct?: number;
  trailing_stop?: boolean;
  trailing_stop_pct?: number;
}) => {
  return request.post('/risk/stop-loss', data);
};

// 获取止损止盈配置
export const getStopLoss = (symbol: string) => {
  return request.get(`/risk/stop-loss/${encodeURIComponent(symbol)}`);
};

// 删除止损止盈
export const removeStopLoss = (symbol: string) => {
  return request.delete(`/risk/stop-loss/${encodeURIComponent(symbol)}`);
};

// 添加到黑名单
export const addToBlacklist = (data: {
  symbol: string;
  reason: string;
  description?: string;
  expires_in_hours?: number;
}) => {
  return request.post('/risk/blacklist', data);
};

// 获取黑名单
export const getBlacklist = () => {
  return request.get('/risk/blacklist');
};

// 从黑名单移除
export const removeFromBlacklist = (symbol: string) => {
  return request.delete(`/risk/blacklist/${symbol}`);
};

// 获取风控告警
export const getRiskAlerts = (acknowledged?: boolean, limit?: number) => {
  return request.get('/risk/alerts', {
    params: { acknowledged, limit }
  });
};

// 确认告警
export const acknowledgeAlert = (alertId: string) => {
  return request.post(`/risk/alerts/${alertId}/acknowledge`);
};

// 清空告警
export const clearAlerts = () => {
  return request.delete('/risk/alerts');
};
