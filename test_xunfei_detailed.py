#!/usr/bin/env python3
"""
详细的讯飞API测试脚本，包含更多调试信息
"""

import os
import sys
import time
import json
import base64
import hashlib
import hmac
import asyncio
import websockets
from urllib.parse import quote

from dotenv import load_dotenv

load_dotenv()

async def test_xunfei_connection():
    """测试讯飞WebSocket连接"""
    app_id = os.getenv("XUNFEI_APP_ID")
    api_key = os.getenv("XUNFEI_API_KEY")
    api_secret = os.getenv("XUNFEI_API_SECRET")
    host = "iat.xf-yun.com"
    path = "/v1/iat"

    print("=== 讯飞API连接测试 ===")
    print(f"APPID: {app_id}")
    print(f"API Key: {api_key}")
    print(f"API Secret: {api_secret[:20]}...")
    print()

    # 生成认证URL
    import datetime
    timestamp = datetime.datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')
    signature_origin = f"host: {host}\ndate: {timestamp}\nGET {path} HTTP/1.1\nappid: {app_id}"
    signature_sha = hmac.new(
        api_secret.encode('utf-8'),
        signature_origin.encode('utf-8'),
        hashlib.sha256
    ).digest()
    signature = base64.b64encode(signature_sha).decode('utf-8')

    authorization_origin = f'api_key="{api_key}", algorithm="hmac-sha256", headers="host date request-line appid", signature="{signature}"'
    authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode('utf-8')
    authorization_enc = quote(authorization)

    uri = f"wss://{host}{path}?authorization={authorization_enc}&date={quote(timestamp)}&host={host}&appid={app_id}"
    print(f"WebSocket URL: {uri}")
    print()

    try:
        print("尝试连接WebSocket...")
        async with websockets.connect(uri, ping_timeout=30, close_timeout=30) as websocket:
            print("✅ WebSocket连接成功！")

            # 发送开始消息
            start_message = {
                "header": {
                    "app_id": app_id,
                    "status": 0
                },
                "parameter": {
                    "result": {
                        "encoding": "raw",
                        "sample_rate": 16000,
                        "speech_rate": 50,
                        "language": "zh_cn",
                        "accent": "mandarin",
                        "domain": "iat",
                        "nunum": 1,
                        "ptc": 1,
                        "rse": 1,
                        "vad_eos": 10000,
                        "dwa": "wpgs"
                    }
                },
                "payload": {
                    "input": {
                        "encoding": "raw",
                        "status": 0,
                        "audio": "",
                        "sample_rate": 16000
                    }
                }
            }

            print("发送开始消息...")
            await websocket.send(json.dumps(start_message))
            print("✅ 开始消息发送成功")

            # 等待响应
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                print(f"✅ 收到响应: {response}")
                return True
            except asyncio.TimeoutError:
                print("⚠️ 等待响应超时，但连接成功")
                return True

    except websockets.exceptions.InvalidStatus as e:
        print(f"❌ WebSocket连接失败 - HTTP状态错误: {e}")
        print(f"   这通常意味着认证失败或权限不足")
        return False
    except websockets.exceptions.WebSocketException as e:
        print(f"❌ WebSocket连接失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return False

async def main():
    """主函数"""
    print("讯飞API详细测试程序")
    print("=" * 50)

    # 检查环境变量
    required_vars = ['XUNFEI_APP_ID', 'XUNFEI_API_KEY', 'XUNFEI_API_SECRET']
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        print(f"❌ 缺少环境变量: {', '.join(missing_vars)}")
        return

    print("✅ 环境变量检查通过")
    print()

    # 测试连接
    success = await test_xunfei_connection()

    if success:
        print("\n🎉 讯飞API连接测试成功！")
        print("现在可以尝试进行语音识别测试。")
    else:
        print("\n❌ 讯飞API连接测试失败")
        print("请检查：")
        print("1. 讯飞控制台是否开通了语音听写（流式版）服务")
        print("2. API Key是否有足够的权限")
        print("3. 账户是否有足够的余额")
        print("4. 服务是否在正常状态")

if __name__ == "__main__":
    asyncio.run(main())