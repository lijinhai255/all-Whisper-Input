import pyperclip
from pynput.keyboard import Controller, Key
import time

def test_type_temp_text():
    """测试临时文本输入功能"""
    keyboard = Controller()
    
    # 测试文本
    test_text = "🎤 正在121212录音..."
    
    print(f"准备输入测试文本: {test_text}")
    print("请在5秒内将光标放在任意文本编辑器中...")
    
    # 给用户时间切换到文本编辑器
    for i in range(5, 0, -1):
        print(f"{i}...")
        time.sleep(1)
    
    try:
        # 将文本复制到剪贴板
        pyperclip.copy(test_text)
        print("文本已复制到剪贴板")
        
        # 模拟 Cmd + V 粘贴文本 (macOS)
        with keyboard.pressed(Key.cmd):
            keyboard.press('v')
            keyboard.release('v')
        
        print("粘贴命令已发送")
        
    except Exception as e:
        print(f"错误: {e}")

if __name__ == "__main__":
    test_type_temp_text()