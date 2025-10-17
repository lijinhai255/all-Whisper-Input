#!/usr/bin/env python3
"""
讯飞API认证调试脚本
"""

import os
import time
import base64
import hashlib
import hmac
from urllib.parse import quote

from dotenv import load_dotenv

load_dotenv()

def generate_auth_url():
    """生成认证URL"""
    app_id = os.getenv("XUNFEI_APP_ID")
    api_key = os.getenv("XUNFEI_API_KEY")
    api_secret = os.getenv("XUNFEI_API_SECRET")
    host = "iat.xf-yun.com"
    path = "/v1"

    print(f"认证信息:")
    print(f"APPID: {app_id}")
    print(f"API Key: {api_key}")
    print(f"API Secret: {api_secret}")
    print()

    timestamp = str(int(time.time()))
    signature_origin = f"host: {host}\ndate: {timestamp}\nGET {path} HTTP/1.1"

    print(f"签名原文:")
    print(repr(signature_origin))
    print()
    print(f"签名原文:")
    print(signature_origin)
    print()

    signature_sha = hmac.new(
        api_secret.encode('utf-8'),
        signature_origin.encode('utf-8'),
        hashlib.sha256
    ).digest()
    signature = base64.b64encode(signature_sha).decode('utf-8')

    print(f"签名结果: {signature}")
    print()

    authorization_origin = f'api_key="{api_key}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature}"'
    authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode('utf-8')

    print(f"Authorization原文:")
    print(repr(authorization_origin))
    print()
    print(f"Authorization编码:")
    print(repr(authorization))
    print()

    authorization_enc = quote(authorization)

    url = f"wss://{host}{path}?authorization={authorization_enc}&date={timestamp}&host={host}"

    print(f"完整WebSocket URL:")
    print(url)
    print()

    return url

if __name__ == "__main__":
    print("讯飞API认证调试")
    print("=" * 50)
    url = generate_auth_url()

    print("请检查以上信息是否正确，并尝试手动访问讯飞控制台确认API权限。")