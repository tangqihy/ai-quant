import React from 'react';

interface NeonBorderProps extends React.HTMLAttributes<HTMLDivElement> {
  glow?: 'soft' | 'strong';
}

/**
 * 手绘便签边框（原霓虹边框，保留组件名以兼容存量引用）。
 * 不规则圆角 + 纸张投影；glow=strong 时加一道主色描边。
 */
export const NeonBorder: React.FC<NeonBorderProps> = ({
  glow = 'soft',
  className = '',
  children,
  ...rest
}) => {
  return (
    <div
      className={className}
      style={{
        position: 'relative',
        borderRadius: 'var(--sketch-radius)',
        background: 'var(--paper-card)',
        border:
          glow === 'strong'
            ? '1.5px solid var(--accent)'
            : '1.5px solid var(--line-strong)',
        boxShadow: '2px 3px 0 rgba(45, 42, 38, 0.08)',
        overflow: 'hidden',
      }}
      {...rest}
    >
      {children}
    </div>
  );
};

export default NeonBorder;
