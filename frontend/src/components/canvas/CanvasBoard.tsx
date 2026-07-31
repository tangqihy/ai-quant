import React, { useMemo } from 'react';
import { ReactFlow, Background, Controls, MiniMap, type NodeTypes } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Empty } from 'antd';
import type { CanvasCard, CanvasEdge } from '../../services/canvasApi';
import { layoutCanvas } from './layout';
import { CanvasCardNode } from './CanvasCardNode';

const nodeTypes: NodeTypes = { canvasCard: CanvasCardNode };

interface CanvasBoardProps {
  cards: CanvasCard[];
  edges: CanvasEdge[];
}

/** 无限画布主体：dagre 自动布局 + React Flow 只读浏览 */
export const CanvasBoard: React.FC<CanvasBoardProps> = ({ cards, edges }) => {
  const { nodes, edges: rfEdges } = useMemo(
    () => layoutCanvas(cards, edges),
    [cards, edges],
  );

  if (cards.length === 0) {
    return (
      <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Empty
          description={
            <span style={{ color: 'var(--cyber-text-secondary)' }}>
              画布还没有卡片。通过 IM 或 CLI（scripts/canvas add-card）写入第一张卡片。
            </span>
          }
        />
      </div>
    );
  }

  return (
    <ReactFlow
      nodes={nodes}
      edges={rfEdges}
      nodeTypes={nodeTypes}
      fitView
      fitViewOptions={{ padding: 0.2, maxZoom: 1 }}
      minZoom={0.2}
      maxZoom={2}
      nodesDraggable={false}
      nodesConnectable={false}
      elementsSelectable={false}
      proOptions={{ hideAttribution: true }}
      style={{ background: 'var(--cyber-bg)' }}
    >
      <Background color="rgba(var(--accent-rgb),0.08)" gap={24} />
      <Controls
        showInteractive={false}
        style={{ background: 'var(--cyber-bg-card)', border: '1px solid rgba(var(--accent-rgb),0.2)' }}
      />
      <MiniMap
        pannable
        zoomable
        style={{ background: 'var(--cyber-bg-card)', border: '1px solid rgba(var(--accent-rgb),0.2)' }}
        nodeColor={() => 'var(--cyber-neon-cyan)'}
        maskColor="rgba(2,4,10,0.7)"
      />
    </ReactFlow>
  );
};
