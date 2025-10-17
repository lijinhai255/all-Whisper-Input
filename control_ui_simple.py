import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import os
import subprocess
import threading
import time
from pathlib import Path

class ControlUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Whisper Input Control Panel")
        self.root.geometry("600x500")
        
        # 主程序进程
        self.main_process = None
        
        # 创建界面
        self.create_widgets()
        
        # 加载现有配置
        self.load_config()
        
    def create_widgets(self):
        # 标题
        title_label = tk.Label(self.root, text="Whisper Input 控制面板", 
                              font=("Arial", 16, "bold"))
        title_label.pack(pady=10)
        
        # API Key 配置区域
        config_frame = ttk.LabelFrame(self.root, text="API 配置", padding=10)
        config_frame.pack(fill="x", padx=20, pady=10)
        
        # SILICONFLOW API Key
        tk.Label(config_frame, text="SILICONFLOW API Key:").pack(anchor="w")
        self.api_key_entry = tk.Entry(config_frame, width=50, show="*")
        self.api_key_entry.pack(fill="x", pady=(0, 10))
        
        # GROQ API Key
        tk.Label(config_frame, text="GROQ API Key:").pack(anchor="w")
        self.groq_key_entry = tk.Entry(config_frame, width=50, show="*")
        self.groq_key_entry.pack(fill="x", pady=(0, 10))
        
        # 保存配置按钮
        save_btn = tk.Button(config_frame, text="保存配置", 
                           command=self.save_config, bg="#4CAF50", fg="white")
        save_btn.pack(pady=5)
        
        # 控制按钮区域
        control_frame = ttk.LabelFrame(self.root, text="程序控制", padding=10)
        control_frame.pack(fill="x", padx=20, pady=10)
        
        button_frame = tk.Frame(control_frame)
        button_frame.pack()
        
        self.start_btn = tk.Button(button_frame, text="启动程序", 
                                  command=self.start_program, 
                                  bg="#2196F3", fg="white", width=12)
        self.start_btn.pack(side="left", padx=5)
        
        self.stop_btn = tk.Button(button_frame, text="停止程序", 
                                 command=self.stop_program, 
                                 bg="#f44336", fg="white", width=12, state="disabled")
        self.stop_btn.pack(side="left", padx=5)
        
        # 状态显示
        self.status_label = tk.Label(control_frame, text="状态: 未启动", 
                                    font=("Arial", 10))
        self.status_label.pack(pady=10)
        
        # 使用说明
        help_frame = ttk.LabelFrame(self.root, text="使用说明", padding=10)
        help_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        help_text = """使用方法：
1. 配置 API Key 并保存
2. 点击"启动程序"开始语音输入服务
3. 使用快捷键：
   • F8: 语音转录
   • F7+F8: 语音翻译
4. 在任意应用中将光标放在想要输入的位置，按快捷键即可

注意事项：
• 首次使用需要授予麦克风和辅助功能权限
• 确保在安静环境中使用以获得最佳效果
• 支持中英文语音输入和翻译"""
        
        help_display = scrolledtext.ScrolledText(help_frame, height=10, 
                                                wrap=tk.WORD, state="disabled")
        help_display.pack(fill="both", expand=True)
        help_display.config(state="normal")
        help_display.insert("1.0", help_text)
        help_display.config(state="disabled")
        
    def load_config(self):
        """加载现有的 .env 配置"""
        env_path = Path(".env")
        if env_path.exists():
            with open(env_path, 'r') as f:
                for line in f:
                    if line.startswith("SILICONFLOW_API_KEY="):
                        key = line.split("=", 1)[1].strip().strip('"')
                        self.api_key_entry.insert(0, key)
                    elif line.startswith("GROQ_API_KEY="):
                        key = line.split("=", 1)[1].strip().strip('"')
                        self.groq_key_entry.insert(0, key)
    
    def save_config(self):
        """保存配置到 .env 文件"""
        try:
            # 读取现有配置
            env_content = {}
            env_path = Path(".env")
            
            if env_path.exists():
                with open(env_path, 'r') as f:
                    for line in f:
                        if '=' in line and not line.strip().startswith('#'):
                            key, value = line.split('=', 1)
                            env_content[key.strip()] = value.strip()
            
            # 更新 API Keys
            if self.api_key_entry.get().strip():
                env_content['SILICONFLOW_API_KEY'] = f'"{self.api_key_entry.get().strip()}"'
            if self.groq_key_entry.get().strip():
                env_content['GROQ_API_KEY'] = f'"{self.groq_key_entry.get().strip()}"'
            
            # 确保必要的配置项
            if 'SYSTEM_PLATFORM' not in env_content:
                env_content['SYSTEM_PLATFORM'] = 'mac'
            if 'SERVICE_PLATFORM' not in env_content:
                env_content['SERVICE_PLATFORM'] = 'groq'
            
            # 写入文件
            with open(env_path, 'w') as f:
                for key, value in env_content.items():
                    f.write(f"{key}={value}\n")
            
            messagebox.showinfo("成功", "配置已保存到 .env 文件")
            
        except Exception as e:
            messagebox.showerror("错误", f"保存配置失败: {str(e)}")
    
    def start_program(self):
        """启动主程序"""
        try:
            # 检查配置
            if not Path(".env").exists():
                messagebox.showwarning("警告", "请先配置并保存 API Key")
                return
            
            # 启动主程序
            self.main_process = subprocess.Popen(
                ["python", "main.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # 更新界面状态
            self.start_btn.config(state="disabled")
            self.stop_btn.config(state="normal")
            self.status_label.config(text="状态: 运行中", fg="green")
            
            # 启动监控线程
            threading.Thread(target=self.monitor_process, daemon=True).start()
            
            messagebox.showinfo("成功", "程序已启动！\n现在可以使用 F8 进行语音转录，F7+F8 进行语音翻译")
            
        except Exception as e:
            messagebox.showerror("错误", f"启动程序失败: {str(e)}")
    
    def stop_program(self):
        """停止主程序"""
        if self.main_process:
            self.main_process.terminate()
            self.main_process = None
            
            # 更新界面状态
            self.start_btn.config(state="normal")
            self.stop_btn.config(state="disabled")
            self.status_label.config(text="状态: 已停止", fg="red")
            
            messagebox.showinfo("成功", "程序已停止")
    
    def monitor_process(self):
        """监控主程序状态"""
        if self.main_process:
            self.main_process.wait()
            # 程序意外退出
            self.root.after(0, self.on_process_exit)
    
    def on_process_exit(self):
        """程序退出时的处理"""
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.status_label.config(text="状态: 已退出", fg="orange")
        self.main_process = None
    
    def run(self):
        """运行 GUI"""
        # 退出时清理
        def on_closing():
            if self.main_process:
                self.main_process.terminate()
            self.root.destroy()
        
        self.root.protocol("WM_DELETE_WINDOW", on_closing)
        self.root.mainloop()

if __name__ == "__main__":
    app = ControlUI()
    app.run()