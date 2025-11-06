from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, AsyncGenerator
import os
import json
import asyncio
import logging
from app.langchain_agent import answer_question, get_formatted_recommendations, get_streaming_recommendations as get_anime_streaming_data  # 导入新的推荐函数
from app.upload_to_qdrant import prepare_works_for_langchain, upload_to_qdrant_using_langchain
from app.qwen_api import get_qwen_client

logger = logging.getLogger(__name__)

app = FastAPI(title="LangChain Anime Agent API", version="1.0")

# 请求模型
class QuestionRequest(BaseModel):
    question: str

# 动漫数据模型（优化版 - 基于 lat_anime_master 表结构）
class AnimeData(BaseModel):
    # ===== 主键与唯一标识字段 =====
    id: Optional[str] = None  # UUID字符串 - 对应 lat_anime_master.id (主键)
    anilist_id: Optional[int] = None  # AniList ID
    mal_id: Optional[int] = None      # MyAnimeList ID
    bangumi_id: Optional[int] = None  # Bangumi网站ID
    
    # ===== 多语言标题 =====
    title_zh: Optional[str] = None    # 中文标题
    title_en: Optional[str] = None    # 英文标题
    title_jp: Optional[str] = None    # 日文标题
    title_romaji: Optional[str] = None # 罗马音标题
    
    # 兼容旧字段（向后兼容）
    name_cn: Optional[str] = None     # 中文名（兼容字段）
    name: Optional[str] = None        # 原名（兼容字段）
    
    # ===== 基础元数据 =====
    description_zh: Optional[str] = None # 中文简介
    description_en: Optional[str] = None # 英文简介
    description: Optional[str] = None    # 简介（兼容字段）
    
    media_type: Optional[str] = None     # 媒体类型: tv, movie, ova, ona, special
    format: Optional[str] = None         # 格式（同 media_type）
    type: Optional[str] = None           # 类型（兼容字段）
    status: Optional[str] = None         # 状态: FINISHED, RELEASING, etc.
    
    # ===== 播出信息 =====
    episodes: Optional[int] = None       # 总集数
    duration: Optional[int] = None       # 单集时长（分钟）
    year: Optional[int] = None           # 年份
    season: Optional[str] = None         # 季节: WINTER, SPRING, SUMMER, FALL
    season_year: Optional[int] = None    # 播出年份
    release_year: Optional[int] = None   # 发行年份（兼容字段）
    
    # ===== 评分和流行度 =====
    average_score: Optional[float] = None # 平均评分 0-100
    mean_score: Optional[float] = None    # 平均分（不同算法）
    popularity: Optional[int] = None      # 流行度排名
    favourites: Optional[int] = None      # 收藏数
    rating: Optional[float] = None        # 评分（兼容字段）
    
    # ===== 分类和标签 =====
    genres: List[str] = []               # 流派列表
    tags: List[str] = []                 # 标签列表（兼容字段）
    
    # ===== 制作信息 =====
    studios_json: Optional[Dict] = None  # 制作公司JSON
    studio: Optional[str] = None         # 制作公司（兼容字段）
    source_type: Optional[str] = None    # 原作类型: manga, original, etc.
    country_of_origin: Optional[str] = "JP" # 国家代码
    
    # ===== 图片相关字段 =====
    image_large: Optional[str] = None    # 大尺寸相对路径
    image_medium: Optional[str] = None   # 中尺寸相对路径
    image_small: Optional[str] = None    # 小尺寸相对路径
    image_grid: Optional[str] = None     # 网格尺寸相对路径
    image_common: Optional[str] = None   # 通用尺寸相对路径
    
    # 兼容字段（向后兼容）
    poster_url: Optional[str] = None     # 主海报图片URL（兼容字段）
    cover_url: Optional[str] = None      # 封面图片URL（兼容字段）
    screenshots: List[str] = []          # 截图列表（兼容字段）
    thumbnail_url: Optional[str] = None  # 缩略图URL（兼容字段）
    
    # ===== 其他信息 =====
    is_adult: Optional[bool] = False     # 是否成人内容
    data_source: Optional[str] = "manual" # 数据来源
    director: Optional[str] = None       # 导演（兼容字段）
    
    class Config:
        # JSON 示例，用于API文档
        schema_extra = {
            "example": {
                # 主键和唯一标识
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "anilist_id": 101922,
                "mal_id": 38000,
                "bangumi_id": 285017,
                
                # 多语言标题示例
                "title_zh": "鬼灭之刃",
                "title_en": "Demon Slayer: Kimetsu no Yaiba", 
                "title_jp": "鬼滅の刃",
                "title_romaji": "Kimetsu no Yaiba",
                
                # 兼容字段
                "name_cn": "鬼灭之刃",
                "name": "Kimetsu no Yaiba",
                
                # 基础信息
                "media_type": "tv",
                "format": "tv",
                "type": "TV",
                "status": "FINISHED",
                
                # 播出信息
                "episodes": 26,
                "duration": 24,
                "year": 2019,
                "season": "SPRING",
                "season_year": 2019,
                "release_year": 2019,
                
                # 简介
                "description_zh": "大正时代背景下，少年炭治郎为了拯救变成鬼的妹妹而踏上猎鬼之路的热血故事。",
                "description_en": "A young boy becomes a demon slayer to save his sister who was turned into a demon.",
                "description": "大正时代背景下的猎鬼传说",
                
                # 分类和评分
                "genres": ["动作", "历史", "超自然"],
                "tags": ["热血", "战斗", "兄妹情"],
                "average_score": 87,
                "rating": 8.7,
                "popularity": 123,
                "favourites": 45892,
                
                # 制作信息
                "studios_json": {
                    "main": [{"name": "ufotable", "is_main": True}]
                },
                "studio": "ufotable",
                "source_type": "manga",
                "country_of_origin": "JP",
                
                # 图片信息
                "image_large": "/images/anime/covers/large/demon_slayer_large.jpg",
                "image_medium": "/images/anime/covers/medium/demon_slayer_medium.jpg",
                "image_small": "/images/anime/covers/small/demon_slayer_small.jpg",
                "image_grid": "/images/anime/covers/grid/demon_slayer_grid.jpg",
                "image_common": "/images/anime/covers/common/demon_slayer_common.jpg",
                
                # 兼容字段
                "poster_url": "https://example.com/posters/demon_slayer.jpg",
                "cover_url": "https://example.com/covers/demon_slayer.jpg",
                "thumbnail_url": "https://example.com/thumbs/demon_slayer.jpg",
                "screenshots": [
                    "https://example.com/screenshots/demon_slayer_1.jpg",
                    "https://example.com/screenshots/demon_slayer_2.jpg"
                ],
                
                # 其他
                "is_adult": False,
                "data_source": "anilist"
            }
        }

# 批量上传动漫数据请求模型
class BulkAnimeUploadRequest(BaseModel):
    animes: List[AnimeData]

# 响应模型（可选）
class QuestionResponse(BaseModel):
    answer: str

class UploadResponse(BaseModel):
    success: bool
    message: str
    count: int

# 格式化的动漫推荐项
class FormattedAnimeItem(BaseModel):
    # 基础信息
    uuid: Optional[str] = None
    title_zh: Optional[str] = None
    title_en: Optional[str] = None
    title_jp: Optional[str] = None
    description_zh: Optional[str] = None
    description_en: Optional[str] = None
    
    # 媒体信息
    media_type: Optional[str] = None
    status: Optional[str] = None
    episodes: Optional[int] = None
    year: Optional[int] = None
    season: Optional[str] = None
    
    # 评分信息
    average_score: Optional[float] = None
    rating: Optional[float] = None
    popularity: Optional[int] = None
    
    # 分类
    genres: List[str] = []
    tags: List[str] = []
    
    # 图片信息（完整的图片链接）
    cover_image: Optional[str] = None  # 主要封面图片
    image_large: Optional[str] = None
    image_medium: Optional[str] = None
    image_small: Optional[str] = None
    image_grid: Optional[str] = None
    thumbnail: Optional[str] = None
    
    # 制作信息
    studio: Optional[str] = None
    source_type: Optional[str] = None
    
    # 匹配信息
    match_score: Optional[float] = None
    
    # 兼容字段
    name_cn: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None
    poster_url: Optional[str] = None
    release_year: Optional[int] = None

# 格式化的推荐响应模型
class FormattedRecommendationResponse(BaseModel):
    answer: str                           # AI生成的文本回答
    recommendations: List[FormattedAnimeItem]  # 格式化的推荐列表
    total_found: int                      # 找到的相关动漫数量
    query_time: Optional[float] = None    # 查询耗时（秒）
    
    class Config:
        schema_extra = {
            "example": {
                "answer": "根据您的问题，我为您推荐以下动漫作品...",
                "recommendations": [
                    {
                        "uuid": "550e8400-e29b-41d4-a716-446655440000",
                        "title_zh": "鬼灭之刃",
                        "title_en": "Demon Slayer: Kimetsu no Yaiba",
                        "description_zh": "大正时代背景下的猎鬼故事",
                        "media_type": "tv",
                        "episodes": 26,
                        "year": 2019,
                        "average_score": 87.0,
                        "genres": ["动作", "历史", "超自然"],
                        "cover_image": "https://example.com/api/images/covers/demon_slayer_cover.jpg",
                        "image_medium": "/images/anime/covers/medium/demon_slayer_medium.jpg",
                        "studio": "ufotable",
                        "match_score": 0.95
                    }
                ],
                "total_found": 5,
                "query_time": 0.234
            }
        }

# 流式推荐响应模型
class StreamingRecommendationResponse(BaseModel):
    stream_answer: bool = True           # 是否需要打字机效果
    answer_chunks: List[str] = []        # 分段的回答文本
    answer_complete: Optional[str] = None # 完整回答（备用）
    recommendations: List[FormattedAnimeItem] = []  # 完整推荐数据
    total_found: int = 0
    query_time: Optional[float] = None
    
    class Config:
        schema_extra = {
            "example": {
                "stream_answer": True,
                "answer_chunks": [
                    "根据您的问题「推荐一些热血动漫」，",
                    "我为您精心挑选了以下几部作品：",
                    "\n\n🔥《火影忍者》- 经典的忍者成长故事...",
                    "\n\n⚔️《鬼灭之刃》- 大正时代的猎鬼传说..."
                ],
                "recommendations": [
                    {
                        "title_zh": "火影忍者",
                        "cover_image": "http://localhost:8000/images/covers/naruto.jpg",
                        "average_score": 85.0,
                        "match_score": 0.95
                    }
                ],
                "total_found": 3,
                "query_time": 1.234
            }
        }

# 渐进式推荐项模型
class ProgressiveItem(BaseModel):
    type: str  # "intro", "anime", "conclusion"
    text: str
    anime: Optional[FormattedAnimeItem] = None
    delay: float = 0.5  # 建议的显示延迟时间（秒）

# 渐进式推荐响应模型
class ProgressiveRecommendationResponse(BaseModel):
    progressive_answer: bool = True
    progressive_items: List[ProgressiveItem] = []
    total_items: int = 0
    estimated_duration: float = 0.0  # 预估总显示时长
    complete_answer: Optional[str] = None
    complete_recommendations: List[FormattedAnimeItem] = []
    total_found: int = 0
    query_time: Optional[float] = None
    
    class Config:
        schema_extra = {
            "example": {
                "progressive_answer": True,
                "progressive_items": [
                    {
                        "type": "intro",
                        "text": "根据您的问题，我为您推荐以下治愈系动漫...",
                        "anime": None,
                        "delay": 0.8
                    },
                    {
                        "type": "anime", 
                        "text": "🎬《龙猫》- 温暖的成长故事...",
                        "anime": {
                            "title_zh": "龙猫",
                            "cover_image": "http://localhost:8000/images/totoro.jpg"
                        },
                        "delay": 0.6
                    }
                ],
                "total_items": 2,
                "estimated_duration": 5.2
            }
        }

# 增强的问答响应模型
class EnhancedQuestionResponse(BaseModel):
    answer: str                    # AI生成的回答
    recommendations: List[Dict]    # 结构化的推荐数据
    total_found: int              # 找到的相关动漫数量
    
    class Config:
        schema_extra = {
            "example": {
                "answer": "根据您的问题，我为您推荐以下动漫作品...",
                "recommendations": [
                    {
                        "name_cn": "你的名字",
                        "name": "君の名は。",
                        "type": "剧场版",
                        "tags": ["爱情", "奇幻"],
                        "description": "一部感人的爱情动漫...",
                        "poster_url": "https://example.com/poster.jpg",
                        "rating": 8.4,
                        "release_year": 2016,
                        "match_score": 0.95
                    }
                ],
                "total_found": 3
            }
        }

# API 路由
@app.post("/api/answer", response_model=QuestionResponse)
async def chat_with_agent(request: QuestionRequest):
    try:
        answer = await answer_question(request.question, k=3)  # 检索 3 个相关作品
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"问答服务出错：{str(e)}")

# 格式化推荐接口（带图片链接）
@app.post("/api/recommendations", response_model=FormattedRecommendationResponse)
async def get_recommendations(request: QuestionRequest, http_request: Request):
    """
    返回格式化的动漫推荐，包含完整的图片链接和结构化数据
    """
    try:
        # 构建基础URL用于图片链接
        base_url = f"{http_request.url.scheme}://{http_request.url.netloc}"
        
        # 获取格式化推荐
        result = await get_formatted_recommendations(
            user_question=request.question, 
            k=5,  # 返回更多推荐
            base_url=base_url
        )
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"推荐服务出错：{str(e)}")

# 精简版推荐接口（仅返回基础信息）
@app.post("/api/recommendations/simple")
async def get_simple_recommendations(request: QuestionRequest, http_request: Request):
    """
    返回精简版推荐，适合移动端或低带宽环境
    """
    try:
        base_url = f"{http_request.url.scheme}://{http_request.url.netloc}"
        
        result = await get_formatted_recommendations(
            user_question=request.question, 
            k=3,
            base_url=base_url
        )
        
        # 精简推荐数据
        simplified_recommendations = []
        for item in result["recommendations"]:
            simplified_item = {
                "uuid": item.get("uuid"),
                "title_zh": item.get("title_zh"),
                "title_en": item.get("title_en"),
                "description_zh": (item.get("description_zh") or "")[:100] + "..." if (item.get("description_zh") or "") else "",
                "cover_image": item.get("cover_image"),
                "thumbnail": item.get("thumbnail"),
                "year": item.get("year"),
                "rating": item.get("average_score") or item.get("rating"),
                "match_score": item.get("match_score")
            }
            simplified_recommendations.append(simplified_item)
        
        return {
            "answer": result["answer"],
            "recommendations": simplified_recommendations,
            "total_found": result["total_found"],
            "query_time": result["query_time"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"推荐服务出错：{str(e)}")

# 流式推荐接口（打字机效果）
@app.post("/api/recommendations/streaming", response_model=StreamingRecommendationResponse)
async def get_streaming_recommendations(request: QuestionRequest, http_request: Request):
    """
    返回支持打字机效果的推荐数据
    """
    try:
        base_url = f"{http_request.url.scheme}://{http_request.url.netloc}"
        
        # 获取完整推荐数据
        result = await get_formatted_recommendations(
            user_question=request.question, 
            k=5,
            base_url=base_url
        )
        
        # 将回答文本分段处理（打字机效果）
        answer = result["answer"]
        answer_chunks = split_text_for_streaming(answer)
        
        return {
            "stream_answer": True,
            "answer_chunks": answer_chunks,
            "answer_complete": answer,
            "recommendations": result["recommendations"],
            "total_found": result["total_found"],
            "query_time": result["query_time"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"流式推荐服务出错：{str(e)}")

# 渐进式流式推荐接口（文案与图片同步）
@app.post("/api/recommendations/progressive", response_model=ProgressiveRecommendationResponse)
async def get_progressive_recommendations(request: QuestionRequest, http_request: Request):
    """
    返回渐进式推荐数据：文案片段与对应的动漫同步显示
    适合需要更强沉浸感的场景
    """
    try:
        base_url = f"{http_request.url.scheme}://{http_request.url.netloc}"
        
        # 获取完整推荐数据
        result = await get_formatted_recommendations(
            user_question=request.question, 
            k=3,  # 渐进式显示推荐较少作品，避免等待过长
            base_url=base_url
        )
        
        # 解析回答文本，提取每部动漫的描述
        answer = result["answer"]
        recommendations = result["recommendations"]
        
        # 构建渐进式数据结构
        progressive_items = []
        
        # 分割回答为引言、动漫介绍段落、结语
        answer_parts = answer.split('🎬')  # 按动漫标记分割
        
        # 引言部分
        if answer_parts[0].strip():
            progressive_items.append({
                "type": "intro",
                "text": answer_parts[0].strip(),
                "anime": None,
                "delay": 0.8  # 引言显示较慢
            })
        
        # 为每部动漫创建渐进项
        for i, anime in enumerate(recommendations):
            # 尝试从回答中提取对应的描述
            anime_text = ""
            if i + 1 < len(answer_parts):
                # 提取动漫介绍段落
                anime_section = answer_parts[i + 1]
                anime_text = f"🎬{anime_section.split('🎬')[0].strip()}"
            
            if not anime_text:
                # 备用：生成简短介绍
                title = anime.get('title_zh') or anime.get('name_cn', '推荐作品')
                description = anime.get('description_zh', '一部值得观看的作品')[:50]
                rating = anime.get('average_score') or anime.get('rating')
                rating_text = f"评分 {rating}" if rating else ""
                anime_text = f"🎬《{title}》- {description}... {rating_text}"
            
            progressive_items.append({
                "type": "anime",
                "text": anime_text,
                "anime": anime,
                "delay": 0.6  # 动漫介绍中等速度
            })
        
        # 结语部分（从最后的文本提取）
        conclusion_keywords = ["希望", "如果", "推荐", "💡", "🌸", "随时"]
        conclusion = ""
        for keyword in conclusion_keywords:
            if keyword in answer:
                conclusion_start = answer.rfind(keyword)
                if conclusion_start > 0:
                    conclusion = answer[conclusion_start:].strip()
                    break
        
        if conclusion:
            progressive_items.append({
                "type": "conclusion", 
                "text": conclusion,
                "anime": None,
                "delay": 0.5  # 结语显示较快
            })
        
        return {
            "progressive_answer": True,
            "progressive_items": progressive_items,
            "total_items": len(progressive_items),
            "estimated_duration": sum(item["delay"] * (len(item["text"]) / 30) for item in progressive_items),  # 预估总时长
            "complete_answer": answer,
            "complete_recommendations": recommendations,
            "total_found": result["total_found"],
            "query_time": result["query_time"]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"渐进式推荐服务出错：{str(e)}")

def split_text_for_streaming(text: str, chunk_size: int = 30) -> List[str]:
    """
    将文本分割成适合打字机效果的片段
    优化版：更好的语义分割和渐进式体验
    """
    if not text:
        return []
    
    chunks = []
    current_chunk = ""
    
    # 多级分割策略：段落 -> 句子 -> 短语
    # 1. 先按段落分割
    paragraphs = text.split('\n\n')
    
    for paragraph in paragraphs:
        if not paragraph.strip():
            continue
            
        # 2. 按句子分割，保持语义完整
        sentences = paragraph.replace('。', '。\n').replace('！', '！\n').replace('？', '？\n').replace('～', '～\n').split('\n')
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # 3. 对长句子进一步分割
            if len(sentence) > chunk_size * 2:
                # 按逗号、分号等分割长句
                sub_parts = sentence.replace('，', '，\n').replace('；', '；\n').replace('：', '：\n').split('\n')
                for part in sub_parts:
                    part = part.strip()
                    if not part:
                        continue
                    
                    if len(current_chunk + part) > chunk_size and current_chunk:
                        chunks.append(current_chunk)
                        current_chunk = part
                    else:
                        current_chunk += part
            else:
                # 正常处理短句
                if len(current_chunk + sentence) > chunk_size and current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = sentence
                else:
                    current_chunk += sentence
    
    # 添加最后一个chunk
    if current_chunk:
        chunks.append(current_chunk)
    
    # 后处理：确保没有太短的片段（除了最后一个）
    optimized_chunks = []
    for i, chunk in enumerate(chunks):
        if i == len(chunks) - 1:  # 最后一个片段
            optimized_chunks.append(chunk)
        elif len(chunk) < 10 and i < len(chunks) - 1:  # 太短的片段与下一个合并
            chunks[i + 1] = chunk + chunks[i + 1]
        else:
            optimized_chunks.append(chunk)
    
    return optimized_chunks

# 单个动漫数据上传接口
@app.post("/api/anime/upload", response_model=UploadResponse)
async def upload_anime(anime: AnimeData):
    """
    上传单个动漫数据到向量数据库
    """
    try:
        # 转换为字典格式
        anime_dict = anime.dict()
        
        # 如果没有提供 UUID，生成一个新的
        if not anime_dict.get("uuid") and not anime_dict.get("id"):
            import uuid
            new_uuid = str(uuid.uuid4())
            anime_dict["uuid"] = new_uuid
            anime_dict["id"] = new_uuid
            print(f"🆔 为新动漫生成 UUID: {new_uuid}")
        elif anime_dict.get("uuid") and not anime_dict.get("id"):
            # 确保 id 和 uuid 一致
            anime_dict["id"] = anime_dict["uuid"]
        elif anime_dict.get("id") and not anime_dict.get("uuid"):
            # 确保 uuid 和 id 一致
            anime_dict["uuid"] = anime_dict["id"]
        
        # 准备数据并上传
        works_data = prepare_works_for_langchain([anime_dict])
        upload_to_qdrant_using_langchain(works_data)
        
        return {
            "success": True,
            "message": "动漫数据上传成功",
            "count": 1
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败：{str(e)}")

# 批量动漫数据上传接口
@app.post("/api/anime/bulk-upload", response_model=UploadResponse)
async def bulk_upload_anime(request: BulkAnimeUploadRequest):
    """
    批量上传动漫数据到向量数据库
    """
    try:
        if not request.animes:
            raise HTTPException(status_code=400, detail="动漫数据列表不能为空")
        
        # 转换为字典格式列表
        anime_dicts = []
        import uuid
        
        for i, anime in enumerate(request.animes):
            anime_dict = anime.dict()
            
            # 如果没有提供 UUID，生成一个新的
            if not anime_dict.get("uuid") and not anime_dict.get("id"):
                new_uuid = str(uuid.uuid4())
                anime_dict["uuid"] = new_uuid
                anime_dict["id"] = new_uuid
            elif anime_dict.get("uuid") and not anime_dict.get("id"):
                # 确保 id 和 uuid 一致
                anime_dict["id"] = anime_dict["uuid"]
            elif anime_dict.get("id") and not anime_dict.get("uuid"):
                # 确保 uuid 和 id 一致
                anime_dict["uuid"] = anime_dict["id"]
                
            anime_dicts.append(anime_dict)
        
        # 准备数据并上传
        works_data = prepare_works_for_langchain(anime_dicts)
        upload_to_qdrant_using_langchain(works_data)
        
        return {
            "success": True,
            "message": f"成功上传 {len(anime_dicts)} 条动漫数据",
            "count": len(anime_dicts)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量上传失败：{str(e)}")

# 健康检查接口
@app.get("/health")
async def health_check():
    """
    健康检查接口
    """
    return {"status": "healthy", "message": "动漫向量数据库服务运行正常"}

# 增强的问答接口（返回结构化数据）
@app.post("/api/answer/enhanced", response_model=EnhancedQuestionResponse)
async def enhanced_chat_with_agent(request: QuestionRequest):
    """
    增强的智能问答接口，返回AI回答 + 结构化推荐数据
    """
    try:
        # 这里需要修改 answer_question 函数来返回结构化数据
        # 暂时先返回标准格式，后续可以扩展
        answer = await answer_question(request.question, k=3)
        
        # TODO: 实现结构化数据返回
        return {
            "answer": answer,
            "recommendations": [],  # 将在后续实现中填充
            "total_found": 0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"增强问答服务出错：{str(e)}")

# 图片上传接口（预留）
@app.post("/api/images/upload")
async def upload_image():
    """
    图片上传接口（预留功能）
    """
    return {"message": "图片上传功能开发中，敬请期待！"}

# 测试接口：从外部API获取动漫列表并存入向量数据库
@app.post("/api/anime/sync-from-external", response_model=UploadResponse)
async def sync_anime_from_external():
    """
    测试接口：从外部API (http://localhost:8080/api/anime/list) 获取动漫列表并存入向量数据库
    """
    import httpx
    import uuid
    
    try:
        # 1. 从外部API获取动漫列表
        external_api_url = "http://host.docker.internal:8080/api/anime/list"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(external_api_url)
            response.raise_for_status()
            
        api_response = response.json()
        print(api_response)
        # 2. 检查响应格式
        if api_response.get("code") != 0:
            raise HTTPException(
                status_code=400, 
                detail=f"外部API返回错误: {api_response.get('msg', '未知错误')}"
            )
        
        anime_list = api_response.get("data", {}).get("animes", [])
        if not anime_list:
            return {
                "success": True,
                "message": "外部API返回空动漫列表",
                "count": 0
            }
        
        # 3. 转换数据格式到本地模型
        converted_animes = []
        for anime_data in anime_list:
            # 确保每个动漫都有UUID
            anime_uuid = anime_data.get("id")
            if not anime_uuid:
                anime_uuid = str(uuid.uuid4())
            
            # 映射外部API数据到本地AnimeData模型
            converted_anime = {
                # 主键和标识
                "id": anime_uuid,
                "uuid": anime_uuid,
                "anilist_id": anime_data.get("anilist_id"),
                "mal_id": anime_data.get("mal_id"),  
                "bangumi_id": anime_data.get("bangumi_id"),
                
                # 标题映射
                "title_zh": anime_data.get("title_zh") or anime_data.get("name_cn"),
                "title_en": anime_data.get("title_en") or anime_data.get("name"),
                "title_jp": anime_data.get("title_jp"),
                "title_romaji": anime_data.get("title_romaji"),
                
                # 兼容字段
                "name_cn": anime_data.get("name_cn") or anime_data.get("title_zh"),
                "name": anime_data.get("name") or anime_data.get("title_en"),
                
                # 简介
                "description_zh": anime_data.get("description_zh") or anime_data.get("description"),
                "description_en": anime_data.get("description_en"),
                "description": anime_data.get("description"),
                
                # 媒体信息
                "media_type": anime_data.get("media_type") or anime_data.get("format") or anime_data.get("type"),
                "format": anime_data.get("format") or anime_data.get("media_type"),
                "type": anime_data.get("type") or anime_data.get("media_type"),
                "status": anime_data.get("status"),
                
                # 播出信息
                "episodes": anime_data.get("episodes"),
                "duration": anime_data.get("duration"),
                "year": anime_data.get("year") or anime_data.get("season_year") or anime_data.get("release_year"),
                "season": anime_data.get("season"),
                "season_year": anime_data.get("season_year") or anime_data.get("year"),
                "release_year": anime_data.get("release_year") or anime_data.get("year"),
                
                # 评分信息
                "average_score": anime_data.get("average_score") or anime_data.get("mean_score"),
                "mean_score": anime_data.get("mean_score") or anime_data.get("average_score"),
                "rating": anime_data.get("rating") or anime_data.get("average_score"),
                "popularity": anime_data.get("popularity"),
                "favourites": anime_data.get("favourites"),
                
                # 分类
                "genres": anime_data.get("genres") or [],
                "tags": anime_data.get("tags") or anime_data.get("genres") or [],
                
                # 制作信息
                "studios_json": anime_data.get("studios_json"),
                "studio": anime_data.get("studio"),
                "source_type": anime_data.get("source_type"),
                "country_of_origin": anime_data.get("country_of_origin", "JP"),
                
                # 图片信息
                "image_large": anime_data.get('images').get("image_large"),
                "image_medium": anime_data.get('images').get("image_medium"),
                "image_small": anime_data.get('images').get("image_small"),
                "image_grid": anime_data.get('images').get("image_grid"),
                "image_common": anime_data.get('images').get("image_common"),
                
                # 兼容图片字段
                "poster_url": anime_data.get("poster_url") or anime_data.get("cover_url"),
                "cover_url": anime_data.get("cover_url") or anime_data.get("poster_url"),
                "thumbnail_url": anime_data.get("thumbnail_url"),
                "screenshots": anime_data.get("screenshots") or [],
                
                # 其他信息
                "is_adult": anime_data.get("is_adult", False),
                "data_source": anime_data.get("data_source", "external_api"),
                "director": anime_data.get("director")
            }
            
            converted_animes.append(converted_anime)
        
        # 4. 批量存入向量数据库
        if converted_animes:
            works_data = prepare_works_for_langchain(converted_animes)
            upload_to_qdrant_using_langchain(works_data)
        
        return {
            "success": True,
            "message": f"成功从外部API同步并存储 {len(converted_animes)} 条动漫数据",
            "count": len(converted_animes)
        }
        
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=503, 
            detail=f"无法连接到外部API ({external_api_url}): {str(e)}"
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"外部API返回错误状态码 {e.response.status_code}: {e.response.text}"
        )
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"同步外部动漫数据异常: {error_trace}")
        raise HTTPException(status_code=500, detail=f"同步外部动漫数据失败：{str(e)}")


# ==================== 新增流式API端点 ====================

@app.post("/api/recommendations/qwen-streaming")
async def get_qwen_streaming_recommendations(request: QuestionRequest, http_request: Request):
    """
    基于千问大模型的真实流式推荐API
    支持文本逐步生成和图片触发显示
    """
    try:
        base_url = f"{http_request.url.scheme}://{http_request.url.netloc}"
        
        # 1. 获取动漫数据
        search_result = await get_anime_streaming_data(
            user_question=request.question,
            k=3,
            base_url=base_url
        )
        
        # 检查搜索结果是否有效
        if not search_result or not search_result.get("streaming_answer"):
            error_message = search_result.get("answer", "搜索服务异常") if search_result else "搜索服务异常"
            return {
                "success": False,
                "error": "向量搜索失败",
                "message": error_message,
                "user_question": request.question,
                "anime_list": [],
                "total_found": 0,
                "query_time": search_result.get("query_time", 0) if search_result else 0,
                "suggestion": "请检查Qdrant数据库连接或尝试重新上传动漫数据"
            }
        
        # 2. 准备动漫列表和上下文
        anime_list = search_result.get("anime_list", [])
        if not anime_list:
            return {
                "success": False,
                "error": "未找到动漫数据",
                "message": "虽然搜索成功，但未找到相关动漫作品",
                "user_question": request.question,
                "anime_list": [],
                "total_found": 0,
                "query_time": search_result.get("query_time", 0),
                "suggestion": "请尝试使用其他关键词或检查动漫数据库"
            }
        context_parts = []
        for anime in anime_list:
            title = anime.get('title_zh', '未知作品')
            description = anime.get('description_zh') or ''  # 处理None值
            if description:
                description = description[:100]
            context_parts.append(f"《{title}》- {description}")
        
        context = "\n".join(context_parts)
        
        return {
            "success": True,
            "user_question": request.question,
            "anime_list": anime_list,
            "context": context,
            "total_found": search_result["total_found"],
            "query_time": search_result["query_time"],
            "message": "请使用 /api/recommendations/qwen-streaming-sse 获取流式文本"
        }
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"千问流式推荐服务异常: {error_trace}")
        raise HTTPException(status_code=500, detail=f"千问流式推荐服务出错：{str(e)} (详细错误已记录到日志)")


@app.post("/api/recommendations/qwen-streaming-sse")
async def get_qwen_streaming_sse(request: QuestionRequest, http_request: Request):
    """
    千问流式推荐 - Server-Sent Events版本
    返回实时生成的文本流和图片触发信号
    """
    async def generate_streaming_response():
        try:
            base_url = f"{http_request.url.scheme}://{http_request.url.netloc}"
            
            # 1. 获取动漫数据
            search_result = await get_anime_streaming_data(
                user_question=request.question,
                k=3,
                base_url=base_url
            )
            
            if not search_result or not search_result.get("streaming_answer"):
                yield f"data: {json.dumps({'type': 'error', 'content': '未找到相关动漫作品'})}\n\n"
                return
            
            # 2. 发送动漫列表
            anime_list = search_result.get("anime_list", [])
            if not anime_list:
                yield f"data: {json.dumps({'type': 'error', 'content': '未找到动漫数据'})}\n\n"
                return
                
            yield f"data: {json.dumps({'type': 'anime_list', 'content': anime_list})}\n\n"
            
            # 3. 准备上下文
            context_parts = []
            for anime in anime_list:
                title = anime.get('title_zh', '未知作品')
                description = anime.get('description_zh') or ''  # 处理None值
                if description:
                    description = description[:100]
                context_parts.append(f"《{title}》- {description}")
            
            context = "\n".join(context_parts)
            
            # 4. 开始千问流式生成
            try:
                qwen_client = get_qwen_client()
                async for chunk in qwen_client.generate_streaming_with_triggers(
                    user_question=request.question,
                    anime_list=anime_list
                ):
                    if chunk["type"] == "text":
                        yield f"data: {json.dumps({'type': 'text', 'content': chunk['content']})}\n\n"
                    elif chunk["type"] == "image_trigger":
                        yield f"data: {json.dumps({'type': 'image_trigger', 'content': chunk['content']})}\n\n"
                    elif chunk["type"] == "error":
                        yield f"data: {json.dumps({'type': 'error', 'content': chunk['content']})}\n\n"
                    
                    # 添加小延迟确保流畅显示
                    await asyncio.sleep(0.05)
            
            except RuntimeError as qwen_error:
                # 千问API配置错误，提供降级响应
                fallback_text = f"🎌 根据您的问题「{request.question}」，为您找到了 {len(anime_list)} 部相关动漫作品：\n\n"
                for i, anime in enumerate(anime_list):
                    title = anime.get('title_zh', '未知作品')
                    fallback_text += f"{i+1}. 《{title}》\n"
                
                fallback_text += f"\n⚠️ AI文案生成功能暂时不可用（{qwen_error}），但动漫推荐数据已为您准备完成。"
                
                # 逐字符发送降级响应
                for char in fallback_text:
                    yield f"data: {json.dumps({'type': 'text', 'content': char})}\n\n"
                    await asyncio.sleep(0.03)
            
            # 5. 发送完成信号
            yield f"data: {json.dumps({'type': 'complete', 'content': 'done'})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': f'流式生成错误: {str(e)}'})}\n\n"
    
    return StreamingResponse(
        generate_streaming_response(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )


# 流式推荐状态模型
class StreamingRecommendationRequest(BaseModel):
    question: str
    enable_image_triggers: bool = True
    max_recommendations: int = 3

@app.post("/api/recommendations/realtime-streaming")
async def get_realtime_streaming_recommendations(request: StreamingRecommendationRequest, http_request: Request):
    """
    实时流式推荐API - 完整版
    支持文本渐进生成 + 图片触发同步显示
    """
    async def generate_realtime_stream():
        try:
            base_url = f"{http_request.url.scheme}://{http_request.url.netloc}"
            
            # 发送开始信号
            yield f"data: {json.dumps({'type': 'start', 'message': '开始处理您的请求...'})}\n\n"
            
            # 1. 向量检索阶段
            yield f"data: {json.dumps({'type': 'status', 'message': '正在搜索相关动漫...'})}\n\n"
            
            search_result = await get_anime_streaming_data(
                user_question=request.question,
                k=request.max_recommendations,
                base_url=base_url
            )
            
            if not search_result or not search_result.get("streaming_answer"):
                yield f"data: {json.dumps({'type': 'error', 'content': '未找到相关动漫作品'})}\n\n"
                return
            
            # 2. 发送搜索结果
            anime_list = search_result.get("anime_list", [])
            if not anime_list:
                yield f"data: {json.dumps({'type': 'error', 'content': '搜索成功但未找到相关动漫作品'})}\n\n"
                return
                
            yield f"data: {json.dumps({'type': 'search_results', 'anime_list': anime_list, 'total_found': len(anime_list)})}\n\n"
            
            # 3. 开始AI文案生成
            yield f"data: {json.dumps({'type': 'status', 'message': '正在生成推荐文案...'})}\n\n"
            
            # 准备上下文
            context_parts = []
            for anime in anime_list:
                title = anime.get('title_zh', '未知作品')
                description = anime.get('description_zh') or ''  # 处理None值
                if description:
                    description = description[:100]
                context_parts.append(f"《{title}》- {description}")
            
            context = "\n".join(context_parts)
            
            # 4. 千问流式生成
            try:
                qwen_client = get_qwen_client()
                text_buffer = ""
                
                async for chunk in qwen_client.generate_streaming_with_triggers(
                    user_question=request.question,
                    anime_list=anime_list
                ):
                    if chunk["type"] == "text":
                        text_content = chunk["content"]
                        text_buffer += text_content
                        yield f"data: {json.dumps({'type': 'text_chunk', 'content': text_content, 'buffer': text_buffer})}\n\n"
                        
                    elif chunk["type"] == "image_trigger" and request.enable_image_triggers:
                        trigger_data = chunk["content"]
                        yield f"data: {json.dumps({'type': 'image_trigger', 'anime_uuid': trigger_data.get('anime_uuid'), 'trigger_text': trigger_data.get('trigger_text')})}\n\n"
                        
                    elif chunk["type"] == "error":
                        yield f"data: {json.dumps({'type': 'warning', 'content': f'生成警告: {chunk.content}'})}\n\n"
                    
                    # 流控制
                    await asyncio.sleep(0.03)
                
            except RuntimeError as qwen_error:
                # 千问API配置错误，使用降级方案
                yield f"data: {json.dumps({'type': 'status', 'message': 'AI文案生成不可用，使用简化推荐'})}\n\n"
                
                text_buffer = f"🎌 根据您的问题「{request.question}」，为您推荐以下动漫：\n\n"
                for i, anime in enumerate(anime_list):
                    title = anime.get('title_zh', '未知作品')
                    desc = anime.get('description_zh', '')[:50]
                    recommendation = f"{i+1}. 《{title}》- {desc}\n"
                    text_buffer += recommendation
                    
                    # 逐字符发送
                    for char in recommendation:
                        yield f"data: {json.dumps({'type': 'text_chunk', 'content': char, 'buffer': text_buffer})}\n\n"
                        await asyncio.sleep(0.02)
                    
                    # 发送图片触发（如果启用）
                    if request.enable_image_triggers:
                        yield f"data: {json.dumps({'type': 'image_trigger', 'anime_uuid': anime.get('uuid', f'fallback-{i}'), 'trigger_text': f'《{title}》'})}\n\n"
                
                text_buffer += f"\n⚠️ 注意：AI文案生成功能需要配置千问API密钥"
            
            # 5. 完成信号
            yield f"data: {json.dumps({'type': 'complete', 'final_text': text_buffer, 'total_anime': len(anime_list)})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': f'实时流式推荐错误: {str(e)}'})}\n\n"
    
    return StreamingResponse(
        generate_realtime_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )