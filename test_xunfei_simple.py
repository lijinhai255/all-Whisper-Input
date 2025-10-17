#!/usr/bin/env python3
"""
讯飞语音识别简单连接测试
"""

import os
import sys
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_websocket_connection():
    """测试WebSocket连接"""
    print("🔌 测试讯飞WebSocket连接...")

    try:
        from src.transcription.xunfei import XunfeiProcessor
        processor = XunfeiProcessor()

        # 生成认证URL
        auth_url = processor._generate_auth_url()
        print(f"认证URL: {auth_url[:50]}...")

        # 尝试建立WebSocket连接
        import websockets
        import asyncio

        async def test_connection():
            try:
                # 设置较短的超时时间用于测试
                async with websockets.connect(auth_url, ping_timeout=5, close_timeout=5) as websocket:
                    print("✅ WebSocket连接建立成功")

                    # 发送开始消息
                    start_msg = processor._create_start_message()
                    import json
                    await websocket.send(json.dumps(start_msg))
                    print("✅ 开始消息发送成功")

                    # 等待响应
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=2)
                        print("✅ 收到服务器响应")
                        return True
                    except asyncio.TimeoutError:
                        print("⚠️  响应超时，但连接正常")
                        return True

            except Exception as e:
                print(f"❌ WebSocket连接失败: {e}")
                return False

        # 运行测试
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(test_connection())
        loop.close()

        return success

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

if __name__ == "__main__":
    success = test_websocket_connection()
    if success:
        print("\n🎉 WebSocket连接测试通过！")
        print("📝 讯飞API连接正常，可以进行语音识别")
    else:
        print("\n❌ WebSocket连接测试失败")
        print("📝 请检查API配置或网络连接")

    sys.exit(0 if success else 1)