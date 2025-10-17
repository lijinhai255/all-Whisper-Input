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
from ..utils.logger import logger

dotenv.load_dotenv()


class HybridProcessor:
    """混合语音处理器：支持故障转移"""

    def __init__(self):
        self.primary_processor = None  # SiliconFlow
        self.secondary_processor = None  # Groq
        self.enable_fallback = os.getenv("ENABLE_FALLBACK", "true").lower() == "true"
        self.fallback_count = 0
        self.max_fallbacks = 3  # 最大故障转移次数
        self.last_fallback_time = 0
        self.fallback_cooldown = 300  # 5分钟冷却时间

        # 初始化处理器
        self._initialize_processors()

    def _initialize_processors(self):
        """初始化语音处理器"""
        try:
            # 尝试初始化 SiliconFlow
            self.primary_processor = SenseVoiceSmallProcessor()
            logger.info("✅ SiliconFlow 处理器初始化成功")
        except Exception as e:
            logger.warning(f"⚠️ SiliconFlow 处理器初始化失败: {e}")
            self.primary_processor = None

        try:
            # 尝试初始化 Groq
            self.secondary_processor = WhisperProcessor()
            logger.info("✅ Groq 处理器初始化成功")
        except Exception as e:
            logger.warning(f"⚠️ Groq 处理器初始化失败: {e}")
            self.secondary_processor = None

        # 检查是否至少有一个处理器可用
        if not self.primary_processor and not self.secondary_processor:
            raise RuntimeError("❌ 所有语音处理器都初始化失败")

    def _should_try_primary(self):
        """判断是否应该尝试主处理器"""
        if not self.primary_processor:
            return False

        # 如果在冷却期内，不尝试主处理器
        current_time = time.time()
        if (self.fallback_count > 0 and
            current_time - self.last_fallback_time < self.fallback_cooldown):
            logger.info(f"🔄 在故障转移冷却期内，暂时使用备用处理器")
            return False

        return True

    def _process_with_primary(self, audio_buffer, mode, prompt):
        """使用主处理器处理音频"""
        if not self._should_try_primary():
            return None, "主处理器在冷却期"

        try:
            logger.info("🎯 尝试使用 SiliconFlow 处理器")
            result = self.primary_processor.process_audio(audio_buffer, mode, prompt)

            # 如果成功，重置故障转移计数
            if self.fallback_count > 0:
                logger.info("✅ SiliconFlow 恢复正常，重置故障转移状态")
                self.fallback_count = 0

            return result

        except Exception as e:
            logger.warning(f"⚠️ SiliconFlow 处理失败: {e}")
            if self.enable_fallback:
                return None, str(e)
            else:
                raise e

    def _process_with_secondary(self, audio_buffer, mode, prompt):
        """使用备用处理器处理音频"""
        if not self.secondary_processor:
            return None, "备用处理器不可用"

        try:
            logger.info("🔄 切换到 Groq 处理器")
            result = self.secondary_processor.process_audio(audio_buffer, mode, prompt)

            # 更新故障转移状态
            self.fallback_count += 1
            self.last_fallback_time = time.time()

            logger.info(f"📊 故障转移计数: {self.fallback_count}/{self.max_fallbacks}")

            return result

        except Exception as e:
            logger.error(f"❌ Groq 处理器也失败: {e}")
            return None, f"所有处理器都失败: {e}"

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

        # 第一步：尝试主处理器（SiliconFlow）
        if self.primary_processor:
            result, error = self._process_with_primary(audio_buffer, mode, prompt)
            if result:
                logger.info(f"✅ 主处理器成功，耗时: {time.time() - start_time:.1f}秒")
                return result, None
            elif not self.enable_fallback:
                return None, error

        # 第二步：故障转移到备用处理器（Groq）
        if self.secondary_processor and self.enable_fallback:
            result, error = self._process_with_secondary(audio_buffer, mode, prompt)
            if result:
                logger.info(f"✅ 备用处理器成功，总耗时: {time.time() - start_time:.1f}秒")
                return result, None
            else:
                return None, error

        # 如果都没有处理器可用
        return None, "没有可用的语音处理器"

    def get_status(self):
        """获取处理器状态"""
        status = {
            "primary_available": self.primary_processor is not None,
            "secondary_available": self.secondary_processor is not None,
            "fallback_enabled": self.enable_fallback,
            "fallback_count": self.fallback_count,
            "in_cooldown": (time.time() - self.last_fallback_time < self.fallback_cooldown) if self.fallback_count > 0 else False
        }
        return status