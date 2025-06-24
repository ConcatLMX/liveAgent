# faiss_utils.py
import os
import json
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
import time
class VectorDatabase:
    def __init__(self, index_dir="./vector_db"):
        """
        初始化向量数据库
        """
        self.index_dir = index_dir
        os.makedirs(index_dir, exist_ok=True)

        # 从配置文件读取模型名称
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
            model_name = config.get('model', 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
        except Exception as e:
            print(f"[warning]读取配置文件失败，使用默认模型: {e}")
            model_name = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'

        # 动态生成本地模型路径
        # 提取模型名称的最后部分作为文件夹名
        model_folder_name = model_name.split('/')[-1] if '/' in model_name else model_name
        local_model_path = os.path.join('local_models', model_folder_name)

        print(f"[info]使用模型: {model_name}")
        print(f"[info]本地路径: {local_model_path}")

        # 检查本地是否有模型，如果没有则下载
        if os.path.exists(local_model_path):
            print("[info]使用本地缓存的模型")
            self.model = SentenceTransformer(local_model_path)
        else:
            print("[info]首次使用，下载模型中...")
            self.model = SentenceTransformer(model_name)
            # 创建目录并保存模型
            os.makedirs('local_models', exist_ok=True)
            self.model.save(local_model_path)
            print(f"[info]模型已保存到: {local_model_path}")

        self.dimension = self.model.get_sentence_embedding_dimension()

        # 文件路径
        self.index_path = os.path.join(index_dir, "chat_index.faiss")
        self.metadata_path = os.path.join(index_dir, "metadata.json")

        # 初始化索引
        if os.path.exists(self.index_path):
            self.index = faiss.read_index(self.index_path)
            with open(self.metadata_path, 'r', encoding='utf-8') as f:
                self.metadata = json.load(f)
            print(f"[info]加载原有索引: {len(self.metadata)}条记录")
        else:
            self.index = faiss.IndexFlatL2(self.dimension)
            self.metadata = []
            print("[info]创建新索引")

    def embed(self, text):
        """文本向量化 (支持字符串或列表)"""
        return self.model.encode(text)

    def add_message(self, message_id, role, content, timestamp):
        """添加消息到向量数据库"""
        embedding = self.embed([content])[0]
        self.index.add(np.array([embedding]))

        self.metadata.append({
            "id": message_id,
            "role": role,
            "content": content,
            "timestamp": timestamp,
            "vector_idx": self.index.ntotal - 1
        })

    def rebuild_with_add_message(self, messages):
        """重建向量数据库"""
        try:
            self._rebuilding = True           #标志位
            print("[info]开始重建向量数据库，方法: add_message")
            start_time = time.time()

            # 创建新的元数据和索引
            new_metadata = []

            # 创建新索引
            dimension = self.model.get_sentence_embedding_dimension()
            new_index = faiss.IndexFlatL2(dimension)

            # 临时保存当前索引和元数据
            old_index = self.index
            old_metadata = self.metadata

            # 设置临时索引和元数据用于重建
            self.index = new_index
            self.metadata = new_metadata

            # 添加所有消息
            for msg in messages:
                # 生成唯一ID
                msg_id = msg.get("id", f"{msg['timestamp']}_{msg['role']}")

                # 使用add_message方法添加消息
                self.add_message(
                    msg_id,
                    msg["role"],
                    msg["content"],
                    msg["timestamp"]
                )

            # 保存重建后的数据库
            self.save()

            end_time = time.time()
            print(f"[info]向量数据库重建完成！用时: {end_time - start_time:.2f}秒")
            print(f"[info]重建后记录数: {len(self.metadata)}")

        except Exception as e:
            print(f"[error]重建向量数据库出错: {str(e)[:200]}，回滚到原数据库")
            # 恢复原始索引和元数据
            self.index = old_index
            self.metadata = old_metadata
        finally:
            self._rebuilding = False

    def search(self, query, k=5, threshold=0.4):
        """相似性搜索"""
        # 检查索引是否为空                                                                                              =
        if self.index is None or self.index.ntotal == 0:
            print("[warning]搜索时索引为空")
            return []

        # 检查元数据与索引是否一致
        if len(self.metadata) != self.index.ntotal:
            print(f"[error]元数据长度({len(self.metadata)})与索引大小({self.index.ntotal})不一致!")
            return []

        try:
            # 获取查询向量
            query_embed = self.embed([query])[0]
            query_vector = np.array([query_embed])

            # Faiss搜索 (返回距离和索引)
            distances, indices = self.index.search(query_vector, k)

            results = []

            # 遍历所有结果
            for idx, dist in zip(indices[0], distances[0]):
                # 跳过无效索引
                if idx < 0 or idx >= self.index.ntotal:
                    continue

                # 跳过元数据范围之外
                if idx >= len(self.metadata):
                    print(f"[warning]索引 {idx} 超出元数据范围(0-{len(self.metadata) - 1})")
                    continue

                # 计算相似度
                similarity = max(0, 1.0 - dist / 10.0)

                if similarity >= threshold:
                    # 创建结果的副本（避免修改原始元数据）
                    result = {
                        "id": self.metadata[idx]["id"],
                        "role": self.metadata[idx]["role"],
                        "content": self.metadata[idx]["content"],
                        "timestamp": self.metadata[idx]["timestamp"],
                        "similarity": similarity
                    }
                    results.append(result)

            # 按相似度排序并返回前k个
            sorted_results = sorted(results, key=lambda x: x["similarity"], reverse=True)
            return sorted_results[:min(k, len(sorted_results))]

        except Exception as e:
            print(f"[error]搜索过程中出错: {str(e)[:200]}")
            return []  # 出错时返回空列表

    def save(self):
        """保存索引和元数据"""
        faiss.write_index(self.index, self.index_path)
        with open(self.metadata_path, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, ensure_ascii=False, indent=2)
        print(f"[info]保存向量数据库: {len(self.metadata)}条记录")

    def clear(self):
        """清空数据库并重建空索引"""
        print("[info]开始清空数据库...")

        try:
            # 1. 清空内存数据
            self.index = None
            self.metadata = []

            # 2. 确保目录存在
            os.makedirs(self.index_dir, exist_ok=True)

            # 3. 创建新的空索引
            self.index = faiss.IndexFlatL2(self.dimension)

            # 4. 保存空数据库
            # 保存索引
            faiss.write_index(self.index, self.index_path)

            # 保存空元数据
            with open(self.metadata_path, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)

            # 5. 更新内存状态
            self.metadata = []

            print("[info]向量数据库已完全清空并重建")
            return True
        except Exception as e:
            # 错误处理：尝试恢复可用状态
            print(f"[error]清空数据库时出错: {e}")

            # 尝试加载之前的数据库（如果存在）
            if os.path.exists(self.index_path) and os.path.exists(self.metadata_path):
                try:
                    self.index = faiss.read_index(self.index_path)
                    with open(self.metadata_path, 'r', encoding='utf-8') as f:
                        self.metadata = json.load(f)
                    print("[info]已恢复之前的数据库状态")
                except:
                    print("[error]无法恢复数据库状态")

            return False

    def size(self):
        """返回当前存储的消息数量"""
        return len(self.metadata)