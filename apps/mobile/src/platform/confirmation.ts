// #ifdef H5
import './confirmation.css';
import { requestId } from './ids';
// #endif

interface ConfirmationOptions {
  title: string;
  content: string;
  confirmText: string;
  cancelText: string;
}

/** Keep business decisions shared; use each platform's modal implementation. */
export function confirmAction(options: ConfirmationOptions): Promise<{ confirm: boolean; cancel: boolean }> {
  // #ifdef H5
  return new Promise(resolve => {
    const trigger = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const dialog = document.createElement('dialog');
    const title = document.createElement('h2');
    const content = document.createElement('p');
    const actions = document.createElement('div');
    const cancel = document.createElement('button');
    const confirm = document.createElement('button');
    const id = `confirmation-${requestId()}`;
    dialog.className = 'confirmation-dialog';
    const shell = trigger?.closest('.phone-shell');
    if (shell) {
      const style = getComputedStyle(shell);
      dialog.style.fontSize = style.fontSize;
      dialog.style.fontFamily = style.fontFamily;
    }
    title.id = `${id}-title`; title.textContent = options.title;
    title.className = 'confirmation-title';
    content.id = `${id}-content`; content.textContent = options.content;
    content.className = 'confirmation-content';
    dialog.setAttribute('aria-labelledby', title.id);
    dialog.setAttribute('aria-describedby', content.id);
    dialog.setAttribute('aria-modal', 'true');
    actions.className = 'confirmation-actions';
    cancel.type = confirm.type = 'button';
    cancel.textContent = options.cancelText; confirm.textContent = options.confirmText;
    cancel.className = 'confirmation-button';
    confirm.className = 'confirmation-button confirmation-accept';
    let accepted = false;
    cancel.addEventListener('click', () => dialog.close());
    confirm.addEventListener('click', () => { accepted = true; dialog.close(); });
    dialog.addEventListener('cancel', event => { event.preventDefault(); dialog.close(); });
    // Native modal inertness blocks background interaction; wrap Tab explicitly
    // so focus also stays within the two actions at either end of the dialog.
    dialog.addEventListener('keydown', event => {
      if (event.key !== 'Tab') return;
      event.preventDefault();
      (document.activeElement === cancel ? confirm : cancel).focus();
    });
    dialog.addEventListener('close', () => {
      dialog.remove();
      if (trigger?.isConnected) trigger.focus({ preventScroll: true });
      resolve({ confirm: accepted, cancel: !accepted });
    }, { once: true });
    actions.append(cancel, confirm); dialog.append(title, content, actions);
    document.body.append(dialog);
    dialog.showModal();
    cancel.focus();
  });
  // #endif
  // #ifndef H5
  return uni.showModal(options);
  // #endif
}
