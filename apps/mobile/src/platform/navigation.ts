export function openExternalMap(url: string): void {
  if (!url.startsWith('https://uri.amap.com/')) {
    uni.showToast({ title: '地图地址无效', icon: 'none' });
    return;
  }
  // #ifdef APP-PLUS
  plus.runtime.openURL(url);
  // #endif
  // #ifdef H5
  window.open(url, '_blank', 'noopener,noreferrer');
  // #endif
}

export function openWebSource(url: string): void {
  if (!/^https?:\/\/[^/@\s]+(?:\/|$)/.test(url)) return;
  // #ifdef APP-PLUS
  plus.runtime.openURL(url);
  // #endif
  // #ifdef H5
  window.open(url, '_blank', 'noopener,noreferrer');
  // #endif
}
