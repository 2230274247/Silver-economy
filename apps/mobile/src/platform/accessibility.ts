/** Label uni-app's inner H5 native text control for screen readers. */
export function labelTextControl(id: string, label: string, labelId?: string): void {
  // #ifdef H5
  const control = document.getElementById(id)?.querySelector('textarea, input');
  control?.setAttribute('aria-label', label);
  if (labelId) control?.setAttribute('aria-labelledby', labelId);
  // #endif
}
