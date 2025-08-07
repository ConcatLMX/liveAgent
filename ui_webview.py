"""
UI模块 - 基于WebView的聊天窗口界面组件
使用HTML/CSS重写聊天界面，保留Qt控件的关闭和设置按钮
"""

import os
import json
import markdown
from datetime import datetime
from PyQt5.QtCore import (Qt, QPropertyAnimation, QPoint, QEasingCurve, 
                         QTimer, QObject, pyqtSignal, pyqtSlot, QEvent, QStandardPaths, QUrl, QThread, QRectF)
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QTextEdit,
                           QLineEdit, QPushButton, QFrame, QScrollArea,
                           QSizePolicy, QHBoxLayout, QLabel, QSystemTrayIcon, 
                           QMenu, QShortcut)
from PyQt5.QtGui import (QFont, QIcon, QColor, QPainter, QBrush, QPen,
                        QLinearGradient, QPalette, QKeyEvent, QKeySequence, QRegion, QPainterPath)
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineProfile, QWebEnginePage
from PyQt5.QtWebChannel import QWebChannel

# 读取配置文件的函数
def load_config():
    """加载配置文件"""
    config_file = "config.json"
    if os.path.exists(config_file):
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    # 如果配置文件不存在，使用默认配置
    default_file = "default.json"
    if os.path.exists(default_file):
        with open(default_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    # 如果都不存在，返回默认主题色
    return {"theme_color": "#ff69b4"}


class ChatBridge(QObject):
    """前后端通信桥梁"""
    message_sent = pyqtSignal(str)
    command_executed = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
    
    def send_message(self, message):
        """从前端发送消息到后端"""
        if message.startswith('--') or message == '-s':
            self.command_executed.emit(message)
        else:
            self.message_sent.emit(message)
    
    @pyqtSlot(str)
    def execute_command(self, command):
        """执行命令"""
        self.command_executed.emit(command)


class SolidBackground(QWidget):
    """纯色背景组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAutoFillBackground(False)
        
    def paintEvent(self, event):
        """绘制背景"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 绘制圆角矩形背景
        bg_color = QColor(255, 255, 255, 250)  # 白色，半透明
        painter.setBrush(QBrush(bg_color))
        painter.setPen(QPen(QColor(200, 200, 200, 100), 1))  # 边框
        
        # 圆角矩形
        rect = self.rect()
        painter.drawRoundedRect(rect, 12, 12)
        
        painter.end()


class CustomWebEnginePage(QWebEnginePage):
    """自定义WebEnginePage，监听JavaScript控制台消息"""
    
    console_message_received = pyqtSignal(str, str)  # (level, message)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        """重写控制台消息处理方法"""
        # 检查是否是我们的通信消息
        if message.startswith('SEND_MESSAGE:'):
            user_message = message[13:]  # 移除'SEND_MESSAGE:'前缀
            self.console_message_received.emit('message', user_message)
            
        elif message.startswith('EXECUTE_COMMAND:'):
            command = message[16:]  # 移除'EXECUTE_COMMAND:'前缀
            self.console_message_received.emit('command', command)
        
        # 调用父类方法以保持默认行为
        super().javaScriptConsoleMessage(level, message, lineNumber, sourceID)


class ChatWebView(QWebEngineView):
    """自定义WebView组件用于显示聊天内容"""
    
    message_sent = pyqtSignal(str)
    command_executed = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.chat_messages = []
        self.thinking_bubble_active = False
        
        # 创建通信桥梁
        self.bridge = ChatBridge()
        # Bridge信号连接到ChatWebView信号，提供双重通信机制
        self.bridge.message_sent.connect(self.message_sent.emit)
        self.bridge.command_executed.connect(self.command_executed.emit)
        
        # 创建自定义页面（支持控制台消息监听）
        self.custom_page = CustomWebEnginePage(self)
        self.custom_page.console_message_received.connect(self._handle_console_message)
        self.setPage(self.custom_page)
        
        # 初始化页面
        self._init_page()
        
        # 设置Web Channel用于JavaScript通信
        self.channel = QWebChannel()
        self.channel.registerObject("bridge", self.bridge)
        self.page().setWebChannel(self.channel)
    
    def _handle_console_message(self, msg_type, content):
        """处理从控制台接收到的消息"""
        if msg_type == 'message':
            self.message_sent.emit(content)
        elif msg_type == 'command':
            self.command_executed.emit(content)
    
    def add_message(self, content, is_user=True, is_thinking=False):
        """添加消息到聊天界面"""
        # 等待页面加载完成
        def wait_and_execute():
            # 检查页面是否加载完成
            check_script = """
            try {
                if (typeof window.chatInterface !== 'undefined' && window.chatInterface && window.chatInterface.addMessage) {
                    'ready';
                } else {
                    'not_ready';
                }
            } catch(e) {
                'error';
            }
            """
            
            def on_check_finished(result):
                if result == 'ready':
                    # 页面准备就绪，执行添加消息
                    script = f"""
                    try {{
                        window.chatInterface.addMessage(
                            {json.dumps(content)}, 
                            {str(is_user).lower()}, 
                            {str(is_thinking).lower()}
                        );
                        console.log('消息添加成功');
                        true;
                    }} catch(e) {{
                        console.error('添加消息时发生错误:', e);
                        false;
                    }}
                    """
                    
                    def on_script_finished(result):
                        pass  # JavaScript执行结果记录已移除
                    
                    self.page().runJavaScript(script, on_script_finished)
                else:
                    # 页面未准备就绪，延迟重试
                    QTimer.singleShot(1000, wait_and_execute)
            
            self.page().runJavaScript(check_script, on_check_finished)
        
        # 延迟执行，确保JavaScript已加载
        QTimer.singleShot(200, wait_and_execute)
        
        # 保存到消息列表
        self.chat_messages.append({
            'content': content,
            'is_user': is_user,
            'is_thinking': is_thinking,
            'timestamp': datetime.now().isoformat()
        })
    
    def clear_chat(self):
        """清空聊天记录"""
        def clear_script():
            # 检查页面是否加载完成
            check_script = """
            try {
                if (typeof window.chatInterface !== 'undefined' && window.chatInterface && window.chatInterface.clearChat) {
                    'ready';
                } else {
                    'not_ready';
                }
            } catch(e) {
                'error';
            }
            """
            
            def on_check_finished(result):
                if result == 'ready':
                    script = """
                    try {
                        window.chatInterface.clearChat();
                        console.log('聊天记录清空成功');
                        true;
                    } catch(e) {
                        console.error('清空聊天记录时发生错误:', e);
                        false;
                    }
                    """
                    self.page().runJavaScript(script)
                else:
                    # 页面未准备就绪，延迟重试
                    QTimer.singleShot(1000, clear_script)
            
            self.page().runJavaScript(check_script, on_check_finished)
        
        QTimer.singleShot(200, clear_script)
        self.chat_messages.clear()
    
    def remove_thinking_bubble(self):
        """移除思考气泡"""
        def remove_script():
            check_script = """
            try {
                if (typeof window.chatInterface !== 'undefined' && window.chatInterface && window.chatInterface.removeThinkingBubble) {
                    'ready';
                } else {
                    'not_ready';
                }
            } catch(e) {
                'error';
            }
            """
            
            def on_check_finished(result):
                if result == 'ready':
                    script = """
                    try {
                        window.chatInterface.removeThinkingBubble();
                        console.log('思考气泡移除成功');
                    } catch(e) {
                        console.error('移除思考气泡时发生错误:', e);
                    }
                    """
                    self.page().runJavaScript(script)
                    self.thinking_bubble_active = False
                else:
                    pass  # 页面未准备就绪
            
            self.page().runJavaScript(check_script, on_check_finished)
        
        QTimer.singleShot(100, remove_script)
    
    def set_ai_processing(self, processing=True):
        """设置AI处理状态"""
        def set_processing_script():
            check_script = """
            try {
                if (typeof window.chatInterface !== 'undefined' && window.chatInterface && window.chatInterface.setAIProcessing) {
                    'ready';
                } else {
                    'not_ready';
                }
            } catch(e) {
                'error';
            }
            """
            
            def on_check_finished(result):
                if result == 'ready':
                    script = f"""
                    try {{
                        window.chatInterface.setAIProcessing({str(processing).lower()});
                        console.log('AI处理状态设置成功: {processing}');
                    }} catch(e) {{
                        console.error('设置AI处理状态时发生错误:', e);
                    }}
                    """
                    self.page().runJavaScript(script)
                    
                    # 更新思考气泡状态标记，但不在后端重复添加消息
                    if processing:
                        self.thinking_bubble_active = True
                    else:
                        self.thinking_bubble_active = False
                else:
                    pass  # 页面未准备就绪
            
            self.page().runJavaScript(check_script, on_check_finished)
        
        QTimer.singleShot(100, set_processing_script)
    
    def _init_page(self):
        """初始化聊天页面"""
        # 强制使用本地HTML文件
        html_file_path = os.path.join(os.path.dirname(__file__), "webview", "chat_view.html")
        if os.path.exists(html_file_path):
            self.load(QUrl.fromLocalFile(html_file_path))
            print(f"[info]加载本地HTML文件: {html_file_path}")
            
            # 页面加载完成后注入主题色
            def on_load_finished():
                self._inject_theme_color()
            
            self.loadFinished.connect(on_load_finished)
        else:
            print(f"[error]HTML文件不存在: {html_file_path}")
            raise FileNotFoundError(f"找不到HTML文件: {html_file_path}")
    
    def _inject_theme_color(self):
        """注入动态主题色"""
        try:
            # 读取配置中的主题色
            config = load_config()
            theme_color = config.get("theme_color", "#ff69b4")
            
            # 从十六进制颜色计算rgba值
            def hex_to_rgba(hex_color, alpha):
                hex_color = hex_color.lstrip('#')
                r = int(hex_color[0:2], 16)
                g = int(hex_color[2:4], 16)
                b = int(hex_color[4:6], 16)
                return f"rgba({r}, {g}, {b}, {alpha})"
            
            # 注入CSS变量的JavaScript代码
            inject_script = f"""
            (function() {{
                // 创建或更新CSS样式
                let styleEl = document.getElementById('dynamic-theme');
                if (!styleEl) {{
                    styleEl = document.createElement('style');
                    styleEl.id = 'dynamic-theme';
                    document.head.appendChild(styleEl);
                }}
                
                // 设置CSS变量
                styleEl.textContent = `
                    :root {{
                        --theme-color: {theme_color} !important;
                        --theme-color-shadow-light: {hex_to_rgba(theme_color, 0.1)} !important;
                        --theme-color-shadow-medium: {hex_to_rgba(theme_color, 0.3)} !important;
                        --theme-color-shadow-heavy: {hex_to_rgba(theme_color, 0.4)} !important;
                        --theme-color-background: {hex_to_rgba(theme_color, 0.05)} !important;
                        --theme-color-shadow-super-heavy: {hex_to_rgba(theme_color, 0.7)} !important;
                    }}
                `;
                
                console.log('主题色已更新为: {theme_color}');
            }})();
            """
            
            # 执行注入脚本
            self.page().runJavaScript(inject_script)
            print(f"[info]主题色已注入: {theme_color}")
            
        except Exception as e:
            print(f"[error]注入主题色失败: {e}")
            # 使用默认主题色
            fallback_script = """
            (function() {
                let styleEl = document.getElementById('dynamic-theme');
                if (!styleEl) {
                    styleEl = document.createElement('style');
                    styleEl.id = 'dynamic-theme';
                    document.head.appendChild(styleEl);
                }
                styleEl.textContent = `
                    :root {
                        --theme-color: #ff69b4 !important;
                        --theme-color-shadow-light: rgba(255, 105, 180, 0.1) !important;
                        --theme-color-shadow-medium: rgba(255, 105, 180, 0.3) !important;
                        --theme-color-shadow-heavy: rgba(255, 105, 180, 0.4) !important;
                        --theme-color-background: rgba(255, 105, 180, 0.05) !important;
                        --theme-color-shadow-super-heavy: rgba(255, 105, 180, 0.7) !important;
                    }
                `;
            })();
            """
            self.page().runJavaScript(fallback_script)


class ChatWindow(QWidget):
    """主聊天窗口类 - 使用WebView重写"""
    
    # 信号定义
    message_sent = pyqtSignal(str)      # 用户消息发送信号
    command_executed = pyqtSignal(str)  # 命令执行信号
    window_hidden = pyqtSignal()        # 窗口隐藏信号
    
    def __init__(self, tray_icon=None):
        super().__init__()
        self.initialized = False
        self.tray_icon = tray_icon
        
        # 读取主题色配置
        self.config = load_config()
        self.theme_color = self.config.get("theme_color", "#ff69b4")
        
        # 初始化窗口尺寸变量
        self.window_height = 650
        self.window_width = int(self.window_height * 4 / 3)  # 4:3比例
        
        # 线程管理
        self.ai_thread = None
        self.thinking_bubble = None
        
        self._init_ui()
        self._setup_shortcuts()

    def _init_ui(self):
        """初始化UI"""
        self.setWindowTitle("")  # 移除窗口标题
        self.setFixedSize(self.window_width, self.window_height)
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.SubWindow |
            Qt.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)

        # 设置窗口样式表，添加圆角
        self.setStyleSheet("""
            QWidget#main_window {
                background-color: rgba(245, 247, 250, 0.95);
                border-radius: 12px;
                border: 1px solid rgba(200, 200, 200, 0.3);
            }
        """)
        self.setObjectName("main_window")

        # 背景
        self.background = SolidBackground(self)
        self.background.setGeometry(0, 0, self.window_width, self.window_height)

        # 创建UI组件
        self._create_title_bar()
        self._create_chat_webview()

        # 初始位置（屏幕外）
        desktop = QApplication.primaryScreen().availableGeometry()
        self.move(
            desktop.width() // 2 - self.width() // 2,
            desktop.height()
        )

        self.initialized = True

    def _create_title_bar(self):
        """创建标题栏 - 保持Qt控件"""
        title_bar = QWidget(self)
        title_bar.setFixedHeight(50)
        title_bar.setStyleSheet("background: transparent;")
        title_bar_layout = QHBoxLayout(title_bar)
        title_bar_layout.setContentsMargins(20, 0, 20, 0)

        # 左侧按钮组（设置和关闭按钮）
        left_buttons_layout = QHBoxLayout()
        left_buttons_layout.setSpacing(8)
        
        # 设置按钮
        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setFixedSize(30, 30)
        
        # 从主题色计算悬停颜色
        def hex_to_rgba(hex_color, alpha):
            hex_color = hex_color.lstrip('#')
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            return f"rgba({r}, {g}, {b}, {alpha})"
        
        hover_bg = hex_to_rgba(self.theme_color, 0.1)
        
        self.settings_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border-radius: 15px;
                border: none;
                font-size: 16px;
                color: #888;
            }}
            QPushButton:hover {{
                background: {hover_bg};
                color: {self.theme_color};
            }}
        """)
        self.settings_btn.clicked.connect(self._handle_settings)
        left_buttons_layout.addWidget(self.settings_btn)

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
                background: #ff4d4f;
                color: white;
            }
        """)
        self.close_btn.clicked.connect(self.hide_with_animation)
        left_buttons_layout.addWidget(self.close_btn)
        
        # 创建左侧按钮容器
        left_buttons_widget = QWidget()
        left_buttons_widget.setLayout(left_buttons_layout)
        title_bar_layout.addWidget(left_buttons_widget)
        
        # 添加弹性空间将按钮推到左边
        title_bar_layout.addStretch()

    def _create_chat_webview(self):
        """创建WebView聊天区域"""
        # 计算WebView区域
        webview_y = 50  # 标题栏高度
        webview_height = self.window_height - webview_y
        webview_width = self.window_width
        
        # 创建WebView
        self.chat_webview = ChatWebView(self)
        self.chat_webview.setGeometry(0, webview_y, webview_width, webview_height)
        
        # 连接信号 - 使用ChatWebView的信号（ChatWebView已经连接了Bridge和控制台消息）
        self.chat_webview.message_sent.connect(self.message_sent.emit)
        self.chat_webview.command_executed.connect(self.command_executed.emit)

    def _handle_settings(self):
        """处理设置按钮点击"""
        self.command_executed.emit('-s')

    def _setup_shortcuts(self):
        """设置快捷键"""
        # Ctrl+Plus 增加高度
        increase_shortcut = QShortcut(QKeySequence("Ctrl+="), self)
        increase_shortcut.activated.connect(lambda: self.increase_height(50))
        
        # Ctrl+Minus 减少高度
        decrease_shortcut = QShortcut(QKeySequence("Ctrl+-"), self)
        decrease_shortcut.activated.connect(lambda: self.decrease_height(50))
        
        # Ctrl+0 重置为默认高度
        reset_shortcut = QShortcut(QKeySequence("Ctrl+0"), self)
        reset_shortcut.activated.connect(self.reset_to_default_height)
        
        # Ctrl+1 紧凑模式
        compact_shortcut = QShortcut(QKeySequence("Ctrl+1"), self)
        compact_shortcut.activated.connect(self.set_compact_height)
        
        # Ctrl+2 扩展模式
        expand_shortcut = QShortcut(QKeySequence("Ctrl+2"), self)
        expand_shortcut.activated.connect(self.set_expanded_height)
        
        print("[info]窗口高度调整快捷键已设置:")
        print("  Ctrl+= : 增加高度")
        print("  Ctrl+- : 减少高度")
        print("  Ctrl+0 : 重置为默认高度")
        print("  Ctrl+1 : 紧凑模式")
        print("  Ctrl+2 : 扩展模式")

    def eventFilter(self, obj, event):
        """事件过滤器，处理滚轮事件"""
        # WebView会自己处理大部分事件，这里主要保留兼容性
        return False

    def add_message(self, text, is_user=True):
        """添加消息到聊天界面"""
        self.chat_webview.add_message(text, is_user, is_thinking=False)

    def add_user_message(self, text):
        """添加用户消息"""
        self.add_message(text, is_user=True)

    def add_ai_message(self, text):
        """添加AI消息"""
        self.add_message(text, is_user=False)

    def add_thinking_bubble(self):
        """添加' 正在思考'的消息"""
        self.chat_webview.set_ai_processing(True)
        return self  # 返回self作为thinking_bubble引用

    def remove_thinking_bubble(self):
        """移除思考气泡"""
        self.chat_webview.set_ai_processing(False)

    def load_history(self, messages):
        """加载并显示历史记录"""
        if not messages:
            return
        
        # 清空现有消息
        self.clear_chat()
        
        # 改进的消息加载逻辑，确保页面准备就绪
        def check_and_load_messages():
            
            # 检查页面是否加载完成的脚本
            check_script = """
            try {
                if (typeof window.chatInterface !== 'undefined' && 
                    window.chatInterface && 
                    window.chatInterface.addMessage &&
                    window.chatInterface.clearChat &&
                    document.getElementById('chat-container') &&
                    document.getElementById('message-input')) {
                    'ready';
                } else {
                    'not_ready';
                }
            } catch(e) {
                'error: ' + e.toString();
            }
            """
            
            def on_check_result(result):
                if result == 'ready':
                    load_messages_batch()
                else:
                    QTimer.singleShot(1000, check_and_load_messages)
            
            self.chat_webview.page().runJavaScript(check_script, on_check_result)
        
        def load_messages_batch():
            """批量加载历史消息"""
            try:
                # 构建所有消息的JavaScript代码
                js_commands = []
                for i, msg in enumerate(messages):
                    role = msg.get('role', msg.get('sender', 'user'))
                    content = msg.get('content', '').strip()
                    is_user = (role == 'user')
                    
                    if content:  # 只加载非空消息
                        # 转义JavaScript字符串
                        escaped_content = content.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r')
                        js_command = f'window.chatInterface.addMessage("{escaped_content}", {str(is_user).lower()}, false);'
                        js_commands.append(js_command)
                
                # 一次性执行所有加载命令
                if js_commands:
                    full_script = f"""
                    try {{
                        console.log('🏁 [HISTORY_LOAD] 开始批量加载{len(js_commands)}条历史消息');
                        {'; '.join(js_commands)}
                        console.log('✅ [HISTORY_COMPLETE] 历史消息批量加载完成');
                        'success';
                    }} catch(e) {{
                        console.error('❌ [HISTORY_ERROR] 历史消息加载失败:', e);
                        'error: ' + e.toString();
                    }}
                    """
                    
                    def on_load_result(result):
                        if result != 'success':
                            print(f"[error]❌ 历史消息加载失败: {result}")
                    
                    self.chat_webview.page().runJavaScript(full_script, on_load_result)
                else:
                    pass  # 没有有效的历史消息需要加载
                    
            except Exception as e:
                print(f"[error]❌ 加载历史消息时发生错误: {e}")
                import traceback
                print(f"[error]🔍 错误堆栈: {traceback.format_exc()}")
        
        # 延迟开始检查，给页面更多时间初始化
        QTimer.singleShot(1000, check_and_load_messages)

    def clear_chat(self):
        """清空聊天记录"""
        self.chat_webview.clear_chat()

    def set_ai_processing(self, processing=True):
        """设置AI处理状态"""
        self.chat_webview.set_ai_processing(processing)

    def show_animation(self):
        """显示窗口动画"""
        if not self.isVisible():
            self.show()

        desktop = QApplication.primaryScreen().availableGeometry()
        center_pos = QPoint(
            desktop.width() // 2 - self.width() // 2,
            desktop.height() // 2 - self.height() // 2
        )

        if self.pos().y() < desktop.height():
            self.move(center_pos)
            return

        start_pos = self.pos()
        self.anim = QPropertyAnimation(self, b"pos")
        self.anim.setDuration(500)
        self.anim.setStartValue(start_pos)
        self.anim.setEndValue(center_pos)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        self.anim.start()

        self.activateWindow()
        self.raise_()

    def hide_with_animation(self):
        """隐藏窗口动画"""
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
        self.anim.finished.connect(self.window_hidden.emit)
        self.anim.start()

    def mousePressEvent(self, event):
        """鼠标按下事件 - 支持窗口拖动"""
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        """鼠标移动事件 - 支持窗口拖动"""
        if event.buttons() == Qt.LeftButton and hasattr(self, 'drag_position'):
            self.move(event.globalPos() - self.drag_position)
            event.accept()

    def contextMenuEvent(self, event):
        """右键菜单"""
        context_menu = QMenu(self)
        
        clear_action = context_menu.addAction("清空聊天记录")
        clear_action.triggered.connect(self.clear_chat)
        
        hide_action = context_menu.addAction("隐藏窗口")
        hide_action.triggered.connect(self.hide_with_animation)
        
        context_menu.exec_(event.globalPos())

    # 窗口高度调整相关方法
    def set_window_height(self, height):
        """设置聊天窗口高度"""
        height = max(500, min(height, 1000))
        
        if height != self.window_height:
            self.window_height = height
            self.window_width = int(height * 4 / 3)
            self._relayout_ui()
    
    def _relayout_ui(self):
        """重新布局界面元素"""
        self.setFixedSize(self.window_width, self.window_height)
        self.background.setGeometry(0, 0, self.window_width, self.window_height)
        
        # 重新调整WebView大小
        webview_y = 50
        webview_height = self.window_height - webview_y
        webview_width = self.window_width
        self.chat_webview.setGeometry(0, webview_y, webview_width, webview_height)
        
        self.center_window()
        print(f"[info]窗口高度调整为: {self.window_height}px")

    def get_current_height(self):
        """获取当前窗口高度"""
        return self.window_height

    def increase_height(self, increment=100):
        """增加窗口高度"""
        self.set_window_height(self.window_height + increment)

    def decrease_height(self, decrement=100):
        """减少窗口高度"""
        self.set_window_height(self.window_height - decrement)

    def reset_to_default_height(self):
        """重置为默认高度"""
        self.set_window_height(650)

    def set_compact_height(self):
        """设置紧凑高度"""
        self.set_window_height(500)

    def set_expanded_height(self):
        """设置扩展高度"""
        self.set_window_height(900)

    def center_window(self):
        """将窗口移动到屏幕中央"""
        desktop = QApplication.primaryScreen().availableGeometry()
        center_pos = QPoint(
            desktop.width() // 2 - self.width() // 2,
            desktop.height() // 2 - self.height() // 2
        )
        self.move(center_pos)

    def showEvent(self, event):
        """窗口显示时设置圆角掩码"""
        super().showEvent(event)
        # 创建圆角区域
        from PyQt5.QtGui import QRegion, QPainterPath
        from PyQt5.QtCore import QRectF
        
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 12, 12)
        region = QRegion(path.toFillPolygon().toPolygon())
        self.setMask(region)

    def resizeEvent(self, event):
        """窗口大小改变时更新圆角掩码"""
        super().resizeEvent(event)
        if self.isVisible():
            from PyQt5.QtGui import QRegion, QPainterPath
            from PyQt5.QtCore import QRectF
            
            path = QPainterPath()
            path.addRoundedRect(QRectF(self.rect()), 12, 12)
            region = QRegion(path.toFillPolygon().toPolygon())
            self.setMask(region)


def setup_system_tray(app):
    """设置系统托盘图标"""
    tray_icon = QSystemTrayIcon(app)

    # 创建系统托盘菜单
    tray_menu = QMenu()

    show_action = tray_menu.addAction("打开聊天窗口")
    show_action.triggered.connect(lambda: app.toggle_chat_window())

    tray_menu.addSeparator()

    exit_action = tray_menu.addAction("退出")
    exit_action.triggered.connect(lambda: app.quit())

    # 设置系统托盘
    tray_icon.setContextMenu(tray_menu)

    # 双击托盘打开窗口
    tray_icon.activated.connect(lambda reason:
                               app.toggle_chat_window() if reason == QSystemTrayIcon.DoubleClick else None
                               )

    tray_icon.show()
    return tray_icon


def setup_webengine_global_config():
    """设置WebEngine全局配置"""
    try:
        from PyQt5.QtWebEngineWidgets import QWebEngineProfile
        from PyQt5.QtCore import QStandardPaths
        
        # 设置默认Profile
        profile = QWebEngineProfile.defaultProfile()
        
        # 设置用户代理
        profile.setHttpUserAgent("liveAgent/1.0 QtWebEngine")
        
        # 设置缓存和数据存储路径
        cache_dir = QStandardPaths.writableLocation(QStandardPaths.CacheLocation)
        data_dir = QStandardPaths.writableLocation(QStandardPaths.DataLocation)
        
        if cache_dir:
            profile.setCachePath(cache_dir + "/WebEngine")
            print(f"[info]WebEngine缓存路径: {cache_dir}/WebEngine")
        
        if data_dir:
            profile.setPersistentStoragePath(data_dir + "/WebEngine")
            print(f"[info]WebEngine数据路径: {data_dir}/WebEngine")
            
        # 设置缓存策略
        profile.setHttpCacheType(QWebEngineProfile.DiskHttpCache)
        profile.setHttpCacheMaximumSize(50 * 1024 * 1024)  # 50MB缓存
        
    except Exception as e:
        print(f"[warning]WebEngine全局配置失败: {e}")
