from win10toast import ToastNotifier


class WindowsControl:
    """Windows系统控制类，用于发送系统消息提醒等功能"""
    
    def __init__(self):
        self.toaster = ToastNotifier()

    def send_notification(self, title: str, message: str, duration: int = 5) -> bool:
        """
        发送Windows Toast通知
        
        Args:
            title (str): 通知标题
            message (str): 通知内容
            duration (int): 显示持续时间（秒），默认5秒
            
        Returns:
            bool: 发送成功返回True，失败返回False
        """
        try:
            self.toaster.show_toast(
                title=title,
                msg=message,
                duration=duration,
                threaded=True
            )
            return True
            
        except Exception as e:
            print(f"[error]发送通知时出现错误: {e}")
            return False