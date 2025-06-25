# liveAgent

长记忆无感AI助手

## 主要特点

- 长期记忆和记忆更新机制（FAISS+JSON）

- 自定义相关机制

- 自定义AI设定

- 接入大模型api

- 接收总结邮件

- 可连接Live2DViewerEX

## 安装步骤

Python版本要求

- Python 3.12

### 1. 克隆项目

```bash
git clone https://github.com/ConcatLMX/liveAgent.git
cd liveAgent
```

### 2. 创建虚拟环境（推荐）

```bash
# 创建虚拟环境
python -m venv venv
# 推荐使用conda
conda create -n venv python=3.12

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# conda:
conda activate venv 
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 手动下载模型（可选）

首次使用新模型时会自动从Huggingface下载

如果网络连接有问题，可以手动下载sentence-transformers模型：

```bash
# 创建模型目录
mkdir -p local_models

# 从Hugging Face手动下载模型到local_models目录
# 例如：paraphrase-multilingual-MiniLM-L12-v2
```

### 5. 运行程序

```bash
python chat_part.py
```

### 配置文件

程序首次运行会创建 `config.json` 配置文件

```python
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
```

## 可能遇到的问题

### 1. 邮箱管理

某些邮件服务器（如 163邮箱）在客户端连接时会返回 "unsafe login" 错误，这是因为服务器要求客户端在连接时发送 IMAP ID 信息以识别客户端类型。程序已在 `EmailUtils` 类中添加了 IMAP ID 支持，完全兼容邮件服务器的要求。

#### 配置方式

- 使用默认配置

- 自定义配置：
  
  在 `data.json` 中添加 `imap_id` 字段：
  
  ```json
  {
    "emails": [
      {
        "email": "your-email@xx.com",
        "password": "your-auth-code",
        "imap_server": "imap.xxx.com",
        "imap_id": {
          "name": "myname",
          "version": "1.0.0",
          "vendor": "myclient",
          "support-email": "testmail@test.com"
        }
      }
    ]
  }
  ```

## 注意事项

1. 确保有稳定的网络连接用于下载模型
2. 首次运行可能需要一些时间下载sentence-transformers模型                                             
3. 使用Live2D功能需要确保Live2D Viewer EX在运行并开放端口                                                                            
4. 邮件功能需要配置IMAP服务器信息
