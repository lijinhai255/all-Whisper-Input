import os
import sys

from dotenv import load_dotenv

load_dotenv()

from src.audio.recorder import AudioRecorder
from src.keyboard.listener import KeyboardManager, check_accessibility_permissions
from src.transcription.whisper import WhisperProcessor
from src.utils.logger import logger
from src.transcription.senseVoiceSmall import SenseVoiceSmallProcessor
from src.transcription.hybrid import HybridProcessor


def check_microphone_permissions():
    """检查麦克风权限并提供指导"""
    logger.warning("\n=== macOS 麦克风权限检查 ===")
    logger.warning("此应用需要麦克风权限才能进行录音。")
    logger.warning("\n请按照以下步骤授予权限：")
    logger.warning("1. 打开 系统偏好设置")
    logger.warning("2. 点击 隐私与安全性")
    logger.warning("3. 点击左侧的 麦克风")
    logger.warning("4. 点击右下角的锁图标并输入密码")
    logger.warning("5. 在右侧列表中找到 Terminal（或者您使用的终端应用）并勾选")
    logger.warning("\n授权后，请重新运行此程序。")
    logger.warning("===============================\n")

class VoiceAssistant:
    def __init__(self, audio_processor):
        self.audio_recorder = AudioRecorder()
        self.audio_processor = audio_processor
        self.keyboard_manager = KeyboardManager(
            on_record_start=self.start_transcription_recording,
            on_record_stop=self.stop_transcription_recording,
            on_translate_start=self.start_translation_recording,
            on_translate_stop=self.stop_translation_recording,
            on_reset_state=self.reset_state
        )
    
    def start_transcription_recording(self):
        """开始录音（转录模式）"""
        self.audio_recorder.start_recording()
    
    def stop_transcription_recording(self):
        """停止录音并处理（转录模式）"""
        audio = self.audio_recorder.stop_recording()
        if audio == "TOO_SHORT":
            logger.warning("录音时长太短，状态将重置")
            self.keyboard_manager.reset_state()
        elif audio:
            result = self.audio_processor.process_audio(
                audio,
                mode="transcriptions",
                prompt=""
            )
            # 解构返回值
            text, error = result if isinstance(result, tuple) else (result, None)
            self.keyboard_manager.type_text(text, error)
        else:
            logger.error("没有录音数据，状态将重置")
            self.keyboard_manager.reset_state()
    
    def start_translation_recording(self):
        """开始录音（翻译模式）"""
        self.audio_recorder.start_recording()
    
    def stop_translation_recording(self):
        """停止录音并处理（翻译模式）"""
        audio = self.audio_recorder.stop_recording()
        if audio == "TOO_SHORT":
            logger.warning("录音时长太短，状态将重置")
            self.keyboard_manager.reset_state()
        elif audio:
            result = self.audio_processor.process_audio(
                    audio,
                    mode="translations",
                    prompt=""
                )
            text, error = result if isinstance(result, tuple) else (result, None)
            self.keyboard_manager.type_text(text,error)
        else:
            logger.error("没有录音数据，状态将重置")
            self.keyboard_manager.reset_state()

    def reset_state(self):
        """重置状态"""
        self.keyboard_manager.reset_state()
    
    def run(self):
        """运行语音助手"""
        logger.info("=== 语音助手已启动 ===")
        self.keyboard_manager.start_listening()

def main():
    # 判断是 Whisper 还是 SiliconFlow
    service_platform = os.getenv("SERVICE_PLATFORM", "siliconflow")

    # 支持故障转移机制
    enable_fallback = os.getenv("ENABLE_FALLBACK", "true").lower() == "true"

    try:
        if service_platform == "groq":
            audio_processor = WhisperProcessor()
            logger.info("使用 Groq Whisper 服务")
        elif service_platform == "siliconflow":
            audio_processor = SenseVoiceSmallProcessor()
            logger.info("使用 SiliconFlow SenseVoice 服务")
        elif service_platform == "hybrid":
            # 混合模式：优先使用 SiliconFlow，失败时切换到 Groq
            audio_processor = HybridProcessor()
            logger.info("使用混合模式服务（优先 SiliconFlow，备用 Groq）")
        else:
            raise ValueError(f"无效的服务平台: {service_platform}")

    except Exception as e:
        if enable_fallback and service_platform == "siliconflow":
            logger.warning("SiliconFlow 初始化失败，尝试切换到 Groq...")
            try:
                audio_processor = WhisperProcessor()
                logger.info("已切换到 Groq Whisper 服务")
            except Exception as fallback_error:
                logger.error(f"Groq 也初始化失败: {fallback_error}")
                raise e
        else:
            raise e

    try:
        assistant = VoiceAssistant(audio_processor)
        assistant.run()
    except Exception as e:
        error_msg = str(e)
        if "Input event monitoring will not be possible" in error_msg:
            check_accessibility_permissions()
            sys.exit(1)
        elif "无法访问音频设备" in error_msg:
            check_microphone_permissions()
            sys.exit(1)
        else:
            logger.error(f"发生错误: {error_msg}", exc_info=True)
            sys.exit(1)

if __name__ == "__main__":
    main() 