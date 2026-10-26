/** H5 key handling stays here; native targets keep uni-app's confirm lifecycle. */
export function bindComposer(id: string, send: () => void | Promise<void>, revealLatest: () => void | Promise<void>, update: (value: string) => void, selector: 'textarea' | 'input' = 'textarea'): () => void {
  // #ifdef H5
  const field = document.getElementById(id)?.querySelector<HTMLTextAreaElement | HTMLInputElement>(selector);
  if (!field) return () => {};
  let composing = false;
  // uni-app throttles its input event by 100ms. Read native input synchronously
  // so immediate Enter cannot send a truncated draft or restore an old value.
  const input = () => update(field.value);
  const start = () => { composing = true; };
  const end = () => { composing = false; };
  const keydown = (nativeEvent: Event) => {
    const event = nativeEvent as KeyboardEvent;
    if (event.key !== 'Enter') return;
    event.stopImmediatePropagation();
    if (composing || event.isComposing || event.keyCode === 229) return;
    if (event.shiftKey || event.ctrlKey || event.altKey || event.metaKey) return;
    event.preventDefault();
    if (!event.repeat) void send();
  };
  const keyup = (nativeEvent: Event) => { const event = nativeEvent as KeyboardEvent; if (event.key === 'Enter') event.stopImmediatePropagation(); };
  field.addEventListener('compositionstart', start, true);
  field.addEventListener('input', input);
  field.addEventListener('compositionend', end, true);
  field.addEventListener('blur', end, true);
  field.addEventListener('keydown', keydown, true);
  field.addEventListener('keyup', keyup, true);
  const viewport = window.visualViewport ?? window;
  const resized = () => {
    if (document.activeElement === field) requestAnimationFrame(() => { void revealLatest(); });
  };
  viewport.addEventListener('resize', resized);
  return () => {
    field.removeEventListener('compositionstart', start, true);
    field.removeEventListener('input', input);
    field.removeEventListener('compositionend', end, true);
    field.removeEventListener('blur', end, true);
    field.removeEventListener('keydown', keydown, true);
    field.removeEventListener('keyup', keyup, true);
    viewport.removeEventListener('resize', resized);
  };
  // #endif
  // #ifndef H5
  return () => {};
  // #endif
}
