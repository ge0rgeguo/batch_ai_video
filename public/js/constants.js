export const PAGE_SIZE = 10;
export const AUTO_REFRESH_INTERVAL = 5000;
export const SMS_RESEND_SECONDS = 60;

export const MODEL_CONFIG = {
  'sora-2-all': {
    durations: [10, 15],
    allowedSizes: ['small'],
    pricing: { 10: 10, 15: 15 },
  },
  'sora-2-pro-all': {
    durations: [10, 15, 25],
    allowedSizes: ['large'],
    pricing: { 10: 50, 15: 75, 25: 100 },
  },
  'veo_3_1': {
    durations: [8],
    allowedSizes: ['720p', '1080p', '4k'],
    defaultSize: '1080p',
    pricingBySize: { '720p': 10, '1080p': 50, '4k': 100 },
  },
};

export const TASK_STATUS_META = {
  pending: { label: '等待中', className: 'status-pending' },
  queued: { label: '排队中', className: 'status-queued' },
  running: { label: '进行中', className: 'status-running' },
  completed: { label: '已完成', className: 'status-completed' },
  failed: { label: '失败', className: 'status-failed' },
  cancelled: { label: '已取消', className: 'status-cancelled' },
};

export const BATCH_STATUS_META = {
  running: { label: '进行中', className: 'status-running', color: '#3182ce' },
  partialFailed: { label: '部分失败', className: 'status-failed', color: '#e53e3e' },
  completed: { label: '全部完成', className: 'status-completed', color: '#38a169' },
  queued: { label: '待启动', className: 'status-pending', color: '#718096' },
};

export const TOAST_DEFAULT_DURATION = 3000;
