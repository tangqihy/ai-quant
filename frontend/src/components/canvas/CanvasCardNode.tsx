import React from 'react';
import { Handle, Position, type NodeProps, type Node } from '@xyflow/react';
import type { CanvasCard } from '../../services/canvasApi';
import { CardShell } from './CardShell';

export type CanvasCardNodeType = Node<{ card: CanvasCard }, 'canvasCard'>;

/** React Flow 自定义节点：卡片左右两侧挂连接点 */
export const CanvasCardNode: React.FC<NodeProps<CanvasCardNodeType>> = ({ data }) => {
  return (
    <>
      <Handle type="target" position={Position.Left} style={{ background: 'var(--cyber-neon-cyan)', width: 6, height: 6 }} />
      <CardShell card={data.card} />
      <Handle type="source" position={Position.Right} style={{ background: 'var(--cyber-neon-cyan)', width: 6, height: 6 }} />
    </>
  );
};
