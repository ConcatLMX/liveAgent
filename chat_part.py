import sys
import os
import json
from datetime import datetime, timedelta
import threading
import keyboard
from PyQt5.QtCore import Qt, QPropertyAnimation, QPoint, QEasingCurve, QTimer, QObject, pyqtSignal
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QTextEdit,
                             QLineEdit, QPushButton, QFrame, QScrollArea,
                             QSizePolicy, QHBoxLayout, QLabel, QSystemTrayIcon, QMenu)
from PyQt5.QtGui import QFont, QIcon, QColor, QPainter, QBrush, QLinearGradient, QPalette
import chat_command
from faiss_utils import VectorDatabase
from module import is_json_file_empty

HISTORY_FILE = "chat_history.json"
DEFAULT_HISTORY = {"messages": []}
COMMAND_LIST = ("--help()","--vb_clear()","--history_clear()","--show_parameters()")


# 创建信号对象用于跨线程通信
class HotkeySignal(QObject):
    toggle_signal = pyqtSignal()
    exit_signal = pyqtSignal()


hotkey_signal = HotkeySignal()


def save_message(role, content):
    """保存消息到JSON文件"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message = {
        "role": role,
        "content": content,
        "timestamp": timestamp
    }

    # 添加到向量数据库
    # 生成唯一ID
    msg_id = f"{timestamp}_{role}"
    app = QApplication.instance()
    if hasattr(app, 'vector_db'):
        app.vector_db.add_message(
            msg_id,
            role,
            content,
            timestamp
        )

    # 读取现有历史记录或创建新的
    history = DEFAULT_HISTORY.copy()
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                if is_json_file_empty(HISTORY_FILE):
                    raise IOError("JSON file is empty")
                history = json.load(f)
        except (json.JSONDecodeError, IOError):
            history = DEFAULT_HISTORY

    # 添加新消息
    history["messages"].append(message)

    # 保存回文件
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except IOError:
        pass


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
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)  # 修改为Preferred以支持动态高度

        # 创建主布局
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        # 文本标签 - 使用QTextEdit以支持自动换行和高度调整
        self.text_label = QTextEdit()
        self.text_label.setPlainText(text)
        self.text_label.setReadOnly(True)
        self.text_label.setStyleSheet("""
            background: transparent;
            border: none;
            color: %s;
            padding: 0px;
            font-size: 15px;
        """ % ("#ffffff" if is_user else "#333333"))
        self.text_label.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.text_label.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.text_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        # 根据内容调整高度
        self._adjust_height()

        layout.addWidget(self.text_label)
        self.setLayout(layout)


    def _adjust_height(self):
        """根据文本内容调整高度"""
        # 确保文本标签宽度已知（否则sizeHint会不准确）
        doc = self.text_label.document()
        doc.adjustSize()

        # 计算合适的高度（内容高度+适当边距）
        height = doc.size().height() + 15

        # 设置最大高度限制，避免过长消息占用太多空间
        max_height = min(height, 500)  # 最大高度为500px

        # 实际设置高度
        self.text_label.setFixedHeight(int(max_height))


    def _get_bubble_style(self):
        if self.is_user:
            return """
                #bubble {
                    background: rgb(10, 132, 255);
                    border-radius: 18px;
                    border-bottom-right-radius: 5px;
                }
            """
        else:
            return """
                #bubble {
                    background: rgb(230, 230, 234);
                    border-radius: 18px;
                    border-bottom-left-radius: 5px;
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

        self.input_field.textChanged.connect(lambda: self.send_btn.setEnabled(
            bool(self.input_field.text().strip())
        ))
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


    def add_message(self, text, is_user=True):
        """添加消息气泡 - 使用动态高度"""
        bubble = ChatBubble(text, is_user)

        # 设置对齐方式
        alignment = Qt.AlignRight | Qt.AlignTop if is_user else Qt.AlignLeft | Qt.AlignTop

        # 添加到布局
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, bubble, alignment=alignment)

        # 滚动到底部
        QTimer.singleShot(50, self.scroll_to_bottom)


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


    def generate_response(self, query):
        app = QApplication.instance()
        context = ""
        if hasattr(app, 'vector_db'):
            # 获取相关历史
            results = app.vector_db.search(query, k=3, threshold=0.5)

            if results:
                context = "\n".join(
                    f"[{res['role']}]: {res['content']}"
                    for res in results
                )

        # 简单示例：使用上下文生成回复
        if context:
            return f"基于您之前的对话，我理解您想问：\n{context}\n需要我做什么吗？"
        else:
            return "好的，我记下了！"


    def handle_send(self):
        msg = self.input_field.text().strip()
        if not msg:
            return

        # 清空输入框
        self.input_field.clear()

        # 判断是否为命令集
        app = QApplication.instance()
        if msg in COMMAND_LIST:
            chat_command.cmd_exec(app.vector_db, msg)
            return

        # 用户消息 - 不再显示时间戳
        self.add_message(msg, is_user=True)

        # AI回复（临时）- 不再显示时间戳你
        ai_response = self.generate_response(msg)
        self.add_message(ai_response, is_user=False)

        # 保存对话
        save_message("user", msg)
        save_message("assistant", ai_response)


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
    # 修改热键为Alt+Q
    keyboard.add_hotkey('alt+q', lambda: hotkey_signal.toggle_signal.emit())
    keyboard.wait()


def is_older_than_seven_days(timestamp_str, current_time=None):
    # 将时间字符串转为datetime对象
    timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
    # 如果没提供当前时间，则使用当前时间
    if current_time is None:
        current_time = datetime.now()
    # 计算时间差
    return current_time - timestamp > timedelta(days=7)


def routine_clear():
    app = QApplication.instance()
    # 第一步：清理JSON文件
    history_file = "chat_history.json"
    if is_json_file_empty(HISTORY_FILE):
        app.vector_db.clear()
        return

    with open(history_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 过滤超过7天的消息
    current_time = datetime.now()
    old_count = len(data["messages"])
    data["messages"] = [
        msg for msg in data["messages"]
        if not is_older_than_seven_days(msg["timestamp"], current_time)
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
    threading.Thread(target=hotkey_listener, daemon=True).start()

    # 确保应用在退出时关闭所有资源
    app.aboutToQuit.connect(lambda: keyboard.unhook_all_hotkeys())
    app.aboutToQuit.connect(lambda: app.vector_db.save())

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
    print("[tips]对话框中输入 --help() 获取帮助文档")
    print("[info]初始化成功!按下Alt+Q唤起聊天窗口")

    # 进入事件循环
    app.exec_()


if __name__ == "__main__":
    print("[info]初始化中...")
    start_app()