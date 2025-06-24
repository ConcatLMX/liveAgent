import sys
import os
import json
import time
from datetime import datetime, timedelta
import threading
import keyboard
from PyQt5.QtCore import Qt, QPropertyAnimation, QPoint, QEasingCurve, QTimer, QObject, pyqtSignal, QThread
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QTextEdit,
                             QLineEdit, QPushButton, QFrame, QScrollArea,
                             QSizePolicy, QHBoxLayout, QLabel, QSystemTrayIcon, QMenu)
from PyQt5.QtGui import QFont, QIcon, QColor, QPainter, QBrush, QLinearGradient, QPalette
import commands
from faiss_utils import VectorDatabase
from modules import is_json_file_empty
from message_utils import MessageUtils
from settings import SettingWindow
from Live2DViewerEX import L2DVEX
from Automation import EmailUtils
from Automation import EmailMonitorThread

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


# 创建信号对象用于跨线程通信
class HotkeySignal(QObject):
    toggle_signal = pyqtSignal()
    exit_signal = pyqtSignal()


hotkey_signal = HotkeySignal()


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
            print(f"[error]{error_msg}")
            self.error_occurred.emit("抱歉，处理您的消息时出现了问题，请稍后再试。")


def load_todays_history():
    """从JSON文件加载今天的历史记录"""
    if not os.path.exists(HISTORY_FILE):
        return []

    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)

            # 只保留今天的消息
            today = datetime.now().strftime("%Y-%m-%d")
            today_messages = [
                msg for msg in history["messages"]
                if msg["timestamp"].startswith(today)
            ]
            return today_messages
    except (json.JSONDecodeError, KeyError, IOError):
        return []


class ChatBubble(QFrame):
    def __init__(self, text, is_user=True, parent=None):
        super().__init__(parent)
        self.is_user = is_user
        self.setObjectName("bubble")
        self.setStyleSheet(self._get_bubble_style())
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)        # 创建主布局
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(0)# 使用QLabel来显示文本，支持自动换行
        self.text_label = QLabel(text)
        self.text_label.setWordWrap(True)  # 启用自动换行
        self.text_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.text_label.setStyleSheet("""
            background: transparent;
            border: none;
            color: %s;
            padding: 4px 6px;
            font-size: 14px;
            line-height: 1.5;
        """ % ("#ffffff" if is_user else "#333333"))
        
        # 设置字体
        font = QFont("Microsoft YaHei UI", 11)
        self.text_label.setFont(font)
        
        # 设置文本标签的大小策略
        self.text_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        
        layout.addWidget(self.text_label)
        self.setLayout(layout)        # 设置最大宽度以确保合适的换行
        self.setMaximumWidth(280)
        self.setMinimumWidth(60)

    def sizeHint(self):
        """返回气泡的推荐大小"""
        # 获取文本标签的大小提示
        label_hint = self.text_label.sizeHint()
        # 添加布局边距
        margins = self.layout().contentsMargins()
        width = label_hint.width() + margins.left() + margins.right()
        height = label_hint.height() + margins.top() + margins.bottom()
        from PyQt5.QtCore import QSize
        return QSize(width, height)

    def minimumSizeHint(self):
        """返回气泡的最小大小"""
        label_hint = self.text_label.minimumSizeHint()
        margins = self.layout().contentsMargins()
        width = label_hint.width() + margins.left() + margins.right()
        height = label_hint.height() + margins.top() + margins.bottom()
        from PyQt5.QtCore import QSize
        return QSize(width, height)
    def _get_bubble_style(self):
        if self.is_user:
            return """
                #bubble {
                    background: rgb(10, 132, 255);
                    border-radius: 18px;
                    border-bottom-right-radius: 5px;
                    padding: 2px;
                }
            """
        else:
            return """
                #bubble {
                    background: rgb(230, 230, 234);
                    border-radius: 18px;
                    border-bottom-left-radius: 5px;
                    padding: 2px;
                }
            """


class SolidBackground(QWidget):
    """使用纯色背景的窗口"""

    def __init__(self, parent=None):
        super(SolidBackground, self).__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground)


    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 绘制纯色背景
        bg_color = QColor(250, 250, 250, 255)  # 完全不透明
        painter.setBrush(bg_color)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect(), 20, 20)

        painter.end()


class ChatWindow(QWidget):
    def __init__(self, tray_icon=None):
        super().__init__()
        self.initialized = False
        self.tray_icon = tray_icon
        self.initUI()


    def initUI(self):
        self.setWindowTitle("live · Agent")
        self.setFixedSize(400, 650)
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.SubWindow |
            Qt.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)

        # 背景使用纯色
        self.background = SolidBackground(self)
        self.background.setGeometry(0, 0, 400, 650)

        # 标题栏
        title_bar = QWidget(self)
        title_bar.setFixedHeight(50)
        title_bar.setStyleSheet("background: transparent;")
        title_bar_layout = QHBoxLayout(title_bar)
        title_bar_layout.setContentsMargins(20, 0, 20, 0)

        # 标题
        title_label = QLabel("live · Agent")
        title_label.setFont(QFont("Microsoft YaHei UI", 12, QFont.Bold))
        title_label.setStyleSheet("color: #333;")
        title_bar_layout.addWidget(title_label)
        title_bar_layout.addStretch()

        # 关闭按钮
        self.close_btn = QPushButton("×")
        self.close_btn.setFixedSize(30, 30)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border-radius: 15px;
                border: none;
                font-size: 18px;
                color: #888;
            }
            QPushButton:hover {
                background: #f0f0f0;
            }
        """)
        self.close_btn.clicked.connect(self.hideWithAnimation)
        title_bar_layout.addWidget(self.close_btn)

        # 滚动区域
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setGeometry(10, 60, 380, 520)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                border: none;
                background: transparent;
                width: 8px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(200, 200, 200, 0.5);
                border-radius: 4px;
                min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
                background: none;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)

        # 聊天内容区域
        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet("background: transparent;")
        self.scroll_content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.chat_layout = QVBoxLayout(self.scroll_content)
        self.chat_layout.setContentsMargins(15, 15, 15, 15)
        self.chat_layout.setSpacing(15)
        self.chat_layout.addStretch(1)  # 确保内容在顶部

        self.scroll_area.setWidget(self.scroll_content)

        # 输入区域
        self.input_container = QWidget(self)
        self.input_container.setGeometry(10, 590, 380, 50)
        self.input_container.setStyleSheet("""
            background: rgb(246, 246, 246);
            border-radius: 18px;
            border: none;
        """)

        input_layout = QHBoxLayout(self.input_container)
        input_layout.setContentsMargins(15, 5, 15, 5)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("说点什么...")
        self.input_field.setStyleSheet("""
            QLineEdit {
                background: rgba(255, 255, 255, 0.8);
                border: none;
                font-size: 15px;
                color: #333;
                padding: 0 10px;
            }
        """)
        self.input_field.setFont(QFont("Microsoft YaHei UI", 12))

        self.send_btn = QPushButton("发送")
        self.send_btn.setFixedSize(60, 35)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background: #0A84FF;
                color: white;
                border-radius: 15px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #0971d9;
            }
            QPushButton:disabled {
                background: #b3d7ff;
            }
        """)
        self.send_btn.setFont(QFont("Microsoft YaHei UI", 10))
        self.send_btn.setEnabled(False)

        self.input_field.textChanged.connect(self.on_input_changed)
        self.input_field.returnPressed.connect(self.handle_send)
        self.send_btn.clicked.connect(self.handle_send)

        input_layout.addWidget(self.input_field)
        input_layout.addWidget(self.send_btn)

        # 初始位置（屏幕外）
        desktop = QApplication.primaryScreen().availableGeometry()
        self.move(
            desktop.width() // 2 - self.width() // 2,
            desktop.height()
        )

        self.initialized = True

    def settings_closed(self):
        """当设置窗口关闭时调用"""
        self.settings_window = None

    def on_input_changed(self):
        """输入框文本改变时的处理"""
        # 只有在不在AI生成过程中才允许启用发送按钮
        if not hasattr(self, 'ai_thread') or self.ai_thread is None:
            self.send_btn.setEnabled(bool(self.input_field.text().strip()))

    def add_message(self, text, is_user=True):
        """添加消息气泡 - 使用动态高度"""
        bubble = ChatBubble(text, is_user)

        # 创建包装器来控制气泡的对齐
        wrapper = QWidget()
        wrapper.setStyleSheet("background: transparent;")
        wrapper_layout = QHBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        
        if is_user:
            # 用户消息：右对齐
            wrapper_layout.addStretch()
            wrapper_layout.addWidget(bubble)
        else:
            # AI消息：左对齐
            wrapper_layout.addWidget(bubble)
            wrapper_layout.addStretch()

        # 添加到主布局
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, wrapper)

        # 滚动到底部
        QTimer.singleShot(100, self.scroll_to_bottom)


    def scroll_to_bottom(self):
        scrollbar = self.scroll_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())


    def clear_chat(self):
        # 清除除最后一项（stretch）之外的所有项目
        while self.chat_layout.count() > 1:
            item = self.chat_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()


    def load_history(self):
        self.clear_chat()
        messages = load_todays_history()  # 改为使用只加载今天历史记录的函数

        for msg in messages:
            role = msg.get("role", "assistant")
            content = msg.get("content", "")

            # 不再添加时间戳显示
            if role == "user":
                self.add_message(content, is_user=True)
            else:
                self.add_message(content, is_user=False)
    
    # 按下发送键后的发送控制
    def handle_send(self):
        msg = self.input_field.text().strip()
        if not msg:
            return

        # 清空输入框
        self.input_field.clear()

        # 判断是否为命令集
        app = QApplication.instance()
        if msg in COMMAND_LIST:
            commands.cmd_exec(app.vector_db, msg)
            return
        if msg == "-s":
            # 创建并显示模态设置窗口
            settings = SettingWindow(vector_db= app.vector_db, parent=self)
            settings.setWindowModality(Qt.ApplicationModal)  # 设置为应用模态
            settings.exec_()  # 模态显示窗口
            return

        # 禁用发送按钮，防止重复发送
        self.send_btn.setEnabled(False)
        self.send_btn.setText("生成中...")
        
        # 用户消息 - 立即显示
        self.add_message(msg, is_user=True)
        
        # 显示"正在思考"的占位符
        self.thinking_bubble = self.add_thinking_bubble()
        
        # 异步生成AI回复
        self.ai_thread = AIResponseThread(app.vector_db, app, msg)
        self.ai_thread.response_ready.connect(self.on_ai_response_ready)
        self.ai_thread.error_occurred.connect(self.on_ai_error)
        self.ai_thread.finished.connect(self.on_ai_thread_finished)
        
        # 保存用户消息
        try:
            mu = MessageUtils(app.vector_db, app)
            mu.save_message("user", msg)
        except Exception as e:
            print(f"[warning]保存用户消息时发生错误: {e}")
          # 启动AI响应线程
        self.ai_thread.start()

    def add_thinking_bubble(self):
        """添加'正在思考'的气泡"""
        thinking_text = "🤔 正在思考中..."
        bubble = ChatBubble(thinking_text, is_user=False)
        bubble.setObjectName("thinking_bubble")  # 设置特殊标识
        
        # 添加动画效果的样式
        bubble.setStyleSheet(bubble._get_bubble_style() + """
            QLabel {
                color: #666666;
                font-style: italic;
            }
        """)
        
        # 创建包装器
        wrapper = QWidget()
        wrapper.setStyleSheet("background: transparent;")
        wrapper_layout = QHBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        
        # AI消息：左对齐
        wrapper_layout.addWidget(bubble)
        wrapper_layout.addStretch()
        
        # 添加到主布局
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, wrapper)
        
        # 滚动到底部
        QTimer.singleShot(100, self.scroll_to_bottom)
        
        return wrapper

    def on_ai_response_ready(self, response):
        """AI回复准备完成"""
        # 移除"正在思考"的气泡
        if hasattr(self, 'thinking_bubble') and self.thinking_bubble:
            self.thinking_bubble.deleteLater()
            
        # 添加AI回复
        self.add_message(response, is_user=False)

        # L2D发送消息
        if CONFIG.get("live2d_listen", False):
            l2d.send_text_message(response)
        
        # 保存AI回复
        try:
            app = QApplication.instance()
            mu = MessageUtils(app.vector_db, app)
            mu.save_message("assistant", response)
        except Exception as e:
            print(f"[warning]保存AI回复时发生错误: {e}")

    def on_ai_error(self, error_msg):
        """AI生成错误"""
        # 移除"正在思考"的气泡
        if hasattr(self, 'thinking_bubble') and self.thinking_bubble:
            self.thinking_bubble.deleteLater()
            
        # 显示错误消息
        self.add_message(error_msg, is_user=False)

    def on_ai_thread_finished(self):
        """AI线程完成"""
        # 重新启用发送按钮
        self.send_btn.setEnabled(True)
        self.send_btn.setText("发送")
        
        # 清理线程引用
        if hasattr(self, 'ai_thread'):
            self.ai_thread.deleteLater()
            self.ai_thread = None


    def showAnimation(self):
        if not self.isVisible():
            self.show()
            self.load_history()

        # 确保窗口在屏幕中央
        desktop = QApplication.primaryScreen().availableGeometry()
        center_pos = QPoint(
            desktop.width() // 2 - self.width() // 2,
            desktop.height() // 2 - self.height() // 2
        )

        # 如果窗口已经在屏幕上，直接移动到中心
        if self.pos().y() < desktop.height():
            self.move(center_pos)
            return

        # 动画效果：从底部滑动到屏幕中央
        start_pos = self.pos()
        self.anim = QPropertyAnimation(self, b"pos")
        self.anim.setDuration(500)
        self.anim.setStartValue(start_pos)
        self.anim.setEndValue(center_pos)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        self.anim.start()

        self.activateWindow()
        self.raise_()
        self.input_field.setFocus()


    def hideWithAnimation(self):
        desktop = QApplication.primaryScreen().availableGeometry()
        start_pos = self.pos()
        end_pos = QPoint(
            desktop.width() // 2 - self.width() // 2,
            desktop.height()
        )

        self.anim = QPropertyAnimation(self, b"pos")
        self.anim.setDuration(400)
        self.anim.setStartValue(start_pos)
        self.anim.setEndValue(end_pos)
        self.anim.setEasingCurve(QEasingCurve.InCubic)
        self.anim.finished.connect(self.hide)
        self.anim.start()

    def mousePressEvent(self, event):
        # 支持窗口拖动
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        # 支持窗口拖动
        if event.buttons() == Qt.LeftButton and hasattr(self, 'drag_position'):
            self.move(event.globalPos() - self.drag_position)
            event.accept()


def setup_system_tray(app):
    """设置系统托盘图标"""
    tray_icon = QSystemTrayIcon(app)

    # 创建系统托盘菜单
    tray_menu = QMenu()

    show_action = tray_menu.addAction("打开liveAgent")
    show_action.triggered.connect(lambda: hotkey_signal.toggle_signal.emit())

    tray_menu.addSeparator()

    exit_action = tray_menu.addAction("退出")
    exit_action.triggered.connect(lambda: hotkey_signal.exit_signal.emit())

    # 设置系统托盘
    tray_icon.setContextMenu(tray_menu)

    # 双击托盘打开窗口
    tray_icon.activated.connect(lambda reason:
                                hotkey_signal.toggle_signal.emit() if reason == QSystemTrayIcon.DoubleClick else None
                                )

    tray_icon.show()

    return tray_icon


def toggle_chat_window():
    """切换聊天窗口显示状态"""
    app = QApplication.instance()

    if not hasattr(app, 'chat_window') or app.chat_window is None:
        app.chat_window = ChatWindow()

    if app.chat_window.isVisible():
        app.chat_window.hideWithAnimation()
    else:
        app.chat_window.showAnimation()


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
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # 设置应用名称
    app.setApplicationName("live · Agent")

    # 设置字体
    app_font = QFont("Microsoft YaHei UI", 10)
    app.setFont(app_font)

    # 设置托盘图标
    tray_icon = setup_system_tray(app)

    # 连接信号
    hotkey_signal.toggle_signal.connect(toggle_chat_window)
    hotkey_signal.exit_signal.connect(lambda: app.quit())

    # 启动热键监听线程
    threading.Thread(target=hotkey_listener, daemon=True).start()    # 确保应用在退出时关闭所有资源
    app.aboutToQuit.connect(lambda: cleanup_on_exit(app))

    # 添加属性用于存储聊天窗口
    app.chat_window = None

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

    # 成功标志
    print("[tips]对话框中输入--help()获取命令集")
    print("[info]初始化成功!按下热键唤起聊天窗口")

    # 进入事件循环
    app.exec_()


if __name__ == "__main__":
    print("[info]初始化中...")    
    
    #l2d连接
    if CONFIG.get("live2d_listen", False):
        l2d = L2DVEX(CONFIG.get("live2d_uri", "ws://"))
    
    #监听邮箱
    if CONFIG.get("receiveemail", False):
        # 启动邮箱监听线程
        email_monitor = EmailMonitorThread()
        email_monitor.start()
        print("[info]邮箱监听线程已启动")


    start_app()