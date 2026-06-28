import React from 'react';

interface NeonBorderProps extends React.HTMLAttributes<HTMLDivElement> {
  glow?: 'soft' | 'strong';
}

export const NeonBorder: React.FC<NeonBorderProps> = ({
  glow = 'soft',
  className = '',
  children,
  ...rest
}) => {
  const glowShadow =
    glow === 'strong'
      ? '0 0 12px rgba(0, 240, 255, 0.7), 0 0 26px rgba(255, 0, 160, 0.55)'
      : '0 0 8px rgba(0, 240, 255, 0.45), 0 0 18px rgba(255, 0, 160, 0.35)';

  return (
    <div
      className={className}
      style={{
        position: 'relative',
        borderRadius: '12px',
        padding: 1,
        background:
          'linear-gradient(135deg, rgba(0,240,255,0.85), rgba(255,0,160,0.9))',
        boxShadow: glowShadow,
      }}
      {...rest}
    >
      <div
        style={{
          borderRadius: '10px',
          background:
            'radial-gradient(circle at top left, #091020 0, #050815 45%, #02040a 100%)',
          border: '1px solid rgba(0, 240, 255, 0.18)',
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        {/* HUD 裁切线 */}
        <div
          style={{
            position: 'absolute',
            inset: 0,
            pointerEvents: 'none',
            borderRadius: '10px',
            boxShadow:
              'inset 0 0 0 1px rgba(0, 240, 255, 0.12), inset 0 0 24px rgba(0, 240, 255, 0.22)',
            mixBlendMode: 'screen',
          }}
        />
        {children}
      </div>
    </div>
  );
};

export default NeonBorder;

