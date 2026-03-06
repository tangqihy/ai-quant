import { useState, useEffect, useCallback } from 'react';

type Theme = 'light' | 'dark';

const THEME_STORAGE_KEY = 'ai-quant-theme-v1';

// 获取系统主题偏好
const getSystemTheme = (): Theme => {
  if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
    return 'dark';
  }
  return 'light';
};

// 从 localStorage 读取主题
const getStoredTheme = (): Theme | null => {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY);
    if (stored === 'dark' || stored === 'light') {
      return stored;
    }
  } catch (e) {
    console.error('Failed to read theme from storage:', e);
  }
  return null;
};

// 保存主题到 localStorage
const storeTheme = (theme: Theme) => {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch (e) {
    console.error('Failed to save theme to storage:', e);
  }
};

// Ant Design 主题配置
export const antdThemeConfig = {
  light: {
    token: {
      colorPrimary: '#1890ff',
      colorBgBase: '#ffffff',
      colorBgContainer: '#ffffff',
      colorBgLayout: '#f5f7fa',
      colorTextBase: '#262626',
      colorBorder: '#f0f0f0',
    },
    components: {
      Layout: {
        siderBg: 'linear-gradient(180deg, #001529 0%, #002140 100%)',
        headerBg: '#ffffff',
        bodyBg: '#f5f7fa',
      },
    },
  },
  dark: {
    token: {
      colorPrimary: '#1890ff',
      colorBgBase: '#141414',
      colorBgContainer: '#1f1f1f',
      colorBgLayout: '#000000',
      colorTextBase: '#ffffff',
      colorBorder: '#434343',
    },
    components: {
      Layout: {
        siderBg: 'linear-gradient(180deg, #000000 0%, #141414 100%)',
        headerBg: '#1f1f1f',
        bodyBg: '#000000',
      },
    },
  },
};

// CSS 变量
export const cssVariables = {
  light: {
    '--bg-primary': '#f5f7fa',
    '--bg-secondary': '#ffffff',
    '--bg-card': '#ffffff',
    '--text-primary': '#262626',
    '--text-secondary': '#8c8c8c',
    '--border-color': '#f0f0f0',
    '--shadow-color': 'rgba(0, 0, 0, 0.06)',
    '--hover-bg': 'rgba(24, 144, 255, 0.04)',
  },
  dark: {
    '--bg-primary': '#000000',
    '--bg-secondary': '#141414',
    '--bg-card': '#1f1f1f',
    '--text-primary': '#ffffff',
    '--text-secondary': '#a6a6a6',
    '--border-color': '#434343',
    '--shadow-color': 'rgba(0, 0, 0, 0.3)',
    '--hover-bg': 'rgba(24, 144, 255, 0.1)',
  },
};

export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(() => {
    return getStoredTheme() || getSystemTheme();
  });

  // 应用 CSS 变量
  const applyCSSVariables = useCallback((t: Theme) => {
    const root = document.documentElement;
    const vars = cssVariables[t];
    Object.entries(vars).forEach(([key, value]) => {
      root.style.setProperty(key, value);
    });
    root.setAttribute('data-theme', t);
  }, []);

  // 初始化时应用主题
  useEffect(() => {
    applyCSSVariables(theme);
  }, [theme, applyCSSVariables]);

  // 监听系统主题变化
  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handleChange = () => {
      // 只有在用户没有手动设置时才跟随系统
      if (!getStoredTheme()) {
        const newTheme = mediaQuery.matches ? 'dark' : 'light';
        setThemeState(newTheme);
        applyCSSVariables(newTheme);
      }
    };

    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, [applyCSSVariables]);

  // 切换主题
  const toggleTheme = useCallback(() => {
    const newTheme = theme === 'light' ? 'dark' : 'light';
    setThemeState(newTheme);
    storeTheme(newTheme);
    applyCSSVariables(newTheme);
  }, [theme, applyCSSVariables]);

  // 设置指定主题
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
