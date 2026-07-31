import axios from 'axios';
import { setupAuthInterceptor } from './auth';

const request = axios.create({
  baseURL: '/api',
  timeout: 30000,
});

setupAuthInterceptor(request);

// ==================== 类型定义 ====================

export type CanvasStatus = 'watching' | 'holding' | 'sold' | 'archived';

export type CardType =
  | 'note' | 'thesis' | 'catalyst' | 'risk'
  | 'financial' | 'valuation' | 'sentiment'
  | 'entry_plan' | 'exit_plan' | 'trade_record';

export type EdgeType = 'supports' | 'contradicts' | 'causes' | 'relates' | 'triggers';

export interface Canvas {
  ts_code: string;
  name: string;
  status: CanvasStatus;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at?: string;
}

export interface CanvasCard {
  id: string;
  ts_code: string;
  card_type: CardType;
  title: string;
  content: string;
  structured_data: Record<string, unknown>;
  tags: string[];
  importance: number;
  source: string;
  source_ref: string;
  position: { x?: number; y?: number };
  created_at: string;
  updated_at?: string;
  expires_at?: string;
}

export interface CanvasEdge {
  id: string;
  source_card_id: string;
  target_card_id: string;
  edge_type: EdgeType;
  label?: string;
  created_at: string;
}

export interface CanvasDetail {
  canvas: Canvas;
  cards: CanvasCard[];
  edges: CanvasEdge[];
}

export interface TimelineEvent {
  date: string;
  card_id: string;
  card_type: CardType;
  title: string;
  structured_data: Record<string, unknown>;
}

// ==================== 画布 ====================

export const getCanvasList = (status?: string) => {
  return request.get('/canvas', { params: status ? { status } : {} });
};

export const createCanvas = (tsCode: string, name: string, status: CanvasStatus = 'watching') => {
  return request.post('/canvas', { ts_code: tsCode, name, status });
};

export const getCanvasDetail = (tsCode: string) => {
  return request.get(`/canvas/${encodeURIComponent(tsCode)}`);
};

export const updateCanvas = (tsCode: string, data: { status?: CanvasStatus; name?: string; metadata?: Record<string, unknown> }) => {
  return request.patch(`/canvas/${encodeURIComponent(tsCode)}`, data);
};

export const deleteCanvas = (tsCode: string) => {
  return request.delete(`/canvas/${encodeURIComponent(tsCode)}`);
};

// ==================== 卡片 ====================

export const addCard = (tsCode: string, data: {
  card_type: CardType;
  title: string;
  content?: string;
  structured_data?: Record<string, unknown>;
  tags?: string[];
  importance?: number;
  source?: string;
}) => {
  return request.post(`/canvas/${encodeURIComponent(tsCode)}/cards`, data);
};

export const updateCard = (cardId: string, data: Partial<{
  title: string;
  content: string;
  structured_data: Record<string, unknown>;
  tags: string[];
  importance: number;
  position: { x: number; y: number };
}>) => {
  return request.patch(`/canvas/cards/${cardId}`, data);
};

export const deleteCard = (cardId: string) => {
  return request.delete(`/canvas/cards/${cardId}`);
};

// ==================== 关联 ====================

export const linkCards = (sourceCardId: string, targetCardId: string, edgeType: EdgeType, label?: string) => {
  return request.post('/canvas/edges', {
    source_card_id: sourceCardId,
    target_card_id: targetCardId,
    edge_type: edgeType,
    label,
  });
};

export const deleteEdge = (edgeId: string) => {
  return request.delete(`/canvas/edges/${edgeId}`);
};

// ==================== 查询 ====================

export const searchCards = (keyword: string, tsCode?: string, cardType?: CardType) => {
  return request.get('/canvas-search', {
    params: { keyword, ...(tsCode ? { ts_code: tsCode } : {}), ...(cardType ? { card_type: cardType } : {}) },
  });
};

export const getTimeline = (tsCode: string) => {
  return request.get(`/canvas/${encodeURIComponent(tsCode)}/timeline`);
};

export const getDecisions = (tsCode: string) => {
  return request.get(`/canvas/${encodeURIComponent(tsCode)}/decisions`);
};
