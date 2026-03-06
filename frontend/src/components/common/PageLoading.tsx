import React from 'react';
import { motion } from 'framer-motion';
import { Spin } from 'antd';

interface PageLoadingProps {
  tip?: string;
  fullscreen?: boolean;
}

export const PageLoading: React.FC<PageLoadingProps> = ({
  tip = '加载中...',
  fullscreen = false,
}) => {
  const containerStyle: React.CSSProperties = fullscreen
    ? {
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(255, 255, 255, 0.9)',
        zIndex: 9999,
      }
    : {
        width: '100%',
        height: '100%',
        minHeight: 200,
      };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        ...containerStyle,
      }}
    >
      <motion.div
        animate={{
          scale: [1, 1.2, 1],
          rotate: [0, 180, 360],
        }}
        transition={{
          duration: 2,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
        style={{
          width: 48,
          height: 48,
          borderRadius: '50%',
          border: '3px solid #1890ff',
          borderTopColor: 'transparent',
        }}
      />
      <motion.p
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        style={{ marginTop: 16, color: '#8c8c8c' }}
      >
        {tip}
      </motion.p>
    </motion.div>
  );
};

// 骨架屏卡片
export const SkeletonCard: React.FC<{ rows?: number }> = ({ rows = 3 }) => {
  return (
    <div style={{ padding: 24 }}>
      <motion.div
        initial={{ opacity: 0.5 }}
        animate={{ opacity: [0.5, 1, 0.5] }}
        transition={{ duration: 1.5, repeat: Infinity }}
      >
        <div
          style={{
            height: 20,
            width: '40%',
            backgroundColor: '#f0f0f0',
            borderRadius: 4,
            marginBottom: 16,
          }}
        />
        {Array.from({ length: rows }).map((_, i) => (
          <div
            key={i}
            style={{
              height: 16,
              width: `${80 + Math.random() * 20}%`,
              backgroundColor: '#f5f5f5',
              borderRadius: 4,
              marginBottom: 12,
            }}
          />
        ))}
      </motion.div>
    </div>
  );
};

// 数据加载状态
export const DataLoading: React.FC<{ height?: number }> = ({ height = 200 }) => {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height,
      }}
    >
      <Spin size="large" tip="数据加载中..." />
    </motion.div>
  );
};
