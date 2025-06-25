# liveAgent

这是一个可以随时随地呼出的便携ai

## 主要特点

- 长期记忆和记忆更新机制（FAISS+JSON）

- 自定义Embed对话的模型

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
# Linux/Mac:
source venv/bin/activate

```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 手动下载模型（可选）

首次使用新模型时会自动下载

如果网络连接有问题，可以手动下载sentence-transformers模型：

```bash
# 创建模型目录
mkdir -p local_models

# 从Hugging Face手动下载模型到local_models目录
# 例如：paraphrase-multilingual-MiniLM-L12-v2
```

## 可能遇到的问题

### 1. PyQt5安装问题

如果PyQt5安装失败，可以尝试：

```bash
pip install PyQt5 --no-cache-dir
```

### 2. faiss安装问题

如果需要GPU版本：

```bash
pip uninstall faiss-cpu
pip install faiss-gpu
```

### 3. Windows上keyboard权限问题

需要以管理员身份运行Python程序

## 运行程序

```bash
python chat_part.py
```

## 配置文件

程序首次运行会创建 `config.json` 配置文件，包含：

- API密钥和基础URL
- 热键设置
- 模型配置
- Live2D设置等

## 注意事项

1. 确保有稳定的网络连接用于下载模型
2. 首次运行可能需要一些时间下载sentence-transformers模型
3. 使用Live2D功能需要确保Live2D Viewer EX在运行并开启WebSocket API
4. 邮件功能需要配置IMAP服务器信息
