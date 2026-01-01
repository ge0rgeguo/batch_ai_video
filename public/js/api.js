import { showToast } from './toast.js';

function buildUrl(path, params) {
  const url = new URL(path, window.location.origin);
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        url.searchParams.set(key, value);
      }
    });
  }
  return url.toString();
}

async function request(path, options = {}) {
  const {
    method = 'GET',
    body,
    params,
    headers = {},
    silent = false,
    idempotencyKey,
  } = options;

  const url = buildUrl(path, params);
  const fetchOptions = {
    method,
    headers: new Headers(headers),
    credentials: 'same-origin',
  };

  if (idempotencyKey) {
    fetchOptions.headers.set('Idempotency-Key', idempotencyKey);
  }

  if (body instanceof FormData) {
    fetchOptions.body = body;
  } else if (body !== undefined) {
    fetchOptions.body = JSON.stringify(body);
    if (!fetchOptions.headers.has('Content-Type')) {
      fetchOptions.headers.set('Content-Type', 'application/json');
    }
  }

  try {
    const response = await fetch(url, fetchOptions);
    const text = await response.text();
    const json = text ? JSON.parse(text) : { ok: response.ok };

    if (!response.ok || json.ok === false) {
      if (!silent) {
        const message = json?.error?.message || json?.message || `请求失败 (${response.status})`;
        showToast(message, 'error');
      }
    }

    return json;
  } catch (error) {
    if (!silent) {
      showToast('网络错误，请稍后重试', 'error');
    }
    throw error;
  }
}

export function getCurrentUser() {
  return request('/api/me', { silent: true });
}

export function login(credentials) {
  return request('/api/login', { method: 'POST', body: credentials });
}

export function sendSmsCode(payload) {
  return request('/api/mobile/send-code', { method: 'POST', body: payload });
}

export function verifySmsCode(payload) {
  return request('/api/mobile/verify', { method: 'POST', body: payload });
}

export function logout() {
  return request('/api/logout', { method: 'POST', silent: true });
}

export function fetchBatches(page, pageSize) {
  return request('/api/batches', { params: { page, page_size: pageSize } });
}

export function fetchBatchTasks(batchId) {
  return request(`/api/batches/${batchId}/tasks`);
}

export function createBatch(payload, { idempotencyKey } = {}) {
  return request('/api/batches', { method: 'POST', body: payload, idempotencyKey });
}

export function uploadImage(file) {
  const formData = new FormData();
  formData.append('file', file);
  return request('/api/images/upload', { method: 'POST', body: formData });
}

export function deleteImage(imagePath) {
  return request('/api/images', {
    method: 'DELETE',
    params: { image_path: imagePath },
  });
}

export function deleteBatch(batchId) {
  return request(`/api/batches/${batchId}`, { method: 'DELETE' });
}

export function retryTask(taskId) {
  return request(`/api/tasks/${taskId}/retry`, { method: 'POST' });
}

export function deleteTask(taskId) {
  return request(`/api/tasks/${taskId}`, { method: 'DELETE' });
}

export function retryFailedTasks(batchId) {
  return request(`/api/batches/${batchId}/tasks`);
}

export function pullUserProfile() {
  return request('/api/me');
}

// Stripe 支付相关 API
export function getStripeConfig() {
  return request('/api/stripe/config', { silent: true });
}

export function createStripeCheckout(packageId) {
  return request(`/api/stripe/create-checkout-session?package_id=${packageId}`, { method: 'POST' });
}

export function createAlipayPayment(packageId) {
  return request(`/api/stripe/create-alipay-payment?package_id=${packageId}`, { method: 'POST' });
}

export function createWechatPayment(packageId, customAmount = null) {
  const params = [`package_id=${packageId}`];
  if (customAmount !== null) {
    params.push(`custom_amount=${customAmount}`);
  }
  return request(`/api/stripe/create-wechat-payment?${params.join('&')}`, { method: 'POST' });
}

export function getStripePaymentStatus(orderId) {
  return request(`/api/stripe/payment-status/${orderId}`, { silent: true });
}

export { request as apiRequest };

