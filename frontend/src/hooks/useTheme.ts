import { useState, useEffect, useCallback } from 'react';

type Theme = 'light' | 'dark';

const THEME_STORAGE_KEY = 'ai-quant-theme-v1';

const getSystemTheme = (): Theme => {
  if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
    return 'dark';
  }
  return 'light'; // 纸面手账默认亮色
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

const SANS_FONT =
  "-apple-system, BlinkMacSystemFont, 'PingFang SC', 'HarmonyOS Sans SC', 'Microsoft YaHei', 'Noto Sans SC', 'Segoe UI', sans-serif";

/**
 * 纸上手账配色：亮 = 暖纸 + 钢笔蓝黑；暗 = 深夜手账。
 * CSS 变量由 index.css 按 data-theme 提供，这里只输出 antd token。
 */
export const antdThemeConfig = {
  light: {
    token: {
      colorPrimary: '#2f5d8a',
      colorInfo: '#2f5d8a',
      colorError: '#c0392b',
      colorSuccess: '#2f9e44',
      colorWarning: '#d9480f',
      colorBgBase: '#f4f0e6',
      colorBgContainer: '#fffdf5',
      colorBgElevated: '#faf7ee',
      colorBgLayout: '#f4f0e6',
      colorTextBase: '#2d2a26',
      colorText: '#2d2a26',
      colorTextSecondary: '#6e675c',
      colorBorder: '#ddd5c3',
      colorBorderSecondary: '#e8e2d3',
      borderRadius: 10,
      fontFamily: SANS_FONT,
    },
    components: {
      Layout: {
        siderBg: '#faf7ee',
        headerBg: '#faf7ee',
        bodyBg: '#f4f0e6',
      },
      Menu: {
        itemColor: '#6e675c',
        itemSelectedColor: '#2d2a26',
        itemSelectedBg: 'rgba(250, 204, 21, 0.32)',
        itemHoverBg: 'rgba(250, 204, 21, 0.15)',
        itemBg: 'transparent',
        subMenuItemBg: 'transparent',
      },
    },
  },
  dark: {
    token: {
      colorPrimary: '#7aa5d1',
      colorInfo: '#7aa5d1',
      colorError: '#d4735a',
      colorSuccess: '#4cba63',
      colorWarning: '#e8890c',
      colorBgBase: '#211e19',
      colorBgContainer: '#2d2921',
      colorBgElevated: '#28241d',
      colorBgLayout: '#211e19',
      colorTextBase: '#e6dfd2',
      colorText: '#e6dfd2',
      colorTextSecondary: '#a39a88',
      colorBorder: '#3f3a2f',
      colorBorderSecondary: '#363125',
      borderRadius: 10,
      fontFamily: SANS_FONT,
    },
    components: {
      Layout: {
        siderBg: '#28241d',
        headerBg: '#28241d',
        bodyBg: '#211e19',
      },
      Menu: {
        itemColor: '#a39a88',
        itemSelectedColor: '#e6dfd2',
        itemSelectedBg: 'rgba(250, 204, 21, 0.14)',
        itemHoverBg: 'rgba(250, 204, 21, 0.07)',
        itemBg: 'transparent',
        subMenuItemBg: 'transparent',
      },
    },
  },
};

export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(() => getStoredTheme() ?? getSystemTheme());

  const applyThemeAttr = useCallback((t: Theme) => {
    document.documentElement.setAttribute('data-theme', t);
  }, []);

  useEffect(() => {
    applyThemeAttr(theme);
  }, [theme, applyThemeAttr]);

  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handleChange = () => {
      if (!getStoredTheme()) {
        const newTheme = mediaQuery.matches ? 'dark' : 'light';
        setThemeState(newTheme);
        applyThemeAttr(newTheme);
      }
    };
    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, [applyThemeAttr]);

  const toggleTheme = useCallback(() => {
    const newTheme = theme === 'light' ? 'dark' : 'light';
    setThemeState(newTheme);
    storeTheme(newTheme);
    applyThemeAttr(newTheme);
  }, [theme, applyThemeAttr]);

  const setTheme = useCallback((t: Theme) => {
    setThemeState(t);
    storeTheme(t);
    applyThemeAttr(t);
  }, [applyThemeAttr]);

  return {
    theme,
    isDark: theme === 'dark',
    toggleTheme,
    setTheme,
    antdConfig: antdThemeConfig[theme],
  };
}
