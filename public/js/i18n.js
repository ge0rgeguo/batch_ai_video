import { state } from './state.js';

const translations = {
    'zh-CN': {
        'app.title': 'AI视频批量生成',
        'nav.brand': '做视频 · AI 视频内容生产平台',
        'nav.contact': '联系客服',
        'nav.contact.qr': '微信扫码联系：齐奥至',
        'nav.login': '登录',
        'nav.register': '注册',
        'hero.badge': '新用户限时福利：注册即送 100 积分',
        'hero.title': '批量制作，高质量，无水印 AI 视频',
        'hero.subtitle': '一键生成电商营销视频，支持 Sora 2 & Pro 模型',
        'hero.cta': '立即登录',
        'hero.note': '无需绑卡 · 注册即用',
        'model.sora2.label': 'Sora2',
        'model.sora2.desc': '适合日常批量生成、快速复刻商品短视频。',
        'model.sora2.params.1': '方向：横向 16:9、纵向 9:16',
        'model.sora2.params.2': '尺寸：720p',
        'model.sora2.params.3': '时长：10秒 / 15秒',
        'model.sora2.params.4': '积分：10分 / 15分',
        'model.sora2.params.5': '批量：同时支持10个任务，单个任务支持50条',
        'model.sora2pro.label': 'Sora2 Pro',
        'model.sora2pro.desc': '适合高质量投放素材、重点活动主视频等场景。',
        'model.sora2pro.params.1': '方向：横向 16:9、纵向 9:16',
        'model.sora2pro.params.2': '尺寸：1080p',
        'model.sora2pro.params.3': '时长：10秒 / 15秒 / 25秒',
        'model.sora2pro.params.4': '积分：50分 / 75分 / 100分',
        'model.sora2pro.params.5': '批量：同时支持10个任务，单个任务支持50条',
        'auth.back': '← 返回首页',
        'auth.login.title': '登录到 AI 视频生成平台',
        'auth.login.sms': '手机号快捷登录',
        'auth.login.password': '账号密码登录',
        'auth.field.mobile': '手机号',
        'auth.placeholder.mobile': '请输入 11 位手机号',
        'auth.field.code': '验证码',
        'auth.placeholder.code': '请输入短信验证码',
        'auth.btn.get_code': '获取验证码',
        'auth.btn.login_register': '登录 / 注册',
        'auth.btn.google': '使用 Google 账号登录',
        'auth.divider': '或使用以下方式',
        'auth.field.username': '用户名',
        'auth.placeholder.username': '请输入用户名',
        'auth.field.password': '密码',
        'auth.placeholder.password': '请输入密码',
        'auth.btn.login': '登录',
        'auth.register.title': '快速注册账号',
        'auth.btn.register': '完成注册',
        'auth.has_account': '已有账号？',
        'auth.link.login': '直接登录',
        'app.header.title': '🎬 AI视频批量生成',
        'app.btn.logout': '退出登录',
        'create.section.image': '图片',
        'create.btn.delete_image': '删除图片',
        'create.section.prompt': '提示词 Prompt',
        'create.placeholder.prompt': '请输入视频生成提示词（必填，≤10000字符）',
        'create.section.params': '模型参数',
        'create.label.model': '模型',
        'create.label.orientation': '方向',
        'create.option.landscape': '横向',
        'create.option.portrait': '纵向',
        'create.label.size': '尺寸',
        'create.label.duration': '时长',
        'create.label.num_videos': '视频数量',
        'create.btn.generate': '🎬 生成视频',
        'batch.title': '任务管理',
        'batch.subtitle': '(点击行查看详情)',
        'batch.col.index': '序号',
        'batch.col.created': '创建时间',
        'batch.col.duration': '完成用时',
        'batch.col.prompt': '提示词',
        'batch.col.image': '图片',
        'batch.col.status': '状态',
        'batch.col.fail_reason': '失败原因',
        'batch.col.action': '操作',
        'batch.btn.prev': '上一页',
        'batch.btn.next': '下一页',
        'batch.status.running': '🔄 进行中',
        'batch.status.partialFailed': '❌ 部分失败',
        'batch.status.completed': '✅ 全部完成',
        'batch.status.queued': '⏸ 待启动',
        'credits.title': '积分充值',
        'credits.option.custom': '自定义金额',
        'credits.placeholder.amount': '输入金额',
        'credits.label.payment_method': '支付方式',
        'credits.method.alipay': '支付宝',
        'credits.method.wechat': '微信支付',
        'credits.btn.pay': '立即充值',
        'credits.tip': '充值比例：1元 ≈ 10积分（套餐更优惠）',
        'credits.history.title': '积分变动历史',
        'credits.col.time': '时间',
        'credits.col.reason': '变动原因',
        'credits.col.change': '积分变动',
        'credits.col.related_id': '关联ID',
        'credits.btn.prev': '上一页',
        'credits.btn.next': '下一页',
        'toast.verify_code_sent': '验证码已发送，请注意查收',
        'toast.login_success': '登录成功',
        'toast.enter_prompt': '请输入提示词',
        'toast.batch_created': '批次创建成功',
        'toast.no_batch_found': '未找到对应批次',
        'toast.params_refilled': '参数已回填，可修改后重新生成',
        'toast.batch_deleted': '批次已删除',
        'toast.no_failed_tasks': '没有失败的任务',
        'toast.retried_tasks': '已重试 {n} 个失败任务',
        'toast.task_resubmitted': '任务已重新提交',
        'toast.task_deleted': '任务已删除',
        'toast.image_uploaded': '图片上传成功',
        'toast.image_deleted': '图片已删除',
        'confirm.delete_batch': '确认删除整个批次？',
        'confirm.delete_task': '确认删除此任务？',
        'btn.expand': '查看',
        'btn.collapse': '收起',
        'btn.refill': '再来一批',
        'btn.delete': '删除',
        'btn.retry': '重试',
        'btn.download': '下载',
        'btn.retry_failed': '重试失败',
        'btn.download_batch': '一键下载',
        'status.pending': '等待中',
        'status.queued': '排队中',
        'status.running': '进行中',
        'status.completed': '已完成',
        'status.failed': '失败',
        'status.cancelled': '已取消',
        'misc.page_info': '第 {current} / {total} 页',
        'misc.credits': '💎 积分：{credits}',
        'misc.user': '👤 {username}',
        'misc.total_completed_failed': '总:{total} 完成:{completed} 失败:{failed}',
        'misc.seconds': '秒',
        'misc.points': '分',
        'misc.hours': '时',
        'misc.minutes': '分',
        'misc.hot': '热销',
        'lang.toggle': 'English/中文',
    },
    'en-US': {
        'app.title': 'AI Batch Video Generation',
        'nav.brand': 'MakeVideo · AI Video Production Platform',
        'nav.contact': 'Contact Support',
        'nav.contact.qr': 'Scan WeChat QR: Qiaozhi',
        'nav.login': 'Log In',
        'nav.register': 'Register',
        'hero.badge': 'New User Benefit: Get 100 Credits on Registration',
        'hero.title': 'Batch, High-Quality, Watermark-Free AI Videos',
        'hero.subtitle': 'One-click generation for e-commerce marketing videos, supporting Sora 2 & Pro models',
        'hero.cta': 'Log In Now',
        'hero.note': 'No Card Required · Instant Access',
        'model.sora2.label': 'Sora2',
        'model.sora2.desc': 'Suitable for daily batch generation and quick replication of product shorts.',
        'model.sora2.params.1': 'Orientation: Landscape 16:9, Portrait 9:16',
        'model.sora2.params.2': 'Size: 720p',
        'model.sora2.params.3': 'Duration: 10s / 15s',
        'model.sora2.params.4': 'Credits: 10 pts / 15 pts',
        'model.sora2.params.5': 'Batch: Supports 10 concurrent tasks, 50 items per task',
        'model.sora2pro.label': 'Sora2 Pro',
        'model.sora2pro.desc': 'Suitable for high-quality ad materials and key campaign videos.',
        'model.sora2pro.params.1': 'Orientation: Landscape 16:9, Portrait 9:16',
        'model.sora2pro.params.2': 'Size: 1080p',
        'model.sora2pro.params.3': 'Duration: 10s / 15s / 25s',
        'model.sora2pro.params.4': 'Credits: 50 pts / 75 pts / 100 pts',
        'model.sora2pro.params.5': 'Batch: Supports 10 concurrent tasks, 50 items per task',
        'auth.back': '← Back to Home',
        'auth.login.title': 'Log in to AI Video Platform',
        'auth.login.sms': 'Mobile Quick Login',
        'auth.login.password': 'Password Login',
        'auth.field.mobile': 'Mobile Number',
        'auth.placeholder.mobile': 'Enter 11-digit mobile number',
        'auth.field.code': 'Verification Code',
        'auth.placeholder.code': 'Enter SMS code',
        'auth.btn.get_code': 'Get Code',
        'auth.btn.login_register': 'Log In / Register',
        'auth.btn.google': 'Continue with Google',
        'auth.divider': 'or continue with',
        'auth.field.username': 'Username',
        'auth.placeholder.username': 'Enter username',
        'auth.field.password': 'Password',
        'auth.placeholder.password': 'Enter password',
        'auth.btn.login': 'Log In',
        'auth.register.title': 'Quick Registration',
        'auth.btn.register': 'Complete Registration',
        'auth.has_account': 'Already have an account?',
        'auth.link.login': 'Log In directly',
        'app.header.title': '🎬 AI Batch Video Generation',
        'app.btn.logout': 'Log Out',
        'create.section.image': 'Image',
        'create.btn.delete_image': 'Delete Image',
        'create.section.prompt': 'Prompt',
        'create.placeholder.prompt': 'Enter video generation prompt (Required, ≤10000 chars)',
        'create.section.params': 'Model Parameters',
        'create.label.model': 'Model',
        'create.label.orientation': 'Orientation',
        'create.option.landscape': 'Landscape',
        'create.option.portrait': 'Portrait',
        'create.label.size': 'Size',
        'create.label.duration': 'Duration',
        'create.label.num_videos': 'Quantity',
        'create.btn.generate': '🎬 Generate Video',
        'batch.title': 'Task Management',
        'batch.subtitle': '(Click row for details)',
        'batch.col.index': 'No.',
        'batch.col.created': 'Created At',
        'batch.col.duration': 'Duration',
        'batch.col.prompt': 'Prompt',
        'batch.col.image': 'Image',
        'batch.col.status': 'Status',
        'batch.col.fail_reason': 'Failure Reason',
        'batch.col.action': 'Action',
        'batch.btn.prev': 'Prev',
        'batch.btn.next': 'Next',
        'batch.status.running': '🔄 Running',
        'batch.status.partialFailed': '❌ Partial Fail',
        'batch.status.completed': '✅ Completed',
        'batch.status.queued': '⏸ Queued',
        'credits.title': 'Recharge Credits',
        'credits.option.custom': 'Custom Amount',
        'credits.placeholder.amount': 'Enter amount',
        'credits.label.payment_method': 'Payment Method',
        'credits.method.alipay': 'Alipay',
        'credits.method.wechat': 'WeChat Pay',
        'credits.btn.pay': 'Recharge Now',
        'credits.tip': 'Rate: 1 CNY ≈ 10 Credits (Packages are cheaper)',
        'credits.history.title': 'Credit History',
        'credits.col.time': 'Time',
        'credits.col.reason': 'Reason',
        'credits.col.change': 'Change',
        'credits.col.related_id': 'Related ID',
        'credits.btn.prev': 'Prev',
        'credits.btn.next': 'Next',
        'toast.verify_code_sent': 'Code sent, please check',
        'toast.login_success': 'Login successful',
        'toast.enter_prompt': 'Please enter a prompt',
        'toast.batch_created': 'Batch created successfully',
        'toast.no_batch_found': 'Batch not found',
        'toast.params_refilled': 'Parameters refilled, modify and regenerate',
        'toast.batch_deleted': 'Batch deleted',
        'toast.no_failed_tasks': 'No failed tasks',
        'toast.retried_tasks': 'Retried {n} failed tasks',
        'toast.task_resubmitted': 'Task resubmitted',
        'toast.task_deleted': 'Task deleted',
        'toast.image_uploaded': 'Image uploaded successfully',
        'toast.image_deleted': 'Image deleted',
        'confirm.delete_batch': 'Delete the entire batch?',
        'confirm.delete_task': 'Delete this task?',
        'btn.expand': 'View',
        'btn.collapse': 'Hide',
        'btn.refill': 'Refill',
        'btn.delete': 'Delete',
        'btn.retry': 'Retry',
        'btn.download': 'Download',
        'btn.retry_failed': 'Retry Failed',
        'btn.download_batch': 'Download All',
        'status.pending': 'Pending',
        'status.queued': 'Queued',
        'status.running': 'Running',
        'status.completed': 'Completed',
        'status.failed': 'Failed',
        'status.cancelled': 'Cancelled',
        'misc.page_info': 'Page {current} / {total}',
        'misc.credits': '💎 Credits: {credits}',
        'misc.user': '👤 {username}',
        'misc.total_completed_failed': 'Total:{total} Done:{completed} Fail:{failed}',
        'misc.seconds': 's',
        'misc.points': 'pts',
        'misc.hours': 'h',
        'misc.minutes': 'm',
        'misc.hot': 'HOT',
        'lang.toggle': 'English/中文',
    },
};

export function t(key, params = {}) {
    const lang = state.language || 'zh-CN';
    let text = translations[lang][key] || key;

    Object.keys(params).forEach(param => {
        text = text.replace(`{${param}}`, params[param]);
    });

    return text;
}

export function getCurrentLang() {
    return state.language || 'zh-CN';
}

export function toggleLanguage() {
    const current = state.language || 'zh-CN';
    const next = current === 'zh-CN' ? 'en-US' : 'zh-CN';
    state.language = next;
    localStorage.setItem('i18n_lang', next);
    applyTranslations();

    // Trigger a custom event for other components to react if needed
    window.dispatchEvent(new CustomEvent('languageChanged', { detail: { language: next } }));
}

export function initLanguage() {
    const saved = localStorage.getItem('i18n_lang');
    state.language = saved || 'zh-CN';
    applyTranslations();
}

export function applyTranslations() {
    document.documentElement.lang = state.language;
    const elements = document.querySelectorAll('[data-i18n]');

    elements.forEach(el => {
        const key = el.getAttribute('data-i18n');
        const text = t(key);

        if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
            if (el.getAttribute('placeholder')) {
                el.setAttribute('placeholder', text);
            }
        } else {
            // Handle nested elements like icons if necessary, but for now simple text replacement
            // If element has children that are not text nodes, we might need a different strategy
            // For this project, assuming most labeled elements are simple text containers
            // BUT for elements with children like <span class="badge-icon">🎁</span>text, this will wipe the icon.
            // We should check if the element has children.

            const hasIcon = el.querySelector('.badge-icon, .icon, .meta-chip');
            if (hasIcon) {
                // Special handling if needed, or we just rely on the text node being distinct.
                // For simplicity in this pass, I will target specific text nodes or use span wrappers in HTML if needed.
                // Let's optimize: if element has specific children structure, we might need to target the text node specifically.
                // However, my plan involves adding data-i18n to the specific text holding elements in HTML.
                el.textContent = text;
            } else {
                el.textContent = text;
            }
        }
    });
}
