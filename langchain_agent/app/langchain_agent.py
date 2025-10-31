# langchain_agent.py
import logging
import os
from langchain_ollama import OllamaLLM
from langchain_huggingface import HuggingFaceEmbeddings
from qdrant_client import QdrantClient
from langchain_qdrant import  QdrantVectorStore


# COLLECTION_PORT
host = os.environ.get('COLLECTION_HOST','localhost')
port = os.environ.get('COLLECTION_PORT',6333)
collection_name = os.environ.get('COLLECTION_NAME',"anime_collections")

# 1. 创建 Qdrant 官方客户端
client = QdrantClient(host=host, port=port)

# 2. 创建 Embeddings 实例（必须！不能为 None）
embedding_model_name = "BAAI/bge-small-zh-v1.5" 
embeddings = HuggingFaceEmbeddings(model_name=embedding_model_name)


qdrant = QdrantVectorStore(
    client=client,
    collection_name=collection_name,
    embedding=embeddings
)


# 使用 Ollama 作为 LLM（比如你本地跑了 llama2 / mistral 等模型）
# llm = OllamaLLM(model="llama2", temperature=0.7)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# --- 检索 + 问答逻辑 ---
async def answer_question(user_question: str, k: int = 3) -> str:
    """
    用户提问，从 Qdrant 检索相关作品，然后调用 LLM 生成回答
    """
    try:
        # 1. 从 Qdrant 检索最相关的 k 个作品
        # docs = vectorstore.similarity_search(user_question, k=k)
        docs = qdrant.similarity_search(user_question, k=3)
        # 2. 拼接作品信息为上下文
        context_list = []
        for doc in docs:
            print(doc)
            payload = doc.metadata  # Qdrant 中存的作品信息（name_cn, description, tags, type）
            context = f"作品名称：{payload.get('name_cn', '未知')}，简介：{payload.get('description', '')}，标签：{', '.join(payload.get('tags', []))}，类型：{payload.get('type', '')}"
            context_list.append(context)

        context = "\n\n".join(context_list)
        print(context)
        # 3. 构造 Prompt（你可以优化这个模板！）
        prompt_template = """
        用户问：{question}

        根据以下番剧信息，帮我回答：

        {context}

        请用中文推荐合适的番剧，并给出理由，语言自然、友好。
        """

        prompt = prompt_template.format(question=user_question, context=context)

        # 4. 调用 LLM 生成回答
        # answer = await llm.ainvoke(prompt)

        return context

    except Exception as e:
        logger.exception("Error in answer_question:")
        raise  # 重新抛出，让 FastAPI 捕获并返回 500