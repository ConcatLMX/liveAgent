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
            # 确保参数不为空且为字符串类型
            title = str(title) if title is not None else "通知"
            message = str(message) if message is not None else "无内容"
            duration = int(duration) if duration is not None else 5
            
            # 限制标题和消息长度，避免显示问题
            if len(title) > 64:
                title = title[:61] + "..."
            if len(message) > 256:
                message = message[:253] + "..."
            
            self.toaster.show_toast(
                title=title,
                msg=message,
                duration=duration,
                threaded=True
            )
            return True
            
        except Exception as e:
            print(f"[error]发送通知时出现错误: {e}")
            # 如果win10toast失败，尝试使用系统级别的fallback
            try:
                import subprocess
                # 使用PowerShell作为备用通知方式
                ps_command = f'''
                Add-Type -AssemblyName System.Windows.Forms
                $notify = New-Object System.Windows.Forms.NotifyIcon
                $notify.Icon = [System.Drawing.SystemIcons]::Information
                $notify.BalloonTipTitle = "{title}"
                $notify.BalloonTipText = "{message}"
                $notify.Visible = $true
                $notify.ShowBalloonTip(5000)
                '''
                subprocess.run(["powershell", "-Command", ps_command], 
                             capture_output=True, text=True, timeout=10)
                print("[info]使用PowerShell备用通知方式")
                return True
            except Exception as fallback_e:
                print(f"[error]备用通知方式也失败: {fallback_e}")
                return False