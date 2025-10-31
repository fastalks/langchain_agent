# embedding_utils.py

from sentence_transformers import SentenceTransformer

# 使用轻量、高效的中文语义模型
model = SentenceTransformer('BAAI/bge-small-zh-v1.5')

def get_embedding(text: str) -> list[float]:
    embedding = model.encode(text, convert_to_tensor=False)
    return embedding.tolist()  # 转为 Python List，用于存入 Qdrant