from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional, Dict
import os
from app.langchain_agent import answer_question, get_formatted_recommendations  # 导入新的推荐函数
from app.upload_to_qdrant import prepare_works_for_langchain, upload_to_qdrant_using_langchain

app = FastAPI(title="LangChain Anime Agent API", version="1.0")

# 挂载静态文件服务（用于图片访问）
# 确保 images 目录存在
images_dir = "/app/images"
if not os.path.exists(images_dir):
    os.makedirs(images_dir, exist_ok=True)

# 挂载静态文件
app.mount("/images", StaticFiles(directory=images_dir), name="images")

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
                "description_zh": item.get("description_zh", "")[:100] + "..." if item.get("description_zh", "") else "",
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