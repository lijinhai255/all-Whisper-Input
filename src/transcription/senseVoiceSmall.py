import os
import threading
import time
from functools import wraps

import dotenv
import httpx

from src.llm.translate import TranslateProcessor
from ..utils.logger import logger

dotenv.load_dotenv()

def timeout_decorator(seconds):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = [None]
            error = [None]
            completed = threading.Event()

            def target():
                try:
                    result[0] = func(*args, **kwargs)
                except Exception as e:
                    error[0] = e
                finally:
                    completed.set()

            thread = threading.Thread(target=target)
            thread.daemon = True
            thread.start()

            if completed.wait(seconds):
                if error[0] is not None:
                    raise error[0]
                return result[0]
            raise TimeoutError(f"操作超时 ({seconds}秒)")

        return wrapper
    return decorator

class SenseVoiceSmallProcessor:
    # 类级别的配置参数
    DEFAULT_TIMEOUT = 20  # API 超时时间（秒）
    DEFAULT_MODEL = "FunAudioLLM/SenseVoiceSmall"
    
    def __init__(self):
        api_key = os.getenv("SILICONFLOW_API_KEY")
        assert api_key, "未设置 SILICONFLOW_API_KEY 环境变量"

        # 支持环境变量配置模型
        self.model = os.getenv("SILICONFLOW_ASR_MODEL", self.DEFAULT_MODEL)
        logger.info(f"使用语音识别模型: {self.model}")

        self.convert_to_simplified = os.getenv("CONVERT_TO_SIMPLIFIED", "false").lower() == "true"
        # self.cc = OpenCC('t2s') if self.convert_to_simplified else None
        # self.symbol = SymbolProcessor()
        # self.add_symbol = os.getenv("ADD_SYMBOL", "false").lower() == "true"
        # self.optimize_result = os.getenv("OPTIMIZE_RESULT", "false").lower() == "true"

        # 支持环境变量配置超时时间
        env_timeout = os.getenv("SILICONFLOW_TIMEOUT")
        if env_timeout:
            try:
                self.timeout_seconds = float(env_timeout)
                logger.info(f"使用环境变量配置的超时时间: {self.timeout_seconds}秒")
            except ValueError:
                logger.warning(f"无效的超时配置: {env_timeout}，使用默认值: {self.DEFAULT_TIMEOUT}秒")
                self.timeout_seconds = self.DEFAULT_TIMEOUT
        else:
            self.timeout_seconds = self.DEFAULT_TIMEOUT

        self.translate_processor = TranslateProcessor()

    def _convert_traditional_to_simplified(self, text):
        """将繁体中文转换为简体中文"""
        if not self.convert_to_simplified or not text:
            return text
        return self.cc.convert(text)

    def _call_api(self, audio_data):
        """调用硅流 API"""
        transcription_url = "https://api.siliconflow.cn/v1/audio/transcriptions"

        files = {
            'file': ('audio.wav', audio_data),
            'model': (None, self.model)
        }

        headers = {
            'Authorization': f"Bearer {os.getenv('SILICONFLOW_API_KEY')}"
        }

        # 设置HTTP客户端超时：根据环境变量动态调整
        read_timeout = min(60.0, self.timeout_seconds * 1.5)  # 读取超时，最大60秒
        timeout = httpx.Timeout(
            connect=15.0,      # 连接超时15秒
            read=read_timeout, # 读取超时，根据配置动态调整
            write=20.0,        # 写入超时20秒（上传音频文件）
            pool=10.0          # 连接池超时10秒
        )
        logger.info(f"HTTP 超时配置 - 连接: 15s, 读取: {read_timeout}s, 写入: 20s")

        # 添加重试机制
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                with httpx.Client(timeout=timeout) as client:
                    logger.info(f"正在上传音频文件到SiliconFlow API (尝试 {attempt + 1}/{max_retries + 1})")
                    response = client.post(transcription_url, files=files, headers=headers)
                    response.raise_for_status()
                    result = response.json().get('text', '获取失败')
                    logger.info("SiliconFlow API 响应成功")
                    return result
            except httpx.TimeoutException as e:
                logger.warning(f"SiliconFlow API 超时 (尝试 {attempt + 1}/{max_retries + 1}): {e}")
                if attempt == max_retries:
                    raise TimeoutError(f"SiliconFlow API 连接超时，已重试 {max_retries} 次")
                time.sleep(1)  # 重试前等待1秒
            except httpx.HTTPStatusError as e:
                logger.error(f"SiliconFlow API HTTP错误: {e.response.status_code} - {e.response.text}")
                raise Exception(f"SiliconFlow API 错误: {e.response.status_code}")
            except Exception as e:
                logger.warning(f"SiliconFlow API 调用失败 (尝试 {attempt + 1}/{max_retries + 1}): {e}")
                if attempt == max_retries:
                    raise
                time.sleep(1)  # 重试前等待1秒


    def _call_api_with_timeout(self, audio_data):
        """带超时控制的API调用"""
        def timeout_wrapper():
            return self._call_api(audio_data)

        result = [None]
        error = [None]
        completed = threading.Event()

        def target():
            try:
                result[0] = timeout_wrapper()
            except Exception as e:
                error[0] = e
            finally:
                completed.set()

        thread = threading.Thread(target=target)
        thread.daemon = True
        thread.start()

        if completed.wait(self.timeout_seconds):
            if error[0] is not None:
                raise error[0]
            return result[0]
        else:
            raise TimeoutError(f"API 请求超时 ({self.timeout_seconds}秒)")

    def process_audio(self, audio_buffer, mode="transcriptions", prompt=""):
        """处理音频（转录或翻译）

        Args:
            audio_buffer: 音频数据缓冲
            mode: 'transcriptions' 或 'translations'，决定是转录还是翻译

        Returns:
            tuple: (结果文本, 错误信息)
            - 如果成功，错误信息为 None
            - 如果失败，结果文本为 None
        """
        try:
            start_time = time.time()

            logger.info(f"正在调用 硅基流动 API... (模式: {mode})")
            result = self._call_api_with_timeout(audio_buffer)

            logger.info(f"API 调用成功 ({mode}), 耗时: {time.time() - start_time:.1f}秒")
            # result = self._convert_traditional_to_simplified(result)
            if mode == "translations":
                result = self.translate_processor.translate(result)
            logger.info(f"识别结果: {result}")

            # if self.add_symbol:
            #     result = self.symbol.add_symbol(result)
            #     logger.info(f"添加标点符号: {result}")
            # if self.optimize_result:
            #     result = self.symbol.optimize_result(result)
            #     logger.info(f"优化结果: {result}")

            return result, None

        except TimeoutError:
            error_msg = f"❌ API 请求超时 ({self.timeout_seconds}秒)"
            logger.error(error_msg)
            return None, error_msg
        except Exception as e:
            error_msg = f"❌ {str(e)}"
            logger.error(f"音频处理错误: {str(e)}", exc_info=True)
            return None, error_msg
        finally:
            audio_buffer.close()  # 显式关闭字节流
