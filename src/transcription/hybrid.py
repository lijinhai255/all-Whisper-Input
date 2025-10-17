"""
混合处理器：优先使用 SiliconFlow，失败时自动切换到 Groq
"""

import os
import threading
import time
from functools import wraps

import dotenv

from src.transcription.whisper import WhisperProcessor
from src.transcription.senseVoiceSmall import SenseVoiceSmallProcessor
from src.transcription.xunfei import XunfeiProcessor
from ..utils.logger import logger

dotenv.load_dotenv()


class HybridProcessor:
    """混合语音处理器：支持故障转移"""

    def __init__(self):
        self.processors = {}  # 所有可用处理器
        self.priority_order = ["siliconflow", "xunfei", "groq"]  # 优先级顺序
        self.enable_fallback = os.getenv("ENABLE_FALLBACK", "true").lower() == "true"
        self.fallback_count = {}
        self.max_fallbacks = 3  # 最大故障转移次数
        self.last_fallback_time = {}
        self.fallback_cooldown = 300  # 5分钟冷却时间

        # 初始化处理器
        self._initialize_processors()

    def _initialize_processors(self):
        """初始化语音处理器"""
        # 初始化 SiliconFlow
        try:
            self.processors["siliconflow"] = SenseVoiceSmallProcessor()
            self.fallback_count["siliconflow"] = 0
            self.last_fallback_time["siliconflow"] = 0
            logger.info("✅ SiliconFlow 处理器初始化成功")
        except Exception as e:
            logger.warning(f"⚠️ SiliconFlow 处理器初始化失败: {e}")

        # 初始化讯飞
        try:
            self.processors["xunfei"] = XunfeiProcessor()
            self.fallback_count["xunfei"] = 0
            self.last_fallback_time["xunfei"] = 0
            logger.info("✅ 讯飞处理器初始化成功")
        except Exception as e:
            logger.warning(f"⚠️ 讯飞处理器初始化失败: {e}")

        # 初始化 Groq
        try:
            self.processors["groq"] = WhisperProcessor()
            self.fallback_count["groq"] = 0
            self.last_fallback_time["groq"] = 0
            logger.info("✅ Groq 处理器初始化成功")
        except Exception as e:
            logger.warning(f"⚠️ Groq 处理器初始化失败: {e}")

        # 检查是否至少有一个处理器可用
        if not self.processors:
            raise RuntimeError("❌ 所有语音处理器都初始化失败")

    def _should_try_processor(self, processor_name):
        """判断是否应该尝试某个处理器"""
        processor = self.processors.get(processor_name)
        if not processor:
            return False

        # 如果在冷却期内，不尝试该处理器
        current_time = time.time()
        if (self.fallback_count.get(processor_name, 0) > 0 and
            current_time - self.last_fallback_time.get(processor_name, 0) < self.fallback_cooldown):
            logger.info(f"🔄 {processor_name} 处理器在冷却期内，跳过")
            return False

        return True

    def _process_with_processor(self, processor_name, audio_buffer, mode, prompt):
        """使用指定处理器处理音频"""
        if not self._should_try_processor(processor_name):
            return None, f"{processor_name} 处理器在冷却期"

        try:
            processor = self.processors[processor_name]
            logger.info(f"🎯 尝试使用 {processor_name} 处理器")
            result = processor.process_audio(audio_buffer, mode, prompt)

            # 如果成功，重置故障转移计数
            if self.fallback_count.get(processor_name, 0) > 0:
                logger.info(f"✅ {processor_name} 恢复正常，重置故障转移状态")
                self.fallback_count[processor_name] = 0

            return result

        except Exception as e:
            logger.warning(f"⚠️ {processor_name} 处理失败: {e}")
            if self.enable_fallback:
                # 更新故障转移状态
                self.fallback_count[processor_name] = self.fallback_count.get(processor_name, 0) + 1
                self.last_fallback_time[processor_name] = time.time()
                logger.info(f"📊 {processor_name} 故障转移计数: {self.fallback_count[processor_name]}/{self.max_fallbacks}")
                return None, str(e)
            else:
                raise e

    def process_audio(self, audio_buffer, mode="transcriptions", prompt=""):
        """处理音频，支持故障转移

        Args:
            audio_buffer: 音频数据缓冲
            mode: 'transcriptions' 或 'translations'
            prompt: 提示词

        Returns:
            tuple: (结果文本, 错误信息)
        """
        start_time = time.time()

        # 按优先级顺序尝试各个处理器
        for processor_name in self.priority_order:
            if processor_name in self.processors:
                result, error = self._process_with_processor(processor_name, audio_buffer, mode, prompt)
                if result:
                    logger.info(f"✅ {processor_name} 处理器成功，耗时: {time.time() - start_time:.1f}秒")
                    return result, None
                elif not self.enable_fallback:
                    return None, error

        # 如果所有处理器都失败了
        return None, "所有语音处理器都失败"

    def get_status(self):
        """获取处理器状态"""
        status = {
            "processors": list(self.processors.keys()),
            "priority_order": self.priority_order,
            "fallback_enabled": self.enable_fallback,
            "fallback_counts": self.fallback_count,
            "in_cooldown": {}
        }

        current_time = time.time()
        for processor_name in self.processors.keys():
            if self.fallback_count.get(processor_name, 0) > 0:
                status["in_cooldown"][processor_name] = (
                    current_time - self.last_fallback_time.get(processor_name, 0) < self.fallback_cooldown
                )
            else:
                status["in_cooldown"][processor_name] = False

        return status