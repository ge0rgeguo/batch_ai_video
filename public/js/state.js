import { AUTO_REFRESH_INTERVAL } from './constants.js';

export const state = {
  currentUser: null,
  uploadedImagePath: null,
  previewObjectUrl: null,
  autoRefreshTimerId: null,
  currentPage: 1,
  totalPages: 1,
  expandedBatches: new Set(),
  batches: [],
  debug: false,
  language: 'zh-CN',
};

export function setCurrentUser(user) {
  state.currentUser = user;
}

export function setUploadedImagePath(path) {
  state.uploadedImagePath = path;
}

export function clearUploadedImagePath() {
  state.uploadedImagePath = null;
}

export function setPreviewObjectUrl(url) {
  if (state.previewObjectUrl && state.previewObjectUrl !== url) {
    URL.revokeObjectURL(state.previewObjectUrl);
  }
  state.previewObjectUrl = url;
}

export function clearPreviewObjectUrl() {
  if (state.previewObjectUrl) {
    URL.revokeObjectURL(state.previewObjectUrl);
    state.previewObjectUrl = null;
  }
}

export function setCurrentPage(page) {
  state.currentPage = page;
}

export function setTotalPages(pages) {
  state.totalPages = pages;
}

export function setBatches(batches) {
  state.batches = Array.isArray(batches) ? batches : [];
}

export function addExpandedBatch(batchId) {
  state.expandedBatches.add(batchId);
}

export function removeExpandedBatch(batchId) {
  state.expandedBatches.delete(batchId);
}

export function isBatchExpanded(batchId) {
  return state.expandedBatches.has(batchId);
}

export function clearExpandedBatches() {
  state.expandedBatches.clear();
}

export function restartAutoRefresh(callback) {
  stopAutoRefresh();
  state.autoRefreshTimerId = window.setInterval(callback, AUTO_REFRESH_INTERVAL);
}

export function stopAutoRefresh() {
  if (state.autoRefreshTimerId) {
    clearInterval(state.autoRefreshTimerId);
    state.autoRefreshTimerId = null;
  }
}

export function setDebug(enabled) {
  state.debug = Boolean(enabled);
}
