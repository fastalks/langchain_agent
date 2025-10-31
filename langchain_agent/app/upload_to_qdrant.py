# upload_to_qdrant.py

from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http import models
from typing import List, Dict
import numpy as np


from langchain.embeddings import HuggingFaceEmbeddings
from qdrant_client import QdrantClient
from qdrant_client.http import models
from typing import List, Dict
import numpy as np
from app.embedding_utils import get_embedding

def prepare_works_for_langchain(works: List[Dict]) -> List[Dict]:
    data = []
    for work in works:
        text = f"作品名称：{work['name_cn'] or ''}，类型：{work['type'] or ''}，标签：{', '.join(work['tags'])}，简介：{work['description'] or ''}"
        embedding = get_embedding(text)
        data.append({
            "page_content": work["description"],  # 关键：简介作为主要内容
            "metadata": {
                "name_cn": work["name_cn"],
                "name": work["name"],
                "tags": work["tags"],
                "type": work["type"],
                "id": work["id"]
            },
            "embedding": embedding
        })
    return data

def upload_to_qdrant_using_langchain(works_data: List[Dict]):
    client = QdrantClient(host="localhost", port=6333)
    collection_name = "anime_collections"

    # 确保集合存在
    client.recreate_collection(
        collection_name=collection_name,
        vectors_config=models.VectorParams(size=512, distance=models.Distance.COSINE)
    )

    # 使用 LangChain 的 Qdrant 接口
    # embeddings = None  # 我们自己传入了 embedding，见下方

    embedding_model_name = "BAAI/bge-small-zh-v1.5" 
    embeddings = HuggingFaceEmbeddings(model_name=embedding_model_name)

    vectorstore = QdrantVectorStore(
    client=client,
    collection_name=collection_name,
    embedding=embeddings
    )


    # 构造 texts, embeddings 和 metadatas
    texts = []
    embeddings_list = []
    metadatas = []

    for item in works_data:
        texts.append(item["page_content"])
        embeddings_list.append(item["embedding"])
        metadatas.append(item["metadata"])

    # 使用 add_texts 并传入 embeddings 和 metadatas
    vectorstore.add_texts(
        texts=texts,
        embeddings=embeddings_list,  # 自己传入 embeddings
        metadatas=metadatas
    )

    print(f"✅ 成功使用 LangChain 接口上传 {len(texts)} 条数据到 Qdrant")

# if __name__ == "__main__":

    # works_data = prepare_works_for_langchain(works)
    # upload_to_qdrant_using_langchain(works_data)