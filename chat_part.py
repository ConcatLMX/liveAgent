import sys
import os
import json
import time
from datetime import datetime, timedelta
import threading
import keyboard
import markdown
from markdown.extensions import codehilite, fenced_code, tables, toc
from PyQt5.QtCore import Qt, QPropertyAnimation, QPoint, QEasingCurve, QTimer, QObject, pyqtSignal, QThread, QEvent, QUrl, QStandardPaths
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QTextEdit,
                             QLineEdit, QPushButton, QFrame, QScrollArea,
                             QSizePolicy, QHBoxLayout, QLabel, QSystemTrayIcon, QMenu, QShortcut)
from PyQt5.QtGui import QFont, QIcon, QColor, QPainter, QBrush, QLinearGradient, QPalette, QKeyEvent, QKeySequence
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineProfile
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


class MessageWidget(QWidget):
    """简洁的消息显示组件 - 无气泡设计"""
    def __init__(self, text, is_user=True, parent=None):
        super().__init__(parent)
        self.is_user = is_user
        self.setStyleSheet("background: transparent;")
        
        # 创建主布局
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 8, 0, 8)
        main_layout.setSpacing(5)
        
        # 添加发送者标识
        sender_label = QLabel("您" if is_user else "AI助手")
        sender_label.setStyleSheet(f"""
            color: {'#0A84FF' if is_user else '#666666'};
            font-weight: 600;
            font-size: 12px;
            margin-bottom: 4px;
        """)
        sender_label.setFont(QFont("Microsoft YaHei UI", 10, QFont.Bold))
        main_layout.addWidget(sender_label)
        
        # 创建内容区域 - 统一使用QWebEngineView，但样式简洁
        self.content_widget = QWebEngineView()
        
        # 简化的WebEngine配置
        try:
            # 禁用JavaScript错误输出到控制台
            self.content_widget.page().javaScriptConsoleMessage = lambda level, message, line, source: None
            
            # 让WebEngineView不拦截滚轮事件，传递给父级
            self.content_widget.setAttribute(Qt.WA_TransparentForMouseEvents, False)
            
        except Exception as e:
            print(f"[warning]WebEngine配置失败: {e}")
        
        self.content_widget.setFixedHeight(120)  # 增加初始高度到120px
        
        # 设置消息样式 - 简洁版本
        if is_user:
            # 用户消息：淡蓝色背景，左侧蓝色边框
            bg_color = "#f8f9fa"  # 淡灰色背景
            border_color = "#0A84FF"  # 蓝色边框
        else:
            # AI消息：淡灰色背景，左侧绿色边框
            bg_color = "#f8f9fa"  # 淡灰色背景
            border_color = "#28a745"  # 绿色边框
        
        # 渲染Markdown - 使用简洁样式
        html_content = self._render_simple_markdown(text, bg_color, border_color)
        self.content_widget.setHtml(html_content)
        
        # 设置大小策略
        self.content_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        # 确保WebEngineView不会阻挡父级的滚轮事件
        self.content_widget.setAttribute(Qt.WA_AcceptTouchEvents, False)
        
        # 尝试禁用WebEngineView的内部滚动
        try:
            settings = self.content_widget.settings()
            settings.setAttribute(settings.ScrollAnimatorEnabled, False)
        except:
            pass
        
        # 页面加载完成后调整高度
        self.content_widget.loadFinished.connect(self._on_page_loaded)
        
        # 设置字体
        font = QFont("Microsoft YaHei UI", 11)
        self.content_widget.setFont(font)
        
        main_layout.addWidget(self.content_widget)
        self.setLayout(main_layout)
    
    def wheelEvent(self, event):
        """滚轮事件处理 - 传递给父级滚动区域"""
        # 不处理滚轮事件，让它传递给父级的事件过滤器
        event.ignore()
        # 不调用 super().wheelEvent(event)，而是让事件冒泡到父级
        
    def _on_page_loaded(self, success):
        """页面加载完成的回调 - 激进LaTeX渲染优化版本"""
        if success:
            # 立即进行第一次高度调整
            QTimer.singleShot(50, self._adjust_web_height)
            # 为MathJax预留更多时间 - 大幅增加调整次数和延长时间
            QTimer.singleShot(150, self._adjust_web_height)
            QTimer.singleShot(300, self._adjust_web_height)
            QTimer.singleShot(600, self._adjust_web_height)
            QTimer.singleShot(1000, self._adjust_web_height)  
            QTimer.singleShot(1500, self._adjust_web_height)  
            QTimer.singleShot(2000, self._adjust_web_height)  # 延长到2秒
            QTimer.singleShot(2500, self._adjust_web_height)  # 最终确保
    
    def _render_simple_markdown(self, text, bg_color, border_color):
        """简洁版本的Markdown渲染，保持原来的样式风格"""
        try:
            # 配置Markdown扩展
            md = markdown.Markdown(
                extensions=[
                    'fenced_code',
                    'tables',
                    'toc',
                    'codehilite'
                ],
                extension_configs={
                    'codehilite': {
                        'css_class': 'highlight',
                        'use_pygments': False
                    }
                }
            )
            
            # 转换为HTML
            html = md.convert(text)
            
            # 创建简洁的HTML页面
            simple_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    
    <!-- 简化的MathJax配置 -->
    <script>
        window.MathJax = {{
            tex: {{
                inlineMath: [['$', '$'], ['\\(', '\\)'], ['[', ']']],
                displayMath: [['$$', '$$'], ['\\[', '\\]']],
                processEscapes: true,
                processEnvironments: true,
                packages: {{'[+]': ['base', 'ams', 'newcommand', 'mathtools']}}
            }},
            options: {{
                skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre'],
                processHtmlClass: 'math-content'
            }},
            startup: {{
                ready() {{
                    MathJax.startup.defaultReady();
                    // 渲染完成后多次通知父级调整高度
                    MathJax.startup.promise.then(() => {{
                        // 多次延迟确保渲染完成
                        setTimeout(() => {{
                            document.dispatchEvent(new Event('mathjax-ready'));
                        }}, 50);
                        setTimeout(() => {{
                            document.dispatchEvent(new Event('mathjax-ready'));
                        }}, 200);
                        setTimeout(() => {{
                            document.dispatchEvent(new Event('mathjax-ready'));
                        }}, 500);
                    }}).catch(() => {{
                        // 即使失败也要触发事件
                        document.dispatchEvent(new Event('mathjax-ready'));
                    }});
                    
                    // 监听MathJax文档状态变化
                    if (MathJax.startup.document) {{
                        MathJax.startup.document.state().addAction('mathjax-rendered', () => {{
                            setTimeout(() => {{
                                document.dispatchEvent(new Event('mathjax-ready'));
                            }}, 100);
                        }});
                    }}
                }}
            }}
        }};
    </script>
    <script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js" async></script>
    
    <style>
        body {{
            font-family: 'Microsoft YaHei UI', sans-serif;
            font-size: 14px;
            line-height: 1.5;
            color: #333;
            margin: 0;
            padding: 10px 12px;
            background: {bg_color};
            border-left: 3px solid {border_color};
            border-radius: 6px;
            word-wrap: break-word;
            overflow: hidden;
        }}
        
        /* 数学公式样式优化 */
        mjx-container {{
            margin: 0.2em 0;
            display: inline-block;
            line-height: 1;
        }}
        
        mjx-container[display="true"] {{
            text-align: center;
            margin: 0.5em 0;
            display: block;
        }}
        
        /* 确保行内数学公式与文本对齐 */
        mjx-container[jax="CHTML"][display="false"] {{
            vertical-align: baseline;
            margin: 0 0.1em;
        }}
        
        p {{
            margin: 0.3em 0;
            line-height: 1.5;
        }}
        
        p:first-child {{ margin-top: 0; }}
        p:last-child {{ margin-bottom: 0; }}
        
        /* 简洁的代码样式 */
        code {{
            background: rgba(0,0,0,0.06);
            padding: 1px 4px;
            border-radius: 3px;
            font-family: 'Consolas', monospace;
            font-size: 13px;
        }}
        
        pre {{
            background: #f6f8fa;
            border: 1px solid #e1e4e8;
            border-radius: 4px;
            padding: 8px;
            margin: 6px 0;
            overflow-x: auto;
            font-family: 'Consolas', monospace;
            font-size: 12px;
        }}
        
        pre code {{
            background: none;
            padding: 0;
            border-radius: 0;
        }}
        
        /* 简洁的表格样式 */
        table {{
            border-collapse: collapse;
            margin: 6px 0;
            width: 100%;
            font-size: 13px;
        }}
        
        th, td {{
            border: 1px solid #ddd;
            padding: 4px 8px;
            text-align: left;
        }}
        
        th {{
            background: #f5f5f5;
            font-weight: 600;
        }}
        
        /* 简洁的标题样式 */
        h1, h2, h3, h4, h5, h6 {{
            margin: 0.8em 0 0.4em 0;
            font-weight: 600;
            line-height: 1.3;
        }}
        
        h1:first-child, h2:first-child, h3:first-child,
        h4:first-child, h5:first-child, h6:first-child {{
            margin-top: 0;
        }}
        
        h1 {{ font-size: 1.3em; }}
        h2 {{ font-size: 1.2em; }}
        h3 {{ font-size: 1.1em; }}
        
        /* 简洁的列表样式 */
        ul, ol {{
            margin: 0.3em 0;
            padding-left: 1.5em;
        }}
        
        li {{
            margin: 0.2em 0;
        }}
        
        /* 简洁的引用样式 */
        blockquote {{
            border-left: 3px solid #ddd;
            padding-left: 10px;
            margin: 6px 0;
            color: #666;
            font-style: italic;
        }}
        
        /* 链接样式 */
        a {{
            color: #0366d6;
            text-decoration: none;
        }}
        
        a:hover {{
            text-decoration: underline;
        }}
        
        /* 强调样式 */
        strong {{ font-weight: 600; }}
        em {{ font-style: italic; }}
    </style>
</head>
<body>
{html}

<script>
    // 获取内容高度的函数 - 激进LaTeX渲染支持
    function getContentHeight() {{
        try {{
            var body = document.body;
            var html = document.documentElement;
            
            // 等待MathJax渲染完成
            if (window.MathJax && window.MathJax.startup && !window.MathJax.startup.document.state().mathJaxReady) {{
                // MathJax还在渲染，返回更大的缓冲高度
                return Math.max(body.scrollHeight, body.offsetHeight, 150);
            }}
            
            // 特别检查MathJax元素的高度
            var mathElements = document.querySelectorAll('mjx-container, .MathJax, .mjx-math');
            var mathHeight = 0;
            for (var i = 0; i < mathElements.length; i++) {{
                var mathRect = mathElements[i].getBoundingClientRect();
                mathHeight += mathRect.height;
            }}
            
            // 获取所有可能影响高度的元素
            var allElements = document.querySelectorAll('*');
            var maxBottom = 0;
            var totalContentHeight = 0;
            
            for (var i = 0; i < allElements.length; i++) {{
                var elem = allElements[i];
                var rect = elem.getBoundingClientRect();
                var bottom = rect.bottom;
                if (bottom > maxBottom) {{
                    maxBottom = bottom;
                }}
                // 累加所有可见元素的高度
                if (rect.height > 0 && elem.offsetParent !== null) {{
                    totalContentHeight += rect.height;
                }}
            }}
            
            // 计算实际内容高度，给LaTeX公式额外空间
            var height = Math.max(
                body.scrollHeight,
                body.offsetHeight,
                body.clientHeight,
                html.scrollHeight,
                html.offsetHeight,
                html.clientHeight,
                maxBottom,
                totalContentHeight,
                mathHeight * 1.5  // 为数学公式预留50%额外空间
            );
            
            // 为LaTeX公式提供更大的最小高度保障
            return Math.max(height, 80);
        }} catch (e) {{
            console.warn('Height calculation failed:', e);
            return Math.max(document.body.scrollHeight, 120);
        }}
    }}
    
    // 页面加载完成后立即计算高度
    window.addEventListener('load', function() {{
        setTimeout(getContentHeight, 50);
    }});
    
    // MathJax渲染完成后再次计算 - 激进调整策略
    document.addEventListener('mathjax-ready', function() {{
        setTimeout(getContentHeight, 50);
        setTimeout(getContentHeight, 150);  
        setTimeout(getContentHeight, 300);  
        setTimeout(getContentHeight, 500);  
        setTimeout(getContentHeight, 800);  // 增加更多调整
        setTimeout(getContentHeight, 1200); // 延长调整时间
    }});
    
    // 兼容旧的adjustHeight函数调用
    function adjustHeight() {{
        return getContentHeight();
    }}
</script>
</body>
</html>"""
            
            return simple_html
            
        except Exception as e:
            print(f"[warning]简洁Markdown渲染失败: {e}")
            # 降级为纯文本
            return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: 'Microsoft YaHei UI', sans-serif;
            font-size: 14px;
            line-height: 1.5;
            color: #333;
            margin: 0;
            padding: 10px 12px;
            background: {bg_color};
            border-left: 3px solid {border_color};
            border-radius: 6px;
            word-wrap: break-word;
        }}
    </style>
</head>
<body><p>{text.replace('<', '&lt;').replace('>', '&gt;')}</p></body>
</html>"""



    def _adjust_web_height(self):
        """调整QWebEngineView的高度 - 优化版本"""
        if not hasattr(self, 'content_widget') or not self.content_widget:
            return
            
        # 避免重复调整，设置调整标志
        if hasattr(self, '_adjusting_height') and self._adjusting_height:
            return
            
        self._adjusting_height = True
        self._do_height_adjustment()
    
    def _do_height_adjustment(self):
        """执行实际的高度调整 - 优化版本"""
        try:
            # 修复的JavaScript代码，直接获取准确高度
            js_code = """
            (function() {
                try {
                    // 直接计算当前内容高度
                    var body = document.body;
                    var html = document.documentElement;
                    
                    // 获取实际内容高度
                    var height = Math.max(
                        body.scrollHeight,
                        body.offsetHeight,
                        body.clientHeight
                    );
                    
                    // 确保最小高度
                    return Math.max(height, 60);
                    
                } catch (e) {
                    console.error('Height calculation failed:', e);
                    return 80;
                }
            })();
            """
            
            self.content_widget.page().runJavaScript(js_code, self._set_web_height)
            
        except Exception as e:
            # 出错时设置默认高度并清除调整标志
            self._set_web_height(100)
    
    def _set_web_height(self, height):
        """设置Web组件高度 - 激进LaTeX优化版本"""
        try:
            # 简化高度处理逻辑
            if not isinstance(height, (int, float)):
                height = 80
            
            if height <= 0:
                height = 80
            
            # 为LaTeX公式预留更多空间，提高上限和边距
            final_height = max(80, min(int(height) + 40, 1000))  # 边距提升到40px，上限提升到1000px
            
            # 设置高度
            if hasattr(self, 'content_widget') and self.content_widget:
                current_height = self.content_widget.height()
                # 更敏感的高度更新策略，任何变化都更新
                if abs(final_height - current_height) > 1:  # 降低阈值到1px
                    self.content_widget.setFixedHeight(final_height)
                    self.updateGeometry()
                    
        except Exception as e:
            # 出错时设置更高的默认高度
            if hasattr(self, 'content_widget') and self.content_widget:
                self.content_widget.setFixedHeight(150)  # 提高默认高度
                self.updateGeometry()
        finally:
            # 清除调整标志
            if hasattr(self, '_adjusting_height'):
                self._adjusting_height = False


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
        
        # 初始化窗口尺寸变量
        self.window_height = 650
        self.window_width = int(self.window_height * 4 / 3)  # 4:3比例
        
        self.initUI()


    def initUI(self):
        self.setWindowTitle("live · Agent")
        # 使用实例变量设置窗口尺寸为4:3比例
        self.setFixedSize(self.window_width, self.window_height)
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.SubWindow |
            Qt.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)

        # 背景使用纯色
        self.background = SolidBackground(self)
        self.background.setGeometry(0, 0, self.window_width, self.window_height)

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
        scroll_area_width = self.window_width - 20  # 左右各留10px边距
        chat_area_height = self.window_height - 60 - 60  # 减去标题栏和输入区域，动态计算
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setGeometry(10, 60, scroll_area_width, chat_area_height)
        self.scroll_area.setWidgetResizable(True)
        
        # 确保滚轮事件正常工作
        self.scroll_area.setFocusPolicy(Qt.ClickFocus)  # 改为ClickFocus，确保可以接收滚轮事件
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # 安装事件过滤器确保滚轮事件传递
        self.scroll_area.installEventFilter(self)
        
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
        
        # 确保滚动内容不会拦截滚轮事件
        self.scroll_content.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        
        # 为滚动内容安装事件过滤器
        self.scroll_content.installEventFilter(self)

        self.chat_layout = QVBoxLayout(self.scroll_content)
        self.chat_layout.setContentsMargins(20, 15, 20, 15)  # 增加左右边距
        self.chat_layout.setSpacing(15)
        self.chat_layout.addStretch(1)  # 确保内容在顶部

        self.scroll_area.setWidget(self.scroll_content)

        # 输入区域 - 动态计算位置
        input_area_width = self.window_width - 20  # 左右各留10px边距
        input_area_y = self.window_height - 60  # 距离底部60px
        self.input_container = QWidget(self)
        self.input_container.setGeometry(10, input_area_y, input_area_width, 50)
        self.input_container.setStyleSheet("""
            background: rgb(246, 246, 246);
            border-radius: 18px;
            border: none;
        """)

        input_layout = QHBoxLayout(self.input_container)
        input_layout.setContentsMargins(15, 5, 15, 5)

        self.input_field = QTextEdit()
        self.input_field.setPlaceholderText("说点什么... (Shift+Enter换行，Enter发送)")
        self.input_field.setStyleSheet("""
            QTextEdit {
                background: rgba(255, 255, 255, 0.8);
                border: none;
                font-size: 15px;
                color: #333;
                padding: 8px 10px;
            }
        """)
        self.input_field.setFont(QFont("Microsoft YaHei UI", 12))
        self.input_field.setMaximumHeight(100)  # 限制最大高度
        self.input_field.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

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
        
        # 安装输入框事件过滤器
        self.input_field.installEventFilter(self)
        
        # 安装滚动区域事件过滤器处理滚轮事件
        self.scroll_area.installEventFilter(self)

        # 添加快捷键用于调整窗口高度
        self.setup_height_shortcuts()

    def setup_height_shortcuts(self):
        """设置调整窗口高度的快捷键"""
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
        """事件过滤器，处理输入框的键盘事件和滚动区域的滚轮事件"""
        # 处理输入框键盘事件
        if hasattr(self, 'input_field') and obj == self.input_field and event.type() == QEvent.KeyPress:
            # Enter键发送消息（但Shift+Enter换行）
            if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
                if event.modifiers() == Qt.ShiftModifier:
                    # Shift+Enter: 换行
                    return False  # 让默认处理继续
                else:
                    # Enter: 发送消息
                    self.handle_send()
                    return True  # 阻止默认处理
        
        # 处理滚轮事件 - 无论是滚动区域还是其子控件
        elif event.type() == QEvent.Wheel:
            # 获取滚动条
            scrollbar = self.scroll_area.verticalScrollBar() if hasattr(self, 'scroll_area') else None
            if scrollbar:
                # 检查滚动条是否可见且可用
                if scrollbar.isVisible() and scrollbar.maximum() > 0:
                    # 计算滚动步长
                    delta = event.angleDelta().y()
                    step = delta // 120  # 标准滚轮步长
                    scroll_amount = step * 60  # 每步滚动60像素，提升滚动速度
                    
                    # 应用滚动
                    new_value = scrollbar.value() - scroll_amount
                    new_value = max(0, min(new_value, scrollbar.maximum()))
                    scrollbar.setValue(new_value)
                    
                    return True  # 事件已处理
        
        return False  # 让其他事件正常处理

    def settings_closed(self):
        """当设置窗口关闭时调用"""
        self.settings_window = None

    def on_input_changed(self):
        """输入框文本改变时的处理"""
        # 只有在不在AI生成过程中才允许启用发送按钮
        if not hasattr(self, 'ai_thread') or self.ai_thread is None:
            self.send_btn.setEnabled(bool(self.input_field.toPlainText().strip()))

    def add_message(self, text, is_user=True):
        """添加消息 - 使用简洁的直接显示"""
        # 直接使用MessageWidget，不需要气泡包装
        message_widget = MessageWidget(text, is_user)
        
        # 为消息组件安装事件过滤器，确保滚轮事件能被捕获
        message_widget.installEventFilter(self)
        if hasattr(message_widget, 'content_widget'):
            message_widget.content_widget.installEventFilter(self)
        
        # 添加到主布局
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, message_widget)
        
        # 延迟滚动到底部，为LaTeX渲染预留更多时间
        QTimer.singleShot(1500, self.scroll_to_bottom)  # 延长到1.5秒
        QTimer.singleShot(2500, self.scroll_to_bottom)  # 添加第二次滚动确保


    def scroll_to_bottom(self):
        """滚动到底部 - 改进版本"""
        try:
            scrollbar = self.scroll_area.verticalScrollBar()
            # 强制刷新滚动区域
            self.scroll_area.ensureWidgetVisible(self.scroll_content)
            # 设置到最大值
            scrollbar.setValue(scrollbar.maximum())
            # 再次确保滚动到底部
            QTimer.singleShot(50, lambda: scrollbar.setValue(scrollbar.maximum()))
        except Exception as e:
            print(f"[warning]滚动到底部失败: {e}")


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
        msg = self.input_field.toPlainText().strip()
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
        """添加'正在思考'的消息 - 简洁样式"""
        thinking_text = "🤔 正在思考中..."
        
        # 创建思考消息组件
        thinking_widget = MessageWidget(thinking_text, is_user=False)
        thinking_widget.setObjectName("thinking_widget")  # 设置特殊标识
        
        # 为思考消息组件安装事件过滤器
        thinking_widget.installEventFilter(self)
        if hasattr(thinking_widget, 'content_widget'):
            thinking_widget.content_widget.installEventFilter(self)
        
        # 不需要额外的样式设置，保持简洁
        
        # 添加到主布局
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, thinking_widget)
        
        # 滚动到底部
        QTimer.singleShot(200, self.scroll_to_bottom)  # 思考气泡不需要等太久
        
        return thinking_widget

    def on_ai_response_ready(self, response):
        """AI回复准备完成"""
        # 移除"正在思考"的气泡
        if hasattr(self, 'thinking_bubble') and self.thinking_bubble:
            self.thinking_bubble.deleteLater()
            
        # 添加AI回复
        self.add_message(response, is_user=False)        # L2D发送消息
        if CONFIG.get("live2d_listen", False):
            try:
                l2d_instance = L2DVEX(CONFIG.get("live2d_uri", "ws://"))
                l2d_instance.send_text_message(response)
            except Exception as e:
                print(f"[error]发送消息到Live2D失败: {e}")
        
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

    def set_window_height(self, height):
        """设置聊天窗口高度"""
        # 限制高度范围：最小500px，最大1000px
        height = max(500, min(height, 1000))
        
        if height != self.window_height:
            self.window_height = height
            self.window_width = int(height * 4 / 3)  # 保持4:3比例
            
            # 重新布局界面
            self._relayout_ui()
    
    def _relayout_ui(self):
        """重新布局界面元素"""
        # 调整窗口大小
        self.setFixedSize(self.window_width, self.window_height)
        
        # 调整背景大小
        self.background.setGeometry(0, 0, self.window_width, self.window_height)
        
        # 重新计算滚动区域大小
        scroll_area_width = self.window_width - 20
        chat_area_height = self.window_height - 60 - 60  # 减去标题栏和输入区域
        self.scroll_area.setGeometry(10, 60, scroll_area_width, chat_area_height)
        
        # 重新计算输入区域位置
        input_area_width = self.window_width - 20
        input_area_y = self.window_height - 60
        self.input_container.setGeometry(10, input_area_y, input_area_width, 50)
        
        # 确保窗口位置居中
        self.center_window()
        
        print(f"[info]窗口高度调整为: {self.window_height}px, 聊天区域高度: {chat_area_height}px")

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
        self.set_window_height(650)  # 原来的默认高度

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

    def contextMenuEvent(self, event):
        """右键菜单"""
        context_menu = QMenu(self)
        
        # 清空聊天记录
        clear_action = context_menu.addAction("清空聊天记录")
        clear_action.triggered.connect(self.clear_chat)
        
        # 隐藏窗口
        hide_action = context_menu.addAction("隐藏窗口")
        hide_action.triggered.connect(self.hideWithAnimation)
        
        context_menu.exec_(event.globalPos())

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
    print("[info]初始化中...")  

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # 设置应用名称
    app.setApplicationName("liveAgent")  # 移除特殊字符，避免路径问题
    app.setApplicationVersion("1.0")
    app.setOrganizationName("liveAgent")

    # 设置WebEngine全局配置，避免缓存权限问题
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

    #l2d连接
    if CONFIG.get("live2d_listen", False):
        l2d = L2DVEX(CONFIG.get("live2d_uri", "ws://"))    #监听邮箱
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