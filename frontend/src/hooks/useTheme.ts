import { useState, useEffect, useCallback } from 'react';

type Theme = 'light' | 'dark';

const THEME_STORAGE_KEY = 'ai-quant-theme-v1';

const getSystemTheme = (): Theme => {
  if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
    return 'dark';
  }
  return 'dark'; // 赛博朋克风格默认深色
};

const getStoredTheme = (): Theme | null => {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY);
    if (stored === 'dark' || stored === 'light') return stored;
  } catch (e) {
    console.error('Failed to read theme from storage:', e);
  }
  return null;
};

const storeTheme = (theme: Theme) => {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch (e) {
    console.error('Failed to save theme to storage:', e);
  }
};

/** 赛博朋克：霓虹绿主色 #00ff41，暗红点缀 #ff0040 */
const NEON_GREEN = '#00ff41';
const NEON_RED = '#ff0040';

export const antdThemeConfig = {
  light: {
    token: {
      colorPrimary: NEON_GREEN,
      colorError: NEON_RED,
      colorBgBase: '#0a0a0a',
      colorBgContainer: '#0d0d0d',
      colorBgLayout: '#000000',
      colorTextBase: NEON_GREEN,
      colorText: 'rgba(0, 255, 65, 0.9)',
      colorTextSecondary: 'rgba(0, 255, 65, 0.55)',
      colorBorder: 'rgba(0, 255, 65, 0.25)',
      fontFamily: "'JetBrains Mono', 'Fira Code', Consolas, monospace",
    },
    components: {
      Layout: {
        siderBg: '#000000',
        headerBg: '#0a0a0a',
        bodyBg: '#000000',
      },
    },
  },
  dark: {
    token: {
      colorPrimary: NEON_GREEN,
      colorError: NEON_RED,
      colorBgBase: '#000000',
      colorBgContainer: '#0a0a0a',
      colorBgLayout: '#000000',
      colorTextBase: 'rgba(0, 255, 65, 0.9)',
      colorText: 'rgba(0, 255, 65, 0.9)',
      colorTextSecondary: 'rgba(0, 255, 65, 0.55)',
      colorBorder: 'rgba(0, 255, 65, 0.25)',
      fontFamily: "'JetBrains Mono', 'Fira Code', Consolas, monospace",
    },
    components: {
      Layout: {
        siderBg: '#000000',
        headerBg: '#0a0a0a',
        bodyBg: '#000000',
      },
    },
  },
};

export const cssVariables = {
  light: {
    '--cyber-bg': '#000000',
    '--cyber-neon-green': NEON_GREEN,
    '--cyber-neon-red': NEON_RED,
    '--cyber-text': 'rgba(0, 255, 65, 0.9)',
    '--cyber-text-secondary': 'rgba(0, 255, 65, 0.55)',
    '--cyber-border': 'rgba(0, 255, 65, 0.25)',
  },
  dark: {
    '--cyber-bg': '#000000',
    '--cyber-neon-green': NEON_GREEN,
    '--cyber-neon-red': NEON_RED,
    '--cyber-text': 'rgba(0, 255, 65, 0.9)',
    '--cyber-text-secondary': 'rgba(0, 255, 65, 0.55)',
    '--cyber-border': 'rgba(0, 255, 65, 0.25)',
  },
};

export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(() => getStoredTheme() ?? getSystemTheme());

  const applyCSSVariables = useCallback((t: Theme) => {
    const root = document.documentElement;
    const vars = cssVariables[t];
    Object.entries(vars).forEach(([key, value]) => {
      root.style.setProperty(key, value);
    });
    root.setAttribute('data-theme', t);
  }, []);

  useEffect(() => {
    applyCSSVariables(theme);
  }, [theme, applyCSSVariables]);

  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handleChange = () => {
      if (!getStoredTheme()) {
        const newTheme = mediaQuery.matches ? 'dark' : 'light';
        setThemeState(newTheme);
        applyCSSVariables(newTheme);
      }
    };
    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, [applyCSSVariables]);

  const toggleTheme = useCallback(() => {
    const newTheme = theme === 'light' ? 'dark' : 'light';
    setThemeState(newTheme);
    storeTheme(newTheme);
    applyCSSVariables(newTheme);
  }, [theme, applyCSSVariables]);

  const setTheme = useCallback((t: Theme) => {
    setThemeState(t);
    storeTheme(t);
    applyCSSVariables(t);
  }, [applyCSSVariables]);

  return {
    theme,
    isDark: theme === 'dark',
    toggleTheme,
    setTheme,
    antdConfig: antdThemeConfig[theme],
  };
}
