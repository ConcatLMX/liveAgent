import sys
import os
import json

from ai_part import AiChat
from faiss_utils import VectorDatabase
from modules import is_json_file_empty
from datetime import datetime, timedelta
from PyQt5.QtCore import Qt, QPropertyAnimation, QPoint, QEasingCurve, QTimer, QObject, pyqtSignal
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QTextEdit,
                             QLineEdit, QPushButton, QFrame, QScrollArea,
                             QSizePolicy, QHBoxLayout, QLabel, QSystemTrayIcon, QMenu)
from PyQt5.QtGui import QFont, QIcon, QColor, QPainter, QBrush, QLinearGradient, QPalette

HISTORY_FILE = "chat_history.json"
DEFAULT_HISTORY = {"messages": []}

class MessageUtils:
    def __init__(self, vector_db: VectorDatabase, app):
        self.vector_db = vector_db
        self.app = app

        # 读取配置文件
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        except Exception as e:
            print(f"[error]读取 config.json 时发生错误: {e}")
            self.config = {} 

    def save_message(self, role, content):
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
        if hasattr(self.app, 'vector_db'):
            self.vector_db.add_message(
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


    def make_messages(self, input: str, n: int = 7) -> list[dict]:
        """生成包含历史与记忆的新对话消息结构"""
        messages = []
        ac = AiChat()

        # 1. 当前用户输入
        messages.append({
            "role": "user",
            "content": input
        })

        # 2. 最近聊天记录
        messages.append({
            "role": "system",
            "content": "以下是你的最近聊天记录，请参考："
        })

        if hasattr(self.vector_db, 'metadata'):
            meta = self.vector_db.metadata[-n:] if self.vector_db.index.ntotal >= n else self.vector_db.metadata
            for item in meta:
                role = item.get('role', 'user')
                content = item.get('content', '')
                messages.append({"role": role, "content": content})

        # 3. 从记忆库检索相似内容
        messages.append({
            "role": "system",
            "content": "以下是从你的记忆库中提取的相关信息："
        })

        if hasattr(self.vector_db, 'search'):
            try:
                # 从配置文件读取余弦相似度阈值
                threshold = self.config.get('cosine_similarity', 0.5)
                results = self.vector_db.search(input, k=3, threshold=threshold)
                for res in results:
                    messages.append({
                        "role": res.get('role', 'user'),
                        "content": res.get('content', '')
                    })
            except Exception as e:                
                print(f"[warning]搜索向量数据库时出错: {e}")
                # 继续执行，不中断对话流程

        # 4. 加入 system prompt
        if hasattr(ac, 'system_message'):
            messages.extend(ac.system_message)

        return messages
    
    def generate_response(self, message):
        """生成回复"""
        try:
            ac = AiChat()
            new_message = self.make_messages(message)
            response = ac.get_message(new_message)
            return response
            
        except Exception as e:
            error_msg = f"生成回复时发生错误: {e}"
            print(f"[error]💥 ========== 回复生成失败 ==========")
            print(f"[error]❌ {error_msg}")
            import traceback
            print(f"[error]🔍 错误堆栈: {traceback.format_exc()}")
            print(f"[error]💥 ========== 返回默认错误消息 ==========")
            
            return "抱歉，我无法生成回复，请稍后再试。"