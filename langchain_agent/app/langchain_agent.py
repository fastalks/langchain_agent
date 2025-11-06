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
    增强版：支持tag和genre精准匹配
    """
    import time
    start_time = time.time()
    
    try:
        # 1. 向量检索阶段 + Tag匹配增强
        logger.info(f"开始格式化推荐查询: {user_question}")
        
        # 生成查询向量
        query_embedding = get_embedding(user_question)
        
        # 先尝试标准向量搜索
        search_results = client.search(
            collection_name=collection_name,
            query_vector=query_embedding,
            limit=k * 2,  # 获取更多结果以便后续过滤
            score_threshold=0.2  # 降低阈值，获取更多候选
        )
        
        # 2. 增强搜索：tag、genre和年份匹配
        enhanced_results = []
        tag_boost_keywords = {
            "动作": ["Action", "动作", "战斗", "打斗"],
            "爱情": ["Romance", "爱情", "恋爱", "浪漫"],
            "喜剧": ["Comedy", "喜剧", "搞笑", "幽默"],
            "恐怖": ["Horror", "恐怖", "惊悚"],
            "科幻": ["Sci-Fi", "科幻", "未来"],
            "奇幻": ["Fantasy", "奇幻", "魔法"],
            "冒险": ["Adventure", "冒险", "探险"],
            "悬疑": ["Mystery", "悬疑", "推理"],
            "热血": ["热血", "燃", "励志"],
            "治愈": ["治愈", "温馨", "感人"],
            "校园": ["校园", "学校", "青春"],
            "运动": ["运动", "体育", "竞技"],
            "音乐": ["音乐", "歌唱", "乐队"],
            "历史": ["历史", "古代", "战国"]
        }
        
        # 检查用户查询是否包含特定tag关键词
        user_query_lower = user_question.lower()
        matched_tags = []
        for tag_cn, tag_variants in tag_boost_keywords.items():
            for variant in tag_variants:
                if variant.lower() in user_query_lower:
                    matched_tags.extend(tag_variants)
                    break
        
        # 检查年份匹配
        import re
        year_pattern = r'(19|20)\d{2}年?'
        target_years = []
        for match in re.finditer(year_pattern, user_question):
            year_str = match.group()
            # 提取数字年份
            year_num = re.search(r'(19|20)\d{2}', year_str)
            if year_num:
                target_years.append(int(year_num.group()))
        
        logger.info(f"检测到目标年份: {target_years}" if target_years else "未检测到特定年份")
        
        # 对结果进行tag匹配和年份匹配评分
        for result in search_results:
            anime = result.payload
            base_score = result.score
            
            # Tag匹配加分
            tag_boost = 0.0
            anime_tags = anime.get('tags', []) or []
            anime_genres = anime.get('genres', []) or []
            all_anime_tags = anime_tags + anime_genres
            
            if matched_tags and all_anime_tags:
                # 计算tag匹配度
                matches = 0
                for tag in matched_tags:
                    for anime_tag in all_anime_tags:
                        if tag.lower() in str(anime_tag).lower():
                            matches += 1
                
                if matches > 0:
                    tag_boost = min(0.3, matches * 0.1)  # 最多加0.3分
                    logger.info(f"Tag匹配加分: {anime.get('title_zh', '未知')} +{tag_boost:.2f}")
            
            # 年份匹配加分
            year_boost = 0.0
            anime_year = anime.get('year') or anime.get('season_year') or anime.get('release_year')
            if target_years and anime_year:
                if anime_year in target_years:
                    year_boost = 0.5  # 年份精确匹配给予较高加分
                    logger.info(f"年份匹配加分: {anime.get('title_zh', '未知')} ({anime_year}年) +{year_boost:.2f}")
                elif any(abs(anime_year - target_year) <= 1 for target_year in target_years):
                    year_boost = 0.2  # 相近年份给予小幅加分
                    logger.info(f"年份相近加分: {anime.get('title_zh', '未知')} ({anime_year}年) +{year_boost:.2f}")
            
            # 计算最终评分
            final_score = base_score + tag_boost + year_boost
            
            enhanced_results.append({
                'payload': anime,
                'score': final_score,
                'original_score': base_score,
                'tag_boost': tag_boost,
                'year_boost': year_boost
            })
        
        # 按最终评分重新排序
        enhanced_results.sort(key=lambda x: x['score'], reverse=True)
        
        # 取前k个结果
        final_results = enhanced_results[:k]
        
        if not final_results:
            return {
                "answer": f"抱歉，没有找到与「{user_question}」相关的动漫作品。请尝试使用其他关键词搜索。",
                "recommendations": [],
                "total_found": 0,
                "query_time": round(time.time() - start_time, 3)
            }
        
        # 2. 格式化推荐数据
        formatted_recommendations = []
        context_parts = []
        
        for result in final_results:
            anime = result['payload']
            score = result['score']
            tag_boost = result.get('tag_boost', 0)
            year_boost = result.get('year_boost', 0)
            
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
                
                # 分类（重点显示匹配的tags）
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
                
                # 匹配信息（包含tag和年份加分）
                "match_score": round(score, 3),
                "tag_boost": round(tag_boost, 3) if tag_boost > 0 else None,
                "year_boost": round(year_boost, 3) if year_boost > 0 else None,
                
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
            
            # 为AI回答构建上下文（突出匹配的tags）
            title = formatted_item.get('title_zh') or formatted_item.get('name_cn', '未知作品')
            description = formatted_item.get('description_zh') or '暂无简介'
            description = description[:100] if description else '暂无简介'
            
            # 添加匹配的tag和年份信息到上下文
            match_info = ""
            if matched_tags and anime.get('tags'):
                matched_anime_tags = []
                for tag in matched_tags:
                    for anime_tag in anime.get('tags', []):
                        if tag.lower() in str(anime_tag).lower():
                            matched_anime_tags.append(anime_tag)
                if matched_anime_tags:
                    match_info += f" [匹配标签: {', '.join(list(set(matched_anime_tags))[:3])}]"
            
            if year_boost > 0:
                anime_year = anime.get('year') or anime.get('season_year') or anime.get('release_year')
                match_info += f" [年份匹配: {anime_year}年]"
            
            context_parts.append(f"《{title}》- {description}...{match_info}")
        
        # 3. 生成AI回答（包含tag匹配说明）
        context = "\n".join(context_parts)
        try:
            # 构建增强的提示，突出tag和年份匹配
            enhanced_prompt = f"用户问题：{user_question}\n"
            if matched_tags:
                enhanced_prompt += f"检测到的关键标签：{', '.join(set(matched_tags))}\n"
            if target_years:
                enhanced_prompt += f"检测到的目标年份：{', '.join(map(str, target_years))}年\n"
            enhanced_prompt += f"推荐内容：\n{context}"
            
            qwen_client = get_qwen_client()
            ai_response = await qwen_client.generate_response(
                user_question=enhanced_prompt,
                context=context,
                temperature=0.7,
                max_tokens=800
            )
        except Exception as llm_error:
            logger.error(f"千问API调用失败: {llm_error}")
            # 备用回答包含tag和年份匹配信息
            match_info = ""
            if matched_tags:
                match_info += f"（基于标签匹配：{', '.join(set(matched_tags))}）"
            if target_years:
                match_info += f"（目标年份：{', '.join(map(str, target_years))}年）"
            ai_response = f"🎌 根据您的问题「{user_question}」{match_info}，为您找到了 {len(formatted_recommendations)} 部相关的动漫作品，详情请查看推荐列表。"
        
        query_time = round(time.time() - start_time, 3)
        
        return {
            "answer": ai_response,
            "recommendations": formatted_recommendations,
            "total_found": len(formatted_recommendations),
            "query_time": query_time,
            "tag_matched": matched_tags if matched_tags else None,  # 返回匹配的tags
            "year_matched": target_years if target_years else None   # 返回匹配的年份
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