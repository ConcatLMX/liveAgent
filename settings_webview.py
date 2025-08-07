"""
Weffrom PyQt5.QtCore import (Qt, QPoint, QSize, QPropertyAnimation, QEasingCurve, 
                         QTimer, QObject, pyqtSignal, QUrl, pyqtSlot)
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                           QLabel, QPushButton, QFrame, QSizePolicy, QDialog)
from PyQt5.QtGui import QFont, QPainter, QColor, QBrush, QPen, QIcon
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineProfile, QWebEnginePage
from PyQt5.QtWebChannel import QWebChannelt5.QtCore import (Qt, QPoint, QSize, QPropertyAnimation, QEasingCurve, 
                         QTimer, QObject, pyqtSignal, QUrl, pyqtSlot, QJsonValue)iew版本的设置窗口
使用QtWebEngineView重写原有的设置界面，保持与聊天窗口一致的风格
"""

import os
import json
from PyQt5.QtCore import (Qt, QPoint, QSize, QPropertyAnimation, QEasingCurve, 
                        QTimer, QObject, pyqtSignal, QUrl, pyqtSlot)
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                            QLabel, QPushButton, QFrame, QSizePolicy, QDialog)
from PyQt5.QtGui import QFont, QPainter, QColor, QBrush, QPen, QIcon
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineProfile, QWebEnginePage
from PyQt5.QtWebChannel import QWebChannel

# 导入默认配置
import json
import os

def load_default_config():
    """加载默认配置"""
    default_file = "default.json"
    if os.path.exists(default_file):
        with open(default_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

DEFAULT_CONFIG = load_default_config()

# 读取当前配置的函数
def load_current_config():
    """加载当前配置文件"""
    config_file = "config.json"
    if os.path.exists(config_file):
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return DEFAULT_CONFIG


class SettingsBridge(QObject):
    """设置窗口的前后端通信桥梁"""
    
    def __init__(self, parent_window, vector_db):
        super().__init__()
        self.parent_window = parent_window
        self.vector_db = vector_db
        self.config = self._load_config()
    
    def _load_config(self):
        """加载配置文件"""
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[error]加载配置文件失败: {e}")
            return DEFAULT_CONFIG.copy()
    
    def _save_config(self, config):
        """保存配置文件"""
        try:
            with open('config.json', 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            return True, "保存成功"
        except Exception as e:
            error_msg = f"保存配置文件失败: {e}"
            print(f"[error]{error_msg}")
            return False, error_msg
    
    @pyqtSlot(object, result='QVariant')
    @pyqtSlot(result='QVariant')
    def getSettings(self, callback=None):
        """获取当前设置（供JavaScript调用）"""
        if callback:
            # QWebChannel在JS和Python之间传递复杂对象时需要序列化
            # self.config是一个字典，可以直接传递
            callback.call([self.config])
        return self.config
    
    @pyqtSlot('QVariant', object)
    @pyqtSlot('QVariant')
    def saveSettings(self, form_data_variant, callback=None):
        """保存设置（供JavaScript调用）"""
        try:
            # 将QVariant转换为Python字典
            # QWebChannel会将JavaScript对象转换为QVariant
            if hasattr(form_data_variant, 'toPyObject'):
                # PyQt5风格的转换
                form_data = form_data_variant.toPyObject()
            elif hasattr(form_data_variant, 'value'):
                # 另一种转换方式
                form_data = form_data_variant.value()
            else:
                # 直接使用
                form_data = form_data_variant
            
            # 确保form_data是字典类型
            if not isinstance(form_data, dict):
                print(f"[error]接收到的数据类型不是字典: {type(form_data)}")
                if callback:
                    callback.call([False, f"数据类型错误: {type(form_data)}"])
                return
            
            # 验证数据
            if not self._validate_config(form_data):
                if callback:
                    callback.call([False, "配置数据验证失败"])
                return
            
            # 保存配置
            success, message = self._save_config(form_data)
            
            if success:
                self.config = form_data
                # 重新加载配置到全局变量
                self._reload_global_config()
            
            if callback:
                callback.call([success, message])
                
        except Exception as e:
            error_msg = f"保存设置时发生错误: {e}"
            print(f"[error]{error_msg}")
            import traceback
            print(f"[error]错误堆栈: {traceback.format_exc()}")
            if callback:
                callback.call([False, error_msg])
    
    def _validate_config(self, config):
        """验证配置数据"""
        try:
            # 验证必要字段
            required_fields = ['max_day', 'hotkey', 'model']
            for field in required_fields:
                if field not in config:
                    print(f"[error]缺少必要字段: {field}")
                    return False
            
            # 验证数值范围
            if not (1 <= config.get('max_day', 0) <= 365):
                print("[error]max_day必须在1-365之间")
                return False
            
            if not (0 <= config.get('temperature', 0) <= 2):
                print("[error]temperature必须在0-2之间")
                return False
            
            if not (0 <= config.get('cosine_similarity', 0) <= 1):
                print("[error]cosine_similarity必须在0-1之间")
                return False
            
            return True
            
        except Exception as e:
            print(f"[error]验证配置时发生错误: {e}")
            return False
    
    def _reload_global_config(self):
        """重新加载全局配置"""
        try:
            # 重新加载chat_part中的CONFIG
            import chat_part
            if chat_part.reload_config():
                print("[info]全局配置重新加载成功")
            else:
                print("[warning]全局配置重新加载失败")
        except Exception as e:
            print(f"[error]重新加载全局配置时发生错误: {e}")
    
    @pyqtSlot()
    def openSystemPromptEditor(self):
        """打开系统提示词编辑器（已废弃，保持兼容性）"""
        print("[info]系统提示词编辑器现在集成在设置页面中")
    
    @pyqtSlot()
    def openEmailConfig(self):
        """打开邮箱配置（已废弃，保持兼容性）"""
        print("[info]邮箱配置现在集成在设置页面中")

    # ==================== 系统提示词相关方法 ====================
    
    @pyqtSlot(object, result='QVariant')
    @pyqtSlot(result='QVariant')
    def getSystemPrompt(self, callback=None):
        """获取系统提示词"""
        try:
            system_prompt_file = "system_prompt.json"
            if os.path.exists(system_prompt_file):
                with open(system_prompt_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    prompt = data.get("preset", "")
            else:
                prompt = ""
            
            if callback:
                callback.call([prompt])
            return prompt
            
        except Exception as e:
            print(f"[error]读取系统提示词失败: {e}")
            if callback:
                callback.call([""])
            return ""
    
    @pyqtSlot(str, object)
    @pyqtSlot(str)
    def saveSystemPrompt(self, prompt, callback=None):
        """保存系统提示词"""
        try:
            system_prompt_file = "system_prompt.json"
            data = {"preset": prompt}
            with open(system_prompt_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            if callback:
                callback.call([True, "保存成功"])
            return True
            
        except Exception as e:
            error_msg = f"保存系统提示词失败: {e}"
            print(f"[error]{error_msg}")
            if callback:
                callback.call([False, error_msg])
            return False

    # ==================== 邮箱配置相关方法 ====================
    
    @pyqtSlot(object, result='QVariant')
    @pyqtSlot(result='QVariant')
    def getEmailConfig(self, callback=None):
        """获取邮箱配置"""
        try:
            email_data_file = "data.json"
            if os.path.exists(email_data_file):
                with open(email_data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = {"accounts": []}
            
            # 转换为前端需要的格式
            config = {
                "checkInterval": data.get("check_interval", 5),
                "emails": []
            }
            
            for account in data.get("accounts", []):
                config["emails"].append({
                    "address": account.get("email", ""),
                    "password": account.get("password", ""),
                    "imapServer": account.get("imap_server", ""),
                    "imapPort": account.get("imap_port", 993),
                    "useSSL": account.get("use_ssl", True),
                    "status": "unknown"
                })
            
            if callback:
                callback.call([config])
            return config
            
        except Exception as e:
            print(f"[error]读取邮箱配置失败: {e}")
            default_config = {
                "checkInterval": 5,
                "emails": []
            }
            if callback:
                callback.call([default_config])
            return default_config
    
    @pyqtSlot('QVariant', object)
    @pyqtSlot('QVariant')
    def saveEmailConfig(self, config_variant, callback=None):
        """保存邮箱配置"""
        try:
            # 将QVariant转换为Python字典
            if hasattr(config_variant, 'toPyObject'):
                config = config_variant.toPyObject()
            elif hasattr(config_variant, 'value'):
                config = config_variant.value()
            else:
                config = config_variant
            
            # 转换为后端需要的格式
            email_data_file = "data.json"
            data = {
                "check_interval": config.get("checkInterval", 5),
                "accounts": []
            }
            
            for email in config.get("emails", []):
                if email.get("address"):  # 只保存有邮箱地址的配置
                    account_data = {
                        "email": email.get("address", ""),
                        "password": email.get("password", ""),
                        "imap_server": email.get("imapServer", ""),
                        "imap_port": int(email.get("imapPort", 993)),
                        "use_ssl": email.get("useSSL", True)
                    }
                    data["accounts"].append(account_data)
            
            with open(email_data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            if callback:
                callback.call([True, "保存成功"])
            return True
            
        except Exception as e:
            error_msg = f"保存邮箱配置失败: {e}"
            print(f"[error]{error_msg}")
            if callback:
                callback.call([False, error_msg])
            return False
    
    @pyqtSlot(str, str, object)
    @pyqtSlot(str, str)
    def testEmailConnection(self, email, password, callback=None):
        """测试邮箱连接"""
        try:
            # 这里可以添加实际的邮箱连接测试逻辑
            # 暂时返回模拟结果
            import time
            time.sleep(1)  # 模拟连接测试时间
            
            if "@" in email and password:
                if callback:
                    callback.call([True, "连接测试成功"])
                return True
            else:
                if callback:
                    callback.call([False, "邮箱或密码格式错误"])
                return False
                
        except Exception as e:
            error_msg = f"邮箱连接测试失败: {e}"
            print(f"[error]{error_msg}")
            if callback:
                callback.call([False, error_msg])
            return False
    
    @pyqtSlot(str)
    def execute_command(self, command):
        """执行命令（用于清除历史记录等操作）"""
        try:
            print(f"[info]设置窗口执行命令: {command}")
            
            # 获取主应用实例
            app = QApplication.instance()
            if hasattr(app, 'chat_controller') and app.chat_controller:
                # 通过聊天控制器处理命令
                app.chat_controller.handle_command(command)
                return True
            else:
                # 直接调用命令处理模块
                import commands
                commands.cmd_exec(self.vector_db, command)
                return True
                
        except Exception as e:
            error_msg = f"执行命令失败: {e}"
            print(f"[error]{error_msg}")
            return False
    
    @pyqtSlot()
    def closeWindow(self):
        """关闭窗口"""
        if self.parent_window:
            self.parent_window.close()


class SettingsWebView(QWebEngineView):
    """设置窗口的WebView组件"""
    
    def __init__(self, parent_window, vector_db):
        super().__init__()
        self.parent_window = parent_window
        self.vector_db = vector_db
        
        # 创建通信桥梁
        self.bridge = SettingsBridge(parent_window, vector_db)
        
        # 设置Web Channel
        self.channel = QWebChannel()
        self.channel.registerObject("bridge", self.bridge)
        self.page().setWebChannel(self.channel)
        
        # 加载HTML页面
        self._init_page()
    
    def _init_page(self):
        """初始化设置页面"""
        html_file_path = os.path.join(os.path.dirname(__file__), "webview", "settings_view.html")
        if os.path.exists(html_file_path):
            self.load(QUrl.fromLocalFile(html_file_path))
            print(f"[info]加载设置页面: {html_file_path}")
            
            # 页面加载完成后注入主题色
            def on_load_finished():
                self._inject_theme_color()
            
            self.loadFinished.connect(on_load_finished)
        else:
            print(f"[error]设置页面文件不存在: {html_file_path}")
            raise FileNotFoundError(f"找不到设置页面文件: {html_file_path}")
    
    def _inject_theme_color(self):
        """注入动态主题色"""
        try:
            # 读取当前配置中的主题色
            config = load_current_config()
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
                    }}
                `;
                
                console.log('设置窗口主题色已更新为: {theme_color}');
            }})();
            """
            
            # 执行注入脚本
            self.page().runJavaScript(inject_script)
            print(f"[info]设置窗口主题色已注入: {theme_color}")
            
        except Exception as e:
            print(f"[error]设置窗口注入主题色失败: {e}")
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
                    }
                `;
            })();
            """
            self.page().runJavaScript(fallback_script)


class SettingWindow(QDialog):
    """WebView版本的设置窗口"""
    
    def __init__(self, vector_db=None, parent=None):
        super().__init__(parent)
        self.vector_db = vector_db
        self.parent_widget = parent
        
        self._init_ui()
        self._setup_window_properties()
    
    def _init_ui(self):
        """初始化UI"""
        self.setWindowTitle("设置")
        self.setFixedSize(506, 670)
        
        # 设置窗口样式
        self.setWindowFlags(
            Qt.Dialog |
            Qt.WindowCloseButtonHint |
            Qt.WindowTitleHint
        )
        
        # 创建布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 创建WebView
        self.webview = SettingsWebView(self, self.vector_db)
        layout.addWidget(self.webview)
        
        # 设置样式
        self.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
                border-radius: 8px;
            }
        """)
    
    def _setup_window_properties(self):
        """设置窗口属性"""
        # 居中显示
        if self.parent_widget:
            # 相对于父窗口居中
            parent_rect = self.parent_widget.geometry()
            x = parent_rect.x() + (parent_rect.width() - self.width()) // 2
            y = parent_rect.y() + (parent_rect.height() - self.height()) // 2
            self.move(x, y)
        else:
            # 相对于屏幕居中
            screen = QApplication.primaryScreen().availableGeometry()
            x = (screen.width() - self.width()) // 2
            y = (screen.height() - self.height()) // 2
            self.move(x, y)
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        event.accept()


