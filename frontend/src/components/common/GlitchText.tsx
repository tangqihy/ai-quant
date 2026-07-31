import React from 'react';

interface GlitchTextProps {
  text: string;
  className?: string;
}

/**
 * 手写标题字（原故障特效字，保留组件名以兼容存量引用）。
 * 手写字体 + 波浪下划线，像是用钢笔写在纸上的标题。
 */
export const GlitchText: React.FC<GlitchTextProps> = ({ text, className }) => {
  return (
    <span
      className={`hand-font ${className ?? ''}`}
      style={{
        fontSize: 26,
        color: 'var(--ink)',
        textDecoration: 'underline wavy var(--accent-warm) 2px',
        textUnderlineOffset: 6,
      }}
    >
      {text}
    </span>
  );
};

export default GlitchText;
