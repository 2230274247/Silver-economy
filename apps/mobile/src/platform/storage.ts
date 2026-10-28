export type FontSize = 18 | 20 | 22;
const FONT_KEY = 'silver-memory:font-size';

export function readFontSize(): FontSize {
  const value: unknown = uni.getStorageSync(FONT_KEY);
  return value === 20 || value === 22 ? value : 18;
}

export function saveFontSize(value: FontSize): void {
  uni.setStorageSync(FONT_KEY, value);
}
