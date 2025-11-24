# Payment Integration Guide
This guide explains how to configure **Alipay** and **WeChat Pay** for the Video Generation Platform.

## Prerequisites
To enable real payments, you need to install the following Python packages:
```bash
pip install alipay-sdk-python-all wechatpayv3
```

## 1. Alipay Configuration
You need an **Alipay Enterprise Account** (支付宝企业账号) and create an application in the [Alipay Open Platform](https://open.alipay.com/).

### Required Keys
- **App ID**: The ID of your application.
- **App Private Key**: Your application's private key (RSA2).
- **Alipay Public Key**: The public key provided by Alipay (not your app's public key).

### Configuration Steps
1. Open `server/settings.py`.
2. Set the following variables (or use Environment Variables):
   ```python
   ALIPAY_APP_ID = "your_app_id"
   ALIPAY_PRIVATE_KEY = "your_private_key_content"
   ALIPAY_PUBLIC_KEY = "alipay_public_key_content"
   ```
   *Note: Keys should be clean strings without `-----BEGIN...` headers if using the SDK's default loading, or keep them if the SDK requires it. The current implementation assumes standard key content.*

3. **Return/Notify URLs**:
   Ensure your `BASE_URL` in `settings.py` is set to your public domain (e.g., `https://your-site.com`).
   - Return URL: `https://your-site.com/api/recharge/alipay/return`
   - Notify URL: `https://your-site.com/api/recharge/alipay/notify`

## 2. WeChat Pay Configuration
You need a **WeChat Pay Merchant Account** (微信支付商户号).

### Required Keys
- **App ID**: Your WeChat App ID (associated with the merchant).
- **MCH ID**: Your Merchant ID.
- **APIv3 Key**: The 32-byte key set in the WeChat Pay Merchant Platform.
- **Merchant Certificate Serial No**: The serial number of your merchant certificate.
- **Private Key**: Your merchant private key (`apiclient_key.pem`).

### Configuration Steps
1. Open `server/settings.py`.
2. Set the following variables:
   ```python
   WECHAT_PAY_APP_ID = "your_app_id"
   WECHAT_PAY_MCH_ID = "your_mch_id"
   WECHAT_PAY_APIV3_KEY = "your_apiv3_key"
   WECHAT_PAY_CERT_SERIAL_NO = "your_cert_serial_no"
   WECHAT_PAY_PRIVATE_KEY = """-----BEGIN PRIVATE KEY-----
   ...your private key content...
   -----END PRIVATE KEY-----"""
   ```

## 3. Switching to Real Payments
The system automatically detects if the keys are configured.
- If `ALIPAY_APP_ID` is set, Alipay requests will use the real API.
- If `WECHAT_PAY_MCH_ID` is set, WeChat Pay requests will use the real API.
- If keys are missing, it falls back to **Mock Mode** (simulated payment).

## 4. Verification
1. Configure the keys.
2. Restart the server.
3. Create a recharge order.
4. **Alipay**: Should redirect to the official Alipay cashier page.
5. **WeChat Pay**: Should display a real WeChat Pay QR code.
