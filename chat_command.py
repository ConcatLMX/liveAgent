from faiss_utils import VectorDatabase
import json



def cmd_exec(vector_db: VectorDatabase,msg):
    """
    执行命令
    """
    cmdd = Command(vector_db)
    if msg == "--help()":
        cmdd.help()
    elif msg == "--vb_clear()":
        cmdd.vb_clear()
    elif msg == "--history_clear()":
        cmdd.history_clear()
    elif msg == "--show_parameters()":
        cmdd.show_parameters()

class Command:
    def __init__(self, vector_db: VectorDatabase):
        self.vector_db = vector_db


    def help(self):
        """帮助文档"""
        print("[help]")
        print(">对话框输入以下命令执行相应操作：")
        print(">--help: 显示帮助信息")
        print(">--vb_clear(): 清除向量数据库并重建")
        print(">--history_clear(): 清除对话历史")
        print(">--show_parameters(): 显示当前运行参数")


    def vb_clear(self):
        """清除向量数据库并重建"""
        try:
            self.vector_db.clear()
        except Exception as e:
            print(f"[error]清空向量数据库时出错: {str(e)}")


    def history_clear(self):
        """清除对话历史"""
        with open('chat_history.json', 'w') as f:
            json.dump({}, f)
        print("[info]对话历史已清除")


    def show_parameters(self):
        """显示运行参数"""
        print("[parameters]当前运行参数：")
        print("> ai_api: Deepseek-v3")
        print("> vector_db: Faiss")
        print("> embed_model: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        print("> db: JSON")