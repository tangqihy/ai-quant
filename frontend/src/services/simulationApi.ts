import axios from 'axios';
import { setupAuthInterceptor } from './auth';

const request = axios.create({
  baseURL: '/api',
  timeout: 30000,
});

setupAuthInterceptor(request);

export interface OrderRequest {
  symbol: string;
  action: 'BUY' | 'SELL';
  order_type: 'LIMIT' | 'MARKET';
  price?: number;
  quantity: number;
}

export interface Order {
  id: string;
  symbol: string;
  action: 'BUY' | 'SELL';
  order_type: 'LIMIT' | 'MARKET';
  price?: number;
  quantity: number;
  filled_quantity: number;
  status: 'PENDING' | 'PARTIAL_FILLED' | 'FILLED' | 'CANCELLED' | 'REJECTED';
  created_at: string;
  updated_at?: string;
  rejected_reason?: string;
}

export interface Trade {
  id: string;
  order_id: string;
  symbol: string;
  action: 'BUY' | 'SELL';
  price: number;
  quantity: number;
  commission: number;
  stamp_tax: number;
  transfer_fee: number;
  total_fee: number;
  timestamp: string;
}

export interface Position {
  symbol: string;
  name: string;
  quantity: number;
  avg_cost: number;
  market_price: number;
  market_value: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
}

export interface Account {
  user_id: string;
  initial_capital: number;
  cash: number;
  frozen_cash: number;
  total_value: number;
  positions_value: number;
  realized_pnl: number;
  total_commission: number;
  total_stamp_tax: number;
  total_transfer_fee: number;
}

// 重置账户
export const resetAccount = (initialCapital: number = 1000000) => {
  return request.post('/simulation/reset', null, {
    params: { initial_capital: initialCapital }
  });
};

// 获取账户信息
export const getAccount = () => {
  return request.get('/simulation/account');
};

// 创建订单
export const createOrder = (data: OrderRequest) => {
  return request.post('/simulation/orders', data);
};

// 撤销订单
export const cancelOrder = (orderId: string) => {
  return request.delete(`/simulation/orders/${orderId}`);
};

// 获取订单列表
export const getOrders = (status?: string) => {
  return request.get('/simulation/orders', {
    params: { status }
  });
};

// 获取成交记录
export const getTrades = () => {
  return request.get('/simulation/trades');
};

// 获取持仓列表
export const getPositions = () => {
  return request.get('/simulation/positions');
};

// 触发撮合
export const matchOrders = () => {
  return request.post('/simulation/match');
};
