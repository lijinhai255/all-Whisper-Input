#!/usr/bin/env python3
"""
讯飞语音API测试脚本
用于验证讯飞语音识别功能是否正常工作
"""

import os
import sys
import time
import wave
import io
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.audio.recorder import AudioRecorder
from src.transcription.xunfei import XunfeiProcessor
from src.utils.logger import logger

def create_test_audio(duration=3, sample_rate=16000):
    """创建测试音频文件（简单的正弦波）"""
    import numpy as np

    # 生成测试音频数据
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    # 生成440Hz的正弦波（A音）
    audio_data = np.sin(2 * np.pi * 440 * t) * 0.3

    # 转换为16位整数
    audio_data = (audio_data * 32767).astype(np.int16)

    # 创建WAV文件
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wav_file:
        wav_file.setnchannels(1)  # 单声道
        wav_file.setsampwidth(2)  # 16位
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_data.tobytes())

    buffer.seek(0)
    return buffer

def test_xunfei_api():
    """测试讯飞API"""
    logger.info("=== 讯飞语音API测试开始 ===")

    # 检查环境变量
    required_env_vars = ['XUNFEI_APP_ID', 'XUNFEI_API_KEY', 'XUNFEI_API_SECRET']
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]

    if missing_vars:
        logger.error(f"缺少环境变量: {', '.join(missing_vars)}")
        return False

    try:
        # 初始化讯飞处理器
        processor = XunfeiProcessor()
        logger.info("讯飞处理器初始化成功")

        # 创建测试音频
        logger.info("创建测试音频...")
        test_audio = create_test_audio(duration=3)

        # 实时结果回调
        def on_partial_result(text):
            logger.info(f"实时结果: {text}")

        # 测试API调用
        logger.info("开始调用讯飞API...")
        start_time = time.time()

        result, error = processor.process_audio(
            test_audio,
            mode="transcriptions",
            on_partial_result=on_partial_result
        )

        duration = time.time() - start_time

        if error:
            logger.error(f"API调用失败: {error}")
            return False

        if result:
            logger.info(f"识别成功: {result}")
            logger.info(f"耗时: {duration:.2f}秒")
            return True
        else:
            logger.warning("API返回空结果")
            return False

    except Exception as e:
        logger.error(f"测试过程中发生错误: {e}", exc_info=True)
        return False
    finally:
        try:
            test_audio.close()
        except:
            pass

def test_real_recording():
    """测试真实录音"""
    logger.info("=== 真实录音测试开始 ===")

    try:
        # 初始化录音器和处理器
        recorder = AudioRecorder()
        processor = XunfeiProcessor()

        logger.info("请准备录音，按回车键开始录音（录音3秒）...")
        input()

        logger.info("开始录音...")
        recorder.start_recording()

        time.sleep(3)

        logger.info("停止录音...")
        audio = recorder.stop_recording()

        if audio == "TOO_SHORT":
            logger.error("录音时长太短")
            return False

        if not audio:
            logger.error("录音失败")
            return False

        # 实时结果回调
        def on_partial_result(text):
            logger.info(f"实时识别: {text}")

        logger.info("开始识别...")
        result, error = processor.process_audio(
            audio,
            mode="transcriptions",
            on_partial_result=on_partial_result
        )

        if error:
            logger.error(f"识别失败: {error}")
            return False

        if result:
            logger.info(f"识别结果: {result}")
            return True
        else:
            logger.warning("识别结果为空")
            return False

    except Exception as e:
        logger.error(f"真实录音测试失败: {e}", exc_info=True)
        return False

def main():
    """主函数"""
    print("讯飞语音API测试程序")
    print("=" * 50)

    # 测试选项
    print("1. 使用测试音频测试")
    print("2. 使用真实录音测试")
    print("3. 运行所有测试")

    choice = input("请选择测试类型 (1/2/3): ").strip()

    success = True

    if choice == "1":
        success = test_xunfei_api()
    elif choice == "2":
        success = test_real_recording()
    elif choice == "3":
        logger.info("运行测试音频测试...")
        success &= test_xunfei_api()

        logger.info("\n运行真实录音测试...")
        success &= test_real_recording()
    else:
        logger.error("无效的选择")
        return

    # 输出测试结果
    if success:
        logger.info("\n✅ 所有测试通过！")
    else:
        logger.error("\n❌ 测试失败！")

    print("\n测试完成")

if __name__ == "__main__":
    main()