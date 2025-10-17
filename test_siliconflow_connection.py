#!/usr/bin/env python3
"""
SiliconFlow API 连接测试工具
用于诊断网络连接和 API 访问问题
"""

import os
import time
import httpx
import dotenv
from pathlib import Path

# 加载环境变量
dotenv.load_dotenv()

def test_basic_connectivity():
    """测试基本网络连接"""
    print("=== 测试基本网络连接 ===")

    api_key = os.getenv("SILICONFLOW_API_KEY")
    if not api_key:
        print("❌ 未找到 SILICONFLOW_API_KEY 环境变量")
        return False

    # 测试基础连接
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get("https://api.siliconflow.cn")
            print(f"✅ 基础连接成功 - 状态码: {response.status_code}")
    except Exception as e:
        print(f"❌ 基础连接失败: {e}")
        return False

    return True

def test_api_access():
    """测试 API 访问权限"""
    print("\n=== 测试 API 访问权限 ===")

    api_key = os.getenv("SILICONFLOW_API_KEY")

    try:
        headers = {
            'Authorization': f"Bearer {api_key}"
        }

        with httpx.Client(timeout=15.0) as client:
            # 测试获取模型列表
            response = client.get("https://api.siliconflow.cn/v1/models", headers=headers)
            if response.status_code == 200:
                print("✅ API 访问权限正常")
                models = response.json().get('data', [])
                audio_models = [m for m in models if 'audio' in m.get('id', '').lower()]
                print(f"📋 发现 {len(audio_models)} 个音频模型")
                for model in audio_models[:3]:  # 显示前3个
                    print(f"   - {model.get('id', 'unknown')}")
            else:
                print(f"❌ API 访问失败 - 状态码: {response.status_code}")
                print(f"   响应: {response.text}")
                return False

    except Exception as e:
        print(f"❌ API 访问异常: {e}")
        return False

    return True

def test_audio_upload_speed():
    """测试音频上传速度"""
    print("\n=== 测试音频上传速度 ===")

    # 创建一个小的测试音频文件（模拟）
    test_audio_data = b"RIFF\x24\x08\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x40\x1f\x00\x00\x80\x3e\x00\x00\x02\x00\x10\x00data\x00\x08\x00\x00" + b"\x00" * 1000

    api_key = os.getenv("SILICONFLOW_API_KEY")
    if not api_key:
        print("❌ 未找到 SILICONFLOW_API_KEY")
        return False

    try:
        files = {
            'file': ('test.wav', test_audio_data),
            'model': (None, "FunAudioLLM/SenseVoiceSmall")
        }

        headers = {
            'Authorization': f"Bearer {api_key}"
        }

        timeout = httpx.Timeout(
            connect=15.0,
            read=60.0,
            write=20.0,
            pool=10.0
        )

        print("📤 正在测试音频上传...")
        start_time = time.time()

        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                "https://api.siliconflow.cn/v1/audio/transcriptions",
                files=files,
                headers=headers
            )

            upload_time = time.time() - start_time
            print(f"⏱️  上传完成，耗时: {upload_time:.2f}秒")

            if response.status_code == 200:
                result = response.json()
                text = result.get('text', '')
                print(f"✅ 转录成功: {text[:50]}...")
                return True
            else:
                print(f"❌ 转录失败 - 状态码: {response.status_code}")
                print(f"   响应: {response.text}")
                return False

    except httpx.TimeoutException as e:
        print(f"❌ 上传超时: {e}")
        return False
    except Exception as e:
        print(f"❌ 上传异常: {e}")
        return False

def main():
    """主测试函数"""
    print("SiliconFlow API 连接诊断工具")
    print("=" * 40)

    # 检查环境变量
    print(f"🔑 API Key: {os.getenv('SILICONFLOW_API_KEY', 'NOT_SET')[:10]}...")
    print(f"⏱️  超时设置: {os.getenv('SILICONFLOW_TIMEOUT', '20')}秒")

    success_count = 0
    total_tests = 3

    if test_basic_connectivity():
        success_count += 1

    if test_api_access():
        success_count += 1

    if test_audio_upload_speed():
        success_count += 1

    print(f"\n=== 测试结果: {success_count}/{total_tests} 通过 ===")

    if success_count == total_tests:
        print("🎉 所有测试通过！SiliconFlow API 连接正常")
    else:
        print("⚠️  部分测试失败，请检查:")
        print("   1. 网络连接是否稳定")
        print("   2. API Key 是否有效")
        print("   3. 是否有防火墙或代理设置")
        print("   4. 考虑增加 SILICONFLOW_TIMEOUT 值")

if __name__ == "__main__":
    main()