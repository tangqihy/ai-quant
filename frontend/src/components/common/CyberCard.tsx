import React from 'react';
import NeonBorder from './NeonBorder';

interface CyberCardProps extends React.HTMLAttributes<HTMLDivElement> {
  title?: React.ReactNode;
  extra?: React.ReactNode;
  footer?: React.ReactNode;
}

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
              textTransform: 'uppercase',
              letterSpacing: '0.16em',
              fontFamily: 'var(--cyber-font-display)',
              color: 'var(--cyber-neon-cyan)',
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
                  width: 4,
                  height: 14,
                  background:
                    'linear-gradient(180deg, var(--cyber-neon-cyan), var(--cyber-neon-pink))',
                  borderRadius: 999,
                  boxShadow:
                    '0 0 6px rgba(0,240,255,0.7), 0 0 12px rgba(255,0,160,0.6)',
                }}
              />
              <span style={{ opacity: 0.96 }}>{title}</span>
            </div>
            {extra && (
              <div
                style={{
                  fontSize: 11,
                  color: 'var(--cyber-text-secondary)',
                  fontFamily: 'var(--cyber-font-mono)',
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
              borderTop: '1px dashed rgba(0, 240, 255, 0.25)',
              marginTop: 6,
              paddingTop: 6,
              fontSize: 11,
              color: 'var(--cyber-text-secondary)',
              fontFamily: 'var(--cyber-font-mono)',
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

