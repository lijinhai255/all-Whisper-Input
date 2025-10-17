#!/usr/bin/env python3
"""
讯飞语音识别完整测试脚本
"""

import os
import sys
import time
import wave
import numpy as np
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def create_test_audio(duration=3, sample_rate=16000):
    """创建测试音频WAV文件"""
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    # 创建一个简单的正弦波，模拟人声频率
    audio_data = np.sin(2 * np.pi * 440 * t) * 0.3  # 440Hz音调

    # 转换为16位整数
    audio_data = (audio_data * 32767).astype(np.int16)

    # 创建WAV文件数据
    import io
    wav_buffer = io.BytesIO()

    with wave.open(wav_buffer, 'wb') as wav_file:
        wav_file.setnchannels(1)  # 单声道
        wav_file.setsampwidth(2)  # 16位
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_data.tobytes())

    wav_buffer.seek(0)
    return wav_buffer

def test_xunfei_complete():
    """完整测试讯飞语音识别"""
    print("🎤 讯飞语音识别完整测试")
    print("=" * 50)

    try:
        from src.transcription.xunfei import XunfeiProcessor
        processor = XunfeiProcessor()

        # 创建测试音频
        print("创建测试音频...")
        audio_buffer = create_test_audio(duration=3, sample_rate=16000)
        print(f"✅ 测试音频创建完成 (3秒, 16kHz)")

        # 测试转录功能
        print("\n开始语音识别测试...")
        start_time = time.time()

        def on_partial_result(text):
            print(f"🔊 实时结果: {text}")

        result, error = processor.process_audio(
            audio_buffer,
            mode="transcriptions",
            on_partial_result=on_partial_result
        )

        elapsed_time = time.time() - start_time

        if error:
            print(f"❌ 识别失败: {error}")
            return False
        else:
            print(f"✅ 识别成功!")
            print(f"📝 识别结果: {result}")
            print(f"⏱️  耗时: {elapsed_time:.1f}秒")
            return True

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_xunfei_complete()

    if success:
        print("\n🎉 讯飞语音识别测试成功！")
        print("🚀 可以正常使用语音转录功能")
    else:
        print("\n❌ 讯飞语音识别测试失败")
        print("🔧 请检查配置或网络连接")

    sys.exit(0 if success else 1)