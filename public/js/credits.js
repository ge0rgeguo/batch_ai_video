import { apiRequest } from './api.js';
import { showToast } from './toast.js';
import { updateUserInfo } from './ui.js';

const state = {
    currentAmount: 9.9,
    currentCredits: 100,
    paymentMethod: 'alipay',
    isCustom: false,
    historyPage: 1,
    historyTotalPages: 1
};

export function initCreditsView() {
    bindEvents();
    // Initial load is not needed until view is shown
}

export function onShowCreditsView() {
    loadHistory(1);
}

function bindEvents() {
    // Recharge Options
    const options = document.querySelectorAll('.recharge-option');
    const customInput = document.getElementById('custom-amount');
    const payBtnText = document.getElementById('pay-amount-display');

    options.forEach(opt => {
        opt.addEventListener('click', () => {
            // Remove active class
            options.forEach(o => o.classList.remove('selected'));
            opt.classList.add('selected');

            if (opt.classList.contains('custom')) {
                state.isCustom = true;
                customInput.focus();
                updateCustomAmount();
            } else {
                state.isCustom = false;
                state.currentAmount = parseFloat(opt.dataset.amount);
                state.currentCredits = parseInt(opt.dataset.credits);
                payBtnText.textContent = state.currentAmount;
            }
        });
    });

    customInput.addEventListener('input', (e) => {
        if (state.isCustom) {
            updateCustomAmount();
        }
    });

    function updateCustomAmount() {
        const val = parseFloat(customInput.value);
        if (val && val > 0) {
            state.currentAmount = val;
            // 1元 = 10积分
            state.currentCredits = Math.floor(val * 10);
            payBtnText.textContent = val;
        } else {
            state.currentAmount = 0;
            state.currentCredits = 0;
            payBtnText.textContent = '0';
        }
    }

    // Payment Methods
    const methods = document.querySelectorAll('.payment-method');
    methods.forEach(m => {
        m.addEventListener('click', () => {
            methods.forEach(o => o.classList.remove('selected'));
            m.classList.add('selected');
            const input = m.querySelector('input');
            input.checked = true;
            state.paymentMethod = input.value;
        });
    });

    // Pay Button
    document.getElementById('btn-pay').addEventListener('click', handlePayment);

    // Pagination
    document.getElementById('credits-prev-page').addEventListener('click', () => {
        if (state.historyPage > 1) loadHistory(state.historyPage - 1);
    });
    document.getElementById('credits-next-page').addEventListener('click', () => {
        if (state.historyPage < state.historyTotalPages) loadHistory(state.historyPage + 1);
    });
}

async function handlePayment() {
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
                credits: state.currentCredits // Optional, backend calculates mostly
            }
        });

        if (res.ok && res.data) {
            const data = res.data;
            if (data.payment_url) {
                // Open payment URL in new window
                window.open(data.payment_url, '_blank');
                // Start polling
                startPolling(data.order_id);
            } else if (data.qr_code) {
                // Show QR Code (Mock mode returns url usually, but for real WeChat/Alipay Native)
                alert(`请扫描二维码支付: ${data.qr_code}`);
                startPolling(data.order_id);
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

let pollTimer = null;

function startPolling(orderId) {
    if (pollTimer) clearInterval(pollTimer);

    // Show a modal or overlay indicating waiting for payment
    showToast('正在等待支付结果...', 'info');

    let attempts = 0;
    const maxAttempts = 60; // 2 minutes

    pollTimer = setInterval(async () => {
        attempts++;
        if (attempts > maxAttempts) {
            clearInterval(pollTimer);
            showToast('支付超时，请刷新页面重试', 'error');
            return;
        }

        try {
            const res = await apiRequest(`/api/recharge/orders/${orderId}/status`);
            if (res.ok && res.data) {
                const data = res.data;
                if (data.status === 'paid') {
                    clearInterval(pollTimer);
                    showToast(`充值成功！获得 ${data.credits_added} 积分`, 'success');
                    // Refresh user info
                    const me = await apiRequest('/api/me');
                    if (me.ok) {
                        updateUserInfo(me.data);
                    }
                    // Refresh history
                    loadHistory(1);
                } else if (data.status === 'failed') {
                    clearInterval(pollTimer);
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

