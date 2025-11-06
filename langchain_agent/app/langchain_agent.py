# langchain_agent.py
import logging
import os
from qdrant_client import QdrantClient
from app.embedding_utils import get_embedding
from app.qwen_api import get_qwen_client

# 配置
host = os.getenv('QDRANT_HOST', 'localhost')
port = os.getenv('QDRANT_PORT', 6333)
collection_name = os.getenv('COLLECTION_NAME', "anime_collections")

# 创建 Qdrant 客户端
client = QdrantClient(host=host, port=port)

# 日志配置
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# --- 检索 + 问答逻辑 ---
async def answer_question(user_question: str, k: int = 3) -> str:
    """
    用户提问，从 Qdrant 检索相关作品，然后调用千问API生成智能推荐
    """
    try:
        # 1. 向量检索阶段
        logger.info(f"开始处理用户问题: {user_question}")
        
        # 生成查询向量
        query_embedding = get_embedding(user_question)
        
        # 使用 Qdrant 客户端进行相似度搜索
        search_result = client.search(
            collection_name=collection_name,
            query_vector=query_embedding,
            limit=k,
            with_payload=True
        )
        
        # 2. 处理检索结果，构建丰富的动漫信息
        anime_info_list = []
        for hit in search_result:
            logger.info(f"检索到相关动漫: 相似度={hit.score:.3f}")
            payload = hit.payload
            
            if payload and payload.get('name_cn'):  # 确保有有效数据
                name_cn = payload.get('name_cn', '未知作品')
                name = payload.get('name', '')
                work_type = payload.get('type', '未知类型')
                tags = payload.get('tags', [])
                
                if isinstance(tags, str):
                    tags = [tags]
                
                # 提取描述信息
                description = payload.get('description', '')
                if not description:
                    # 从 full_text 中提取简介
                    full_text = payload.get('full_text', '')
                    if '简介：' in full_text:
                        description = full_text.split('简介：')[1] if len(full_text.split('简介：')) > 1 else '暂无简介'
                    else:
                        description = '暂无简介'
                
                # 提取图片信息
                poster_url = payload.get('poster_url', '')
                cover_url = payload.get('cover_url', '')
                screenshots = payload.get('screenshots', [])
                thumbnail_url = payload.get('thumbnail_url', '')
                
                # 提取扩展信息
                release_year = payload.get('release_year')
                episodes = payload.get('episodes')
                duration = payload.get('duration', '')
                rating = payload.get('rating')
                studio = payload.get('studio', '')
                director = payload.get('director', '')
                
                # 构建结构化的动漫信息
                anime_info = {
                    'name_cn': name_cn,
                    'name': name,
                    'type': work_type,
                    'tags': tags,
                    'description': description,
                    'score': hit.score,
                    # 图片信息
                    'poster_url': poster_url,
                    'cover_url': cover_url,
                    'screenshots': screenshots,
                    'thumbnail_url': thumbnail_url,
                    # 扩展信息
                    'release_year': release_year,
                    'episodes': episodes,
                    'duration': duration,
                    'rating': rating,
                    'studio': studio,
                    'director': director
                }
                anime_info_list.append(anime_info)
        
        # 3. 检查是否找到相关动漫
        if not anime_info_list:
            return "很抱歉，我没有找到相关的动漫作品信息。请尝试其他关键词或添加更多动漫数据到数据库中。"
        
        # 4. 构建丰富的上下文信息（包含图片和扩展信息）
        context_parts = []
        for i, anime in enumerate(anime_info_list, 1):
            context = f"{i}. **{anime['name_cn']}"
            if anime['name'] and anime['name'] != anime['name_cn']:
                context += f"**（{anime['name']}）"
            else:
                context += "**"
            
            context += f"\n   - 类型：{anime['type']}"
            context += f"\n   - 标签：{', '.join(anime['tags'])}"
            context += f"\n   - 简介：{anime['description']}"
            
            # 添加扩展信息
            if anime['release_year']:
                context += f"\n   - 发行年份：{anime['release_year']}"
            if anime['rating']:
                context += f"\n   - 评分：{anime['rating']}/10"
            if anime['studio']:
                context += f"\n   - 制作公司：{anime['studio']}"
            if anime['director']:
                context += f"\n   - 导演：{anime['director']}"
            if anime['episodes']:
                context += f"\n   - 集数：{anime['episodes']}集"
            if anime['duration']:
                context += f"\n   - 时长：{anime['duration']}"
            
            # 添加图片信息提示
            image_info = []
            if anime['poster_url']:
                image_info.append("主海报")
            if anime['cover_url']:
                image_info.append("封面图")
            if anime['screenshots']:
                image_info.append(f"{len(anime['screenshots'])}张截图")
            if anime['thumbnail_url']:
                image_info.append("缩略图")
            
            if image_info:
                context += f"\n   - 可用图片：{', '.join(image_info)}"
            
            context += f"\n   - 匹配度：{anime['score']:.2f}"
            
            context_parts.append(context)
        
        context = "\n\n".join(context_parts)
        logger.info(f"构建的上下文长度: {len(context)} 字符")
        
        # 5. 调用千问API生成智能推荐
        try:
            qwen_client = get_qwen_client()
            ai_response = await qwen_client.generate_response(
                user_question=user_question,
                context=context,
                temperature=0.7,
                max_tokens=1000
            )
            logger.info("千问API调用成功")
            return ai_response
            
        except Exception as llm_error:
            logger.error(f"千问API调用失败，使用备用回答: {llm_error}")
            # 备用方案：返回格式化的检索结果
            fallback_response = f"🎌 根据您的问题「{user_question}」，我为您推荐以下动漫作品：\n\n{context}\n\n💫 希望这些推荐对您有帮助！如需更详细信息，请告诉我~"
            return fallback_response

    except Exception as e:
        logger.exception("answer_question 执行异常:")
        raise


async def get_formatted_recommendations(user_question: str, k: int = 3, base_url: str = "") -> dict:
    """
    返回格式化的推荐数据，包含完整的图片链接和结构化信息
    """
    import time
    start_time = time.time()
    
    try:
        # 1. 向量检索阶段
        logger.info(f"开始格式化推荐查询: {user_question}")
        
        # 生成查询向量
        query_embedding = get_embedding(user_question)
        
        # 执行向量搜索
        search_results = client.search(
            collection_name=collection_name,
            query_vector=query_embedding,
            limit=k,
            score_threshold=0.3
        )
        
        if not search_results:
            return {
                "answer": f"抱歉，没有找到与「{user_question}」相关的动漫作品。请尝试使用其他关键词搜索。",
                "recommendations": [],
                "total_found": 0,
                "query_time": round(time.time() - start_time, 3)
            }
        
        # 2. 格式化推荐数据
        formatted_recommendations = []
        context_parts = []
        
        for result in search_results:
            anime = result.payload
            score = result.score
            
            # 构建图片链接
            def build_image_url(relative_path: str) -> str:
                if not relative_path:
                    return None
                if relative_path.startswith('http'):
                    return relative_path
                return f"{base_url.rstrip('/')}{relative_path}" if base_url else relative_path
            
            # 确定主要封面图片
            cover_image = None
            if anime.get('image_medium'):
                cover_image = build_image_url(anime['image_medium'])
            elif anime.get('image_large'):
                cover_image = build_image_url(anime['image_large'])
            elif anime.get('cover_url'):
                cover_image = anime['cover_url']
            elif anime.get('poster_url'):
                cover_image = anime['poster_url']
            
            # 格式化单个推荐项
            formatted_item = {
                "uuid": anime.get('uuid'),
                "title_zh": anime.get('title_zh') or anime.get('name_cn'),
                "title_en": anime.get('title_en') or anime.get('name'),
                "title_jp": anime.get('title_jp'),
                "description_zh": anime.get('description_zh') or anime.get('description'),
                "description_en": anime.get('description_en'),
                
                # 媒体信息
                "media_type": anime.get('media_type') or anime.get('format') or anime.get('type'),
                "status": anime.get('status'),
                "episodes": anime.get('episodes'),
                "year": anime.get('year') or anime.get('season_year') or anime.get('release_year'),
                "season": anime.get('season'),
                
                # 评分信息
                "average_score": anime.get('average_score'),
                "rating": anime.get('rating'),
                "popularity": anime.get('popularity'),
                
                # 分类
                "genres": anime.get('genres', []),
                "tags": anime.get('tags', []),
                
                # 图片信息
                "cover_image": cover_image,
                "image_large": build_image_url(anime.get('image_large')),
                "image_medium": build_image_url(anime.get('image_medium')),
                "image_small": build_image_url(anime.get('image_small')),
                "image_grid": build_image_url(anime.get('image_grid')),
                "thumbnail": build_image_url(anime.get('image_common')) or anime.get('thumbnail_url'),
                
                # 制作信息
                "studio": anime.get('studio'),
                "source_type": anime.get('source_type'),
                
                # 匹配信息
                "match_score": round(score, 3),
                
                # 兼容字段
                "name_cn": anime.get('name_cn'),
                "name": anime.get('name'),
                "type": anime.get('type'),
                "poster_url": anime.get('poster_url'),
                "release_year": anime.get('release_year')
            }
            
            # 清理空值
            formatted_item = {k: v for k, v in formatted_item.items() if v is not None and v != [] and v != ""}
            formatted_recommendations.append(formatted_item)
            
            # 为AI回答构建上下文
            title = formatted_item.get('title_zh') or formatted_item.get('name_cn', '未知作品')
            description = formatted_item.get('description_zh') or '暂无简介'
            description = description[:100] if description else '暂无简介'
            context_parts.append(f"《{title}》- {description}...")
        
        # 3. 生成AI回答
        context = "\n".join(context_parts)
        try:
            qwen_client = get_qwen_client()
            ai_response = await qwen_client.generate_response(
                user_question=user_question,
                context=context,
                temperature=0.7,
                max_tokens=800
            )
        except Exception as llm_error:
            logger.error(f"千问API调用失败: {llm_error}")
            ai_response = f"🎌 根据您的问题「{user_question}」，为您找到了 {len(formatted_recommendations)} 部相关的动漫作品，详情请查看推荐列表。"
        
        query_time = round(time.time() - start_time, 3)
        
        return {
            "answer": ai_response,
            "recommendations": formatted_recommendations,
            "total_found": len(formatted_recommendations),
            "query_time": query_time
        }
        
    except Exception as e:
        logger.exception("get_formatted_recommendations 执行异常:")
        return {
            "answer": f"查询过程中出现错误: {str(e)}",
            "recommendations": [],
            "total_found": 0,
            "query_time": round(time.time() - start_time, 3)
        }


async def get_streaming_recommendations(user_question: str, k: int = 3, base_url: str = "") -> dict:
    """
    返回流式推荐数据，支持实时文案生成和图片触发
    """
    import time
    start_time = time.time()
    
    try:
        # 1. 向量检索阶段
        logger.info(f"开始流式推荐查询: {user_question}")
        
        # 生成查询向量
        query_embedding = get_embedding(user_question)
        
        # 执行向量搜索
        search_results = client.search(
            collection_name=collection_name,
            query_vector=query_embedding,
            limit=k,
            score_threshold=0.3
        )
        
        if not search_results:
            return {
                "streaming_answer": False,
                "answer": f"抱歉，没有找到与「{user_question}」相关的动漫作品。",
                "recommendations": [],
                "total_found": 0,
                "query_time": round(time.time() - start_time, 3)
            }
        
        # 2. 准备动漫列表数据
        anime_list = []
        for result in search_results:
            anime = result.payload
            score = result.score
            
            # 构建图片链接
            def build_image_url(relative_path: str) -> str:
                if not relative_path:
                    return None
                if relative_path.startswith('http'):
                    return relative_path
                return f"{base_url.rstrip('/')}{relative_path}" if base_url else relative_path
            
            cover_image = None
            if anime.get('image_medium'):
                cover_image = build_image_url(anime['image_medium'])
            elif anime.get('cover_url'):
                cover_image = anime['cover_url']
            
            anime_data = {
                "uuid": anime.get('uuid') or anime.get('id'),
                "title_zh": anime.get('title_zh') or anime.get('name_cn'),
                "description_zh": anime.get('description_zh') or anime.get('description'),
                "cover_image": cover_image,
                "average_score": anime.get('average_score') or anime.get('rating'),
                "match_score": round(score, 3)
            }
            anime_list.append(anime_data)
        
        query_time = round(time.time() - start_time, 3)
        
        return {
            "streaming_answer": True,
            "anime_list": anime_list,
            "total_found": len(anime_list),
            "query_time": query_time,
            "user_question": user_question
        }
        
    except Exception as e:
        logger.exception("get_streaming_recommendations 执行异常:")
        return {
            "streaming_answer": False,
            "answer": f"流式查询过程中出现错误: {str(e)}",
            "recommendations": [],
            "total_found": 0,
            "query_time": round(time.time() - start_time, 3)
        }