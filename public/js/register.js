import { SMS_RESEND_SECONDS } from './constants.js';
import { sendSmsCode, verifySmsCode } from './api.js';
import { showToast } from './toast.js';

const form = document.getElementById('register-form');
const mobileInput = document.getElementById('register-mobile');
const codeInput = document.getElementById('register-code');
const sendBtn = document.getElementById('register-send-btn');
const countdownEl = document.getElementById('register-countdown');
const submitBtn = document.getElementById('register-submit');
const errorEl = document.getElementById('register-error');

let countdownTimerId = null;
let countdownRemaining = 0;

const REGISTER_SCENE = 'register';

function setError(message) {
  if (!errorEl) return;
  if (message) {
    errorEl.textContent = message;
    errorEl.style.display = 'block';
  } else {
    errorEl.textContent = '';
    errorEl.style.display = 'none';
  }
}

function getMobileValue() {
  return (mobileInput?.value || '').trim();
}

function startCountdown() {
  clearCountdown();
  countdownRemaining = SMS_RESEND_SECONDS;
  updateCountdown();
  countdownTimerId = window.setInterval(() => {
    countdownRemaining -= 1;
    if (countdownRemaining <= 0) {
      clearCountdown();
    } else {
      updateCountdown();
    }
  }, 1000);
}

function updateCountdown() {
  if (!countdownEl || !sendBtn) return;
  if (countdownRemaining > 0) {
    countdownEl.textContent = `验证码已发送，${countdownRemaining}s 后可重新获取`;
    countdownEl.classList.remove('hidden');
    sendBtn.disabled = true;
    sendBtn.textContent = `${countdownRemaining}s`;
  } else {
    countdownEl.textContent = '';
    countdownEl.classList.add('hidden');
    sendBtn.disabled = false;
    sendBtn.textContent = '获取验证码';
  }
}

function clearCountdown() {
  if (countdownTimerId) {
    clearInterval(countdownTimerId);
    countdownTimerId = null;
  }
  countdownRemaining = 0;
  updateCountdown();
}

sendBtn?.addEventListener('click', async () => {
  const mobile = getMobileValue();
  if (!mobile) {
    setError('请输入手机号');
    mobileInput?.focus();
    return;
  }
  setError('');
  sendBtn.disabled = true;
  sendBtn.textContent = '发送中...';
  try {
    const response = await sendSmsCode({ mobile, scene: REGISTER_SCENE });
    if (!response.ok) {
      setError(response?.error?.message || '验证码发送失败');
      return;
    }
    showToast('验证码已发送，请注意查收', 'success');
    startCountdown();
  } catch (error) {
    setError('验证码发送失败，请稍后再试');
  } finally {
    if (countdownRemaining <= 0) {
      sendBtn.disabled = false;
      sendBtn.textContent = '获取验证码';
    }
  }
});

form?.addEventListener('submit', async (event) => {
  event.preventDefault();
  const mobile = getMobileValue();
  const code = (codeInput?.value || '').trim();

  if (!mobile) {
    setError('请输入手机号');
    mobileInput?.focus();
    return;
  }
  if (!code) {
    setError('请输入短信验证码');
    codeInput?.focus();
    return;
  }

  setError('');
  const originalText = submitBtn?.textContent;
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.textContent = '提交中...';
  }

  try {
    const response = await verifySmsCode({ mobile, code, scene: REGISTER_SCENE });
    if (!response.ok) {
      setError(response?.error?.message || '注册失败');
      return;
    }
    clearCountdown();
    showToast('注册成功，正在跳转...', 'success');
    setTimeout(() => {
      window.location.href = '/index.html';
    }, 800);
  } catch (error) {
    setError('注册失败，请稍后再试');
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.textContent = originalText ?? '完成注册';
    }
  }
});


