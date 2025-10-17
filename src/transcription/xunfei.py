import os
import threading
import time
import json
import base64
import hashlib
import hmac
import wave
import io
import uuid
from functools import wraps
from typing import Optional, Callable, Tuple

import dotenv
import websockets
import numpy as np

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

class XunfeiProcessor:
    DEFAULT_TIMEOUT = 30
    MAX_DURATION = 60  # 讯飞限制60秒

    def __init__(self):
        self.app_id = os.getenv("XUNFEI_APP_ID")
        self.api_key = os.getenv("XUNFEI_API_KEY")
        self.api_secret = os.getenv("XUNFEI_API_SECRET")

        if not all([self.app_id, self.api_key, self.api_secret]):
            raise ValueError("未设置完整的讯飞API认证信息 (XUNFEI_APP_ID, XUNFEI_API_KEY, XUNFEI_API_SECRET)")

        self.host = "iat.xf-yun.com"
        self.path = "/v1"
        self.timeout_seconds = self.DEFAULT_TIMEOUT

        # 支持环境变量配置超时时间
        env_timeout = os.getenv("XUNFEI_TIMEOUT")
        if env_timeout:
            try:
                self.timeout_seconds = float(env_timeout)
                logger.info(f"使用环境变量配置的超时时间: {self.timeout_seconds}秒")
            except ValueError:
                logger.warning(f"无效的超时配置: {env_timeout}，使用默认值: {self.DEFAULT_TIMEOUT}秒")

        # 初始化翻译处理器
        self.translate_processor = TranslateProcessor()

        logger.info("讯飞语音处理器初始化完成")

    def _generate_auth_url(self) -> str:
        """生成讯飞WebSocket认证URL"""
        from urllib.parse import quote
        import datetime

        # 使用RFC1123格式的时间
        timestamp = datetime.datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')

        # 构建签名字符串
        signature_origin = f"host: {self.host}\ndate: {timestamp}\nGET {self.path} HTTP/1.1"

        # 使用hmac-sha256进行加密
        signature_sha = hmac.new(
            self.api_secret.encode('utf-8'),
            signature_origin.encode('utf-8'),
            hashlib.sha256
        ).digest()

        # 进行base64编码
        signature = base64.b64encode(signature_sha).decode('utf-8')

        # 构建authorization_origin
        authorization_origin = f'api_key="{self.api_key}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature}"'

        # 进行base64编码
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode('utf-8')

        # URL编码
        authorization_enc = quote(authorization)
        date_enc = quote(timestamp)

        return f"wss://{self.host}{self.path}?authorization={authorization_enc}&date={date_enc}&host={self.host}"

    def _convert_wav_to_pcm(self, wav_data: bytes) -> bytes:
        """将WAV格式转换为PCM格式，并进行必要的采样率转换"""
        try:
            # 使用io.BytesIO处理内存中的WAV数据
            wav_io = io.BytesIO(wav_data)

            with wave.open(wav_io, 'rb') as wav_file:
                # 获取WAV文件参数
                params = wav_file.getparams()
                frames = wav_file.readframes(params.nframes)

                # 检查格式是否满足讯飞要求
                if params.sampwidth != 2:
                    raise ValueError(f"不支持的位深: {params.sampwidth * 8}bit，需要16bit")

                # 转换为numpy数组进行处理
                audio_array = np.frombuffer(frames, dtype=np.int16)

                # 重采样到16kHz（如果需要）
                if params.framerate not in [8000, 16000]:
                    target_rate = 16000  # 优先使用16kHz
                    logger.info(f"正在重采样音频: {params.framerate}Hz -> {target_rate}Hz")

                    # 计算重采样比例
                    resample_ratio = target_rate / params.framerate
                    target_length = int(len(audio_array) * resample_ratio)

                    # 使用线性插值进行重采样
                    original_indices = np.arange(len(audio_array))
                    target_indices = np.linspace(0, len(audio_array) - 1, target_length)
                    resampled_audio = np.interp(target_indices, original_indices, audio_array).astype(np.int16)

                    audio_array = resampled_audio
                    logger.info(f"音频重采样完成: {params.framerate}Hz -> {target_rate}Hz")

                return audio_array.tobytes()

        except Exception as e:
            logger.error(f"WAV转PCM失败: {e}")
            raise

    def _create_start_message(self) -> dict:
        """创建开始识别的消息"""
        return {
            "header": {
                "app_id": self.app_id,
                "res_id": str(uuid.uuid4()),  # 生成唯一请求ID
                "status": 0
            },
            "parameter": {
                "iat": {
                    "domain": "slm",
                    "language": "zh_cn",
                    "accent": "mandarin",
                    "encoding": "raw",
                    "sample_rate": 16000,
                    "vad_eos": 5000
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

    def _create_end_message(self) -> dict:
        """创建结束识别的消息"""
        return {
            "header": {
                "app_id": self.app_id,
                "res_id": str(uuid.uuid4()),
                "status": 2
            },
            "parameter": {},
            "payload": {
                "audio": {
                    "encoding": "raw",
                    "sample_rate": 16000,
                    "seq": 0,
                    "audio": "",
                    "status": 2
                }
            }
        }

    @timeout_decorator(30)
    def _call_api_websocket(self, pcm_data: bytes,
                           on_partial_result: Optional[Callable[[str], None]] = None) -> str:
        """通过WebSocket调用讯飞API"""

        async def websocket_call():
            uri = self._generate_auth_url()

            try:
                # 使用ping_timeout和close_timeout替代timeout参数
                async with websockets.connect(uri, ping_timeout=self.timeout_seconds, close_timeout=self.timeout_seconds) as websocket:
                    # 发送开始消息
                    start_message = self._create_start_message()
                    await websocket.send(json.dumps(start_message))
                    logger.info("已发送开始识别消息")

                    # 生成唯一的res_id用于整个会话
                    res_id = str(uuid.uuid4())

                    # 分帧发送音频数据
                    frame_size = 1280  # 40ms的音频数据 (16kHz * 16bit * 0.04s)
                    total_frames = (len(pcm_data) + frame_size - 1) // frame_size

                    final_result = ""

                    for seq, i in enumerate(range(0, len(pcm_data), frame_size)):
                        frame_data = pcm_data[i:i + frame_size]
                        is_last = (i + frame_size) >= len(pcm_data)
                        status = 2 if is_last else 1

                        # 构造音频数据消息
                        audio_message = {
                            "header": {
                                "app_id": self.app_id,
                                "res_id": res_id,
                                "status": status
                            },
                            "parameter": {},
                            "payload": {
                                "audio": {
                                    "encoding": "raw",
                                    "sample_rate": 16000,
                                    "seq": seq,
                                    "audio": base64.b64encode(frame_data).decode('utf-8'),
                                    "status": status
                                }
                            }
                        }

                        await websocket.send(json.dumps(audio_message))

                        # 接收识别结果
                        try:
                            response = await websocket.recv()
                            result_data = json.loads(response)

                            if result_data.get("header", {}).get("code") == 0:
                                # 解析识别结果
                                payload = result_data.get("payload", {})
                                result = payload.get("result", {})

                                # 处理文本结果
                                text_data = result.get("text", "")
                                if text_data:
                                    # 解码base64文本
                                    try:
                                        decoded_text = base64.b64decode(text_data).decode('utf-8')
                                        if decoded_text:
                                            if on_partial_result:
                                                on_partial_result(decoded_text)
                                            final_result = decoded_text
                                    except:
                                        # 如果base64解码失败，直接使用原文
                                        if text_data:
                                            if on_partial_result:
                                                on_partial_result(text_data)
                                            final_result = text_data

                                # 备用解析方式 - 兼容旧格式
                                if not final_result and "ws" in result:
                                    ws = result.get("ws", [])
                                    for item in ws:
                                        cw = item.get("cw", [])
                                        for word in cw:
                                            final_result += word.get("w", "")

                            else:
                                error_msg = result_data.get("header", {}).get("message", "未知错误")
                                logger.error(f"讯飞API返回错误: {error_msg}")

                        except websockets.exceptions.ConnectionClosed:
                            logger.warning("WebSocket连接已关闭")
                            break

                        # 控制发送频率，避免过快
                        await asyncio.sleep(0.04)  # 40ms间隔

                    # 最后一个音频帧已经发送了status=2，不需要单独发送结束消息
                    logger.info("所有音频帧发送完成")

                    # 等待最终结果
                    try:
                        # 等待一段时间让服务器处理最后的音频
                        await asyncio.sleep(1)

                        final_response = await websocket.recv()
                        final_data = json.loads(final_response)

                        if final_data.get("header", {}).get("code") == 0:
                            payload = final_data.get("payload", {})
                            result = payload.get("result", {})

                            # 处理文本结果
                            text_data = result.get("text", "")
                            if text_data:
                                try:
                                    decoded_text = base64.b64decode(text_data).decode('utf-8')
                                    if decoded_text:
                                        final_result = decoded_text
                                except:
                                    if text_data:
                                        final_result = text_data

                            # 备用解析方式 - 兼容旧格式
                            if not final_result and "ws" in result:
                                ws = result.get("ws", [])
                                final_text = ""
                                for item in ws:
                                    cw = item.get("cw", [])
                                    for word in cw:
                                        final_text += word.get("w", "")
                                if final_text:
                                    final_result = final_text
                    except Exception as e:
                        logger.debug(f"获取最终结果时出错: {e}")
                        pass  # 忽略最终结果的获取错误，使用已接收的结果

                    return final_result

            except Exception as e:
                logger.error(f"WebSocket连接失败: {e}")
                raise

        # 运行异步WebSocket调用
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(websocket_call())

    def process_audio(self, audio_buffer, mode="transcriptions", prompt="",
                     on_partial_result: Optional[Callable[[str], None]] = None) -> Tuple[Optional[str], Optional[str]]:
        """处理音频（转录或翻译）

        Args:
            audio_buffer: 音频数据缓冲 (WAV格式)
            mode: 'transcriptions' 或 'translations'
            prompt: 提示词（讯飞暂不支持）
            on_partial_result: 实时结果回调函数

        Returns:
            tuple: (结果文本, 错误信息)
        """
        try:
            start_time = time.time()

            # 检查录音时长限制
            if hasattr(audio_buffer, 'getvalues'):
                duration = len(audio_buffer.getvalues()) / audio_buffer.getframerate()
                if duration > self.MAX_DURATION:
                    error_msg = f"❌ 录音时长超过限制 ({duration:.1f}s > {self.MAX_DURATION}s)"
                    logger.error(error_msg)
                    return None, error_msg

            logger.info(f"正在调用讯飞语音API... (模式: {mode})")

            # 将WAV转换为PCM
            pcm_data = self._convert_wav_to_pcm(audio_buffer.read())
            logger.info(f"音频格式转换完成，数据大小: {len(pcm_data)} bytes")

            # 调用讯飞API
            result = self._call_api_websocket(pcm_data, on_partial_result)

            logger.info(f"讯飞API调用成功 ({mode})，耗时: {time.time() - start_time:.1f}秒")
            logger.info(f"识别结果: {result}")

            # 如果是翻译模式，使用翻译处理器
            if mode == "translations":
                result = self.translate_processor.translate(result)
                logger.info(f"翻译结果: {result}")

            return result, None

        except TimeoutError:
            error_msg = f"❌ 讯飞API请求超时 ({self.timeout_seconds}秒)"
            logger.error(error_msg)
            return None, error_msg
        except Exception as e:
            error_msg = f"❌ 讯飞音频处理错误: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return None, error_msg
        finally:
            try:
                audio_buffer.close()
            except:
                pass