import { PAGE_SIZE } from './constants.js';
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
} from './ui.js';
import {
  getCurrentUser,
  login,
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

async function init() {
  initDurationOptions();

  registerEventHandlers({
    onLogin: handleLogin,
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

  await bootstrapCurrentUser();
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
    setLoginError('请输入用户名和密码');
    return;
  }
  setLoginError('');

  const response = await login({ username, password });
  if (!response.ok) {
    setLoginError(response?.error?.message || '登录失败');
    return;
  }

  const profile = await pullUserProfile();
  const user = profile.ok ? profile.data : response.data;
  await enterApp(user);
}

async function enterApp(user) {
  setCurrentUser(user);
  updateUserInfo(user);
  setCurrentPage(1);
  showAppView();
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
    showToast('请输入提示词', 'error');
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

  showToast('批次创建成功', 'success');
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
    showToast('未找到对应批次', 'error');
    return;
  }

  fillBatchForm(batch);

  if (batch.image_path) {
    setUploadedImagePath(batch.image_path);
    clearPreviewObjectUrl();
    setImagePreview(`/uploads/${batch.image_path}`);
  } else {
    clearUploadedImagePath();
    clearPreviewObjectUrl();
    clearImagePreview();
  }

  window.scrollTo({ top: 0, behavior: 'smooth' });
  showToast('参数已回填，可修改后重新生成', 'info');
}

async function handleDeleteBatch(batchId) {
  if (!batchId) return;
  if (!window.confirm('确认删除整个批次？')) {
    return;
  }
  const response = await deleteBatch(batchId);
  if (!response.ok) {
    return;
  }
  removeExpandedBatch(batchId);
  removeTaskDetail(batchId);
  showToast('批次已删除', 'success');
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
    showToast('没有失败的任务', 'info');
    return;
  }
  await Promise.all(failedTasks.map((task) => retryTask(task.id)));
  showToast(`已重试 ${failedTasks.length} 个失败任务`, 'success');
  await refreshBatchTasks(batchId);
  await loadBatches({ silent: true });
}

async function handleRetryTask(taskId, batchId) {
  if (!taskId) return;
  const response = await retryTask(taskId);
  if (!response.ok) {
    return;
  }
  showToast('任务已重新提交', 'success');
  if (batchId) {
    await refreshBatchTasks(batchId);
    await loadBatches({ silent: true });
  }
}

async function handleDeleteTask(taskId, batchId) {
  if (!taskId) return;
  if (!window.confirm('确认删除此任务？')) {
    return;
  }
  const response = await deleteTask(taskId);
  if (!response.ok) {
    return;
  }
  showToast('任务已删除', 'success');
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
  setImagePreview(objectUrl);
  showToast('图片上传成功', 'success');
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
  showToast('图片已删除', 'success');
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

init();
