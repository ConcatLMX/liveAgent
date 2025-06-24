import json
from openai import OpenAI

class AiChat:
    def __init__(self):
        # 读取 system_prompt.json
        try:
            with open('system_prompt.json', 'r', encoding='utf-8') as f:
                self.system_prompt = json.load(f)
        except Exception as e:
            print(f"[error]读取 system_prompt.json 时发生错误: {e}")
            self.system_prompt = {}

        # 获取 preset 键值
        self.preset = self.system_prompt.get('preset', '')

        # 读取 config.json
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        except Exception as e:
            print(f"[error]读取 config.json 时发生错误: {e}")
            self.config = {}        
        
        # 获取 config 配置键值
        self.api_url = self.config.get('api_baseurl')
        self.api_key = self.config.get('apikey')
        self.model = self.config.get('api_model', 'gpt-4o')
        self.temperature = self.config.get('temperature', 0.7)

        # 初始化 client
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.api_url,
        )        # 系统消息和对话记录
        self.system_messages =[{"role": "system",
                                "content": self.preset}]

    def get_message(self, message: list) -> str:
        """发送请求并返回 AI 回复"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=message,
                temperature=self.temperature,
            )

            return response.choices[0].message.content
        except Exception as e:
            print(f"[error]AI 回复生成失败: {e}")
            return "抱歉，我现在无法回复您的消息，请稍后再试。"
