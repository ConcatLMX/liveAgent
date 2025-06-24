import json
import os
import sys
from PyQt5.QtCore import Qt, QPoint, QSize, QRect, QPropertyAnimation, QEasingCurve, pyqtSignal, pyqtProperty, QTimer
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QFrame, QLineEdit,
                             QComboBox, QSlider, QFormLayout,
                             QSizePolicy, QDialog, QMessageBox,
                             QTextEdit, QGridLayout, QSpacerItem)
from PyQt5.QtGui import QFont, QPainter, QColor, QBrush, QIcon, QIntValidator, QPalette
from faiss_utils import VectorDatabase
from commands import cmd_exec

CONFIG_FILE = "config.json"
SYSTEM_PROMPT_FILE = "system_prompt.json"
DEFAULT_CONFIG = {
    "max_day": 7,
    "model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "hotkey": "Alt+Q",
    "apikey": "",
    "api_baseurl": "",
    "temperature": 0.7,
    "receiveemail": False,
    "cosine_similarity": 0.5,
    "api_model": "",
    "live2d_uri": "ws://127.0.0.1:10086/api",
    "live2d_listen": False
}


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
        painter.drawRoundedRect(self.rect(), 12, 12)

        painter.end()


class ModernSwitch(QWidget):
    """现代风格开关按钮"""
    stateChanged = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(44, 24)  # 更小的尺寸
        self._state = False
        self._thumb_position = 4
        self.setCursor(Qt.PointingHandCursor)

        # 动画属性
        self.animation = None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 绘制轨道
        track_rect = QRect(0, 0, self.width(), self.height())
        track_color = QColor(220, 220, 220) if not self._state else QColor(10, 132, 255)
        painter.setBrush(track_color)
        painter.drawRoundedRect(track_rect, 12, 12)

        # 绘制滑块
        thumb_color = QColor(255, 255, 255)
        thumb_rect = QRect(self._thumb_position, 4, 16, 16)  # 更小的滑块
        painter.setBrush(thumb_color)
        painter.drawEllipse(thumb_rect)

        painter.end()

    def mousePressEvent(self, event):
        self.toggle()
        event.accept()

    def toggle(self):
        self._state = not self._state
        self.animate_thumb()
        self.stateChanged.emit(self._state)

    def animate_thumb(self):
        if self.animation:
            self.animation.stop()

        start_pos = self._thumb_position
        end_pos = 24 if self._state else 4  # 调整位置

        self.animation = QPropertyAnimation(self, b"thumbPosition")
        self.animation.setDuration(200)
        self.animation.setStartValue(start_pos)
        self.animation.setEndValue(end_pos)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.animation.start()

    def getThumbPosition(self):
        return self._thumb_position

    def setThumbPosition(self, position):
        self._thumb_position = position
        self.update()

    thumbPosition = pyqtProperty(int, getThumbPosition, setThumbPosition)

    def isChecked(self):
        return self._state

    def setChecked(self, state):
        if state != self._state:
            self._state = state
            self._thumb_position = 24 if state else 4  # 调整位置
            self.update()


class SettingWindow(QDialog):
    def __init__(self, vector_db: VectorDatabase, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置 · liveAgent")
        self.setFixedSize(420, 640)  # 高度增加100像素以容纳新控件
        self.setWindowFlags(
            Qt.Window |
            Qt.WindowCloseButtonHint |
            Qt.WindowTitleHint |
            Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)

        # 背景使用纯色
        self.background = SolidBackground(self)
        self.background.setGeometry(0, 0, 420, 640)  # 高度增加100像素

        self.initUI()
        self.load_config()

        # 用于窗口拖动
        self.drag_position = None

        # 放置中央
        self.center()

        # 确保窗口关闭时被删除
        self.setAttribute(Qt.WA_DeleteOnClose)

        # 设置向量数据库
        self.vector_db = vector_db

    def center(self):
        """将窗口置于屏幕中央"""
        frame_geometry = self.frameGeometry()
        center_point = QApplication.primaryScreen().availableGeometry().center()
        frame_geometry.moveCenter(center_point)
        self.move(frame_geometry.topLeft())

    def initUI(self):
        # 标题栏
        title_bar = QWidget(self)
        title_bar.setFixedHeight(42)
        title_bar.setStyleSheet("background: transparent;")
        title_bar_layout = QHBoxLayout(title_bar)
        title_bar_layout.setContentsMargins(20, 0, 15, 0)

        # 标题
        title_label = QLabel("设置")
        title_label.setFont(QFont("Microsoft YaHei UI", 11, QFont.Bold))
        title_label.setStyleSheet("color: #333;")
        title_bar_layout.addWidget(title_label)
        title_bar_layout.addStretch()

        # 关闭按钮
        self.close_btn = QPushButton("×")
        self.close_btn.setFixedSize(28, 28)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border-radius: 14px;
                border: none;
                font-size: 16px;
                color: #888;
            }
            QPushButton:hover {
                background: #f0f0f0;
            }
        """)
        self.close_btn.clicked.connect(self.close)
        title_bar_layout.addWidget(self.close_btn)

        # 主布局
        main_layout = QVBoxLayout(self)
        # 增加顶部边距30（原10），使内容整体下移20像素
        main_layout.setContentsMargins(20, 30, 20, 20)
        main_layout.setSpacing(15)

        # 表单布局 - 使用网格布局，提供更多间距
        grid_layout = QGridLayout()
        grid_layout.setVerticalSpacing(16)  # 增加行间距
        grid_layout.setHorizontalSpacing(20)  # 增加列间距
        grid_layout.setColumnMinimumWidth(0, 100)  # 设置标签列最小宽度
        grid_layout.setColumnMinimumWidth(1, 250)  # 设置输入列最小宽度

        # 设置项字体
        setting_font = QFont("Microsoft YaHei UI", 9)

        # 行计数器
        row = 0

        # max_day设置
        self.max_day_label = QLabel("历史保留天数:")
        self.max_day_label.setFont(setting_font)
        grid_layout.addWidget(self.max_day_label, row, 0, Qt.AlignRight | Qt.AlignVCenter)

        self.max_day_input = QLineEdit()
        self.max_day_input.setFont(setting_font)
        self.max_day_input.setFixedHeight(34)  # 增加高度
        self.max_day_input.setStyleSheet("""
            QLineEdit {
                background: white;
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 0 12px;
            }
        """)
        self.max_day_input.setValidator(QIntValidator(1, 365))
        grid_layout.addWidget(self.max_day_input, row, 1)
        row += 1

        # 添加间距
        grid_layout.addItem(QSpacerItem(10, 10), row, 0)
        row += 1

        # 模型选择
        self.model_label = QLabel("Embed模型:")
        self.model_label.setFont(setting_font)
        grid_layout.addWidget(self.model_label, row, 0, Qt.AlignRight | Qt.AlignVCenter)

        self.model_combo = QComboBox()
        self.model_combo.setFont(setting_font)
        self.model_combo.setFixedHeight(34)
        self.model_combo.addItems([
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            "sentence-transformers/all-MiniLM-L6-v2",
            "sentence-transformers/all-mpnet-base-v2",
            "sentence-transformers/paraphrase-MiniLM-L6-v2",
            "sentence-transformers/distiluse-base-multilingual-cased"
        ])
        self.model_combo.setStyleSheet("""
            QComboBox {
                background: white;
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 0 12px;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
        """)
        grid_layout.addWidget(self.model_combo, row, 1)
        row += 1

        # 添加间距
        grid_layout.addItem(QSpacerItem(10, 10), row, 0)
        row += 1        # 热键设置
        self.hotkey_label = QLabel("热键:")
        self.hotkey_label.setFont(setting_font)
        grid_layout.addWidget(self.hotkey_label, row, 0, Qt.AlignRight | Qt.AlignVCenter)

        hotkey_layout = QHBoxLayout()
        hotkey_layout.setSpacing(8)
        
        self.hotkey_input = QLineEdit()
        self.hotkey_input.setFont(setting_font)
        self.hotkey_input.setFixedHeight(34)
        self.hotkey_input.setPlaceholderText("例如: Alt+Q, Ctrl+Shift+H")
        self.hotkey_input.setStyleSheet("""
            QLineEdit {
                background: white;
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 0 12px;
            }
        """)
        hotkey_layout.addWidget(self.hotkey_input, 1)
        
        # 热键测试按钮
        self.test_hotkey_btn = QPushButton("测试")
        self.test_hotkey_btn.setFont(setting_font)
        self.test_hotkey_btn.setFixedSize(48, 34)
        self.test_hotkey_btn.setStyleSheet("""
            QPushButton {
                background: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 6px;
                color: #333;
            }
            QPushButton:hover {
                background: #e5e5e5;
            }
            QPushButton:pressed {
                background: #d0d0d0;
            }
        """)
        self.test_hotkey_btn.clicked.connect(self.test_hotkey)
        hotkey_layout.addWidget(self.test_hotkey_btn)
        
        grid_layout.addLayout(hotkey_layout, row, 1)
        row += 1

        # 添加间距
        grid_layout.addItem(QSpacerItem(10, 10), row, 0)
        row += 1

        # API基础URL
        self.baseurl_label = QLabel("API_base_url:")
        self.baseurl_label.setFont(setting_font)
        grid_layout.addWidget(self.baseurl_label, row, 0, Qt.AlignRight | Qt.AlignVCenter)

        self.baseurl_input = QLineEdit()
        self.baseurl_input.setFont(setting_font)
        self.baseurl_input.setFixedHeight(34)
        self.baseurl_input.setStyleSheet("""
            QLineEdit {
                background: white;
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 0 12px;
            }
        """)
        grid_layout.addWidget(self.baseurl_input, row, 1)
        row += 1

        # 添加间距
        grid_layout.addItem(QSpacerItem(10, 10), row, 0)
        row += 1

        # API密钥
        self.apikey_label = QLabel("API_key:")
        self.apikey_label.setFont(setting_font)
        grid_layout.addWidget(self.apikey_label, row, 0, Qt.AlignRight | Qt.AlignVCenter)

        self.apikey_input = QLineEdit()
        self.apikey_input.setFont(setting_font)
        self.apikey_input.setFixedHeight(34)
        self.apikey_input.setStyleSheet("""
            QLineEdit {
                background: white;
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 0 12px;
            }
        """)
        grid_layout.addWidget(self.apikey_input, row, 1)
        row += 1

        # 添加间距
        grid_layout.addItem(QSpacerItem(10, 10), row, 0)
        row += 1

        # API模型设置
        self.api_model_label = QLabel("API模型:")
        self.api_model_label.setFont(setting_font)
        grid_layout.addWidget(self.api_model_label, row, 0, Qt.AlignRight | Qt.AlignVCenter)

        self.api_model_input = QLineEdit()
        self.api_model_input.setFont(setting_font)
        self.api_model_input.setFixedHeight(34)
        self.api_model_input.setStyleSheet("""
            QLineEdit {
                background: white;
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 0 12px;
            }
        """)
        grid_layout.addWidget(self.api_model_input, row, 1)
        row += 1

        # 添加间距
        grid_layout.addItem(QSpacerItem(10, 10), row, 0)
        row += 1

        # 余弦相似度设置
        self.cosine_label = QLabel("余弦相似度:")
        self.cosine_label.setFont(setting_font)
        grid_layout.addWidget(self.cosine_label, row, 0, Qt.AlignRight | Qt.AlignVCenter)

        cosine_layout = QHBoxLayout()
        cosine_layout.setSpacing(10)

        # 添加滑块
        self.cosine_slider = QSlider(Qt.Horizontal)
        self.cosine_slider.setFixedHeight(34)
        self.cosine_slider.setRange(0, 100)
        self.cosine_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 4px;
                background: #e0e0e0;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #0A84FF;
                width: 16px;
                height: 16px;
                margin: -6px 0;
                border-radius: 8px;
            }
            QSlider::sub-page:horizontal {
                background: #0A84FF;
                border-radius: 2px;
            }
        """)
        cosine_layout.addWidget(self.cosine_slider, 1)

        # 添加数值标签
        self.cosine_value = QLabel("0.50")
        self.cosine_value.setFont(setting_font)
        self.cosine_value.setFixedWidth(36)
        self.cosine_value.setAlignment(Qt.AlignCenter)
        self.cosine_value.setStyleSheet("color: #333; font-weight: 500;")
        cosine_layout.addWidget(self.cosine_value)

        grid_layout.addLayout(cosine_layout, row, 1)
        row += 1        # 添加间距
        grid_layout.addItem(QSpacerItem(10, 10), row, 0)
        row += 1

        # 温度设置
        self.temp_label = QLabel("Temperature:")
        self.temp_label.setFont(setting_font)
        grid_layout.addWidget(self.temp_label, row, 0, Qt.AlignRight | Qt.AlignVCenter)

        temp_layout = QHBoxLayout()
        temp_layout.setSpacing(10)

        # 添加滑块
        self.temp_slider = QSlider(Qt.Horizontal)
        self.temp_slider.setFixedHeight(34)
        self.temp_slider.setRange(0, 100)
        self.temp_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 4px;
                background: #e0e0e0;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #0A84FF;
                width: 16px;
                height: 16px;
                margin: -6px 0;
                border-radius: 8px;
            }
            QSlider::sub-page:horizontal {
                background: #0A84FF;
                border-radius: 2px;
            }
        """)
        temp_layout.addWidget(self.temp_slider, 1)

        # 添加数值标签
        self.temp_value = QLabel("0.70")
        self.temp_value.setFont(setting_font)
        self.temp_value.setFixedWidth(36)
        self.temp_value.setAlignment(Qt.AlignCenter)
        self.temp_value.setStyleSheet("color: #333; font-weight: 500;")
        temp_layout.addWidget(self.temp_value)

        grid_layout.addLayout(temp_layout, row, 1)
        row += 1

        # 添加间距
        grid_layout.addItem(QSpacerItem(10, 10), row, 0)
        row += 1

        # 接收邮件通知
        self.email_label = QLabel("邮件总结:")
        self.email_label.setFont(setting_font)
        grid_layout.addWidget(self.email_label, row, 0, Qt.AlignRight | Qt.AlignVCenter)        # 使用现代风格开关
        self.email_switch = ModernSwitch()
        self.email_switch.stateChanged.connect(self.on_switch_changed)
        grid_layout.addWidget(self.email_switch, row, 1, Qt.AlignLeft | Qt.AlignVCenter)
        row += 1

        # 添加间距
        grid_layout.addItem(QSpacerItem(10, 10), row, 0)
        row += 1        # Live2D URI设置
        self.live2d_uri_label = QLabel("Live2D URI:")
        self.live2d_uri_label.setFont(setting_font)
        grid_layout.addWidget(self.live2d_uri_label, row, 0, Qt.AlignRight | Qt.AlignVCenter)

        self.live2d_uri_input = QLineEdit()
        self.live2d_uri_input.setFont(setting_font)
        self.live2d_uri_input.setFixedHeight(34)
        self.live2d_uri_input.setPlaceholderText("例如: ws://127.0.0.1:10086/api")
        self.live2d_uri_input.setStyleSheet("""
            QLineEdit {
                background: white;
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 0 12px;
            }
        """)
        grid_layout.addWidget(self.live2d_uri_input, row, 1)
        row += 1

        # 添加间距
        grid_layout.addItem(QSpacerItem(10, 10), row, 0)
        row += 1

        # Live2D是否监听
        self.live2d_listen_label = QLabel("Live2D监听:")
        self.live2d_listen_label.setFont(setting_font)
        grid_layout.addWidget(self.live2d_listen_label, row, 0, Qt.AlignRight | Qt.AlignVCenter)

        # 使用现代风格开关
        self.live2d_listen_switch = ModernSwitch()
        self.live2d_listen_switch.stateChanged.connect(self.on_live2d_switch_changed)
        grid_layout.addWidget(self.live2d_listen_switch, row, 1, Qt.AlignLeft | Qt.AlignVCenter)
        row += 1

        main_layout.addLayout(grid_layout)

        # 添加弹性空间
        main_layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # 操作按钮
        action_layout = QHBoxLayout()
        action_layout.setSpacing(12)

        # 清除历史记录按钮
        self.clear_btn = QPushButton("删除所有历史（不可逆）")
        self.clear_btn.setFont(QFont("Microsoft YaHei UI", 9))
        self.clear_btn.setFixedHeight(38)
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background: white;
                color: #e53e3e;
                border: 1px solid #e53e3e;
                border-radius: 8px;
                padding: 0 12px;
            }
            QPushButton:hover {
                background: #fff5f5;
            }
            QPushButton:pressed {
                background: #fed7d7;
            }
        """)
        self.clear_btn.clicked.connect(self.vb_clear)
        action_layout.addWidget(self.clear_btn)

        # 系统提示设置按钮
        self.prompt_btn = QPushButton("角色预设")
        self.prompt_btn.setFont(QFont("Microsoft YaHei UI", 9))
        self.prompt_btn.setFixedHeight(38)
        self.prompt_btn.setStyleSheet("""
            QPushButton {
                background: white;
                color: #3182ce;
                border: 1px solid #3182ce;
                border-radius: 8px;
                padding: 0 12px;
            }
            QPushButton:hover {
                background: #ebf8ff;
            }
            QPushButton:pressed {
                background: #bee3f8;
            }
        """)
        self.prompt_btn.clicked.connect(self.edit_system_prompt)
        action_layout.addWidget(self.prompt_btn)

        main_layout.addLayout(action_layout)

        # 添加弹性空间
        main_layout.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Minimum, QSizePolicy.Fixed))

        # 保存按钮
        self.save_btn = QPushButton("保存设置")
        self.save_btn.setFont(QFont("Microsoft YaHei UI", 10, QFont.Medium))
        self.save_btn.setFixedHeight(42)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background: #0A84FF;
                color: white;
                border-radius: 8px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #0971d9;
            }
            QPushButton:pressed {
                background: #0961b9;
            }
        """)
        self.save_btn.clicked.connect(self.save_config)
        main_layout.addWidget(self.save_btn)        # 连接信号
        self.temp_slider.valueChanged.connect(self.update_temp_value)
        self.cosine_slider.valueChanged.connect(self.update_cosine_value)

        # 初始位置居中
        self.center_window()

    def center_window(self):
        """将窗口置于屏幕中央"""
        frame_geometry = self.frameGeometry()
        center_point = QApplication.desktop().availableGeometry().center()
        frame_geometry.moveCenter(center_point)
        self.move(frame_geometry.topLeft())

    def update_temp_value(self, value):
        """更新温度值显示"""
        self.temp_value.setText(f"{value / 100:.2f}")

    def update_cosine_value(self, value):
        """更新余弦相似度值显示"""
        self.cosine_value.setText(f"{value / 100:.2f}")

    def on_switch_changed(self, state):
        """开关状态变化处理"""
        # 这里可以根据需要处理状态变化
        pass

    def on_live2d_switch_changed(self, state):
        """Live2D开关状态变化处理"""
        # 这里可以根据需要处理Live2D监听状态变化
        pass

    def load_config(self):
        """从配置文件加载设置"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    config = json.load(f)
            except:
                config = DEFAULT_CONFIG
        else:
            config = DEFAULT_CONFIG        # 设置UI控件的值
        self.max_day_input.setText(str(config.get("max_day", 7)))
        self.model_combo.setCurrentText(config.get("model", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"))
        self.hotkey_input.setText(config.get("hotkey", "Alt+Q"))
        self.baseurl_input.setText(config.get("api_baseurl", ""))
        self.apikey_input.setText(config.get("apikey", ""))

        temp_value = int(config.get("temperature", 0.7) * 100)
        self.temp_slider.setValue(temp_value)
        self.temp_value.setText(f"{temp_value / 100:.2f}")

        cosine_value = int(config.get("cosine_similarity", 0.5) * 100)
        self.cosine_slider.setValue(cosine_value)
        self.cosine_value.setText(f"{cosine_value / 100:.2f}")

        self.api_model_input.setText(config.get("api_model", ""))        # 设置开关状态
        switch_state = config.get("receiveemail", True)
        self.email_switch.setChecked(switch_state)        # 设置Live2D相关配置
        self.live2d_uri_input.setText(str(config.get("live2d_uri", "ws://127.0.0.1:10086/api")))
        live2d_listen_state = config.get("live2d_listen", False)
        self.live2d_listen_switch.setChecked(live2d_listen_state)

    def save_config(self):
        """保存设置到配置文件"""
        config = {
            "max_day": int(self.max_day_input.text()),
            "model": self.model_combo.currentText(),
            "hotkey": self.hotkey_input.text(),
            "api_baseurl": self.baseurl_input.text(),
            "apikey": self.apikey_input.text(),
            "temperature": float(self.temp_value.text()),
            "cosine_similarity": float(self.cosine_value.text()),
            "api_model": self.api_model_input.text(),            "receiveemail": self.email_switch.isChecked(),
            "live2d_uri": self.live2d_uri_input.text(),
            "live2d_listen": self.live2d_listen_switch.isChecked()
        }

        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            self.close()
            QMessageBox.information(self, "设置已保存", 
                "配置已成功保存！\n\n热键等某些设置需要重启程序才能完全生效。")
                
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存配置时出错:\n{str(e)}")

    def vb_clear(self):
        """清除向量数据库和历史记录"""
        reply = QMessageBox.question(
            self, "确认清除",
            "确定要清除所有历史记录吗？此操作不可撤销！",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        cmd_exec(self.vector_db, "--history_clear()")

    def edit_system_prompt(self):
        """编辑系统提示"""
        # 创建对话框
        prompt_dialog = QDialog(self)
        prompt_dialog.setWindowTitle("系统提示设置")
        prompt_dialog.setFixedSize(500, 400)
        prompt_dialog.setWindowFlags(
            Qt.Window |
            Qt.WindowCloseButtonHint |
            Qt.WindowTitleHint
        )

        layout = QVBoxLayout(prompt_dialog)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(15)

        # 提示标签
        label = QLabel("编辑系统提示:")
        label.setFont(QFont("Microsoft YaHei UI", 9))
        layout.addWidget(label)

        # 文本编辑区域
        text_edit = QTextEdit()
        text_edit.setFont(QFont("Microsoft YaHei UI", 9))
        text_edit.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 12px;
                background: white;
            }
        """)

        # 加载现有系统提示（如果有）
        if os.path.exists(SYSTEM_PROMPT_FILE):
            try:
                with open(SYSTEM_PROMPT_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    text_edit.setText(data.get("preset", ""))
            except:
                pass
        layout.addWidget(text_edit, 1)

        # 按钮布局
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)

        # 取消按钮
        cancel_btn = QPushButton("取消")
        cancel_btn.setFont(QFont("Microsoft YaHei UI", 9))
        cancel_btn.setFixedHeight(36)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: #f0f0f0;
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 0;
            }
            QPushButton:hover {
                background: #e5e5e5;
            }
        """)
        cancel_btn.clicked.connect(prompt_dialog.reject)
        button_layout.addWidget(cancel_btn)

        button_layout.addStretch()

        # 保存按钮
        save_btn = QPushButton("保存")
        save_btn.setFont(QFont("Microsoft YaHei UI", 9))
        save_btn.setFixedHeight(36)
        save_btn.setStyleSheet("""
            QPushButton {
                background: #0A84FF;
                color: white;
                border-radius: 8px;
                padding: 0;
            }
            QPushButton:hover {
                background: #0971d9;
            }
        """)
        save_btn.clicked.connect(lambda: self.save_system_prompt(text_edit.toPlainText(), prompt_dialog))
        button_layout.addWidget(save_btn)

        layout.addLayout(button_layout)

        prompt_dialog.exec_()

    def save_system_prompt(self, prompt_text, dialog):
        """保存系统提示到文件"""
        # 创建或更新JSON文件
        data = {"preset": prompt_text}

        try:
            with open(SYSTEM_PROMPT_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, "保存成功", "系统提示已更新！")
            dialog.accept()
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存系统提示时出错:\n{str(e)}")

    def mousePressEvent(self, event):
        """支持窗口拖动"""
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        """支持窗口拖动"""
        if event.buttons() == Qt.LeftButton and self.drag_position:
            self.move(event.globalPos() - self.drag_position)
            event.accept()

    def test_hotkey(self):
        """测试热键是否有效"""
        hotkey_text = self.hotkey_input.text().strip()
        if not hotkey_text:
            QMessageBox.warning(self, "测试失败", "请先输入热键！")
            return
            
        try:
            import keyboard
            # 标准化热键格式
            hotkey = hotkey_text.lower().replace(' ', '')
            
            # 尝试注册一个临时热键来测试
            test_successful = False
            
            def test_callback():
                nonlocal test_successful
                test_successful = True
                
            # 注册测试热键
            keyboard.add_hotkey(hotkey, test_callback)
            
            # 显示测试对话框
            msg = QMessageBox(self)
            msg.setWindowTitle("热键测试")
            msg.setText(f"请按下热键: {hotkey_text}")
            msg.setInformativeText("如果热键有效，此对话框将自动关闭。\n如果5秒后未响应，请检查热键设置。")
            msg.setStandardButtons(QMessageBox.Cancel)
            
            # 设置5秒超时
            timer = QTimer()
            timer.timeout.connect(lambda: self.check_test_result(msg, test_successful, hotkey))
            timer.start(5000)  # 5秒
            
            # 也设置一个更频繁的检查，以便及时响应
            check_timer = QTimer()
            check_timer.timeout.connect(lambda: self.check_test_result(msg, test_successful, hotkey, check_timer))
            check_timer.start(100)  # 100ms
            
            msg.exec_()
            
        except Exception as e:
            QMessageBox.critical(self, "测试失败", f"热键测试时出错:\n{str(e)}")
    
    def check_test_result(self, msg, test_successful, hotkey, check_timer=None):
        """检查测试结果"""
        try:
            import keyboard
            if test_successful:
                keyboard.remove_hotkey(hotkey)
                if check_timer:
                    check_timer.stop()
                msg.accept()
                QMessageBox.information(self, "测试成功", "热键设置有效！")
            elif not msg.isVisible():
                # 对话框已关闭，清理热键
                keyboard.remove_hotkey(hotkey)
                if check_timer:
                    check_timer.stop()
        except:
            pass    # ...existing code...

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # 设置应用样式
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(250, 250, 250))
    app.setPalette(palette)

    settings = SettingWindow()
    settings.show()
    sys.exit(app.exec_())