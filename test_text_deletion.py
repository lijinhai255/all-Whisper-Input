#!/usr/bin/env python3
"""
测试文本删除功能
"""

import time
import pyperclip
from pynput.keyboard import Controller

def test_text_deletion():
    """测试文本删除功能"""
    keyboard = Controller()

    print("🧪 测试文本删除功能")
    print("请在 3 秒内点击要测试的文本输入区域...")

    # 等待用户点击输入区域
    time.sleep(3)

    # 测试1：输入状态文本
    test_text = "🔄 正在转录..."
    print(f"📝 输入测试文本: {test_text}")

    pyperclip.copy(test_text)
    with keyboard.pressed(Key.cmd):  # macOS 使用 Cmd
        keyboard.press('v')
        keyboard.release('v')

    time.sleep(1)

    # 测试2：删除文本
    print("🗑️ 删除测试文本...")
    text_length = len(test_text)
    print(f"文本长度: {text_length}")

    for i in range(text_length):
        keyboard.press(Key.backspace)
        keyboard.release(Key.backspace)
        time.sleep(0.02)  # 短暂延迟
        print(f"删除进度: {i+1}/{text_length}")

    time.sleep(0.5)

    # 测试3：输入实际内容
    result_text = "这是一个测试转录结果"
    print(f"✅ 输入实际内容: {result_text}")

    pyperclip.copy(result_text)
    with keyboard.pressed(Key.cmd):
        keyboard.press('v')
        keyboard.release('v')

    print("✨ 测试完成！")

if __name__ == "__main__":
    from pynput.keyboard import Key
    test_text_deletion()