import { TOAST_DEFAULT_DURATION } from './constants.js';

function getContainer() {
  const container = document.getElementById('toast-container');
  if (!container) {
    throw new Error('Toast container element not found');
  }
  return container;
}

function resolveIcon(type) {
  switch (type) {
    case 'success':
      return '✓';
    case 'error':
      return '✗';
    default:
      return 'ℹ';
  }
}

export function showToast(message, type = 'success', options = {}) {
  if (!message) return () => {};

  const duration = options.duration ?? TOAST_DEFAULT_DURATION;
  const container = getContainer();
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span style="font-size:20px;">${resolveIcon(type)}</span><span>${message}</span>`;

  container.appendChild(toast);

  const removeToast = () => {
    toast.classList.add('hiding');
    window.setTimeout(() => toast.remove(), 300);
  };

  window.setTimeout(removeToast, duration);
  return removeToast;
}

export function clearToasts() {
  const container = document.getElementById('toast-container');
  if (!container) return;
  container.innerHTML = '';
}
