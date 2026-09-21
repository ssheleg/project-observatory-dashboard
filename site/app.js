'use strict';
document.querySelector('#sample-after').hidden = true;
const controls = document.querySelectorAll('[data-state]');
controls.forEach(button => button.addEventListener('click', () => {
  const next = button.dataset.state;
  controls.forEach(other => other.setAttribute('aria-pressed', String(other === button)));
  document.querySelector('#sample-before').hidden = next !== 'before';
  document.querySelector('#sample-after').hidden = next !== 'after';
}));
document.querySelector('#copy-prompt').addEventListener('click', async () => {
  const text = document.querySelector('#agent-prompt').textContent;
  const status = document.querySelector('#copy-status');
  try {
    if (!navigator.clipboard) throw new Error('unavailable');
    await navigator.clipboard.writeText(text);
    status.textContent = 'Copied. Paste this prompt into your coding agent.';
  } catch (_) {
    const range = document.createRange();
    range.selectNodeContents(document.querySelector('#agent-prompt'));
    const selection = window.getSelection();
    selection.removeAllRanges(); selection.addRange(range);
    status.textContent = 'Clipboard unavailable. The prompt is selected; copy it with your keyboard.';
  }
});
