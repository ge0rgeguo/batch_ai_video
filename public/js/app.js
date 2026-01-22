import { PAGE_SIZE, SMS_RESEND_SECONDS } from './constants.js';
import {
  state,
  setCurrentUser,
  setUploadedImagePath,
  clearUploadedImagePath,
  setPreviewObjectUrl,
  clearPreviewObjectUrl,
  setCurrentPage,
  setTotalPages,
  setBatches,
  addExpandedBatch,
  removeExpandedBatch,
  isBatchExpanded,
  clearExpandedBatches,
  restartAutoRefresh,
  stopAutoRefresh,
} from './state.js';
import { showToast } from './toast.js';
import {
  showLoginView,
  showAppView,
  updateUserInfo,
  updatePagination,
  initDurationOptions,
  updateDurationOptions,
  setImagePreview,
  clearImagePreview,
  renderBatchTable,
  renderTaskDetail,
  toggleBatchExpansion,
  ensureTaskDetailShell,
  removeTaskDetail,
  fillBatchForm,
  tryUpdateBatchTable,
  updatePromptTooltip,
  switchAppView,
} from './ui.js';
import { initCreditsView, onShowCreditsView } from './credits.js';
import {
  getCurrentUser,
  login,
  sendSmsCode,
  verifySmsCode,
  logout,
  fetchBatches,
  fetchBatchTasks,
  createBatch,
  uploadImage,
  deleteImage,
  deleteBatch,
  retryTask,
  deleteTask,
  pullUserProfile,
} from './api.js';
import { registerEventHandlers } from './events.js';
import { initLanguage, toggleLanguage, t } from './i18n.js';

let currentLoginMode = 'sms';
let smsCountdownTimerId = null;
let smsCountdownRemaining = 0;

async function init() {
  initLanguage();
  initCreditsView();
  initDurationOptions();

  registerEventHandlers({
    onLogin: handleLogin,
    onLoginModeChange: handleLoginModeChange,
    onSmsSend: handleSmsSend,
    onSmsLogin: handleSmsLogin,
    onLogout: handleLogout,
    onGenerate: handleGenerate,
    onModelChange: (model) => updateDurationOptions(model),
    onImageSelected: handleImageSelected,
    onRemoveImage: handleRemoveImage,
    onAction: handleAction,
    onRowToggle: handleRowToggle,
    onPagination: handlePagination,
    onPromptHover: updatePromptTooltip,
  });

  // Bind Nav Events
  document.getElementById('nav-create-btn')?.addEventListener('click', () => switchAppView('create'));
  document.getElementById('nav-home-btn')?.addEventListener('click', () => switchAppView('create'));

  const goCredits = () => {
    switchAppView('credits');
    onShowCreditsView();
  };
  // document.getElementById('nav-credits-btn')?.addEventListener('click', goCredits); // Removed nav button
  document.getElementById('user-credits')?.addEventListener('click', goCredits);
  // document.getElementById('nav-credits-link')?.addEventListener('click', goCredits);

  // Close Credits Button
  document.getElementById('close-credits-btn')?.addEventListener('click', () => switchAppView('create'));

  // Language Toggle (both landing page and app page)
  document.getElementById('lang-toggle-btn')?.addEventListener('click', handleLanguageToggle);
  document.getElementById('app-lang-toggle-btn')?.addEventListener('click', handleLanguageToggle);

  handleLoginModeChange(currentLoginMode);
  await bootstrapCurrentUser();
}

function handleLanguageToggle() {
  toggleLanguage();
  // Refresh dynamic content that might depend on language
  if (state.currentUser) {
    updateUserInfo(state.currentUser);
    loadBatches();
  }
  updateDurationOptions(document.getElementById('model')?.value);
}

async function bootstrapCurrentUser() {
  try {
    const response = await getCurrentUser();
    if (response.ok) {
      await enterApp(response.data);
    } else {
      showLoginView();
    }
  } catch (error) {
    showLoginView();
  }
}

async function handleLogin({ username, password }) {
  const errorEl = document.getElementById('login-error');
  if (!username || !password) {
    setLoginError('请输入用户名和密码'); // Leaving as is for now, or could localize
    return;
  }
  setLoginError('');

  const response = await login({ username, password });
  if (!response.ok) {
    setLoginError(response?.error?.message || t('toast.login_failed') || '登录失败');
    return;
  }

  const profile = await pullUserProfile();
  const user = profile.ok ? profile.data : response.data;
  await enterApp(user);
}

function handleLoginModeChange(mode) {
  if (mode !== 'password' && mode !== 'sms') {
    return;
  }
  currentLoginMode = mode;
  const passwordForm = document.getElementById('login-form');
  const smsForm = document.getElementById('sms-login-form');
  passwordForm?.classList.toggle('hidden', mode !== 'password');
  smsForm?.classList.toggle('hidden', mode !== 'sms');
  const tabs = document.querySelectorAll('#login-tabs button[data-login-mode]');
  tabs.forEach((btn) => {
    btn.classList.toggle('active', btn.dataset.loginMode === mode);
  });
  setLoginError('');
  setSmsLoginError('');
  if (mode === 'password') {
    resetSmsLoginUI();
  }
}

async function handleSmsSend() {
  const mobileInput = document.getElementById('sms-mobile');
  if (!mobileInput) return;
  const mobile = mobileInput.value.trim();
  if (!mobile) {
    setSmsLoginError(t('auth.placeholder.mobile'));
    mobileInput.focus();
    return;
  }

  setSmsLoginError('');
  setSmsSendingState(true, '发送中...');
  try {
    const response = await sendSmsCode({ mobile, scene: 'login' });
    if (!response.ok) {
      clearSmsCountdown();
      setSmsSendingState(false);
      return;
    }
    showToast(t('toast.verify_code_sent'), 'success');
    startSmsCountdown();
  } catch (error) {
    clearSmsCountdown();
    setSmsSendingState(false);
    setSmsLoginError('验证码发送失败，请稍后重试');
  }
}

async function handleSmsLogin({ mobile, code }) {
  const mobileInput = document.getElementById('sms-mobile');
  const codeInput = document.getElementById('sms-code');
  const submitBtn = document.getElementById('sms-login-submit');

  const mobileValue = (mobile || mobileInput?.value || '').trim();
  const codeValue = (code || codeInput?.value || '').trim();

  if (!mobileValue) {
    setSmsLoginError(t('auth.placeholder.mobile'));
    mobileInput?.focus();
    return;
  }
  if (!codeValue) {
    setSmsLoginError(t('auth.placeholder.code'));
    codeInput?.focus();
    return;
  }

  setSmsLoginError('');
  const originalText = submitBtn?.textContent;
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.textContent = '验证中...';
  }

  try {
    const response = await verifySmsCode({ mobile: mobileValue, code: codeValue, scene: 'login' });
    if (!response.ok) {
      setSmsLoginError(response?.error?.message || '验证码验证失败');
      return;
    }
    clearSmsCountdown();
    resetSmsLoginUI();
    showToast(t('toast.login_success'), 'success');
    await enterApp(response.data);
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.textContent = originalText ?? t('auth.btn.login_register');
    }
  }
}

async function enterApp(user) {
  setCurrentUser(user);
  updateUserInfo(user);
  setCurrentPage(1);
  showAppView();
  resetSmsLoginUI();
  await loadBatches();
  restartAutoRefresh(() => loadBatches({ silent: true }));
}

async function handleLogout() {
  try {
    await logout();
  } finally {
    stopAutoRefresh();
    clearExpandedBatches();
    setBatches([]);
    setCurrentUser(null);
    updateUserInfo(null);
    clearImagePreview();
    clearUploadedImagePath();
    clearPreviewObjectUrl();
    setLoginError('');
    showLoginView();
    handleLoginModeChange('sms');
  }
}

async function handleGenerate() {
  const promptInput = document.getElementById('prompt');
  const modelSelect = document.getElementById('model');
  const orientationSelect = document.getElementById('orientation');
  const sizeSelect = document.getElementById('size');
  const durationSelect = document.getElementById('duration');
  const numVideosInput = document.getElementById('num-videos');

  const prompt = promptInput?.value.trim();
  if (!prompt) {
    showToast(t('toast.enter_prompt'), 'error');
    return;
  }

  const payload = {
    prompt,
    model: modelSelect?.value,
    orientation: orientationSelect?.value,
    size: sizeSelect?.value,
    duration: Number(durationSelect?.value || 0),
    num_videos: Number(numVideosInput?.value || 1),
    image_path: state.uploadedImagePath,
  };

  const idempotencyKey = `${Date.now()}-${Math.random()}`;
  const response = await createBatch(payload, { idempotencyKey });
  if (!response.ok) {
    return;
  }

  showToast(t('toast.batch_created'), 'success');
  await loadBatches();
  const profile = await pullUserProfile();
  if (profile.ok) {
    setCurrentUser(profile.data);
    updateUserInfo(profile.data);
  }
}

async function loadBatches(options = {}) {
  const { silent = false } = options;
  const response = await fetchBatches(state.currentPage, PAGE_SIZE);
  if (!response.ok) {
    return;
  }

  const data = response.data;
  setTotalPages(data.total_pages || 1);
  if (state.currentPage > state.totalPages && state.totalPages > 0) {
    setCurrentPage(state.totalPages);
    return loadBatches(options);
  }
  setBatches(data.items);
  updatePagination(state.currentPage, state.totalPages);

  const startIndex = (state.currentPage - 1) * PAGE_SIZE;
  const expandedIds = new Set(state.expandedBatches);

  if (silent) {
    const updated = tryUpdateBatchTable(data.items);
    if (!updated) {
      renderBatchTable(data.items, { expandedBatchIds: expandedIds, startIndex });
    }
  } else {
    renderBatchTable(data.items, { expandedBatchIds: expandedIds, startIndex });
  }

  if (expandedIds.size > 0) {
    await Promise.all(
      Array.from(expandedIds).map(async (batchId) => {
        await refreshBatchTasks(batchId);
      })
    );
  }
}

async function refreshBatchTasks(batchId) {
  const response = await fetchBatchTasks(batchId);
  if (!response.ok) {
    return;
  }
  ensureTaskDetailShell(batchId);
  renderTaskDetail(batchId, response.data);
}

async function handleRowToggle(batchId, event) {
  if (!batchId) return;
  if (isBatchExpanded(batchId)) {
    removeExpandedBatch(batchId);
    toggleBatchExpansion(batchId, false);
  } else {
    addExpandedBatch(batchId);
    toggleBatchExpansion(batchId, true);
    await refreshBatchTasks(batchId);
  }
}

async function handleAction(action, dataset, event) {
  const batchId = dataset.batchId;
  switch (action) {
    case 'toggle-detail':
      await handleRowToggle(batchId, event);
      break;
    case 'refill-batch':
      await handleRefillBatch(batchId);
      break;
    case 'delete-batch':
      await handleDeleteBatch(batchId);
      break;
    case 'retry-failed':
      await handleRetryFailed(batchId);
      break;
    case 'download-batch':
      if (batchId) {
        window.location.href = `/api/batches/${batchId}/download`;
      }
      break;
    case 'retry-task':
      await handleRetryTask(dataset.taskId, batchId);
      break;
    case 'delete-task':
      await handleDeleteTask(dataset.taskId, batchId);
      break;
    case 'download-task':
      if (dataset.resultUrl) {
        const url = decodeURIComponent(dataset.resultUrl);
        window.open(url, '_blank', 'noopener');
      }
      break;
    default:
      break;
  }
}

async function handleRefillBatch(batchId) {
  if (!batchId) return;
  let batch = state.batches.find((item) => item.id === batchId);
  if (!batch) {
    const response = await fetchBatches(1, 100);
    if (response.ok) {
      batch = response.data.items.find((item) => item.id === batchId);
    }
  }
  if (!batch) {
    showToast(t('toast.no_batch_found'), 'error');
    return;
  }

  fillBatchForm(batch);

  if (batch.image_path) {
    setUploadedImagePath(batch.image_path);
    clearPreviewObjectUrl();
    setImagePreview(`/uploads/${batch.image_path}`, batch.image_path);
  } else {
    clearUploadedImagePath();
    clearPreviewObjectUrl();
    clearImagePreview();
  }

  window.scrollTo({ top: 0, behavior: 'smooth' });
  showToast(t('toast.params_refilled'), 'info');
}

async function handleDeleteBatch(batchId) {
  if (!batchId) return;
  if (!window.confirm(t('confirm.delete_batch'))) {
    return;
  }
  const response = await deleteBatch(batchId);
  if (!response.ok) {
    return;
  }
  removeExpandedBatch(batchId);
  removeTaskDetail(batchId);
  showToast(t('toast.batch_deleted'), 'success');
  await loadBatches();
}

async function handleRetryFailed(batchId) {
  if (!batchId) return;
  const response = await fetchBatchTasks(batchId);
  if (!response.ok) {
    return;
  }
  const failedTasks = response.data.filter((task) => task.status === 'failed');
  if (!failedTasks.length) {
    showToast(t('toast.no_failed_tasks'), 'info');
    return;
  }
  await Promise.all(failedTasks.map((task) => retryTask(task.id)));
  showToast(t('toast.retried_tasks', { n: failedTasks.length }), 'success');
  await refreshBatchTasks(batchId);
  await loadBatches({ silent: true });
}

async function handleRetryTask(taskId, batchId) {
  if (!taskId) return;
  const response = await retryTask(taskId);
  if (!response.ok) {
    return;
  }
  showToast(t('toast.task_resubmitted'), 'success');
  if (batchId) {
    await refreshBatchTasks(batchId);
    await loadBatches({ silent: true });
  }
}

async function handleDeleteTask(taskId, batchId) {
  if (!taskId) return;
  if (!window.confirm(t('confirm.delete_task'))) {
    return;
  }
  const response = await deleteTask(taskId);
  if (!response.ok) {
    return;
  }
  showToast(t('toast.task_deleted'), 'success');
  if (batchId) {
    await refreshBatchTasks(batchId);
  }
  await loadBatches({ silent: true });
}

async function handleImageSelected(file) {
  const response = await uploadImage(file);
  if (!response.ok) {
    return;
  }
  const objectUrl = URL.createObjectURL(file);
  setPreviewObjectUrl(objectUrl);
  setUploadedImagePath(response.data.path);
  setImagePreview(objectUrl, file.name);
  showToast(t('toast.image_uploaded'), 'success');
}

async function handleRemoveImage() {
  if (!state.uploadedImagePath) {
    clearPreviewObjectUrl();
    clearImagePreview();
    return;
  }
  const response = await deleteImage(state.uploadedImagePath);
  if (!response.ok) {
    return;
  }
  clearUploadedImagePath();
  clearPreviewObjectUrl();
  clearImagePreview();
  showToast(t('toast.image_deleted'), 'success');
}

function handlePagination(direction) {
  if (direction === 'prev' && state.currentPage > 1) {
    setCurrentPage(state.currentPage - 1);
    loadBatches();
  }
  if (direction === 'next' && state.currentPage < state.totalPages) {
    setCurrentPage(state.currentPage + 1);
    loadBatches();
  }
}

function setLoginError(message) {
  const errorEl = document.getElementById('login-error');
  if (!errorEl) return;
  if (message) {
    errorEl.textContent = message;
    errorEl.style.display = 'block';
  } else {
    errorEl.textContent = '';
    errorEl.style.display = 'none';
  }
}

function setSmsSendingState(disabled, text) {
  const btn = document.getElementById('sms-send-btn');
  if (!btn) return;
  btn.disabled = disabled;
  if (text !== undefined) {
    btn.textContent = text;
  } else if (!disabled && smsCountdownRemaining <= 0) {
    btn.textContent = t('auth.btn.get_code');
  }
}

function startSmsCountdown() {
  clearSmsCountdown();
  smsCountdownRemaining = SMS_RESEND_SECONDS;
  updateSmsCountdown();
  smsCountdownTimerId = window.setInterval(() => {
    smsCountdownRemaining -= 1;
    if (smsCountdownRemaining <= 0) {
      clearSmsCountdown();
    } else {
      updateSmsCountdown();
    }
  }, 1000);
}

function updateSmsCountdown() {
  const countdownEl = document.getElementById('sms-countdown');
  const btn = document.getElementById('sms-send-btn');
  if (!countdownEl || !btn) return;
  if (smsCountdownRemaining > 0) {
    countdownEl.textContent = `验证码已发送，${smsCountdownRemaining}s 后可重新获取`; // Could be localized
    countdownEl.classList.remove('hidden');
    btn.disabled = true;
    btn.textContent = `${smsCountdownRemaining}s`;
  } else {
    countdownEl.textContent = '';
    countdownEl.classList.add('hidden');
    btn.disabled = false;
    btn.textContent = t('auth.btn.get_code');
  }
}

function clearSmsCountdown() {
  if (smsCountdownTimerId) {
    clearInterval(smsCountdownTimerId);
    smsCountdownTimerId = null;
  }
  smsCountdownRemaining = 0;
  updateSmsCountdown();
}

function resetSmsLoginUI() {
  clearSmsCountdown();
  const mobileInput = document.getElementById('sms-mobile');
  const codeInput = document.getElementById('sms-code');
  if (mobileInput) {
    mobileInput.value = '';
  }
  if (codeInput) {
    codeInput.value = '';
  }
  setSmsLoginError('');
}

function setSmsLoginError(message) {
  const errorEl = document.getElementById('sms-login-error');
  if (!errorEl) return;
  if (message) {
    errorEl.textContent = message;
    errorEl.style.display = 'block';
  } else {
    errorEl.textContent = '';
    errorEl.style.display = 'none';
  }
}

init();
