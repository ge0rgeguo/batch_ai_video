import { MODEL_CONFIG, BATCH_STATUS_META, TASK_STATUS_META } from './constants.js';

const tooltipEstimatedHeight = 200;

const selectors = {
  loginContainer: () => document.getElementById('login-container'),
  appContainer: () => document.getElementById('app-container'),
  userDisplay: () => document.getElementById('user-display'),
  userCredits: () => document.getElementById('user-credits'),
  batchTableBody: () => document.getElementById('batch-tbody'),
  pageInfo: () => document.getElementById('page-info'),
  thumb: () => document.getElementById('thumb'),
  removeImageBtn: () => document.getElementById('remove-img'),
  imageInput: () => document.getElementById('image-file'),
  imageFilename: () => document.getElementById('image-filename'),
  promptInput: () => document.getElementById('prompt'),
  modelSelect: () => document.getElementById('model'),
  orientationSelect: () => document.getElementById('orientation'),
  sizeSelect: () => document.getElementById('size'),
  durationSelect: () => document.getElementById('duration'),
  numVideosInput: () => document.getElementById('num-videos'),
};

export function showLoginView() {
  selectors.loginContainer()?.classList.remove('hidden');
  selectors.appContainer()?.classList.add('hidden');
}

export function showAppView() {
  selectors.loginContainer()?.classList.add('hidden');
  selectors.appContainer()?.classList.remove('hidden');
}

export function updateUserInfo(user) {
  const display = selectors.userDisplay();
  const credits = selectors.userCredits();
  if (display) {
    display.textContent = user ? `👤 ${user.username}` : '';
  }
  if (credits) {
    const creditValue = user?.credits ?? 0;
    credits.textContent = `💎 余额：${creditValue}`;
  }
}

export function updatePagination(page, totalPages) {
  const pageInfo = selectors.pageInfo();
  if (pageInfo) {
    pageInfo.textContent = `第 ${page} / ${Math.max(totalPages, 1)} 页`;
  }
}

export function initDurationOptions() {
  const modelSelect = selectors.modelSelect();
  if (!modelSelect) return;
  updateDurationOptions(modelSelect.value || 'sora-2');
}

export function updateDurationOptions(model) {
  const durationSelect = selectors.durationSelect();
  const sizeSelect = selectors.sizeSelect();
  const config = MODEL_CONFIG[model] || MODEL_CONFIG['sora-2'];

  if (durationSelect) {
    const currentValue = durationSelect.value;
    durationSelect.innerHTML = '';
    config.durations.forEach((duration) => {
      const option = document.createElement('option');
      option.value = String(duration);
      const cost = config.pricing[duration] || 0;
      option.textContent = `${duration}秒 (${cost}分)`;
      durationSelect.appendChild(option);
    });
    if (config.durations.includes(Number(currentValue))) {
      durationSelect.value = currentValue;
    }
  }

  if (sizeSelect) {
    const defaultSize = config.allowedSizes[0] || 'small';
    sizeSelect.value = defaultSize;
    sizeSelect.disabled = config.allowedSizes.length === 1;
  }
}

export function setImagePreview(src, filename = null) {
  const thumb = selectors.thumb();
  const removeBtn = selectors.removeImageBtn();
  const filenameDiv = selectors.imageFilename();
  const fileInput = selectors.imageInput();
  
  if (thumb) {
    thumb.src = src;
    thumb.classList.remove('hidden');
  }
  if (removeBtn) {
    removeBtn.classList.remove('hidden');
  }
  
  // 显示文件名
  if (filenameDiv) {
    if (filename) {
      filenameDiv.textContent = `📎 ${filename}`;
      filenameDiv.classList.remove('hidden');
    } else {
      filenameDiv.classList.add('hidden');
    }
  }
  
  // 隐藏文件输入框（当显示已上传的图片时）
  if (fileInput && filename) {
    fileInput.classList.add('hidden');
  }
}

export function clearImagePreview() {
  const thumb = selectors.thumb();
  const removeBtn = selectors.removeImageBtn();
  const imageInput = selectors.imageInput();
  const filenameDiv = selectors.imageFilename();
  
  if (thumb) {
    thumb.src = '';
    thumb.classList.add('hidden');
  }
  if (removeBtn) {
    removeBtn.classList.add('hidden');
  }
  if (imageInput) {
    imageInput.value = '';
    imageInput.classList.remove('hidden');
  }
  if (filenameDiv) {
    filenameDiv.textContent = '';
    filenameDiv.classList.add('hidden');
  }
}

export function fillBatchForm(batch) {
  const promptInput = selectors.promptInput();
  const modelSelect = selectors.modelSelect();
  const orientationSelect = selectors.orientationSelect();
  const sizeSelect = selectors.sizeSelect();
  const durationSelect = selectors.durationSelect();
  const numVideosInput = selectors.numVideosInput();

  if (promptInput) promptInput.value = batch.prompt || '';
  if (modelSelect) {
    modelSelect.value = batch.model;
    updateDurationOptions(batch.model);
  }
  if (orientationSelect) orientationSelect.value = batch.orientation;
  if (sizeSelect) sizeSelect.value = batch.size;
  if (durationSelect) durationSelect.value = String(batch.duration);
  if (numVideosInput) numVideosInput.value = String(batch.num_videos || 1);
}

export function renderBatchTable(batches, { expandedBatchIds = new Set(), startIndex = 0 } = {}) {
  const tbody = selectors.batchTableBody();
  if (!tbody) return;

  tbody.innerHTML = '';
  batches.forEach((batch, idx) => {
    const isExpanded = expandedBatchIds.has(batch.id);
    const row = buildBatchRow(batch, startIndex + idx + 1, isExpanded);
    tbody.appendChild(row);
    if (isExpanded) {
      const detailRow = buildTaskDetailShell(batch.id);
      row.after(detailRow);
    }
  });
}

export function tryUpdateBatchTable(batches) {
  const tbody = selectors.batchTableBody();
  if (!tbody) return false;

  const rows = Array.from(tbody.querySelectorAll('tr.batch-row'));
  if (rows.length !== batches.length) {
    return false;
  }

  let valid = true;
  batches.forEach((batch) => {
    const row = tbody.querySelector(`tr.batch-row[data-batch-id="${batch.id}"]`);
    if (!row) {
      valid = false;
      return;
    }
    updateBatchStatusCell(row, batch);
  });
  return valid;
}

export function renderTaskDetail(batchId, tasks) {
  const tbody = document.getElementById(`tasks-tbody-${batchId}`);
  if (!tbody) return;

  tbody.innerHTML = '';
  if (!tasks.length) {
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#718096;padding:20px;">暂无任务</td></tr>';
    return;
  }

  tasks.forEach((task, index) => {
    const statusMeta = TASK_STATUS_META[task.status] || TASK_STATUS_META.pending;
    const row = document.createElement('tr');
    row.dataset.taskId = task.id;

    const resultUrl = resolveResultUrl(task.result_path);
    const resultHtml = buildResultCell(task, resultUrl);
    
    // 构建状态显示，如果是 in_progress 且有 progress 字段，显示进度
    let statusDisplay = statusMeta.label;
    if (task.status === 'in_progress' && task.progress) {
      statusDisplay = `${statusMeta.label} (${task.progress})`;
    }
    
    // 计算任务用时
    const taskDuration = formatDuration(task.created_at, task.updated_at, task.status);

    row.innerHTML = `
      <td style="text-align:center;">${index + 1}</td>
      <td><span class="${statusMeta.className}">${statusDisplay}</span></td>
      <td style="text-align:center;">${taskDuration}</td>
      <td>${resultHtml}</td>
      <td>
        <div class="action-buttons">
          ${resultUrl ? `<button type="button" class="btn btn-primary" data-action="download-task" data-task-id="${task.id}" data-result-url="${escapeHtml(resultUrl)}" data-batch-id="${batchId}">下载</button>` : ''}
          ${task.status === 'failed' ? `<button type="button" class="btn btn-primary" data-action="retry-task" data-task-id="${task.id}" data-batch-id="${batchId}">重试</button>` : ''}
          <button type="button" class="btn btn-danger" data-action="delete-task" data-task-id="${task.id}" data-batch-id="${batchId}">删除</button>
        </div>
      </td>
    `;

    const link = row.querySelector('.result-link');
    if (link && resultUrl) {
      link.href = resultUrl;
    }

    tbody.appendChild(row);
  });
}

export function removeTaskDetail(batchId) {
  const detailRow = document.querySelector(`tr.tasks-detail-row[data-batch-id="${batchId}"]`);
  if (detailRow) {
    detailRow.remove();
  }
}

export function toggleBatchExpansion(batchId, expanded) {
  const row = getBatchRow(batchId);
  if (!row) return;
  row.classList.toggle('expanded', expanded);

  const toggleBtn = row.querySelector('[data-action="toggle-detail"]');
  if (toggleBtn) {
    toggleBtn.setAttribute('aria-expanded', String(expanded));
    toggleBtn.innerHTML = `<span class="expand-icon ${expanded ? 'expanded' : ''}">▶</span>${expanded ? '收起' : '查看'}`;
  }

  if (!expanded) {
    removeTaskDetail(batchId);
  } else {
    const existing = document.querySelector(`tr.tasks-detail-row[data-batch-id="${batchId}"]`);
    if (!existing) {
      const detailRow = buildTaskDetailShell(batchId);
      row.after(detailRow);
    }
  }
}

export function getBatchRow(batchId) {
  const tbody = selectors.batchTableBody();
  if (!tbody) return null;
  return tbody.querySelector(`tr.batch-row[data-batch-id="${batchId}"]`);
}

export function ensureTaskDetailShell(batchId) {
  let detailRow = document.querySelector(`tr.tasks-detail-row[data-batch-id="${batchId}"]`);
  if (!detailRow) {
    const batchRow = getBatchRow(batchId);
    if (!batchRow) return null;
    detailRow = buildTaskDetailShell(batchId);
    batchRow.after(detailRow);
  }
  return detailRow;
}

export function updatePromptTooltip(cell) {
  if (!cell) return;
  const tooltip = cell.querySelector('.prompt-tooltip');
  if (!tooltip) return;

  const prompt = cell.dataset.fullPrompt || '';
  tooltip.textContent = prompt;

  const rect = cell.getBoundingClientRect();
  const spaceBelow = window.innerHeight - rect.bottom;
  const spaceAbove = rect.top;
  if (spaceBelow < tooltipEstimatedHeight && spaceAbove > spaceBelow) {
    tooltip.classList.add('show-above');
  } else {
    tooltip.classList.remove('show-above');
  }
}

function buildBatchRow(batch, displayIndex, expanded) {
  const row = document.createElement('tr');
  row.className = `batch-row${expanded ? ' expanded' : ''}`;
  row.dataset.batchId = batch.id;

  // 序号
  const indexCell = document.createElement('td');
  indexCell.textContent = displayIndex;
  row.appendChild(indexCell);

  // 创建时间
  const createdCell = document.createElement('td');
  createdCell.textContent = formatDateTime(batch.created_at);
  row.appendChild(createdCell);

  // 完成用时
  const durationCell = document.createElement('td');
  durationCell.style.textAlign = 'center';
  const batchStatus = batch.completed === batch.total && batch.total > 0 ? 'completed' : 'in_progress';
  durationCell.textContent = formatDuration(batch.created_at, batch.updated_at, batchStatus);
  row.appendChild(durationCell);

  // 提示词单元格
  const promptCell = document.createElement('td');
  promptCell.className = 'prompt-cell';
  promptCell.dataset.fullPrompt = batch.prompt || '';
  const preview = document.createElement('div');
  preview.className = 'prompt-preview';
  preview.innerHTML = buildPromptPreview(batch.prompt);
  const tooltip = document.createElement('div');
  tooltip.className = 'prompt-tooltip';
  promptCell.appendChild(preview);
  promptCell.appendChild(tooltip);
  row.appendChild(promptCell);

  // 图片单元格
  const imageCell = document.createElement('td');
  imageCell.style.textAlign = 'center';
  if (batch.image_path) {
    const img = document.createElement('img');
    img.src = `/uploads/${encodeURIComponent(batch.image_path)}`;
    img.className = 'thumb-small';
    img.alt = '图片预览';
    imageCell.appendChild(img);
  } else {
    const placeholder = document.createElement('span');
    placeholder.className = 'text-muted';
    placeholder.textContent = '-';
    imageCell.appendChild(placeholder);
  }
  row.appendChild(imageCell);

  // 状态单元格
  const statusCell = document.createElement('td');
  statusCell.className = 'batch-status-cell';
  statusCell.innerHTML = buildStatusCellContent(batch);
  row.appendChild(statusCell);

  // 操作单元格
  const actionCell = document.createElement('td');
  actionCell.innerHTML = `
    <div class="action-buttons">
      <button type="button" class="btn btn-secondary" data-action="toggle-detail" data-batch-id="${batch.id}" aria-expanded="${expanded}">
        <span class="expand-icon ${expanded ? 'expanded' : ''}">▶</span>${expanded ? '收起' : '查看'}
      </button>
      <button type="button" class="btn btn-primary" data-action="refill-batch" data-batch-id="${batch.id}">再来一批</button>
      <button type="button" class="btn btn-danger" data-action="delete-batch" data-batch-id="${batch.id}">删除</button>
    </div>
  `;
  row.appendChild(actionCell);

  return row;
}

function buildTaskDetailShell(batchId) {
  const detailRow = document.createElement('tr');
  detailRow.className = 'tasks-detail-row';
  detailRow.dataset.batchId = batchId;
  detailRow.innerHTML = `
    <td colspan="7" class="tasks-detail-cell">
      <div class="tasks-inner-container">
        <div class="tasks-actions">
          <button type="button" class="btn btn-secondary" data-action="retry-failed" data-batch-id="${batchId}">重试失败</button>
          <button type="button" class="btn btn-secondary" data-action="download-batch" data-batch-id="${batchId}">一键下载</button>
        </div>
        <table class="tasks-table">
          <thead>
            <tr>
              <th style="width:50px;">序号</th>
              <th style="width:160px;">状态</th>
              <th style="width:100px;">用时</th>
              <th style="width:380px;">结果</th>
              <th style="width:240px;">操作</th>
            </tr>
          </thead>
          <tbody id="tasks-tbody-${batchId}"></tbody>
        </table>
      </div>
    </td>
  `;
  return detailRow;
}

function buildStatusCellContent(batch) {
  const meta = resolveBatchStatus(batch);
  return `
    <span class="${meta.className}" style="color:${meta.color};font-weight:600;">${meta.label}</span><br />
    <small class="text-muted">总:${batch.total} 完成:${batch.completed} 失败:${batch.failed}</small>
  `;
}

function updateBatchStatusCell(row, batch) {
  const cell = row.querySelector('.batch-status-cell');
  if (!cell) return;
  cell.innerHTML = buildStatusCellContent(batch);
}

function resolveBatchStatus(batch) {
  if (batch.running > 0 || batch.queued > 0) {
    return BATCH_STATUS_META.running;
  }
  if (batch.failed > 0) {
    return BATCH_STATUS_META.partialFailed;
  }
  if (batch.completed === batch.total && batch.total > 0) {
    return BATCH_STATUS_META.completed;
  }
  return BATCH_STATUS_META.queued;
}

function buildPromptPreview(prompt = '') {
  const trimmed = prompt ?? '';
  if (trimmed.length <= 50) {
    return escapeHtml(trimmed);
  }
  return `${escapeHtml(trimmed.slice(0, 50))}...`;
}

function formatDateTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hour = String(date.getHours()).padStart(2, '0');
  const minute = String(date.getMinutes()).padStart(2, '0');
  const second = String(date.getSeconds()).padStart(2, '0');
  return `${year}/${month}/${day} ${hour}:${minute}:${second}`;
}

function escapeHtml(str = '') {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function formatDuration(createdAt, updatedAt, status) {
  // 只有已完成的任务才计算用时
  if (status !== 'completed') {
    return '-';
  }
  
  const created = new Date(createdAt);
  const updated = new Date(updatedAt);
  
  if (Number.isNaN(created.getTime()) || Number.isNaN(updated.getTime())) {
    return '-';
  }
  
  const diffMs = updated.getTime() - created.getTime();
  if (diffMs < 0) {
    return '-';
  }
  
  const totalSeconds = Math.floor(diffMs / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  
  const parts = [];
  if (hours > 0) {
    parts.push(`${hours}时`);
  }
  if (minutes > 0 || hours > 0) {
    parts.push(`${minutes}分`);
  }
  parts.push(`${seconds}秒`);
  
  return parts.join('');
}

function resolveResultUrl(path) {
  if (!path) return '';
  if (/^https?:\/\//i.test(path)) {
    return path;
  }
  return `/public/temp-results/${path}`;
}

function buildResultCell(task, resultUrl) {
  if (resultUrl) {
    return `<a class="btn-link result-link" href="${resultUrl}" target="_blank" rel="noopener noreferrer">查看视频</a>`;
  }
  if (task.error_summary) {
    return `<span style="color:#e53e3e;font-size:12px;">${escapeHtml(task.error_summary)}</span>`;
  }
  return '<span class="text-muted">-</span>';
}
