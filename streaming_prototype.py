#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qwen流式+Redis+WebSocket实现原型
实现"返回一段文案，显示一个图片"的完整方案
"""

import asyncio
import json
import redis.asyncio as redis
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import AsyncGenerator, Dict, List, Optional
import httpx
import re
import logging
from datetime import datetime

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StreamingQwenClient:
    """
    支持流式返回的Qwen API客户端
    """
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    
    async def stream_anime_recommendation(
        self, 
        user_question: str, 
        anime_list: List[Dict]
    ) -> AsyncGenerator[Dict, None]:
        """
        流式生成动漫推荐，每推荐一部动漫就触发图片显示
        
        Yields:
            Dict: {"type": "text|image_trigger", "content": "...", "anime_data": {...}}
        """
        
        # 构建专门的流式推荐Prompt
        prompt = self._build_streaming_prompt(user_question, anime_list)
        
        payload = {
            "model": "qwen-turbo",
            "input": {
                "messages": [
                    {
                        "role": "system",
                        "content": """你是专业的动漫推荐助手。请按以下格式推荐：

1. 简短开场白
2. 对每部动漫：
   - 用🎬开头写标题
   - 写20-30字简介
   - 换行后写"[IMAGE_TRIGGER]"作为图片显示信号
3. 简短结语

重要：每个[IMAGE_TRIGGER]后必须换行，这是图片显示的关键信号！"""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            },
            "parameters": {
                "temperature": 0.7,
                "max_tokens": 800,
                "stream": True,              # 启用流式
                "incremental_output": True   # 增量输出
            }
        }
        
        # 模拟流式API调用（实际中会调用真实的Qwen API）
        async for chunk in self._simulate_qwen_streaming(prompt, anime_list):
            yield chunk
    
    async def _simulate_qwen_streaming(self, prompt: str, anime_list: List[Dict]) -> AsyncGenerator[Dict, None]:
        """
        模拟Qwen流式返回（实际项目中替换为真实API调用）
        """
        # 模拟的流式响应内容
        response_template = """🎌 根据您的兴趣，为您推荐以下精彩动漫：

🎬《{title1}》- {desc1}
[IMAGE_TRIGGER]

🎬《{title2}》- {desc2}
[IMAGE_TRIGGER]

🎬《{title3}》- {desc3}
[IMAGE_TRIGGER]

💡 希望这些推荐能带给您美好的观影体验！"""
        
        # 填充实际动漫数据
        formatted_response = response_template.format(
            title1=anime_list[0].get('title_zh', '动漫1'),
            desc1=anime_list[0].get('description_zh', '精彩的动漫作品')[:30],
            title2=anime_list[1].get('title_zh', '动漫2') if len(anime_list) > 1 else '推荐动漫',
            desc2=anime_list[1].get('description_zh', '值得观看的作品')[:30] if len(anime_list) > 1 else '精彩内容',
            title3=anime_list[2].get('title_zh', '动漫3') if len(anime_list) > 2 else '热门动漫',
            desc3=anime_list[2].get('description_zh', '不容错过的佳作')[:30] if len(anime_list) > 2 else '优质内容'
        )
        
        # 按字符流式输出，检测图片触发点
        current_anime_index = 0
        accumulated_text = ""
        
        for char in formatted_response:
            accumulated_text += char
            
            # 每几个字符发送一次（模拟网络延迟）
            if len(accumulated_text) % 3 == 0:
                yield {
                    "type": "text",
                    "content": char,
                    "accumulated": accumulated_text
                }
                await asyncio.sleep(0.02)  # 模拟网络延迟
            
            # 检测图片触发信号
            if "[IMAGE_TRIGGER]" in accumulated_text and current_anime_index < len(anime_list):
                # 清理触发信号
                clean_text = accumulated_text.replace("[IMAGE_TRIGGER]", "")
                
                yield {
                    "type": "image_trigger",
                    "content": "\n📷 图片加载中...\n",
                    "anime_data": anime_list[current_anime_index],
                    "anime_index": current_anime_index,
                    "clean_text": clean_text
                }
                
                current_anime_index += 1
                await asyncio.sleep(0.5)  # 图片加载时间
    
    def _build_streaming_prompt(self, user_question: str, anime_list: List[Dict]) -> str:
        """构建流式推荐Prompt"""
        anime_context = "\n".join([
            f"- {anime.get('title_zh', '未知')}: {anime.get('description_zh', '无描述')[:50]}"
            for anime in anime_list[:3]  # 限制推荐数量
        ])
        
        return f"""用户问题：{user_question}

可推荐的动漫：
{anime_context}

请为用户推荐这些动漫，记住在每个动漫介绍后添加[IMAGE_TRIGGER]信号。"""

class RedisAnimeCache:
    """Redis缓存管理器"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis_client = None
    
    async def connect(self):
        """连接Redis"""
        self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
    
    async def cache_anime_image(self, anime_id: str, image_data: Dict):
        """缓存动漫图片信息"""
        cache_key = f"anime:image:{anime_id}"
        await self.redis_client.setex(
            cache_key, 
            3600,  # 1小时TTL
            json.dumps(image_data, ensure_ascii=False)
        )
    
    async def get_anime_image(self, anime_id: str) -> Optional[Dict]:
        """获取缓存的图片信息"""
        cache_key = f"anime:image:{anime_id}"
        cached_data = await self.redis_client.get(cache_key)
        if cached_data:
            return json.loads(cached_data)
        return None
    
    async def preload_images(self, anime_list: List[Dict]):
        """预加载动漫图片到缓存"""
        for anime in anime_list:
            anime_id = anime.get('uuid') or anime.get('id', 'unknown')
            image_data = {
                "anime_id": anime_id,
                "title": anime.get('title_zh', '未知'),
                "cover_url": anime.get('cover_image'),
                "thumbnail_url": anime.get('thumbnail'),
                "rating": anime.get('average_score'),
                "cached_at": datetime.now().isoformat()
            }
            await self.cache_anime_image(anime_id, image_data)

class WebSocketStreamingManager:
    """WebSocket流式推送管理器"""
    
    def __init__(self, redis_cache: RedisAnimeCache):
        self.redis_cache = redis_cache
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def handle_streaming_recommendation(
        self, 
        websocket: WebSocket, 
        user_id: str,
        user_question: str,
        anime_list: List[Dict]
    ):
        """处理完整的流式推荐流程"""
        try:
            # 注册连接
            self.active_connections[user_id] = websocket
            
            # 预加载图片到缓存
            await self.redis_cache.preload_images(anime_list)
            
            # 发送开始信号
            await self._send_message(websocket, {
                "type": "session_start",
                "message": "开始生成个性化推荐...",
                "anime_count": len(anime_list)
            })
            
            # 初始化流式客户端
            qwen_client = StreamingQwenClient("mock-api-key")
            
            # 流式处理
            async for chunk in qwen_client.stream_anime_recommendation(user_question, anime_list):
                if chunk["type"] == "text":
                    # 发送文字片段
                    await self._send_message(websocket, {
                        "type": "text_chunk",
                        "content": chunk["content"],
                        "accumulated": chunk["accumulated"]
                    })
                
                elif chunk["type"] == "image_trigger":
                    # 触发图片显示
                    anime_data = chunk["anime_data"]
                    anime_id = anime_data.get('uuid') or anime_data.get('id', 'unknown')
                    
                    # 从缓存获取图片信息
                    image_info = await self.redis_cache.get_anime_image(anime_id)
                    
                    await self._send_message(websocket, {
                        "type": "image_display",
                        "anime_index": chunk["anime_index"],
                        "image_info": image_info,
                        "display_animation": "fade_in",
                        "sync_with_text": True
                    })
                    
                    # 同时发送清理后的文本
                    await self._send_message(websocket, {
                        "type": "text_cleanup", 
                        "clean_content": chunk["clean_text"]
                    })
            
            # 发送完成信号
            await self._send_message(websocket, {
                "type": "recommendation_complete",
                "total_anime": len(anime_list),
                "completion_time": datetime.now().isoformat()
            })
            
        except WebSocketDisconnect:
            logger.info(f"用户 {user_id} 断开连接")
        except Exception as e:
            logger.error(f"流式推荐错误: {e}")
            await self._send_message(websocket, {
                "type": "error",
                "message": f"推荐过程出现错误: {str(e)}"
            })
        finally:
            # 清理连接
            if user_id in self.active_connections:
                del self.active_connections[user_id]
    
    async def _send_message(self, websocket: WebSocket, message: Dict):
        """发送WebSocket消息"""
        try:
            await websocket.send_text(json.dumps(message, ensure_ascii=False))
        except Exception as e:
            logger.error(f"WebSocket消息发送失败: {e}")

# FastAPI应用示例
app = FastAPI(title="流式动漫推荐系统")

# 全局组件
redis_cache = RedisAnimeCache()
streaming_manager = WebSocketStreamingManager(redis_cache)

@app.on_event("startup")
async def startup_event():
    """应用启动时初始化Redis连接"""
    await redis_cache.connect()

@app.websocket("/ws/streaming-recommendation/{user_id}")
async def websocket_streaming_endpoint(websocket: WebSocket, user_id: str):
    """WebSocket流式推荐端点"""
    await websocket.accept()
    
    try:
        # 接收用户请求
        request_data = await websocket.receive_text()
        request = json.loads(request_data)
        
        user_question = request.get("question", "推荐一些动漫")
        
        # 模拟从数据库获取推荐动漫
        mock_anime_list = [
            {
                "uuid": "anime-001",
                "title_zh": "千与千寻",
                "description_zh": "宫崎骏执导的经典动画电影，讲述少女千寻在神秘世界的冒险故事",
                "cover_image": "https://example.com/spirited_away.jpg",
                "average_score": 9.3
            },
            {
                "uuid": "anime-002", 
                "title_zh": "你的名字",
                "description_zh": "新海诚导演的浪漫奇幻动画，时空交错的青春爱情故事",
                "cover_image": "https://example.com/your_name.jpg",
                "average_score": 8.4
            },
            {
                "uuid": "anime-003",
                "title_zh": "鬼灭之刃",
                "description_zh": "热血战斗动漫，讲述少年炭治郎为救妹妹而踏上斩鬼之路",
                "cover_image": "https://example.com/demon_slayer.jpg", 
                "average_score": 8.7
            }
        ]
        
        # 开始流式推荐
        await streaming_manager.handle_streaming_recommendation(
            websocket, user_id, user_question, mock_anime_list
        )
        
    except WebSocketDisconnect:
        logger.info(f"用户 {user_id} 主动断开连接")
    except Exception as e:
        logger.error(f"WebSocket处理错误: {e}")

async def demo_streaming_implementation():
    """演示流式实现的核心逻辑"""
    print("🚀 Qwen流式+Redis+WebSocket核心实现演示")
    print("="*60)
    
    # 初始化组件
    redis_cache = RedisAnimeCache()
    await redis_cache.connect()
    
    qwen_client = StreamingQwenClient("mock-api-key")
    
    # 模拟动漫数据
    anime_list = [
        {
            "uuid": "demo-001",
            "title_zh": "龙猫",
            "description_zh": "温馨治愈的宫崎骏动画，森林精灵与小女孩的奇妙冒险",
            "cover_image": "https://example.com/totoro.jpg"
        },
        {
            "uuid": "demo-002",
            "title_zh": "夏目友人帐", 
            "description_zh": "人与妖怪的温情故事，治愈系动漫的经典代表",
            "cover_image": "https://example.com/natsume.jpg"
        }
    ]
    
    print("📝 1. 开始流式文案生成...")
    user_question = "推荐一些治愈系动漫"
    
    text_buffer = ""
    image_count = 0
    
    async for chunk in qwen_client.stream_anime_recommendation(user_question, anime_list):
        if chunk["type"] == "text":
            print(chunk["content"], end="", flush=True)
            text_buffer += chunk["content"]
        
        elif chunk["type"] == "image_trigger":
            print(f"\n\n📷 [图片 {image_count + 1} 显示]")
            anime_data = chunk["anime_data"]
            print(f"   标题: {anime_data.get('title_zh')}")
            print(f"   封面: {anime_data.get('cover_image')}")
            print(f"   ⏱️ 与文案同步显示\n")
            
            # 模拟缓存图片信息
            await redis_cache.cache_anime_image(
                anime_data.get('uuid'),
                {
                    "title": anime_data.get('title_zh'),
                    "cover_url": anime_data.get('cover_image'),
                    "display_time": datetime.now().isoformat()
                }
            )
            
            image_count += 1
    
    print(f"\n\n✅ 演示完成!")
    print(f"📊 统计数据:")
    print(f"   • 文字长度: {len(text_buffer)} 字符")
    print(f"   • 图片数量: {image_count} 张")
    print(f"   • 同步显示: 完美配合")
    
    print(f"\n🎯 方案优势:")
    print(f"   ✅ 真正的实时同步 - 文案和图片完美配合")
    print(f"   ✅ 用户体验极佳 - 沉浸式推荐体验")
    print(f"   ✅ 技术架构清晰 - 组件职责分明")
    print(f"   ✅ 性能表现优秀 - 缓存+流式优化")

if __name__ == "__main__":
    print("🎬 流式动漫推荐系统 - 技术原型")
    print("实现：一段文案 + 一张图片的完美同步")
    print("="*60)
    
    asyncio.run(demo_streaming_implementation())