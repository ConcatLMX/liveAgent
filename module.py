import json
import os

def is_json_file_empty(file_path):
    # 检查文件是否存在
    if not os.path.exists(file_path) or os.path.getsize(file_path)==0:
        return True

    # 读取文件内容
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read().strip()

    # 如果去除空格后为空字符串
    if content == "":
        return True

    # 如果是空对象或空数组的字符串
    if content == "{}" or content == "[]":
        return True

    # 尝试解析JSON
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        # 无法解析，但内容非空，所以我们认为不是空（但也可以根据需求返回True，这里按非空处理）
        return False

    # 判断解析后的数据类型和长度
    if isinstance(data, (dict, list)):
        return len(data) == 0
    else:
        # 其他类型（数字、字符串、布尔值、null）都视为非空
        return False