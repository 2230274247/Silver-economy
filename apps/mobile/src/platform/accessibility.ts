/** Label uni-app's inner H5 native text control for screen readers. */
export function labelTextControl(id: string, label: string): void {
  // #ifdef H5
  document.getElementById(id)?.querySelector('textarea, input')?.setAttribute('aria-label', label);
  // #endif
}
