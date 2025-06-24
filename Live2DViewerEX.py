import json
from websocket import create_connection

class L2DVEX:
    def __init__(self, uri: str):
        self.uri =uri                          #ws://127.0.0.1:10086/api

    def send_text_message(self,text: str):
        '''发送文本消息'''
        uri = self.uri
        data = {
            "msg": 11000,
            "msgId": 1,
            "data": {
                "id": 0,
                "text": text,
                "textFrameColor": 0x000000,
                "textColor": 0xFFFFFF,
                "duration": 15000
            }
        }

        # 尝试发出json消息
        try:
            ws = create_connection(uri)
            ws.send(json.dumps(data))
        except Exception as e:
            print("[error]L2D错误：", str(e))