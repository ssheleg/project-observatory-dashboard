'use strict';
const after = document.querySelector('#sample-after');
if (after) after.hidden = true;
const controls = document.querySelectorAll('[data-state]');
controls.forEach(button => button.addEventListener('click', () => {
  const next = button.dataset.state;
  controls.forEach(other => other.setAttribute('aria-pressed', String(other === button)));
  document.querySelector('#sample-before').hidden = next !== 'before';
  after.hidden = next !== 'after';
}));
const copyButton = document.querySelector('#copy-prompt');
if (copyButton) copyButton.addEventListener('click', async () => {
  const prompt = document.querySelector('#agent-prompt');
  const status = document.querySelector('#copy-status');
  copyButton.disabled = true;
  try {
    if (!navigator.clipboard) throw new Error('unavailable');
    await navigator.clipboard.writeText(prompt.textContent);
    status.textContent = 'Copied. Paste this prompt into your coding agent.';
  } catch (_) {
    const details = document.querySelector('#prompt-details');
    if (details) details.open = true;
    prompt.focus();
    const range = document.createRange();
    range.selectNodeContents(prompt);
    const selection = window.getSelection();
    if (selection) { selection.removeAllRanges(); selection.addRange(range); }
    status.textContent = 'Clipboard unavailable. The prompt is selected; copy it with your keyboard.';
  } finally {
    copyButton.disabled = false;
  }
});
