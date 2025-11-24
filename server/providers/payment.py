import logging
import uuid
from datetime import datetime
from typing import Optional, Tuple

# 尝试导入支付库，如果没有则忽略（由用户自行安装）
try:
    from alipay import AliPay
except ImportError:
    AliPay = None

from ..models import RechargeOrder, User, utcnow
from ..settings import settings

logger = logging.getLogger(__name__)

class PaymentProvider:
    def __init__(self):
        self.mock_mode = True  # 默认为 Mock 模式，除非配置了真实 Key

    def calculate_credits(self, amount_cny: float) -> int:
        """
        根据金额计算积分
        规则：
        9.9 -> 100
        44.9 -> 500
        89.9 -> 1000
        其他 -> floor(amount * 10)
        """
        # 浮点数比较用 epsilon
        if abs(amount_cny - 9.9) < 0.01:
            return 100
        if abs(amount_cny - 44.9) < 0.01:
            return 500
        if abs(amount_cny - 89.9) < 0.01:
            return 1000
        
        return int(amount_cny * 10)

    def create_order(self, user_id: int, amount_cny: float, payment_method: str, db_session) -> Tuple[RechargeOrder, dict]:
        """
        创建本地订单并返回支付参数
        """
        order_id = uuid.uuid4().hex
        credits = self.calculate_credits(amount_cny)
        amount_fen = int(amount_cny * 100)

        order = RechargeOrder(
            id=order_id,
            user_id=user_id,
            amount=amount_fen,
            credits=credits,
            payment_method=payment_method,
            status="pending",
            created_at=utcnow()
        )
        db_session.add(order)
        db_session.commit()

        pay_info = self._get_pay_params(order)
        return order, pay_info

    def _get_pay_params(self, order: RechargeOrder) -> dict:
        """
        获取支付参数（URL 或 二维码）
        """
        # 优先检查是否配置了真实支付参数
        if order.payment_method == "alipay" and settings.ALIPAY_APP_ID:
            return self._get_alipay_params(order)
        elif order.payment_method == "wechat" and settings.WECHAT_PAY_MCH_ID:
            return self._get_wechat_params(order)

        if self.mock_mode:
            # Mock 模式：返回一个模拟的支付链接
            # 实际前端会展示这个二维码或链接，点击后跳转到 mock 页面
            return {
                "payment_url": f"/mock-pay.html?order_id={order.id}&amount={order.amount/100}&credits={order.credits}",
                "qr_code": f"MOCK_PAYMENT:{order.id}",
                "method": "mock"
            }
            
        return {"error": "Payment method not configured"}

    def _get_alipay_params(self, order: RechargeOrder) -> dict:
        """
        支付宝支付参数生成
        需要安装: pip install alipay-sdk-python-all
        """
        try:
            from alipay.aop.api.AlipayClientConfig import AlipayClientConfig
            from alipay.aop.api.DefaultAlipayClient import DefaultAlipayClient
            from alipay.aop.api.domain.AlipayTradePagePayModel import AlipayTradePagePayModel
            from alipay.aop.api.request.AlipayTradePagePayRequest import AlipayTradePagePayRequest
        except ImportError:
            logger.error("Alipay SDK not installed. Run: pip install alipay-sdk-python-all")
            return {"error": "Alipay SDK missing"}

        # 配置
        alipay_config = AlipayClientConfig()
        alipay_config.server_url = "https://openapi.alipay.com/gateway.do"
        alipay_config.app_id = settings.ALIPAY_APP_ID
        alipay_config.app_private_key = settings.ALIPAY_PRIVATE_KEY
        alipay_config.alipay_public_key = settings.ALIPAY_PUBLIC_KEY
        alipay_config.sign_type = "RSA2"

        client = DefaultAlipayClient(alipay_config=alipay_config)

        # 构造请求
        model = AlipayTradePagePayModel()
        model.out_trade_no = order.id
        model.total_amount = str(order.amount / 100.0)
        model.subject = f"积分充值-{order.credits}分"
        model.product_code = "FAST_INSTANT_TRADE_PAY"
        model.qr_pay_mode = "2" # 订单码-跳转模式

        request = AlipayTradePagePayRequest(biz_model=model)
        # 支付成功跳转地址
        request.return_url = f"{settings.BASE_URL}/api/recharge/alipay/return"
        # 异步通知地址
        request.notify_url = f"{settings.BASE_URL}/api/recharge/alipay/notify"

        try:
            # 生成跳转URL
            response_content = client.page_execute(request, http_method="GET")
            return {
                "payment_url": response_content, # 这里返回的是完整的 URL
                "method": "alipay"
            }
        except Exception as e:
            logger.error(f"Alipay create order failed: {e}")
            return {"error": str(e)}

    def _get_wechat_params(self, order: RechargeOrder) -> dict:
        """
        微信支付 Native 模式参数生成
        需要安装: pip install wechatpayv3
        """
        try:
            from wechatpayv3 import WeChatPay, WeChatPayType
        except ImportError:
            logger.error("WeChatPay SDK not installed. Run: pip install wechatpayv3")
            return {"error": "WeChatPay SDK missing"}

        try:
            wxpay = WeChatPay(
                wechatpay_type=WeChatPayType.NATIVE,
                mchid=settings.WECHAT_PAY_MCH_ID,
                private_key=settings.WECHAT_PAY_PRIVATE_KEY,
                cert_serial_no=settings.WECHAT_PAY_CERT_SERIAL_NO,
                apiv3_key=settings.WECHAT_PAY_APIV3_KEY,
                appid=settings.WECHAT_PAY_APP_ID,
                notify_url=f"{settings.BASE_URL}/api/recharge/wechat/notify",
                cert_dir=None, # 如果需要验证平台证书，可指定目录
                logger=logger
            )

            code, message = wxpay.pay(
                description=f"积分充值-{order.credits}分",
                out_trade_no=order.id,
                amount={"total": order.amount},
                attach=str(order.user_id)
            )
            
            if code == 200:
                return {
                    "qr_code": message.get("code_url"),
                    "method": "wechat"
                }
            else:
                logger.error(f"WeChatPay create order failed: {message}")
                return {"error": f"WeChatPay error: {message}"}
        except Exception as e:
            logger.error(f"WeChatPay init failed: {e}")
            return {"error": str(e)}

    def check_order_status(self, order: RechargeOrder, db_session) -> str:
        """
        主动查询订单状态（用于轮询或回调缺失的情况）
        """
        if order.status == "paid":
            return "paid"
            
        # 真实支付查询逻辑
        if order.payment_method == "alipay" and settings.ALIPAY_APP_ID:
            # TODO: 实现支付宝查询接口 alipay.trade.query
            pass
        elif order.payment_method == "wechat" and settings.WECHAT_PAY_MCH_ID:
            # TODO: 实现微信支付查询接口
            pass

        # Mock 模式下，如果访问了 mock-confirm 接口，状态会被改为 paid
        return order.status

    def mock_pay_success(self, order_id: str, db_session) -> bool:
        """
        模拟支付成功（仅供测试使用）
        """
        from ..models import CreditTransaction

        order = db_session.query(RechargeOrder).filter(RechargeOrder.id == order_id).first()
        if not order:
            return False
        
        if order.status == "paid":
            return True

        # 更新订单状态
        order.status = "paid"
        order.paid_at = utcnow()

        # 增加积分
        user = db_session.query(User).filter(User.id == order.user_id).first()
        if user:
            # 添加积分变动记录
            tx = CreditTransaction(
                user_id=user.id,
                delta=order.credits,
                reason="recharge",
                ref_batch_id=order.id, # 复用 batch_id 字段存储订单号
                created_at=utcnow()
            )
            db_session.add(tx)
            
        db_session.commit()
        return True

payment_service = PaymentProvider()

