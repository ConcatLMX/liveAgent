"""
聊天应用的核心逻辑模块
包含配置管理、消息处理、应用程序控制等逻辑
"""

import sys
import os
import json
import time
from datetime import datetime, timedelta
import threading
import keyboard
from PyQt5.QtCore import QObject, pyqtSignal, QThread, QTimer
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont

import commands
from faiss_utils import VectorDatabase
from modules import is_json_file_empty
from message_utils import MessageUtils
from settings import SettingWindow
from Live2DViewerEX import L2DVEX
from Automation import EmailUtils
from Automation import EmailMonitorThread

from ui_webview import ChatWindow, setup_system_tray, setup_webengine_global_config

HISTORY_FILE = "chat_history.json"
DEFAULT_HISTORY = {"messages": []}
COMMAND_LIST = ("--help()","--vb_clear()","--history_clear()","--show_parameters()")

# 读取配置文件
def reload_config():
    """重新加载配置文件"""
    global CONFIG
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            CONFIG = json.load(f)
        return True
    except Exception as e:
        print(f"[error]重新加载配置文件时发生错误: {e}")
        return False

# 从 settings.py 导入默认配置
from settings import DEFAULT_CONFIG

try:
    with open('config.json', 'r', encoding='utf-8') as f:
        CONFIG = json.load(f)
except Exception as e:
    print(f"[error]读取 config.json 时发生错误: {e}")
    # 配置文件不存在或读取失败，创建默认配置文件
    CONFIG = DEFAULT_CONFIG
    try:
        with open('config.json', 'w', encoding='utf-8') as f:
            json.dump(CONFIG, f, ensure_ascii=False, indent=2)
        print("[info]已创建默认配置文件 config.json")
    except Exception as create_error:
        print(f"[error]创建默认配置文件失败: {create_error}")
        CONFIG = {} 


# 创建热键信号系统
class HotkeySignals(QObject):
    toggle_signal = pyqtSignal()
    exit_signal = pyqtSignal()

hotkey_signal = HotkeySignals()


# AI响应生成线程
class AIResponseThread(QThread):
    response_ready = pyqtSignal(str)  # 响应准备完成信号
    error_occurred = pyqtSignal(str)  # 错误发生信号
    
    def __init__(self, vector_db, app, message):
        super().__init__()
        self.vector_db = vector_db
        self.app = app
        self.message = message
    
    def run(self):
        
        try:
            mu = MessageUtils(self.vector_db, self.app)
            
            response = mu.generate_response(self.message)
            
            self.response_ready.emit(response)
            
        except Exception as e:
            error_msg = f"生成回复时发生错误: {e}"
            print(f"[error]:{error_msg}")
            import traceback
            print(f"[error]错误堆栈: {traceback.format_exc()}")
            
            self.error_occurred.emit("抱歉，处理您的消息时出现了问题，请稍后再试。")


# 聊天控制器类
class ChatController:
    def __init__(self, vector_db, app):
        self.vector_db = vector_db
        self.app = app
        self.chat_window = None
        self.ai_thread = None
        
    def create_chat_window(self):
        """创建聊天窗口"""
        if self.chat_window is None:
            self.chat_window = ChatWindow()
            # 连接信号到控制器方法
            self.chat_window.message_sent.connect(self.handle_message)
            self.chat_window.command_executed.connect(self.handle_command)
        return self.chat_window
    
    def handle_message(self, message):
        """处理用户消息"""
        
        try:
            # 保存用户消息到历史记录（前端已经显示了用户消息）
            mu = MessageUtils(self.vector_db, self.app)
            mu.save_message("user", message)
            
            # 通过WebView接口显示思考气泡（前端会自动处理）
            self.chat_window.set_ai_processing(True)
            
            # 异步生成AI回复
            self.ai_thread = AIResponseThread(self.vector_db, self.app, message)
            self.ai_thread.response_ready.connect(
                lambda response: self._on_ai_response_ready(response, None)
            )
            self.ai_thread.error_occurred.connect(
                lambda error: self._on_ai_error(error, None)
            )
            self.ai_thread.start()
                    
        except Exception as e:
            error_msg = f"处理消息时发生错误: {e}"
            print(f"[error]{error_msg}")
            import traceback
            print(f"[error]错误堆栈: {traceback.format_exc()}")
            
            # 确保即使出错也要移除思考气泡
            self.chat_window.set_ai_processing(False)
            
            self.chat_window.add_ai_message("抱歉，处理您的消息时出现了问题，请稍后再试。")
    
    def _on_ai_response_ready(self, response, thinking_bubble):
        """AI回复准备完成"""
        # 设置AI处理状态为完成，前端会自动移除思考气泡
        self.chat_window.set_ai_processing(False)
        # 添加AI回复
        self.chat_window.add_ai_message(response)
        
        # 保存AI回复
        try:
            mu = MessageUtils(self.vector_db, self.app)
            mu.save_message("assistant", response)
        except Exception as e:
            print(f"[error]保存AI回复时发生错误: {e}")
        
        # L2D发送消息
        if CONFIG.get("live2d_listen", False):
            try:
                l2d_instance = L2DVEX(CONFIG.get("live2d_uri", "ws://"))
                l2d_instance.send_text_message(response)
            except Exception as e:
                print(f"[error]发送消息到Live2D失败: {e}")
        else:
            print(f"[info]Live2D监听已禁用，跳过")
    
    def _on_ai_error(self, error_msg, thinking_bubble):
        """AI生成错误"""
        print(f"[error]AI生成错误: {error_msg}")
        
        # 设置AI处理状态为完成，前端会自动移除思考气泡
        self.chat_window.set_ai_processing(False)
            
        # 显示错误消息
        self.chat_window.add_ai_message(error_msg)
    
    def handle_command(self, command):
        """处理命令"""
        if command in COMMAND_LIST:
            commands.cmd_exec(self.vector_db, command)
        elif command == "-s":
            settings = SettingWindow(vector_db=self.vector_db, parent=self.chat_window)
            settings.exec_()


def load_todays_history():
    """加载今天的聊天历史记录"""
    today = datetime.now().strftime("%Y-%m-%d")
    
    if not os.path.exists(HISTORY_FILE):
        print(f"[info]历史文件不存在: {HISTORY_FILE}")
        return []
    
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        total_messages = len(data.get("messages", []))
        print(f"[info]历史文件中共有{total_messages}条消息")

        # 过滤今天的消息
        today_messages = []
        for msg in data.get("messages", []):
            timestamp_str = msg.get("timestamp", "")
            if timestamp_str.startswith(today):
                today_messages.append(msg)

        return today_messages
    except Exception as e:
        print(f"[error]加载历史记录失败: {e}")
        import traceback
        print(f"[error]错误堆栈: {traceback.format_exc()}")
        return []


def toggle_chat_window():
    """切换聊天窗口显示状态"""
    app = QApplication.instance()

    if not hasattr(app, 'chat_controller') or app.chat_controller is None:
        app.chat_controller = ChatController(app.vector_db, app)
    
    chat_window = app.chat_controller.create_chat_window()

    if chat_window.isVisible():
        chat_window.hide_with_animation()
    else:
        # 检查是否是首次显示（通过检查是否有历史记录标记）
        if not hasattr(chat_window, '_history_loaded'):
            # 先显示窗口动画，然后加载历史记录
            chat_window.show_animation()
            
            # 延迟加载历史记录，确保窗口和WebView完全初始化
            def delayed_load_history():
                history_messages = load_todays_history()
                print(f"[info]历史记录数据获取完成，消息数量: {len(history_messages)}")
                if history_messages:
                    chat_window.load_history(history_messages)
                else:
                    print(f"[info]没有历史记录需要加载")
                # 标记历史记录已加载
                chat_window._history_loaded = True
            
            # 2秒后加载历史，确保窗口动画完成且WebView完全准备就绪
            QTimer.singleShot(2000, delayed_load_history)
        else:

            chat_window.show_animation()


def hotkey_listener():
    """热键监听函数，在单独的线程中运行"""
    try:
        # 读取配置文件中的热键设置
        hotkey_raw = CONFIG.get("hotkey", "Alt+Q")
        # 标准化热键格式
        hotkey = hotkey_raw.strip().lower()
        # 确保组合键格式正确
        hotkey = hotkey.replace(' ', '').replace('alt+', 'alt+').replace('ctrl+', 'ctrl+').replace('shift+', 'shift+')
        
        # 注册热键
        try:
            keyboard.add_hotkey(hotkey, lambda: hotkey_signal.toggle_signal.emit())
            print(f"[info]已注册热键: {hotkey} (原始: {hotkey_raw})")
        except Exception as e:
            print(f"[error]注册热键失败: {e}, 热键: {hotkey}")
            # 尝试使用默认热键
            try:
                default_hotkey = "alt+q"
                keyboard.add_hotkey(default_hotkey, lambda: hotkey_signal.toggle_signal.emit())
                print(f"[info]使用默认热键: {default_hotkey}")
            except Exception as e2:
                print(f"[error]连默认热键也注册失败: {e2}")
        
        # 保持线程运行
        while True:
            import time
            time.sleep(60)  # 每分钟检查一次线程状态
            
    except Exception as e:
        print(f"[error]热键监听器错误: {e}")
        import time
        time.sleep(5)


def is_older_than_given_day(timestamp_str, current_time=None, day=7):
    # 将时间字符串转为datetime对象
    timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
    # 如果没提供当前时间，则使用当前时间
    if current_time is None:
        current_time = datetime.now()
    # 计算时间差
    return current_time - timestamp > timedelta(days=day)


def routine_clear():
    app = QApplication.instance()
    # 第一步：清理JSON文件
    history_file = "chat_history.json"
    if is_json_file_empty(HISTORY_FILE):
        app.vector_db.clear()
        return

    with open(history_file, "r", encoding="utf-8") as f:
        data = json.load(f)    # 过滤超过配置天数的消息
    current_time = datetime.now()
    max_days = CONFIG.get("max_day", 7)  # 从配置文件读取保留天数，默认7天
    old_count = len(data["messages"])
    data["messages"] = [
        msg for msg in data["messages"]
        if not is_older_than_given_day(msg["timestamp"], current_time, max_days)
    ]
    new_count = len(data["messages"])
    print(f"[info]清理JSON文件: 原始记录数: {old_count}, 清理后记录数: {new_count}")

    # 写回文件
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # 第二步：重建向量数据库
    if hasattr(app, 'vector_db') and app.vector_db is not None:
        # 使用清理后的消息重建向量数据库
        app.vector_db.rebuild_with_add_message(data["messages"])
    else:
        print("[warning]向量数据库未初始化，跳过重建")


def cleanup_on_exit(app):
    """应用退出时的清理工作"""
    try:
        # 清理热键
        keyboard.unhook_all_hotkeys()
        print("[info]已清理所有热键")
    except:
        pass
    
    try:
        # 保存向量数据库
        if hasattr(app, 'vector_db') and app.vector_db:
            app.vector_db.save()
            print("[info]已保存向量数据库")
    except:
        pass


def start_app():
    """主应用启动函数"""
    print("[info]初始化中...")  

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # 设置应用名称
    app.setApplicationName("liveAgent")  # 移除特殊字符，避免路径问题
    app.setApplicationVersion("1.0")
    app.setOrganizationName("liveAgent")

    # 设置WebEngine全局配置
    setup_webengine_global_config()

    # 设置字体
    app_font = QFont("Microsoft YaHei UI", 10)
    app.setFont(app_font)

    # 设置托盘图标
    tray_icon = setup_system_tray(app)

    # 连接信号
    hotkey_signal.toggle_signal.connect(toggle_chat_window)
    hotkey_signal.exit_signal.connect(lambda: app.quit())

    # 启动热键监听线程
    threading.Thread(target=hotkey_listener, daemon=True).start()
    
    # 确保应用在退出时关闭所有资源
    app.aboutToQuit.connect(lambda: cleanup_on_exit(app))

    # 添加属性用于存储聊天控制器
    app.chat_controller = None

    # 初始化时创建历史文件（如果不存在）
    if not os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_HISTORY, f, indent=2)

    #初始化FAISS向量数据库
    # 在应用启动时
    app.vector_db = VectorDatabase()

    #清理记录
    routine_clear()

    # 加载现有历史记录
    load_todays_history()

    #l2d连接
    if CONFIG.get("live2d_listen", False):
        l2d = L2DVEX(CONFIG.get("live2d_uri", "ws://"))
    
    #监听邮箱
    if CONFIG.get("receiveemail", False):
        # 启动邮箱监听线程，传递app和vector_db实例
        # 检查间隔设为300秒（5分钟），避免频繁连接邮件服务器
        email_monitor = EmailMonitorThread("data.json", 300, app, app.vector_db)
        email_monitor.start()
        print("[info]邮箱监听线程已启动，检查间隔: 5分钟")

    # 成功标志
    print("[tips]对话框中输入--help()获取命令集")
    print("[info]初始化成功!按下热键唤起聊天窗口")

    # 进入事件循环
    app.exec_()


if __name__ == "__main__":  
    start_app()
