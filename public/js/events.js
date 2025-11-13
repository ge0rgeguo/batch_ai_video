export function registerEventHandlers(handlers) {
  const loginForm = document.getElementById('login-form');
  if (loginForm) {
    loginForm.addEventListener('submit', (event) => {
      event.preventDefault();
      const formData = new FormData(loginForm);
      handlers.onLogin?.({
        username: formData.get('username')?.toString().trim() ?? '',
        password: formData.get('password')?.toString() ?? '',
      });
    });
  }

  const logoutBtn = document.getElementById('logout-btn');
  if (logoutBtn) {
    logoutBtn.addEventListener('click', () => handlers.onLogout?.());
  }

  const generateBtn = document.getElementById('generate-btn');
  if (generateBtn) {
    generateBtn.addEventListener('click', () => handlers.onGenerate?.());
  }

  const modelSelect = document.getElementById('model');
  if (modelSelect) {
    modelSelect.addEventListener('change', (event) => {
      handlers.onModelChange?.(event.target.value);
    });
  }

  const imageInput = document.getElementById('image-file');
  if (imageInput) {
    imageInput.addEventListener('change', (event) => {
      const file = event.target.files?.[0];
      if (file) {
        handlers.onImageSelected?.(file);
      }
    });
  }

  const removeImageBtn = document.getElementById('remove-img');
  if (removeImageBtn) {
    removeImageBtn.addEventListener('click', () => handlers.onRemoveImage?.());
  }

  const prevPageBtn = document.getElementById('prev-page');
  if (prevPageBtn) {
    prevPageBtn.addEventListener('click', () => handlers.onPagination?.('prev'));
  }

  const nextPageBtn = document.getElementById('next-page');
  if (nextPageBtn) {
    nextPageBtn.addEventListener('click', () => handlers.onPagination?.('next'));
  }

  const batchTable = document.getElementById('batch-table');
  if (batchTable) {
    batchTable.addEventListener('click', (event) => {
      const actionEl = event.target.closest('[data-action]');
      if (actionEl) {
        event.preventDefault();
        handlers.onAction?.(actionEl.dataset.action, actionEl.dataset, event);
        return;
      }

      const detailRow = event.target.closest('tr.tasks-detail-row');
      if (detailRow) {
        return; // 不对任务详情表进行行级切换
      }

      const batchRow = event.target.closest('tr.batch-row');
      if (batchRow) {
        handlers.onRowToggle?.(batchRow.dataset.batchId, event);
      }
    });

    batchTable.addEventListener('mouseover', (event) => {
      const cell = event.target.closest('.prompt-cell');
      if (cell && batchTable.contains(cell)) {
        cell.classList.add('is-hovered');
        handlers.onPromptHover?.(cell);
      }
    });

    batchTable.addEventListener('mouseout', (event) => {
      const cell = event.target.closest('.prompt-cell');
      if (cell) {
        cell.classList.remove('is-hovered');
        const tooltip = cell.querySelector('.prompt-tooltip');
        tooltip?.classList.remove('show-above');
      }
    });
  }
}
