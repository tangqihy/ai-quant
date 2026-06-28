import React from 'react';

interface GlitchTextProps {
  text: string;
  className?: string;
}

export const GlitchText: React.FC<GlitchTextProps> = ({ text, className }) => {
  return (
    <span
      className={`glitch-text ${className ?? ''}`}
      data-text={text}
      style={{
        position: 'relative',
        color: 'var(--cyber-neon-cyan)',
      }}
    >
      {text}
      <span
        aria-hidden="true"
        style={{
          content: 'attr(data-text)',
          position: 'absolute',
          top: 0,
          left: 0,
          color: 'var(--cyber-neon-pink)',
          mixBlendMode: 'screen',
          textShadow:
            '-1px 0 rgba(255, 0, 160, 0.8), -2px 0 rgba(255, 0, 160, 0.6)',
          animation: 'glitch-clip-1 2s infinite linear alternate-reverse',
          overflow: 'hidden',
          whiteSpace: 'nowrap',
        }}
      >
        {text}
      </span>
      <span
        aria-hidden="true"
        style={{
          content: 'attr(data-text)',
          position: 'absolute',
          top: 0,
          left: 0,
          color: 'var(--cyber-neon-cyan)',
          mixBlendMode: 'screen',
          textShadow:
            '1px 0 rgba(0, 240, 255, 0.85), 2px 0 rgba(0, 240, 255, 0.65)',
          animation: 'glitch-clip-2 3s infinite linear alternate',
          overflow: 'hidden',
          whiteSpace: 'nowrap',
        }}
      >
        {text}
      </span>
    </span>
  );
};

export default GlitchText;

