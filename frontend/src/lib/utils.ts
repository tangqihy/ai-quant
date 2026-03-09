import { clsx, ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** 价格保留 2 位小数 */
export function formatPrice(val: number | undefined | null): string {
  if (val == null || Number.isNaN(val)) return '-';
  return val.toFixed(2);
}

/** 涨跌幅保留 2 位小数，带 %；正数带 + */
export function formatChangePct(val: number | undefined | null): string {
  if (val == null || Number.isNaN(val)) return '-';
  const sign = val >= 0 ? '+' : '';
  return `${sign}${val.toFixed(2)}%`;
}

/** 涨跌额保留 2 位小数；正数带 + */
export function formatChangeAmount(val: number | undefined | null): string {
  if (val == null || Number.isNaN(val)) return '-';
  const sign = val >= 0 ? '+' : '';
  return `${sign}${val.toFixed(2)}`;
}

/** 成交量格式化：万/亿 */
export function formatVolume(val: number | undefined | null): string {
  if (val == null || val <= 0 || Number.isNaN(val)) return '-';
  if (val >= 1e8) return (val / 1e8).toFixed(2) + '亿';
  if (val >= 1e4) return (val / 1e4).toFixed(2) + '万';
  return String(Math.round(val));
}
