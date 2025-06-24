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


class EmailUtils:
    """邮件处理工具类"""
    
    def __init__(self, imap_server='', username='', password=''):
        """
        初始化邮件工具
        
        Args:
            imap_server: IMAP服务器地址
            username: 邮箱用户名
            password: 邮箱密码或授权码
        """
        self.imap_server = imap_server
        self.username = username
        self.password = password
        self.uids_seen = set()  # 已处理的邮件UID集合
        
    def connect(self):
        """连接到IMAP服务器"""
        try:
            self.imap_object = imapclient.IMAPClient(self.imap_server, ssl=True)
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
            str: 提取的纯文本内容
        """
        try:
            soup = BeautifulSoup(html, 'lxml')
            return soup.get_text(strip=True)
        except Exception as e:
            print(f"[error]解析HTML内容失败: {e}")
            return html  # 如果解析失败，返回原始HTML
    
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
    
    def update_credentials(self, imap_server, username, password):
        """
        更新邮件服务器凭据
        
        Args:
            imap_server: IMAP服务器地址
            username: 邮箱用户名
            password: 邮箱密码或授权码
        """
        self.imap_server = imap_server
        self.username = username
        self.password = password
        self.uids_seen.clear()  # 清空已处理的邮件记录


class EmailMonitorThread(threading.Thread):
    """邮箱监听线程类"""
    
    def __init__(self, email_data_file="data.json", check_interval=300):
        """
        初始化邮箱监听线程
        
        Args:
            email_data_file: 邮箱配置文件路径
            check_interval: 检查邮件的间隔时间（秒），默认5分钟
        """
        super().__init__(daemon=True)
        self.email_data_file = email_data_file
        self.check_interval = check_interval
        self.email_monitors = []
        self.running = True

        #读取config.json
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
            
            emails_config = data.get("emails", [])
            if not emails_config:
                print("[warning]未配置邮箱账户，跳过邮箱监听")
                return []
            
            # 为每个邮箱创建监听器
            monitors = []
            for email_config in emails_config:
                email_utils = EmailUtils(
                    imap_server=email_config.get("imap_server", ""),
                    username=email_config.get("email", ""),
                    password=email_config.get("password", "")
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
            summary = AiChat().general_summary(f"用户收到了一封邮件: {subject} 来自 {sender} 的邮件内容: {email['content']}，请进行总结。")
            if not self.config.get("live2d_listen", False):
                return
            l2d = L2DVEX(self.config.get("live2d_uri", "ws://"))
            l2d.send_text_message(summary)


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
