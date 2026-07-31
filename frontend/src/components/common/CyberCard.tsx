import React from 'react';
import NeonBorder from './NeonBorder';

interface CyberCardProps extends React.HTMLAttributes<HTMLDivElement> {
  title?: React.ReactNode;
  extra?: React.ReactNode;
  footer?: React.ReactNode;
}

/**
 * 手账卡片（原赛博卡片，保留组件名以兼容存量引用）。
 * 标题带荧光笔标记方块，页脚为铅笔虚线。
 */
export const CyberCard: React.FC<CyberCardProps> = ({
  title,
  extra,
  footer,
  children,
  style,
  className = '',
  ...rest
}) => {
  return (
    <NeonBorder
      className={className}
      style={{
        ...style,
      }}
    >
      <div
        style={{
          padding: 14,
          display: 'flex',
          flexDirection: 'column',
          gap: 10,
        }}
        {...rest}
      >
        {(title || extra) && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              fontSize: 13,
              fontWeight: 600,
              letterSpacing: '0.02em',
              color: 'var(--ink)',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
              }}
            >
              <div
                style={{
                  width: 10,
                  height: 10,
                  background: 'var(--marker)',
                  border: '1.5px solid var(--accent-warm)',
                  borderRadius: '3px 4px 3px 5px / 4px 3px 5px 4px',
                  transform: 'rotate(-4deg)',
                }}
              />
              <span>{title}</span>
            </div>
            {extra && (
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 400,
                  color: 'var(--ink-faint)',
                  fontFamily: 'var(--mono-font)',
                }}
              >
                {extra}
              </div>
            )}
          </div>
        )}

        <div
          style={{
            position: 'relative',
          }}
        >
          {children}
        </div>

        {footer && (
          <div
            style={{
              borderTop: '1.5px dashed var(--line)',
              marginTop: 6,
              paddingTop: 6,
              fontSize: 11,
              color: 'var(--ink-soft)',
              fontFamily: 'var(--mono-font)',
            }}
          >
            {footer}
          </div>
        )}
      </div>
    </NeonBorder>
  );
};

export default CyberCard;
