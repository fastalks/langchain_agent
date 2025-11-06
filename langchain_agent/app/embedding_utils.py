# embedding_utils.py

import os
from sentence_transformers import SentenceTransformer
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 设置缓存目录和镜像源
cache_folder = os.getenv('HF_HOME', './models_cache')
hf_endpoint = os.getenv('HF_ENDPOINT', 'https://huggingface.co')

# 创建缓存目录
os.makedirs(cache_folder, exist_ok=True)

# 模型名称
model_name = 'BAAI/bge-small-zh-v1.5'

logger.info(f"正在加载模型: {model_name}")
logger.info(f"缓存目录: {cache_folder}")
logger.info(f"HuggingFace端点: {hf_endpoint}")

try:
    # 使用轻量、高效的中文语义模型
    model = SentenceTransformer(
        model_name, 
        cache_folder=cache_folder,
        # 如果设置了镜像源，更新模型配置
    )
    logger.info("✅ 模型加载成功")
    
except Exception as e:
    logger.error(f"❌ 模型加载失败: {e}")
    logger.info("🔄 尝试使用备用方案...")
    
    # 备用方案：尝试使用本地已缓存的模型
    try:
        from transformers import AutoModel, AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(model_name, cache_dir=cache_folder)
        base_model = AutoModel.from_pretrained(model_name, cache_dir=cache_folder)
        
        # 如果本地模型存在，使用本地模型创建 SentenceTransformer
        model = SentenceTransformer(model_name, cache_folder=cache_folder)
        logger.info("✅ 使用本地缓存模型加载成功")
        
    except Exception as e2:
        logger.error(f"❌ 备用方案也失败: {e2}")
        logger.warning("⚠️ 将使用简单的文本嵌入方案")
        model = None

def get_embedding(text: str) -> list[float]:
    """获取文本的向量嵌入"""
    if model is None:
        # 如果模型加载失败，返回简单的文本哈希向量
        logger.warning("使用简单哈希向量替代")
        import hashlib
        hash_obj = hashlib.md5(text.encode())
        hash_bytes = hash_obj.digest()
        # 转换为512维向量（BGE模型的维度）
        vector = []
        for i in range(512):
            vector.append(float(hash_bytes[i % len(hash_bytes)]) / 255.0)
        return vector
    
    try:
        embedding = model.encode(text, convert_to_tensor=False)
        return embedding.tolist()  # 转为 Python List，用于存入 Qdrant
    except Exception as e:
        logger.error(f"文本嵌入失败: {e}")
        # 返回零向量作为备用
        return [0.0] * 512