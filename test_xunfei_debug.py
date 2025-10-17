#!/usr/bin/env python3
"""
讯飞API调试脚本 - 详细查看服务器响应
"""

import os
import sys
import json
import asyncio
import websockets
from dotenv import load_dotenv

load_dotenv()

async def test_xunfei_debug():
    """调试讯飞API连接和消息格式"""
    app_id = os.getenv("XUNFEI_APP_ID")
    api_key = os.getenv("XUNFEI_API_KEY")
    api_secret = os.getenv("XUNFEI_API_SECRET")
    host = "rtasr.xfyun.cn"
    path = "/v1"

    print("=== 讯飞API调试测试 ===")

    # 生成认证URL
    import datetime
    import hashlib
    import hmac
    import base64
    from urllib.parse import quote

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
    print(f"连接URL: {uri}")

    try:
        print("尝试连接WebSocket...")
        async with websockets.connect(uri, ping_timeout=30, close_timeout=30) as websocket:
            print("✅ WebSocket连接成功！")

            # 创建开始消息 - RTASR格式
            start_message = {
                "data": {
                    "status": 0,  # 0表示第一帧
                    "encoding": "raw",
                    "audio": "",
                    "format": "audio/L16;rate=16000"
                }
            }

            print(f"发送开始消息: {json.dumps(start_message, indent=2, ensure_ascii=False)}")
            await websocket.send(json.dumps(start_message))
            print("开始消息已发送")

            # 接收服务器响应
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=10)
                print(f"收到服务器响应: {response}")
                result_data = json.loads(response)
                print(f"解析后的响应: {json.dumps(result_data, indent=2, ensure_ascii=False)}")

                # 检查响应状态
                code = result_data.get("code", "")
                message = result_data.get("message", "")

                if code == 0:
                    print("✅ 服务器确认成功！")
                    return True
                else:
                    print(f"❌ 服务器返回错误: code={code}, message={message}")
                    return False

            except asyncio.TimeoutError:
                print("❌ 响应超时")
                return False

    except Exception as e:
        print(f"❌ WebSocket连接失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_xunfei_debug())

    if success:
        print("\n🎉 讯飞API调试测试成功！")
    else:
        print("\n❌ 讯飞API调试测试失败")

    sys.exit(0 if success else 1)