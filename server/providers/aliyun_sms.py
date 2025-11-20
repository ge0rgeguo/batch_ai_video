from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, Optional

try:
    from alibabacloud_dypnsapi20170525 import models as dypns_models
    from alibabacloud_dypnsapi20170525.client import Client as DypnsapiClient
    from alibabacloud_tea_openapi import models as open_api_models
    from alibabacloud_tea_util import models as tea_models
    from Tea.exceptions import TeaException
    HAS_ALIYUN_SDK = True
except ImportError:
    HAS_ALIYUN_SDK = False
    # Dummy classes to prevent NameError
    dypns_models = None
    DypnsapiClient = None
    open_api_models = None
    tea_models = None
    TeaException = Exception

from ..settings import settings


class AliyunSmsError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


@dataclass
class SendResult:
    sms_session_id: str
    sms_code: str


class AliyunSmsClient:
    def __init__(
        self,
        access_key_id: Optional[str],
        access_key_secret: Optional[str],
        endpoint: str,
        region_id: str,
    ) -> None:
        self._client: Optional[DypnsapiClient] = None
        self._init_error: Optional[AliyunSmsError] = None
        
        if not HAS_ALIYUN_SDK:
            self._init_error = AliyunSmsError("MissingDependency", "未安装阿里云短信 SDK")
            return

        if not access_key_id or not access_key_secret:
            self._init_error = AliyunSmsError("InvalidAccessKey", "未配置阿里云短信 AccessKey，请检查环境变量")
            return

        endpoint_host = endpoint.replace("https://", "").replace("http://", "")
        config = open_api_models.Config(
            access_key_id=access_key_id,
            access_key_secret=access_key_secret,
            endpoint=endpoint_host,
            region_id=region_id,
        )
        self._client = DypnsapiClient(config)

    def send_sms_code(
        self,
        phone_number: str,
        scene: str,
        sign_name: Optional[str],
        template_code: Optional[str],
        template_param: Optional[Dict[str, str]] = None,
        expire_seconds: Optional[int] = None,
    ) -> SendResult:
        if not self._client:
            raise self._init_error or AliyunSmsError("InvalidAccessKey", "未配置阿里云短信 AccessKey")
        request = dypns_models.SendSmsVerifyCodeRequest(
            phone_number=phone_number,
            sign_name=sign_name,
            template_code=template_code,
            template_param=json.dumps(template_param, ensure_ascii=False) if template_param else None,
            scheme_name=scene,
            valid_time=expire_seconds,
            country_code="86",
            code_type=1,
            return_verify_code=True,
            duplicate_policy=1,
            interval=60,
        )
        runtime = tea_models.RuntimeOptions()
        try:
            response = self._client.send_sms_verify_code_with_options(request, runtime)
        except TeaException as exc:
            message = exc.message or "Aliyun SMS error"
            code = exc.code or "AliyunError"
            raise AliyunSmsError(code, message) from exc
        except Exception as exc:  # pragma: no cover
            message = getattr(exc, "message", str(exc))
            raise AliyunSmsError("AliyunError", message) from exc

        body = response.body
        model = getattr(body, "model", None)
        verify_code = getattr(model, "verify_code", None) if model else None
        session_id = getattr(model, "biz_id", None) or getattr(body, "request_id", None)
        if not verify_code:
            try:
                print("[aliyun_sms] send response:", body.to_map())
            except Exception:
                pass
            raise AliyunSmsError("MissingVerifyCode", "阿里云返回结果缺少验证码")
        if not session_id:
            session_id = getattr(model, "request_id", None) or "aliyun"
        return SendResult(sms_session_id=session_id, sms_code=verify_code)

    def check_sms_code(self, phone_number: str, sms_code: str, scheme_name: Optional[str] = None) -> None:
        if not self._client:
            raise self._init_error or AliyunSmsError("InvalidAccessKey", "未配置阿里云短信 AccessKey")
        request = dypns_models.CheckSmsVerifyCodeRequest(
            phone_number=phone_number,
            verify_code=sms_code,
            scheme_name=scheme_name,
        )
        runtime = tea_models.RuntimeOptions()
        try:
            self._client.check_sms_verify_code_with_options(request, runtime)
        except TeaException as exc:
            message = exc.message or "Aliyun SMS error"
            code = exc.code or "AliyunError"
            raise AliyunSmsError(code, message) from exc
        except Exception as exc:  # pragma: no cover
            message = getattr(exc, "message", str(exc))
            raise AliyunSmsError("AliyunError", message) from exc


client = AliyunSmsClient(
    access_key_id=settings.ALIYUN_SMS_ACCESS_KEY_ID,
    access_key_secret=settings.ALIYUN_SMS_ACCESS_KEY_SECRET,
    endpoint=settings.ALIYUN_SMS_ENDPOINT,
    region_id=settings.ALIYUN_SMS_REGION_ID,
)
