import { apiRequest, createStripeCheckout, createAlipayPayment, createWechatPayment, getStripePaymentStatus } from './api.js';
import { showToast } from './toast.js';
import { updateUserInfo } from './ui.js';

const state = {
    currentAmount: 9.9,
    currentCredits: 100,
    paymentMethod: 'alipay',
    isCustom: false,
    historyPage: 1,
    historyTotalPages: 1,
    // Stripe/Alipay/WeChat state
    stripePackageId: 'pkg_100',
    alipayPackageId: 'pkg_100',
    wechatPackageId: 'pkg_100',
    stripeAmount: 1.99,
    alipayAmount: 1.99,
    wechatAmount: 14,  // CNY (¥14 for pkg_100)
    wechatIsCustom: false,  // Track if using custom amount
    currentPaymentType: 'wechat',  // Default to wechat now
    // QR polling
    currentOrderId: null,
    pollTimer: null
};

// Stripe/Alipay 套餐配置（USD，与后端保持一致）
const STRIPE_PACKAGES = {
    'pkg_100': { price: 1.99, credits: 100 },
    'pkg_500': { price: 8.99, credits: 500 },
    'pkg_1000': { price: 15.99, credits: 1000 }
};

// 微信支付套餐配置（CNY，与后端保持一致）
const WECHAT_PACKAGES = {
    'pkg_100': { price: 14, credits: 100 },
    'pkg_500': { price: 64, credits: 500 },
    'pkg_1000': { price: 115, credits: 1000 }
};

export function initCreditsView() {
    bindEvents();
}

export function onShowCreditsView() {
    loadHistory(1);
}

function bindEvents() {
    // ========== Payment Tab Switching ==========
    const paymentTabs = document.querySelectorAll('.payment-tab');
    const stripeSection = document.getElementById('stripe-payment-section');
    const wechatSection = document.getElementById('wechat-payment-section');

    paymentTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            paymentTabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            const paymentType = tab.dataset.paymentType;
            state.currentPaymentType = paymentType;

            // Hide all sections
            stripeSection?.classList.add('hidden');
            wechatSection?.classList.add('hidden');

            // Show the selected section
            if (paymentType === 'stripe') {
                stripeSection?.classList.remove('hidden');
            } else if (paymentType === 'wechat') {
                wechatSection?.classList.remove('hidden');
            }
        });
    });

    // ========== Stripe Package Selection ==========
    setupPackageSelection('#stripe-packages', 'stripePackageId', 'stripeAmount', 'stripe-amount-display');

    // ========== WeChat Package Selection with Custom Amount ==========
    setupWechatPackageSelection();

    // ========== Pay Buttons ==========
    document.getElementById('btn-stripe-pay')?.addEventListener('click', handleStripePayment);


    // ========== CNY Recharge Options ==========
    const cnyOptions = document.querySelectorAll('#cny-payment-section .recharge-option');
    const customInput = document.getElementById('custom-amount');
    const payBtnText = document.getElementById('pay-amount-display');

    cnyOptions.forEach(opt => {
        opt.addEventListener('click', () => {
            cnyOptions.forEach(o => o.classList.remove('selected'));
            opt.classList.add('selected');

            if (opt.classList.contains('custom')) {
                state.isCustom = true;
                customInput?.focus();
                updateCustomAmount();
            } else {
                state.isCustom = false;
                state.currentAmount = parseFloat(opt.dataset.amount);
                state.currentCredits = parseInt(opt.dataset.credits);
                if (payBtnText) payBtnText.textContent = state.currentAmount;
            }
        });
    });

    customInput?.addEventListener('input', () => {
        if (state.isCustom) {
            updateCustomAmount();
        }
    });

    function updateCustomAmount() {
        const val = parseFloat(customInput?.value);
        if (val && val > 0) {
            state.currentAmount = val;
            state.currentCredits = Math.floor(val * 10);
            if (payBtnText) payBtnText.textContent = val;
        } else {
            state.currentAmount = 0;
            state.currentCredits = 0;
            if (payBtnText) payBtnText.textContent = '0';
        }
    }

    // ========== CNY Payment Methods ==========
    const methods = document.querySelectorAll('.payment-method');
    methods.forEach(m => {
        m.addEventListener('click', () => {
            methods.forEach(o => o.classList.remove('selected'));
            m.classList.add('selected');
            const input = m.querySelector('input');
            if (input) {
                input.checked = true;
                state.paymentMethod = input.value;
            }
        });
    });

    // CNY Pay Button
    document.getElementById('btn-pay')?.addEventListener('click', handleCNYPayment);

    // Pagination
    document.getElementById('credits-prev-page')?.addEventListener('click', () => {
        if (state.historyPage > 1) loadHistory(state.historyPage - 1);
    });
    document.getElementById('credits-next-page')?.addEventListener('click', () => {
        if (state.historyPage < state.historyTotalPages) loadHistory(state.historyPage + 1);
    });
}

function setupPackageSelection(containerSelector, statePackageKey, stateAmountKey, displayElementId, packageConfig = STRIPE_PACKAGES, isInteger = false) {
    const packages = document.querySelectorAll(`${containerSelector} .recharge-option`);
    const amountDisplay = document.getElementById(displayElementId);

    packages.forEach(pkg => {
        pkg.addEventListener('click', () => {
            packages.forEach(p => p.classList.remove('selected'));
            pkg.classList.add('selected');

            const packageId = pkg.dataset.packageId;
            state[statePackageKey] = packageId;

            if (packageConfig[packageId]) {
                state[stateAmountKey] = packageConfig[packageId].price;
                if (amountDisplay) {
                    // CNY uses integer, USD uses decimal
                    amountDisplay.textContent = isInteger ? state[stateAmountKey] : state[stateAmountKey].toFixed(2);
                }
            }
        });
    });
}

// ========== WeChat Package Selection with Auto QR Generation ==========
let wechatQrDebounceTimer = null;

function setupWechatPackageSelection() {
    const packages = document.querySelectorAll('#wechat-packages .recharge-option');
    const customInput = document.getElementById('wechat-custom-amount');

    packages.forEach(pkg => {
        pkg.addEventListener('click', () => {
            packages.forEach(p => p.classList.remove('selected'));
            pkg.classList.add('selected');

            const packageId = pkg.dataset.packageId;
            state.wechatPackageId = packageId;

            if (packageId === 'pkg_custom') {
                // Custom amount mode
                state.wechatIsCustom = true;
                customInput?.focus();
                updateWechatCustomAmount();
            } else if (WECHAT_PACKAGES[packageId]) {
                // Preset package mode
                state.wechatIsCustom = false;
                state.wechatAmount = WECHAT_PACKAGES[packageId].price;
                // Auto-generate QR for preset package
                generateWechatQR();
            }
        });
    });

    // Handle custom amount input with debounce
    customInput?.addEventListener('input', () => {
        if (state.wechatIsCustom) {
            updateWechatCustomAmount();
        }
    });

    // Generate initial QR for default selection
    setTimeout(() => {
        generateWechatQR();
    }, 500);

    function updateWechatCustomAmount() {
        const val = parseInt(customInput?.value);
        if (val && val > 0) {
            state.wechatAmount = val;
            // Update display in QR section immediately
            updateQRDisplay(val, val * 10);
            // Debounce QR generation to avoid too many API calls
            if (wechatQrDebounceTimer) clearTimeout(wechatQrDebounceTimer);
            wechatQrDebounceTimer = setTimeout(() => {
                generateWechatQR();
            }, 800);
        } else {
            state.wechatAmount = 0;
            updateQRDisplay(0, 0);
        }
    }
}

// Update QR display values without regenerating QR
function updateQRDisplay(amount, credits) {
    const amountEl = document.getElementById('wechat-qr-pay-amount');
    const creditsEl = document.getElementById('wechat-qr-credits-amount');
    if (amountEl) amountEl.textContent = amount;
    if (creditsEl) creditsEl.textContent = credits;
}

// Generate WeChat QR code
async function generateWechatQR() {
    // Don't generate if amount is 0
    if (state.wechatAmount <= 0) return;

    const qrLoading = document.getElementById('wechat-qr-loading');
    const qrImage = document.getElementById('wechat-qr-image');
    const qrStatus = document.getElementById('wechat-pay-status');

    // Show loading
    qrLoading?.classList.remove('hidden');
    qrImage?.classList.add('hidden');
    if (qrStatus) qrStatus.innerHTML = '<span class="status-waiting">⏳ 正在生成二维码...</span>';

    // Update display
    const credits = state.wechatIsCustom ? state.wechatAmount * 10 : WECHAT_PACKAGES[state.wechatPackageId]?.credits || 0;
    updateQRDisplay(state.wechatAmount, credits);

    try {
        const customAmount = state.wechatIsCustom ? state.wechatAmount : null;
        const res = await createWechatPayment(state.wechatPackageId, customAmount);

        if (res.ok && res.data?.qr_code_url) {
            // Update with actual values from server
            updateQRDisplay(res.data.amount_cny, res.data.credits);

            // Show QR code
            if (qrImage) {
                qrImage.src = `https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(res.data.qr_code_url)}`;
                qrImage.onload = () => {
                    qrLoading?.classList.add('hidden');
                    qrImage.classList.remove('hidden');
                };
            }
            if (qrStatus) qrStatus.innerHTML = '<span class="status-waiting">⏳ 等待支付中...</span>';

            // Store order ID and start polling
            state.currentOrderId = res.data.order_id;
            startPaymentPolling('wechat', res.data.order_id);
        } else {
            if (qrStatus) qrStatus.innerHTML = '<span class="status-error">生成失败，请重新选择套餐</span>';
            qrLoading?.classList.add('hidden');
        }
    } catch (err) {
        console.error('WeChat QR generation error:', err);
        if (qrStatus) qrStatus.innerHTML = '<span class="status-error">网络错误，请重试</span>';
        qrLoading?.classList.add('hidden');
    }
}

// ========== Stripe Payment Handler ==========
async function handleStripePayment() {
    const btn = document.getElementById('btn-stripe-pay');
    if (!btn) return;

    btn.disabled = true;
    const originalText = btn.innerHTML;
    btn.textContent = '正在创建支付会话...';

    try {
        const res = await createStripeCheckout(state.stripePackageId);

        if (res.ok && res.data?.checkout_url) {
            window.location.href = res.data.checkout_url;
        } else {
            showToast(res.error?.message || '创建支付会话失败', 'error');
        }
    } catch (err) {
        console.error('Stripe checkout error:', err);
        showToast(err.message || '创建支付会话失败', 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}

// ========== Alipay Payment Handler ==========
async function handleAlipayPayment() {
    const btn = document.getElementById('btn-alipay-pay');
    if (!btn) return;

    btn.disabled = true;
    const originalText = btn.innerHTML;
    btn.innerHTML = '正在创建支付...';

    try {
        const res = await createAlipayPayment(state.alipayPackageId);

        if (res.ok && res.data?.redirect_url) {
            showQRCode('alipay', res.data.redirect_url, res.data.amount_usd, res.data.credits, res.data.order_id);
        } else {
            showToast(res.error?.message || '创建支付宝支付失败', 'error');
        }
    } catch (err) {
        console.error('Alipay payment error:', err);
        showToast(err.message || '创建支付宝支付失败', 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}


// ========== Shared QR Code Display ==========
function showQRCode(type, qrUrl, amount, credits, orderId) {
    const qrContainer = document.getElementById(`${type}-qr-container`);
    const qrLoading = document.getElementById(`${type}-qr-loading`);
    const qrImage = document.getElementById(`${type}-qr-image`);
    const qrPayAmount = document.getElementById(`${type}-qr-pay-amount`);
    const qrCreditsAmount = document.getElementById(`${type}-qr-credits-amount`);
    const qrStatus = document.getElementById(`${type}-pay-status`);

    // Show QR container with loading
    qrContainer?.classList.remove('hidden');
    qrLoading?.classList.remove('hidden');
    qrImage?.classList.add('hidden');

    // Update amount info
    if (qrPayAmount) qrPayAmount.textContent = amount;
    if (qrCreditsAmount) qrCreditsAmount.textContent = credits;

    // Generate QR code from URL
    const qrCodeApiUrl = `https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(qrUrl)}`;

    qrImage.onload = () => {
        qrLoading?.classList.add('hidden');
        qrImage?.classList.remove('hidden');
    };
    qrImage.src = qrCodeApiUrl;

    // Update status
    if (qrStatus) {
        qrStatus.innerHTML = '<span class="status-waiting">⏳ 等待支付中...</span>';
    }

    // Save order info and start polling
    state.currentOrderId = orderId;
    startPaymentPolling(orderId, type);
}

function closeQR(type) {
    const qrContainer = document.getElementById(`${type}-qr-container`);
    qrContainer?.classList.add('hidden');

    // Stop polling
    if (state.pollTimer) {
        clearInterval(state.pollTimer);
        state.pollTimer = null;
    }
    state.currentOrderId = null;
}

function startPaymentPolling(orderId, type) {
    if (state.pollTimer) {
        clearInterval(state.pollTimer);
    }

    let attempts = 0;
    const maxAttempts = 90; // 3 minutes

    state.pollTimer = setInterval(async () => {
        attempts++;
        if (attempts > maxAttempts) {
            clearInterval(state.pollTimer);
            state.pollTimer = null;

            const qrStatus = document.getElementById(`${type}-pay-status`);
            if (qrStatus) {
                qrStatus.innerHTML = '<span class="status-failed">支付超时，请重试</span>';
            }
            return;
        }

        try {
            const res = await getStripePaymentStatus(orderId);
            if (res.ok && res.data) {
                const qrStatus = document.getElementById(`${type}-pay-status`);

                if (res.data.status === 'paid') {
                    clearInterval(state.pollTimer);
                    state.pollTimer = null;

                    if (qrStatus) {
                        qrStatus.innerHTML = '<span class="status-success">支付成功！</span>';
                    }

                    showToast(`支付成功！获得 ${res.data.credits} 积分`, 'success');

                    // Refresh user info
                    const me = await apiRequest('/api/me');
                    if (me.ok) {
                        updateUserInfo(me.data);
                    }

                    // Refresh history
                    loadHistory(1);

                    // Close QR after 2 seconds
                    setTimeout(() => {
                        closeQR(type);
                    }, 2000);

                } else if (res.data.status === 'failed') {
                    clearInterval(state.pollTimer);
                    state.pollTimer = null;

                    if (qrStatus) {
                        qrStatus.innerHTML = '<span class="status-failed">支付失败</span>';
                    }
                }
            }
        } catch (e) {
            console.error('Payment polling error', e);
        }
    }, 2000);
}

async function handleCNYPayment() {
    if (state.currentAmount <= 0) {
        showToast('请输入有效的充值金额', 'error');
        return;
    }

    const btn = document.getElementById('btn-pay');
    btn.disabled = true;
    btn.textContent = '正在创建订单...';

    try {
        const res = await apiRequest('/api/recharge/orders', {
            method: 'POST',
            body: {
                amount: state.currentAmount,
                payment_method: state.paymentMethod,
                credits: state.currentCredits
            }
        });

        if (res.ok && res.data) {
            const data = res.data;
            if (data.payment_url) {
                window.open(data.payment_url, '_blank');
                startCNYPolling(data.order_id);
            } else if (data.qr_code) {
                alert(`请扫描二维码支付: ${data.qr_code}`);
                startCNYPolling(data.order_id);
            }
        }
    } catch (err) {
        console.error(err);
        showToast(err.message || '创建订单失败', 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = `立即充值 ¥ <span id="pay-amount-display">${state.currentAmount}</span>`;
    }
}

let cnyPollTimer = null;

function startCNYPolling(orderId) {
    if (cnyPollTimer) clearInterval(cnyPollTimer);

    showToast('正在等待支付结果...', 'info');

    let attempts = 0;
    const maxAttempts = 60;

    cnyPollTimer = setInterval(async () => {
        attempts++;
        if (attempts > maxAttempts) {
            clearInterval(cnyPollTimer);
            showToast('支付超时，请刷新页面重试', 'error');
            return;
        }

        try {
            const res = await apiRequest(`/api/recharge/orders/${orderId}/status`);
            if (res.ok && res.data) {
                const data = res.data;
                if (data.status === 'paid') {
                    clearInterval(cnyPollTimer);
                    showToast(`充值成功！获得 ${data.credits_added} 积分`, 'success');
                    const me = await apiRequest('/api/me');
                    if (me.ok) {
                        updateUserInfo(me.data);
                    }
                    loadHistory(1);
                } else if (data.status === 'failed') {
                    clearInterval(cnyPollTimer);
                    showToast('支付失败', 'error');
                }
            }
        } catch (e) {
            console.error('Polling error', e);
        }
    }, 2000);
}

async function loadHistory(page) {
    const tbody = document.getElementById('credits-tbody');
    tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;">加载中...</td></tr>';

    try {
        const res = await apiRequest(`/api/credits/history?page=${page}&page_size=10`);
        state.historyPage = res.page;
        state.historyTotalPages = Math.ceil(res.total / res.page_size);
        renderHistory(res.items);
        updatePagination(res.page, state.historyTotalPages, res.total);
    } catch (err) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:red;">加载失败</td></tr>';
    }
}

function renderHistory(items) {
    const tbody = document.getElementById('credits-tbody');
    if (!items || items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;">暂无记录</td></tr>';
        return;
    }

    tbody.innerHTML = items.map(item => {
        const isPlus = item.delta > 0;
        const deltaClass = isPlus ? 'delta-plus' : 'delta-minus';
        const deltaSign = isPlus ? '+' : '';
        const date = new Date(item.created_at).toLocaleString();

        return `
            <tr>
                <td>${date}</td>
                <td>${formatReason(item.reason)}</td>
                <td class="${deltaClass}">${deltaSign}${item.delta}</td>
                <td class="text-muted">${item.ref_batch_id || '-'}</td>
            </tr>
        `;
    }).join('');
}

function formatReason(reason) {
    if (reason === 'recharge') return '充值';
    if (reason === 'stripe_recharge') return 'Stripe 信用卡充值';
    if (reason === 'alipay_recharge') return '支付宝充值';
    if (reason === 'wechat_pay_recharge') return '微信支付充值';
    if (reason === 'new_user_gift') return '新用户赠送';
    if (reason.startsWith('deduct_for_batch')) return '创建任务扣费';
    if (reason.startsWith('refund_task')) return '任务失败退款';
    return reason;
}

function updatePagination(page, totalPages, total) {
    document.getElementById('credits-page-info').textContent = `第 ${page} / ${totalPages || 1} 页 (共 ${total} 条)`;
    document.getElementById('credits-prev-page').disabled = page <= 1;
    document.getElementById('credits-next-page').disabled = page >= totalPages;
}
