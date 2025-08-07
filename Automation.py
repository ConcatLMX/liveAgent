import imapclient
import pyzmail
from datetime import date
import time
import threading
import json
import os
from bs4 import BeautifulSoup
from ai_part import AiChat
from Live2DViewerEX import L2DVEX
from message_utils import MessageUtils
from control import WindowsControl


class EmailUtils:
    """邮件处理工具类"""
    
    def __init__(self, imap_server='', username='', password='', use_ssl=True, imap_id_info=None):
        """
        初始化邮件工具
        
        Args:
            imap_server: IMAP服务器地址
            username: 邮箱用户名
            password: 邮箱密码或授权码
            use_ssl: 是否使用SSL/TLS连接
            imap_id_info: IMAP ID信息字典，用于解决某些服务器的unsafe login问题
        """
        self.imap_server = imap_server
        self.username = username
        self.password = password
        self.use_ssl = use_ssl
        self.uids_seen = set()  # 已处理的邮件UID集合
        
        # 设置默认的IMAP ID信息
        self.imap_id_info = imap_id_info or {
            b'name': b'liveAgent',
            b'version': b'1.0.0',            b'vendor': b'liveAgent-client',
            b'support-email': b'support@liveagent.com'
        }
        
    def connect(self):
        """连接到IMAP服务器"""
        try:
            self.imap_object = imapclient.IMAPClient(self.imap_server, ssl=self.use_ssl)
            
            # 发送IMAP ID信息（解决unsafe login问题）
            try:
                self.imap_object.id_(self.imap_id_info)
                print(f"[info]已发送IMAP ID信息到服务器: {self.imap_id_info}")
            except Exception as id_e:
                print(f"[warning]发送IMAP ID失败，继续尝试连接: {id_e}")
            
            self.imap_object.login(self.username, self.password)
            self.imap_object.select_folder('INBOX', readonly=False)
            return True
        except Exception as e:
            print(f"[error]连接邮件服务器失败: {e}")
            return False
    
    def disconnect(self):
        """断开IMAP连接"""
        try:
            if hasattr(self, 'imap_object'):
                self.imap_object.logout()
        except Exception as e:
            print(f"[error]断开邮件服务器连接失败: {e}")
    
    def text_from_html(self, html: str) -> str:
        """
        从HTML内容中提取纯文本
        
        Args:
            html: HTML内容字符串
            
        Returns:
            str: 提取的纯文本内容        """
        try:
            # 使用内置的 html.parser，不依赖 lxml
            soup = BeautifulSoup(html, 'html.parser')
            return soup.get_text(strip=True)
        except Exception as e:
            print(f"[error]解析HTML内容失败: {e}")
            # 如果HTML解析失败，尝试简单的文本提取
            try:
                import re
                # 移除HTML标签的简单正则表达式
                clean_text = re.sub(r'<[^>]+>', '', html)
                # 清理多余的空白字符
                clean_text = re.sub(r'\s+', ' ', clean_text).strip()
                return clean_text
            except Exception as fallback_e:
                print(f"[error]备用文本提取也失败: {fallback_e}")
                return html  # 最后返回原始HTML
    
    def get_today_unread_emails(self):
        """
        获取今日未读邮件
        
        Returns:
            list: 邮件内容列表，每个元素包含邮件信息
        """
        emails = []
        
        if not self.connect():
            return emails
        
        try:
            # 获取今日未读邮件
            since_date = date.today().strftime('%d-%b-%Y')
            uids = self.imap_object.search(['SINCE', since_date, 'UNSEEN'])
            
            for uid in uids:
                if uid not in self.uids_seen:
                    try:
                        # 获取邮件内容
                        raw_message = self.imap_object.fetch(uid, ['BODY[]'])
                        message_object = pyzmail.PyzMessage.factory(raw_message[uid][b'BODY[]'])
                        
                        # 提取邮件信息
                        email_data = {
                            'uid': uid,
                            'subject': message_object.get_subject(),
                            'from': message_object.get_addresses('from'),
                            'to': message_object.get_addresses('to'),
                            'date': message_object.get_decoded_header('date'),
                            'content': ''
                        }
                        
                        # 提取邮件内容
                        if message_object.html_part is not None:
                            html_content = message_object.html_part.get_payload().decode(
                                message_object.html_part.charset or 'utf-8'
                            )
                            email_data['content'] = self.text_from_html(html_content)
                        elif message_object.text_part is not None:
                            email_data['content'] = message_object.text_part.get_payload().decode(
                                message_object.text_part.charset or 'utf-8'
                            )
                        
                        emails.append(email_data)
                        self.uids_seen.add(uid)
                        
                        # 添加延时防止频繁请求
                        time.sleep(1)
                        
                    except Exception as e:
                        print(f"[error]处理邮件 {uid} 失败: {e}")
                        continue
                        
        except Exception as e:
            print(f"[error]获取邮件失败: {e}")
        finally:
            self.disconnect()
            
        return emails
    
    def get_unread_emails_summary(self):
        """
        获取未读邮件摘要
        
        Returns:
            str: 未读邮件的摘要信息
        """
        emails = self.get_today_unread_emails()
        
        if not emails:
            return "今日暂无未读邮件"
        
        summary = f"今日收到 {len(emails)} 封未读邮件:\n\n"
        
        for i, email in enumerate(emails, 1):
            sender = email['from'][0][1] if email['from'] else "未知发件人"
            subject = email['subject'] or "无主题"
            content_preview = email['content'][:100] + "..." if len(email['content']) > 100 else email['content']
            
            summary += f"{i}. 发件人: {sender}\n"
            summary += f"   主题: {subject}\n"
            summary += f"   内容预览: {content_preview}\n\n"
        
        return summary
    
    def listen_email(self, callback=None, interval=300):
        """
        持续监听邮件
        
        Args:
            callback: 收到新邮件时的回调函数，接收邮件列表作为参数
            interval: 检查邮件的间隔时间（秒），默认5分钟
        """
        print(f"[info]开始监听邮件，检查间隔: {interval}秒")
        
        while True:
            try:
                emails = self.get_today_unread_emails()
                
                if emails and callback:
                    callback(emails)
                elif emails:
                    print(f"[info]收到 {len(emails)} 封新邮件")
                
                time.sleep(interval)
                
            except KeyboardInterrupt:
                print("[info]邮件监听已停止")
                break
            except Exception as e:
                print(f"[error]邮件监听过程中发生错误: {e}")
                time.sleep(60)  # 出错后等待1分钟再重试
    
    def update_credentials(self, imap_server, username, password, use_ssl=True):
        """
        更新邮件服务器凭据
        
        Args:
            imap_server: IMAP服务器地址
            username: 邮箱用户名
            password: 邮箱密码或授权码
            use_ssl: 是否使用SSL/TLS连接
        """
        self.imap_server = imap_server
        self.username = username
        self.password = password
        self.use_ssl = use_ssl
        self.uids_seen.clear()  # 清空已处理的邮件记录


class EmailMonitorThread(threading.Thread):
    """邮箱监听线程类"""
    
    def __init__(self, email_data_file: str, check_interval: int, app=None, vector_db=None):
        """
        初始化邮箱监听线程
        
        Args:
            email_data_file: 邮箱配置文件路径
            check_interval: 检查邮件的间隔时间（秒）
            app: 主应用程序实例
            vector_db: 向量数据库实例
        """
        super().__init__(daemon=True)
        self.email_data_file = email_data_file
        self.check_interval = check_interval
        self.email_monitors = []
        self.running = True
        self.app = app
        self.vector_db = vector_db        #读取config.json
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        except Exception as e:
            print(f"[error]读取 config.json 时发生错误: {e}")

    def load_email_configs(self):
        """加载邮箱配置"""
        try:
            if not os.path.exists(self.email_data_file):
                print(f"[warning]{self.email_data_file} 文件不存在，跳过邮箱监听")
                return []
            
            with open(self.email_data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            emails_config = data.get("accounts", [])  # 修改为 accounts
            if not emails_config:
                print("[warning]未配置邮箱账户，跳过邮箱监听")
                return []
            
            # 为每个邮箱创建监听器
            monitors = []
            for email_config in emails_config:
                # 处理IMAP ID配置
                imap_id_config = email_config.get("imap_id")
                imap_id_info = None
                
                if imap_id_config:
                    # 将字符串键值转换为bytes（IMAP协议要求）
                    imap_id_info = {
                        key.encode() if isinstance(key, str) else key: 
                        value.encode() if isinstance(value, str) else value
                        for key, value in imap_id_config.items()
                    }
                    print(f"[info]邮箱 {email_config.get('email', '')} 使用自定义IMAP ID: {imap_id_config}")
                
                email_utils = EmailUtils(
                    imap_server=email_config.get("imap_server", ""),
                    username=email_config.get("email", ""),
                    password=email_config.get("password", ""),
                    use_ssl=email_config.get("use_ssl", True),
                    imap_id_info=imap_id_info
                )
                monitors.append({
                    'utils': email_utils,
                    'email': email_config.get("email", ""),
                    'last_check': 0
                })
            
            return monitors
        except Exception as e:
            print(f"[error]加载邮箱配置失败: {e}")
            return []
    
    def handle_new_emails(self, emails, email_account):
        """
        处理新邮件的回调函数
        
        Args:
            emails: 新邮件列表
            email_account: 邮箱账户
        """
        if not emails:
            return
        
        print(f"[info]邮箱 {email_account} 收到 {len(emails)} 封新邮件")
        
        # 这里可以添加更多的邮件处理逻辑
        for email in emails:
            sender = email['from'][0][1] if email['from'] else "未知发件人"
            subject = email['subject'] or "无主题"
            
            # 处理邮件内容，限制长度并清理特殊字符
            email_content = email.get('content', '')
            if len(email_content) > 1000:  # 限制邮件内容长度
                email_content = email_content[:1000] + "..."
              # 清理可能导致API问题的字符
            email_content = email_content.replace('\x00', '').replace('\r', ' ').replace('\n', ' ')
            # 移除多余的空白字符
            import re
            email_content = re.sub(r'\s+', ' ', email_content).strip()
            
            try:
                # 构造AI摘要请求 - 改进prompt，让摘要更简洁
                summary_prompt = f"请为这封邮件生成一个简洁的中文摘要（不超过50字）：\n主题：{subject}\n发件人：{sender}\n内容：{email_content}，格式如下：您受到了封邮件：“总结内容”"
                print(f"[info]正在为邮件生成摘要，主题: {subject}")
                
                # 使用修复后的general_summary方法
                from ai_part import AiChat
                ai_chat = AiChat()
                summary = ai_chat.general_summary(summary_prompt)
                print(f"[info]邮件摘要生成成功")
                
            except Exception as ai_error:
                print(f"[error]AI 摘要生成失败: {ai_error}")
                # 使用简单的邮件信息作为摘要
                summary = f"收到来自 {sender} 的邮件，主题：{subject}"
                if email_content:
                    summary += f"，内容预览：{email_content[:100]}..."
            
            # 格式化邮件摘要内容
            email_summary_content = summary

            # 使用 MessageUtils 保存消息（这会同时处理 chat_history.json 和向量数据库）
            if self.vector_db:
                try:
                    mu = MessageUtils(self.vector_db, self.app)
                    mu.save_message("assistant", email_summary_content)
                    print(f"[info]邮件摘要已保存到消息历史和向量数据库")
                except Exception as e:
                    print(f"[error]保存邮件摘要失败: {e}")
                    # 如果 MessageUtils 失败，则直接写入 chat_history.json 作为备用
                    try:
                        from datetime import datetime
                        import json
                        
                        email_message = {
                            "role": "assistant",
                            "content": email_summary_content,
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        
                        history_file = "chat_history.json"
                        if os.path.exists(history_file):
                            with open(history_file, "r", encoding="utf-8") as f:
                                history_data = json.load(f)
                        else:
                            history_data = {"messages": []}
                        
                        history_data["messages"].append(email_message)
                        
                        with open(history_file, "w", encoding="utf-8") as f:
                            json.dump(history_data, f, ensure_ascii=False, indent=2)
                        
                        print(f"[info]邮件摘要已直接添加到 chat_history.json（备用方式）")
                    except Exception as backup_e:
                        print(f"[error]备用方式保存邮件摘要也失败: {backup_e}")

            #Windows消息提醒 - 发送AI生成的摘要
            try:
                WindowsControl().send_notification(
                    title=f"新邮件来自 {sender}",
                    message=summary  # 使用AI生成的摘要而不是原始主题
                )
                print(f"[info]已发送邮件通知: {summary[:50]}...")
            except Exception as e:
                print(f"[error]发送Windows通知失败: {e}")
            
            # 发送到Live2D（如果启用）
            if self.config.get("live2d_listen", False):
                try:
                    l2d = L2DVEX(self.config.get("live2d_uri", "ws://"))
                    l2d.send_text_message(f"你有一封新邮件来自{sender}的新邮件！")
                    print(f"[info]邮件摘要已发送到 Live2D")
                except Exception as e:
                    print(f"[error]发送邮件摘要到 Live2D 失败: {e}")
            
            # 添加到聊天窗口（如果聊天窗口存在）
            if self.app and hasattr(self.app, 'chat_window') and self.app.chat_window:
                try:
                    # 使用Qt的信号槽机制安全地在主线程中更新UI
                    from PyQt5.QtCore import QTimer
                    
                    def add_to_chat():
                        if self.app.chat_window.isVisible():
                            self.app.chat_window.add_message(email_summary_content, is_user=False)
                    
                    # 在主线程中执行UI更新
                    QTimer.singleShot(0, add_to_chat)
                    print(f"[info]邮件摘要已添加到聊天窗口")
                except Exception as e:
                    print(f"[error]添加邮件摘要到聊天窗口失败: {e}")


    def run(self):
        """邮箱监听主循环"""
        print("[info]邮箱监听线程启动")
        
        # 加载邮箱配置
        self.email_monitors = self.load_email_configs()
        
        if not self.email_monitors:
            print("[warning]没有可用的邮箱配置，邮箱监听线程退出")
            return
        
        print(f"[info]开始监听 {len(self.email_monitors)} 个邮箱账户")
        
        while self.running:
            try:
                current_time = time.time()
                
                for monitor in self.email_monitors:
                    # 检查是否到了检查时间
                    if current_time - monitor['last_check'] >= self.check_interval:
                        try:
                            emails = monitor['utils'].get_today_unread_emails()
                            if emails:
                                self.handle_new_emails(emails, monitor['email'])
                            monitor['last_check'] = current_time
                        except Exception as e:
                            print(f"[error]检查邮箱 {monitor['email']} 失败: {e}")
                
                # 短暂休眠，避免CPU占用过高
                time.sleep(30)  # 每30秒检查一次是否有邮箱需要更新
                
            except Exception as e:
                print(f"[error]邮箱监听过程中发生错误: {e}")
                time.sleep(60)  # 出错后等待1分钟再重试
    
    def stop(self):
        """停止邮箱监听"""
        self.running = False
        print("[info]邮箱监听线程正在停止...")
    
    def get_email_summary(self):
        """
        获取所有监听邮箱的未读邮件摘要
        
        Returns:
            str: 所有邮箱的未读邮件摘要
        """
        if not self.email_monitors:
            return "暂无配置的邮箱"
        
        all_summaries = []
        for monitor in self.email_monitors:
            try:
                summary = monitor['utils'].get_unread_emails_summary()
                all_summaries.append(f"[info]邮箱 {monitor['email']}:\n{summary}")
            except Exception as e:
                all_summaries.append(f"[error]邮箱 {monitor['email']}: 获取摘要失败 - {e}")

        return "\n\n".join(all_summaries)
