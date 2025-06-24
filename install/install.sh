#!/bin/bash

echo "================================"
echo "liveAgent 快速安装脚本"
echo "================================"
echo

echo "检查Python版本..."
python3 --version
if [ $? -ne 0 ]; then
    echo "错误：未找到Python3，请先安装Python 3.8+"
    exit 1
fi

echo
echo "升级pip..."
python3 -m pip install --upgrade pip

echo
echo "安装项目依赖..."
pip3 install -r requirements.txt

if [ $? -eq 0 ]; then
    echo
    echo "================================"
    echo "安装完成！"
    echo "================================"
    echo
    echo "运行程序：python3 chat_part.py"
    echo
    echo "注意事项："
    echo "1. 首次运行会下载AI模型，请耐心等待"
    echo "2. 需要配置API密钥才能使用AI功能"
    echo "3. 某些功能可能需要管理员权限"
    echo
else
    echo
    echo "安装过程中出现错误，请检查网络连接和Python环境"
    exit 1
fi
