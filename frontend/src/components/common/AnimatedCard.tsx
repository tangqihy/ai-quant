import React from 'react';
import { motion } from 'framer-motion';
import { Card, Statistic } from 'antd';
import CountUp from 'react-countup';

interface AnimatedCardProps {
  title: React.ReactNode;
  value: number | string;
  prefix?: React.ReactNode;
  suffix?: string;
  valueStyle?: React.CSSProperties;
  color?: string;
  onClick?: () => void;
  delay?: number;
}

export const AnimatedCard: React.FC<AnimatedCardProps> = ({
  title,
  value,
  prefix,
  suffix,
  valueStyle,
  color = '#1890ff',
  onClick,
  delay = 0,
}) => {
  const isNumber = typeof value === 'number';

  return (
    <motion.div
      initial={{ opacity: 0, y: 30, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{
        duration: 0.5,
        delay,
        ease: [0.25, 0.46, 0.45, 0.94],
      }}
      whileHover={{
        scale: 1.02,
        boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
        transition: { duration: 0.2 },
      }}
    >
      <Card
        hoverable={!!onClick}
        onClick={onClick}
        style={{
          borderRadius: 12,
          boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
          cursor: onClick ? 'pointer' : 'default',
        }}
        bodyStyle={{ padding: 20 }}
      >
        <Statistic
          title={<span style={{ fontSize: 14, color: '#8c8c8c' }}>{title}</span>}
          value={isNumber ? undefined : value}
          prefix={prefix}
          suffix={suffix}
          valueStyle={{
            fontSize: 32,
            fontWeight: 700,
            color,
            ...valueStyle,
          }}
          formatter={() =>
            isNumber ? (
              <CountUp
                end={value as number}
                duration={2}
                separator=","
                decimals={typeof value === 'number' && value % 1 !== 0 ? 2 : 0}
              />
            ) : (
              value
            )
          }
        />
      </Card>
    </motion.div>
  );
};

// 带动效的列表项
export const AnimatedListItem: React.FC<{
  children: React.ReactNode;
  index?: number;
}> = ({ children, index = 0 }) => {
  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{
        duration: 0.4,
        delay: index * 0.05,
        ease: 'easeOut',
      }}
      whileHover={{
        backgroundColor: 'rgba(24, 144, 255, 0.04)',
        x: 4,
        transition: { duration: 0.15 },
      }}
    >
      {children}
    </motion.div>
  );
};

// 脉冲动画指示器
export const PulseIndicator: React.FC<{ color?: string; size?: number }> = ({
  color = '#52c41a',
  size = 8,
}) => {
  return (
    <motion.span
      style={{
        display: 'inline-block',
        width: size,
        height: size,
        borderRadius: '50%',
        backgroundColor: color,
      }}
      animate={{
        scale: [1, 1.3, 1],
        opacity: [1, 0.7, 1],
      }}
      transition={{
        duration: 2,
        repeat: Infinity,
        ease: 'easeInOut',
      }}
    />
  );
};
