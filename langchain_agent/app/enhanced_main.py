"""
推荐系统新架构的FastAPI集成示例
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import asyncio
import json
import time
from datetime import datetime

# 导入新的推荐系统组件
from .recommendation_system.factory import (
    get_recommendation_engine, 
    initialize_recommendation_system,
    close_recommendation_system
)
from .recommendation_system.core import RecommendationRequest, AnimeItem
from .recommendation_system.user_behavior import ActionType, UserBehaviorTracker
from .recommendation_system.config import get_config

app = FastAPI(title="增强推荐系统API", version="2.0.0")


# Pydantic模型定义
class RecommendRequest(BaseModel):
    query: str
    user_id: Optional[str] = None
    num_recommendations: int = 10
    filters: Optional[Dict] = None
    stream: bool = False


class RecommendResponse(BaseModel):
    recommendations: List[Dict]
    recall_info: Dict
    ranking_info: Dict
    response_time: float


class UserActionRequest(BaseModel):
    user_id: str
    item_id: str
    action_type: str
    value: Optional[str] = None
    context: Optional[Dict] = None


# 全局变量
recommendation_engine = None
behavior_tracker = None


@app.on_event("startup")
async def startup_event():
    """应用启动时初始化推荐系统"""
    global recommendation_engine, behavior_tracker
    
    try:
        # 初始化推荐系统
        recommendation_engine = await initialize_recommendation_system()
        
        # 获取用户行为跟踪器
        from .recommendation_system.factory import recommendation_manager
        factory = recommendation_manager._factory
        if factory:
            behavior_tracker = factory.behavior_tracker
        
        print("✅ 增强推荐系统启动成功")
    except Exception as e:
        print(f"❌ 推荐系统启动失败: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理资源"""
    await close_recommendation_system()
    print("✅ 推荐系统已关闭")


@app.post("/api/v2/recommendations", response_model=RecommendResponse)
async def get_recommendations(request: RecommendRequest):
    """获取推荐结果（同步版本）"""
    start_time = time.time()
    
    try:
        # 构建推荐请求
        rec_request = RecommendationRequest(
            user_id=request.user_id,
            query=request.query,
            filters=request.filters,
            num_recommendations=request.num_recommendations
        )
        
        # 执行推荐
        result = await recommendation_engine.recommend(rec_request)
        
        # 记录用户行为（搜索行为）
        if request.user_id and behavior_tracker:
            await behavior_tracker.track_action(
                user_id=request.user_id,
                item_id="search",
                action_type=ActionType.SEARCH,
                value=request.query,
                context={"timestamp": datetime.now().isoformat()}
            )
        
        # 转换结果格式
        recommendations = []
        for i, item in enumerate(result.items):
            rec = {
                "id": item.id,
                "title": item.title,
                "title_zh": item.title_zh,
                "year": item.year,
                "genres": item.genres,
                "tags": item.tags,
                "description": item.description,
                "rating": item.rating,
                "score": result.scores[i],
                "explanation": result.explanations[i] if i < len(result.explanations) else ""
            }
            recommendations.append(rec)
        
        response_time = time.time() - start_time
        
        return RecommendResponse(
            recommendations=recommendations,
            recall_info=result.recall_info,
            ranking_info=result.ranking_info,
            response_time=response_time
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"推荐失败: {str(e)}")


@app.post("/api/v2/recommendations/stream")
async def stream_recommendations(request: RecommendRequest):
    """流式推荐API"""
    if not request.stream:
        # 如果不是流式请求，直接返回结果
        return await get_recommendations(request)
    
    async def generate_stream():
        """生成流式响应"""
        try:
            # 构建推荐请求
            rec_request = RecommendationRequest(
                user_id=request.user_id,
                query=request.query,
                filters=request.filters,
                num_recommendations=request.num_recommendations
            )
            
            # 分阶段生成推荐结果
            yield "data: " + json.dumps({
                "type": "status",
                "message": "开始生成推荐...",
                "progress": 0
            }, ensure_ascii=False) + "\n\n"
            
            # 执行推荐
            result = await recommendation_engine.recommend(rec_request)
            
            # 逐个推送推荐结果
            total_items = len(result.items)
            for i, item in enumerate(result.items):
                rec = {
                    "id": item.id,
                    "title": item.title,
                    "title_zh": item.title_zh,
                    "year": item.year,
                    "genres": item.genres,
                    "tags": item.tags,
                    "description": item.description,
                    "rating": item.rating,
                    "score": result.scores[i],
                    "explanation": result.explanations[i] if i < len(result.explanations) else ""
                }
                
                yield "data: " + json.dumps({
                    "type": "recommendation",
                    "data": rec,
                    "index": i,
                    "total": total_items,
                    "progress": int((i + 1) / total_items * 100)
                }, ensure_ascii=False) + "\n\n"
                
                # 模拟流式延迟
                await asyncio.sleep(0.1)
            
            # 发送完成信息
            yield "data: " + json.dumps({
                "type": "complete",
                "recall_info": result.recall_info,
                "ranking_info": result.ranking_info,
                "total_recommendations": total_items
            }, ensure_ascii=False) + "\n\n"
            
            # 记录用户行为
            if request.user_id and behavior_tracker:
                await behavior_tracker.track_action(
                    user_id=request.user_id,
                    item_id="search",
                    action_type=ActionType.SEARCH,
                    value=request.query,
                    context={"stream": True, "timestamp": datetime.now().isoformat()}
                )
                
        except Exception as e:
            yield "data: " + json.dumps({
                "type": "error",
                "message": f"推荐失败: {str(e)}"
            }, ensure_ascii=False) + "\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        }
    )


@app.post("/api/v2/user/action")
async def track_user_action(action: UserActionRequest, background_tasks: BackgroundTasks):
    """记录用户行为"""
    if not behavior_tracker:
        raise HTTPException(status_code=503, detail="用户行为跟踪未启用")
    
    try:
        # 验证action_type
        try:
            action_type = ActionType(action.action_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效的行为类型: {action.action_type}")
        
        # 后台记录用户行为
        background_tasks.add_task(
            behavior_tracker.track_action,
            user_id=action.user_id,
            item_id=action.item_id,
            action_type=action_type,
            value=action.value,
            context=action.context
        )
        
        return {"status": "success", "message": "用户行为记录成功"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"行为记录失败: {str(e)}")


@app.get("/api/v2/user/{user_id}/profile")
async def get_user_profile(user_id: str):
    """获取用户画像"""
    try:
        from .recommendation_system.factory import recommendation_manager
        factory = recommendation_manager._factory
        
        if not factory or not factory.behavior_analyzer:
            raise HTTPException(status_code=503, detail="用户行为分析未启用")
        
        profile = await factory.behavior_analyzer.analyze_user_preferences(user_id)
        
        return {
            "user_id": profile.user_id,
            "preferences": profile.preferences,
            "genre_preferences": profile.genre_preferences,
            "tag_preferences": profile.tag_preferences,
            "year_preferences": profile.year_preferences,
            "rating_bias": profile.rating_bias,
            "activity_level": profile.activity_level,
            "last_active": profile.last_active.isoformat(),
            "created_at": profile.created_at.isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取用户画像失败: {str(e)}")


@app.get("/api/v2/system/status")
async def get_system_status():
    """获取系统状态"""
    config = get_config()
    
    status = {
        "system": "Enhanced Recommendation System",
        "version": "2.0.0",
        "status": "running" if recommendation_engine else "error",
        "config": {
            "recall_strategies": {
                "vector_recall_k": config.recall.vector_recall_k,
                "cf_recall_k": config.recall.cf_recall_k,
                "tag_recall_k": config.recall.tag_recall_k,
                "max_candidates": config.recall.max_candidates
            },
            "ranking": {
                "use_llm_rerank": config.ranking.use_llm_rerank,
                "feature_weights": config.ranking.feature_weights
            },
            "cache": {
                "enabled": config.enable_cache,
                "ttl": config.cache_ttl
            }
        },
        "features": [
            "多路召回策略",
            "智能排序融合", 
            "用户行为分析",
            "LLM增强推荐",
            "实时流式推荐",
            "用户画像构建"
        ]
    }
    
    return status


@app.get("/api/v2/config")
async def get_system_config():
    """获取系统配置"""
    config = get_config()
    return {
        "database": {
            "qdrant_host": config.database.qdrant_host,
            "qdrant_port": config.database.qdrant_port,
            "postgres_host": config.database.postgres_host,
            "postgres_port": config.database.postgres_port,
        },
        "model": {
            "embedding_model": config.model.embedding_model,
            "embedding_dim": config.model.embedding_dim,
            "llm_model": config.model.llm_model,
        },
        "recall": config.recall.__dict__,
        "ranking": {
            "feature_weights": config.ranking.feature_weights,
            "use_llm_rerank": config.ranking.use_llm_rerank,
            "llm_rerank_top_k": config.ranking.llm_rerank_top_k,
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)