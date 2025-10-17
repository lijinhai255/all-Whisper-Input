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
import asyncio
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

        self.host = "iat-api.xfyun.cn"
        self.path = "/v2/iat"
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
        """生成讯飞语音听写流式版 WebSocket认证URL"""
        import datetime
        import hashlib
        import hmac
        import base64
        from urllib.parse import quote

        # 使用RFC1123格式的时间
        timestamp = datetime.datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')

        # 构建签名原文
        signature_origin = f"host: {self.host}\ndate: {timestamp}\nGET {self.path} HTTP/1.1"

        # 使用HMAC-SHA256进行加密
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
        """创建开始识别的消息 - 语音听写流式版格式"""
        return {
            "common": {
                "app_id": self.app_id
            },
            "business": {
                "language": "zh_cn",
                "domain": "iat",
                "accent": "mandarin",
                "vad_eos": 5000,
                "dwa": "wpgs"
            },
            "data": {
                "status": 0,  # 0表示第一帧
                "encoding": "raw",
                "audio": "",
                "format": "audio/L16;rate=16000"
            }
        }

    def _create_audio_message(self, audio_data: str, status: int = 2) -> dict:
        """创建音频数据消息 - 语音听写流式版格式"""
        return {
            "data": {
                "status": status,  # 1表示中间帧，2表示最后一帧
                "encoding": "raw",
                "audio": audio_data,
                "format": "audio/L16;rate=16000"
            }
        }

    @timeout_decorator(30)
    def _call_api_websocket(self, pcm_data: bytes,
                           on_partial_result: Optional[Callable[[str], None]] = None) -> str:
        """通过WebSocket调用讯飞Spark API"""

        async def websocket_call():
            uri = self._generate_auth_url()

            try:
                async with websockets.connect(uri, ping_timeout=self.timeout_seconds, close_timeout=self.timeout_seconds) as websocket:
                    logger.info("WebSocket连接成功")

                    # 接收识别结果
                    final_result = ""
                    try:
                        # 1. 发送开始消息
                        logger.info("发送开始消息...")
                        start_message = self._create_start_message()
                        await websocket.send(json.dumps(start_message))

                        # 2. 等待服务器确认
                        try:
                            response = await asyncio.wait_for(websocket.recv(), timeout=5)
                            result_data = json.loads(response)
                            logger.debug(f"服务器确认: {result_data}")

                            if str(result_data.get("code", "")) != "0":
                                error_msg = result_data.get("message", "未知错误")
                                logger.debug(f"服务器响应: code={result_data.get('code')}, message={error_msg}")
                                # 不抛出异常，继续处理
                        except asyncio.TimeoutError:
                            logger.warning("服务器确认超时，继续发送音频...")

                        # 3. 发送音频数据
                        logger.info("发送音频数据...")
                        audio_b64 = base64.b64encode(pcm_data).decode('utf-8')
                        audio_message = self._create_audio_message(audio_b64, status=2)  # status=2表示最后一帧
                        await websocket.send(json.dumps(audio_message))

                        # 2. 等待并接收识别结果
                        timeout_count = 0
                        max_wait_time = self.timeout_seconds  # 使用配置的超时时间

                        while timeout_count < max_wait_time * 10:  # 每0.1秒检查一次
                            try:
                                response = await asyncio.wait_for(websocket.recv(), timeout=0.1)
                                result_data = json.loads(response)

                                logger.info(f"收到响应: code={result_data.get('code', 'N/A')}, status={result_data.get('data', {}).get('status', 'N/A')}")
                                logger.debug(f"完整响应: {result_data}")

                                # 解析语音听写流式版API响应格式
                                if "code" in result_data and "data" in result_data:
                                    # 标准响应格式
                                    code = str(result_data.get("code", ""))
                                    data = result_data.get("data", {})
                                    sid = result_data.get("sid", "")

                                    if code == "0":
                                        # 成功响应，解析data字段
                                        if isinstance(data, dict):
                                            # 新格式：data.result.ws
                                            if "result" in data and "ws" in data["result"]:
                                                ws_data = data["result"]["ws"]
                                                current_text = ""
                                                for ws_item in ws_data:
                                                    for cw_item in ws_item.get("cw", []):
                                                        word = cw_item.get("w", "")
                                                        if word:  # 只添加非空的词
                                                            current_text += word

                                                if current_text:
                                                    final_result = current_text
                                                    if on_partial_result:
                                                        on_partial_result(current_text)
                                                    logger.info(f"识别结果: {current_text}")

                                            # 旧格式：data.cn
                                            elif "cn" in data:
                                                cn_data = data["cn"]
                                                if "st" in cn_data and "rt" in cn_data["st"]:
                                                    rt_data = cn_data["st"]["rt"]
                                                    if rt_data and len(rt_data) > 0:
                                                        ws_data = rt_data[0].get("ws", [])
                                                        current_text = ""
                                                        for ws_item in ws_data:
                                                            for cw_item in ws_item.get("cw", []):
                                                                current_text += cw_item.get("w", "")

                                                        if current_text:
                                                            final_result = current_text
                                                            if on_partial_result:
                                                                on_partial_result(current_text)
                                                            logger.info(f"识别结果: {current_text}")

                                        # 检查是否是最终结果
                                        if data.get("status", 0) == 2:  # status=2表示最后一帧
                                            logger.info("收到最终结果，结束识别")
                                            break
                                    else:
                                        logger.error(f"API错误: code={code}, sid={sid}")
                                        break

                                elif "cn" in result_data:
                                    # 直接返回语音听写格式
                                    cn_data = result_data["cn"]
                                    if "st" in cn_data and "rt" in cn_data["st"]:
                                        rt_data = cn_data["st"]["rt"]
                                        if rt_data and len(rt_data) > 0:
                                            ws_data = rt_data[0].get("ws", [])
                                            current_text = ""
                                            for ws_item in ws_data:
                                                for cw_item in ws_item.get("cw", []):
                                                    current_text += cw_item.get("w", "")

                                            if current_text:
                                                final_result = current_text
                                                if on_partial_result:
                                                    on_partial_result(current_text)
                                                logger.info(f"识别结果: {current_text}")

                                elif "code" in result_data:
                                    # 错误响应或其他响应
                                    code = str(result_data.get("code", ""))
                                    message = result_data.get("message", "")
                                    if code != "0":
                                        logger.debug(f"API响应: code={code}, message={message}")
                                        # code=0 是成功，其他是调试信息

                            except asyncio.TimeoutError:
                                timeout_count += 1
                                if timeout_count % 50 == 0:  # 每5秒打印一次
                                    logger.debug(f"等待结果... ({timeout_count/10:.1f}s)")
                            except websockets.exceptions.ConnectionClosed:
                                logger.info("WebSocket连接关闭")
                                break
                            except json.JSONDecodeError:
                                # 如果不是JSON，可能是纯文本响应
                                if response and response.strip():
                                    final_result = response
                                    if on_partial_result:
                                        on_partial_result(response)
                                    logger.info(f"识别结果: {response}")
                                    break

                    except Exception as e:
                        logger.error(f"处理响应时出错: {e}")

                    return final_result

            except Exception as e:
                logger.error(f"WebSocket通信失败: {e}")
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