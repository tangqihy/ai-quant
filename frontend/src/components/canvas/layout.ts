import dagre from 'dagre';
import type { Node, Edge } from '@xyflow/react';
import type { CanvasCard, CanvasEdge } from '../../services/canvasApi';

const NODE_WIDTH = 300;
const NODE_HEIGHT = 140;

// 卡片类型 → 层级列（研究层左、数据层中、决策层右）
const TYPE_COLUMN: Record<string, number> = {
  thesis: 0, catalyst: 0, risk: 0, note: 0,
  financial: 1, valuation: 1, sentiment: 1,
  entry_plan: 2, exit_plan: 2, trade_record: 2,
};

/**
 * 用 dagre 按边方向自动布局；
 * 无边孤立节点按类型列分区摆放。
 */
export function layoutCanvas(cards: CanvasCard[], edges: CanvasEdge[]): { nodes: Node[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: 'LR', nodesep: 40, ranksep: 120, marginx: 20, marginy: 20 });

  const cardIds = new Set(cards.map((c) => c.id));
  const connected = new Set<string>();

  edges.forEach((e) => {
    if (cardIds.has(e.source_card_id) && cardIds.has(e.target_card_id)) {
      connected.add(e.source_card_id);
      connected.add(e.target_card_id);
      g.setEdge(e.source_card_id, e.target_card_id);
    }
  });

  cards.forEach((c) => {
    g.setNode(c.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
    // 无关联的节点给一个隐形自环锚点会破坏布局，直接留孤立即可，
    // dagre 会将其放在第一列，再由下方按列重排
  });

  dagre.layout(g);

  // 统计每列已用行数，用于把孤立节点分配到对应列
  const colRows: Record<number, number> = { 0: 0, 1: 0, 2: 0 };
  const positioned: Record<string, { x: number; y: number }> = {};

  cards.forEach((c) => {
    if (connected.has(c.id)) {
      const n = g.node(c.id);
      positioned[c.id] = { x: n.x - NODE_WIDTH / 2, y: n.y - NODE_HEIGHT / 2 };
      const col = TYPE_COLUMN[c.card_type] ?? 0;
      colRows[col] = Math.max(colRows[col], Math.ceil((n.y + NODE_HEIGHT) / (NODE_HEIGHT + 40)));
    }
  });

  // 孤立节点按类型列补充摆放
  const COL_X = [0, NODE_WIDTH + 160, (NODE_WIDTH + 160) * 2];
  cards.forEach((c) => {
    if (!positioned[c.id]) {
      const col = TYPE_COLUMN[c.card_type] ?? 0;
      const row = colRows[col]++;
      positioned[c.id] = { x: COL_X[col], y: row * (NODE_HEIGHT + 40) };
    }
  });

  const nodes: Node[] = cards.map((c) => ({
    id: c.id,
    type: 'canvasCard',
    position: positioned[c.id],
    data: { card: c },
  }));

  const rfEdges: Edge[] = edges
    .filter((e) => cardIds.has(e.source_card_id) && cardIds.has(e.target_card_id))
    .map((e) => ({
      id: e.id,
      source: e.source_card_id,
      target: e.target_card_id,
      label: e.label || undefined,
      animated: e.edge_type === 'triggers',
      style: {
        stroke: e.edge_type === 'contradicts' ? '#f5222d' : e.edge_type === 'supports' ? '#52c41a' : '#00f0ff',
        strokeWidth: 1.5,
      },
      labelStyle: { fill: '#8899aa', fontSize: 11 },
    }));

  return { nodes, edges: rfEdges };
}
