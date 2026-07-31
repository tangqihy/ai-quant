/**
 * 图表主题色工具。
 * ECharts 输出到 canvas，无法解析 CSS 变量，必须在渲染时从 DOM 取值。
 * 图表组件在渲染期调用 chartColors() / accentRgba() 即可随主题切换。
 */

export const cssVar = (name: string, fallback: string): string => {
  const val = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return val || fallback;
};

/** 钢笔蓝黑主色的 rgba */
export const accentRgba = (alpha: number): string =>
  `rgba(${cssVar('--accent-rgb', '47, 93, 138')}, ${alpha})`;

/** 朱砂暖红的 rgba */
export const accentWarmRgba = (alpha: number): string =>
  `rgba(${cssVar('--accent-warm-rgb', '192, 57, 43')}, ${alpha})`;

export interface ChartPalette {
  accent: string;
  accentWarm: string;
  up: string;
  down: string;
  ink: string;
  inkSoft: string;
  inkFaint: string;
  line: string;
  lineStrong: string;
  paperCard: string;
  paperElevated: string;
}

export const chartColors = (): ChartPalette => ({
  accent: cssVar('--accent', '#2f5d8a'),
  accentWarm: cssVar('--accent-warm', '#c0392b'),
  up: cssVar('--up', '#c0392b'),
  down: cssVar('--down', '#2f9e44'),
  ink: cssVar('--ink', '#2d2a26'),
  inkSoft: cssVar('--ink-soft', '#6e675c'),
  inkFaint: cssVar('--ink-faint', '#a39a89'),
  line: cssVar('--line', '#ddd5c3'),
  lineStrong: cssVar('--line-strong', '#b5ab94'),
  paperCard: cssVar('--paper-card', '#fffdf5'),
  paperElevated: cssVar('--paper-elevated', '#faf7ee'),
});
