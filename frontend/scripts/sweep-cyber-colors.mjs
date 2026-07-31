/**
 * 一次性清扫脚本：把残留的赛博霓虹硬编码颜色替换为主题变量。
 * 用法：node scripts/sweep-cyber-colors.mjs
 * 语义红绿（涨跌/买卖）已手工改为 var(--up)/var(--down)，本脚本只处理装饰色。
 */
import { readdirSync, readFileSync, writeFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

const SRC = new URL('../src', import.meta.url).pathname;

const EXCLUDE = new Set([
  'index.css',
  'App.css',
  'useTheme.ts',
  'KLineChart.tsx',
  'Sparkline.tsx',
  'Login.tsx',
  'MainLayout.tsx',
  'NeonBorder.tsx',
  'CyberCard.tsx',
  'GlitchText.tsx',
]);

// 顺序敏感：先长后短
const MAP = [
  ['rgba(0, 240, 255, ', 'rgba(var(--accent-rgb), '],
  ['rgba(0,240,255,', 'rgba(var(--accent-rgb),'],
  ['rgba(255, 0, 160, ', 'rgba(var(--accent-warm-rgb), '],
  ['rgba(255,0,160,', 'rgba(var(--accent-warm-rgb),'],
  ['rgba(0, 255, 65, ', 'rgba(var(--accent-rgb), '],
  ['rgba(255, 0, 64, ', 'rgba(var(--accent-warm-rgb), '],
  ['#00f0ff', 'var(--cyber-neon-cyan)'],
  ['#00ff41', 'var(--cyber-neon-cyan)'],
  ['#ff00a0', 'var(--cyber-neon-pink)'],
  ['#ff0040', 'var(--cyber-neon-pink)'],
  ['#02040a', 'var(--cyber-bg)'],
  ['#050815', 'var(--cyber-bg-elevated)'],
  ['#0a1020', 'var(--cyber-bg-card)'],
  ['#091020', 'var(--cyber-bg-elevated)'],
  ['#e8f4ff', 'var(--cyber-text)'],
  ['#ccd6e0', 'var(--cyber-text)'],
  ['#9fb3c8', 'var(--cyber-text-secondary)'],
  ['#8899aa', 'var(--cyber-text-secondary)'],
  ['#556677', 'var(--cyber-text-faint)'],
  ["fontFamily: \"'JetBrains Mono', monospace\"", "fontFamily: 'var(--mono-font)'"],
];

function* walk(dir) {
  for (const entry of readdirSync(dir)) {
    const p = join(dir, entry);
    if (statSync(p).isDirectory()) yield* walk(p);
    else if (/\.(tsx?|css)$/.test(entry) && !EXCLUDE.has(entry)) yield p;
  }
}

let totalFiles = 0;
let totalHits = 0;
for (const file of walk(SRC)) {
  let content = readFileSync(file, 'utf8');
  let hits = 0;
  for (const [from, to] of MAP) {
    const count = content.split(from).length - 1;
    if (count > 0) {
      content = content.split(from).join(to);
      hits += count;
    }
  }
  if (hits > 0) {
    writeFileSync(file, content);
    console.log(`${file.replace(SRC, 'src')}: ${hits} 处`);
    totalFiles += 1;
    totalHits += hits;
  }
}
console.log(`\n完成：${totalFiles} 个文件，共 ${totalHits} 处替换`);
