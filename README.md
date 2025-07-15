# liveAgent

长记忆无感AI助手

## 主要特点

- 长期记忆和记忆更新机制

- 自定义模型

- 自定义AI设定

- 邮件提醒

- Markdown渲染

- 可连接Live2DViewerEX

- 现代化的交互界面

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
# 推荐使用conda
conda create -n agent python=3.12
conda activate agent
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 手动下载模型（可选）

首次使用新模型时会自动从Huggingface下载

如果网络连接有问题，可以手动下载sentence-transformers模型

### 5. 运行程序

```bash
python chat_part.py
```

## 配置文件

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

## 注意事项

1. 确保有稳定的网络连接用于下载模型
2. 首次运行可能需要一些时间下载sentence-transformers模型                                             
3. 使用Live2D功能需要确保Live2D Viewer EX在运行并开放端口                                                                        
