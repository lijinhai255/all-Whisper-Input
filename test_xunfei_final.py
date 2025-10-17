#!/usr/bin/env python3
"""
讯飞API最终测试脚本 - 尝试不同的消息格式
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
import numpy as np
from urllib.parse import quote

from dotenv import load_dotenv

load_dotenv()

def create_test_audio(duration=3, sample_rate=16000):
    """创建测试音频数据"""
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    audio_data = np.sin(2 * np.pi * 440 * t) * 0.3
    audio_data = (audio_data * 32767).astype(np.int16)
    return base64.b64encode(audio_data.tobytes()).decode('utf-8')

async def test_xunfei_format():
    """测试讯飞API的不同格式"""
    app_id = os.getenv("XUNFEI_APP_ID")
    api_key = os.getenv("XUNFEI_API_KEY")
    api_secret = os.getenv("XUNFEI_API_SECRET")
    host = "iat.xf-yun.com"
    path = "/v1"

    print("=== 讯飞API格式测试 ===")

    # 生成认证URL
    import datetime
    timestamp = datetime.datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')
    signature_origin = f"host: {host}\ndate: {timestamp}\nGET {path} HTTP/1.1"
    signature_sha = hmac.new(
        api_secret.encode('utf-8'),
        signature_origin.encode('utf-8'),
        hashlib.sha256
    ).digest()
    signature = base64.b64encode(signature_sha).decode('utf-8')

    authorization_origin = f'api_key="{api_key}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature}"'
    authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode('utf-8')
    authorization_enc = quote(authorization)

    uri = f"wss://{host}{path}?authorization={authorization_enc}&date={quote(timestamp)}&host={host}"

    try:
        print("尝试连接WebSocket...")
        async with websockets.connect(uri, ping_timeout=30, close_timeout=30) as websocket:
            print("✅ WebSocket连接成功！")

            # 尝试格式1: 使用我们修正的格式
            print("\n测试格式1: 修正的API格式")
            test_audio_data = create_test_audio(2)

            format1_message = {
                "header": {
                    "app_id": app_id,
                    "res_id": "test-request-001",
                    "status": 0
                },
                "parameter": {
                    "iat": {
                        "domain": "iat",
                        "language": "zh_cn",
                        "accent": "mandarin"
                    }
                },
                "payload": {
                    "audio": {
                        "encoding": "raw",
                        "sample_rate": 16000,
                        "seq": 0,
                        "audio": "",
                        "status": 0
                    }
                }
            }

            await websocket.send(json.dumps(format1_message))
            print("发送格式1消息...")

            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                result_data = json.loads(response)
                print(f"格式1响应: {result_data}")

                if result_data.get("header", {}).get("code") == 0:
                    print("✅ 格式1成功！尝试发送音频数据...")

                    # 发送音频数据
                    audio_message = {
                        "header": {
                            "app_id": app_id,
                            "res_id": "test-request-001",
                            "status": 2  # 结束状态
                        },
                        "parameter": {},
                        "payload": {
                            "audio": {
                                "encoding": "raw",
                                "sample_rate": 16000,
                                "seq": 1,
                                "audio": test_audio_data,
                                "status": 2
                            }
                        }
                    }

                    await websocket.send(json.dumps(audio_message))
                    print("发送音频数据...")

                    # 等待最终结果
                    final_response = await asyncio.wait_for(websocket.recv(), timeout=10)
                    final_data = json.loads(final_response)
                    print(f"最终结果: {final_data}")

                    return True
                else:
                    print(f"格式1失败: {result_data.get('header', {}).get('message', '未知错误')}")

            except asyncio.TimeoutError:
                print("格式1响应超时")
            except Exception as e:
                print(f"格式1异常: {e}")

    except Exception as e:
        print(f"❌ WebSocket连接失败: {e}")
        return False

    return False

async def main():
    """主函数"""
    print("讯飞API格式测试程序")
    print("=" * 50)

    # 检查环境变量
    required_vars = ['XUNFEI_APP_ID', 'XUNFEI_API_KEY', 'XUNFEI_API_SECRET']
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        print(f"❌ 缺少环境变量: {', '.join(missing_vars)}")
        return

    print("✅ 环境变量检查通过")
    print()

    # 测试不同格式
    success = await test_xunfei_format()

    if success:
        print("\n🎉 讯飞API格式测试成功！")
        print("语音识别功能正常工作！")
    else:
        print("\n❌ 讯飞API格式测试失败")
        print("可能需要进一步调试消息格式。")

if __name__ == "__main__":
    asyncio.run(main())