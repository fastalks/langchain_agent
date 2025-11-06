# qwen_api.py - 千问API集成模块

import os
import httpx
import json
from typing import List, Dict, Optional, AsyncGenerator
import logging
import asyncio

logger = logging.getLogger(__name__)

class QwenAPI:
    """千问API客户端"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('DASHSCOPE_API_KEY')
        if not self.api_key:
            raise ValueError("请设置 DASHSCOPE_API_KEY 环境变量")
        
        self.base_url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    async def generate_response(
        self, 
        user_question: str, 
        context: str,
        model: str = "qwen-turbo",
        temperature: float = 0.7,
        max_tokens: int = 1500
    ) -> str:
        """
        生成智能推荐回答
        
        Args:
            user_question: 用户问题
            context: 检索到的动漫信息上下文
            model: 使用的模型名称
            temperature: 创造性参数
            max_tokens: 最大token数
            
        Returns:
            生成的推荐回答
        """
        
        # 构建专门的动漫推荐Prompt
        prompt = self._build_anime_recommendation_prompt(user_question, context)
        
        payload = {
            "model": model,
            "input": {
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一个专业的动漫推荐助手，具有丰富的动漫知识和推荐经验。你的回答应该热情、专业、有趣，能够根据用户需求提供个性化的动漫推荐。"
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ]
            },
            "parameters": {
                "temperature": temperature,
                "max_tokens": max_tokens,
                "top_p": 0.8,
                "result_format": "message"
            }
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.base_url,
                    headers=self.headers,
                    json=payload
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get("output") and result["output"].get("choices"):
                        return result["output"]["choices"][0]["message"]["content"]
                    else:
                        logger.error(f"API响应格式异常: {result}")
                        return self._fallback_response(user_question, context)
                else:
                    logger.error(f"API调用失败: {response.status_code}, {response.text}")
                    return self._fallback_response(user_question, context)
                    
        except Exception as e:
            logger.exception(f"千问API调用异常: {e}")
            return self._fallback_response(user_question, context)
    
    async def generate_streaming_response(
        self, 
        user_question: str, 
        context: str,
        model: str = "qwen-turbo",
        temperature: float = 0.7,
        max_tokens: int = 1500
    ) -> AsyncGenerator[str, None]:
        """
        生成流式智能推荐回答
        
        Args:
            user_question: 用户问题
            context: 检索到的动漫信息上下文
            model: 使用的模型名称
            temperature: 创造性参数
            max_tokens: 最大token数
            
        Yields:
            流式文本片段
        """
        
        # 构建专门的流式动漫推荐Prompt
        prompt = self._build_streaming_anime_recommendation_prompt(user_question, context)
        
        payload = {
            "model": model,
            "input": {
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一个专业的动漫推荐助手。请按照指定格式进行推荐，在每个动漫介绍后使用特殊标记来指示图片显示时机。"
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ]
            },
            "parameters": {
                "temperature": temperature,
                "max_tokens": max_tokens,
                "top_p": 0.8,
                "result_format": "message",
                "stream": True,              # 启用流式输出
                "incremental_output": True   # 启用增量输出
            }
        }
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream(
                    "POST",
                    self.base_url,
                    headers={
                        **self.headers,
                        "Accept": "text/event-stream"  # 接受SSE格式
                    },
                    json=payload
                ) as response:
                    if response.status_code == 200:
                        async for chunk in self._parse_streaming_response(response):
                            if chunk:
                                yield chunk
                    else:
                        error_text = await response.aread()
                        logger.error(f"流式API调用失败: {response.status_code}, {error_text}")
                        # 降级到非流式方法
                        fallback_response = await self.generate_response(user_question, context, model, temperature, max_tokens)
                        yield fallback_response
                        
        except Exception as e:
            logger.exception(f"流式千问API调用异常: {e}")
            # 降级到非流式方法
            try:
                fallback_response = await self.generate_response(user_question, context, model, temperature, max_tokens)
                yield fallback_response
            except Exception as fallback_error:
                logger.exception(f"降级调用也失败: {fallback_error}")
                yield self._fallback_response(user_question, context)
    
    async def _parse_streaming_response(self, response) -> AsyncGenerator[str, None]:
        """
        解析千问API的流式响应（SSE格式）
        
        Args:
            response: httpx流式响应对象
            
        Yields:
            解析出的文本片段
        """
        buffer = ""
        
        async for chunk_bytes in response.aiter_bytes():
            chunk = chunk_bytes.decode('utf-8', errors='ignore')
            buffer += chunk
            
            # 按行处理SSE事件
            while '\n' in buffer:
                line, buffer = buffer.split('\n', 1)
                line = line.strip()
                
                if line.startswith('data: '):
                    data = line[6:]  # 移除 'data: ' 前缀
                    
                    # 检查结束标记
                    if data == '[DONE]':
                        return
                    
                    try:
                        # 解析JSON数据
                        event_data = json.loads(data)
                        
                        # 提取文本内容
                        if 'output' in event_data:
                            output = event_data['output']
                            if 'choices' in output and output['choices']:
                                choice = output['choices'][0]
                                
                                # 处理不同的响应格式
                                if 'delta' in choice:
                                    # 增量模式
                                    delta = choice['delta']
                                    if 'content' in delta:
                                        yield delta['content']
                                elif 'message' in choice:
                                    # 消息模式
                                    message = choice['message']
                                    if 'content' in message:
                                        yield message['content']
                                        
                    except json.JSONDecodeError as e:
                        logger.warning(f"解析SSE数据失败: {data}, 错误: {e}")
                        continue
                    except Exception as e:
                        logger.warning(f"处理SSE事件失败: {e}")
                        continue
    
    async def generate_streaming_with_triggers(
        self, 
        user_question: str, 
        anime_list: List[Dict],
        model: str = "qwen-turbo",
        temperature: float = 0.7,
        max_tokens: int = 1500
    ) -> AsyncGenerator[Dict, None]:
        """
        生成带图片触发标记的流式推荐
        
        Args:
            user_question: 用户问题
            anime_list: 推荐的动漫列表
            model: 使用的模型名称
            temperature: 创造性参数
            max_tokens: 最大token数
            
        Yields:
            Dict: {"type": "text|image_trigger", "content": "...", "anime_data": {...}}
        """
        
        # 构建上下文
        context = self._build_context_from_anime_list(anime_list)
        
        current_anime_index = 0
        accumulated_text = ""
        
        async for text_chunk in self.generate_streaming_response(
            user_question, context, model, temperature, max_tokens
        ):
            accumulated_text += text_chunk
            
            # 检测图片触发标记
            trigger_pattern = f"[IMAGE_TRIGGER:{current_anime_index}]"
            if trigger_pattern in accumulated_text:
                # 移除触发标记
                clean_text = accumulated_text.replace(trigger_pattern, "")
                
                yield {
                    "type": "image_trigger",
                    "content": text_chunk,
                    "clean_text": clean_text,
                    "anime_index": current_anime_index,
                    "anime_data": anime_list[current_anime_index] if current_anime_index < len(anime_list) else None
                }
                
                current_anime_index += 1
                accumulated_text = clean_text
            else:
                # 普通文本
                yield {
                    "type": "text",
                    "content": text_chunk,
                    "accumulated_text": accumulated_text
                }
    
    def _build_streaming_anime_recommendation_prompt(self, user_question: str, context: str) -> str:
        """构建流式动漫推荐专用的Prompt"""
        
        prompt = f"""请根据用户的问题和提供的动漫信息，生成一个专业、热情的动漫推荐回答。

用户问题：{user_question}

相关动漫信息：
{context}

请按以下格式要求回答：

1. **开场**：简短回应用户的问题（1-2句话）

2. **推荐格式**：对每部动漫按以下格式推荐
   🎬《动漫标题》- 简短介绍（20-30字）
   [IMAGE_TRIGGER:0]  ← 第一部动漫后插入此标记
   
   🎬《动漫标题》- 简短介绍（20-30字）
   [IMAGE_TRIGGER:1]  ← 第二部动漫后插入此标记
   
   （依此类推）

3. **结尾**：简短的总结和友好结束语

重要要求：
- 严格按照 [IMAGE_TRIGGER:数字] 格式插入标记
- 每个标记后必须换行
- 介绍要简洁有趣，突出作品特色
- 使用表情符号增加趣味性
- 总字数控制在200-400字

请开始你的推荐："""
        
        return prompt
    
    def _build_context_from_anime_list(self, anime_list: List[Dict]) -> str:
        """从动漫列表构建上下文"""
        context_parts = []
        for i, anime in enumerate(anime_list):
            title = anime.get('title_zh') or anime.get('name_cn', f'动漫{i+1}')
            description = anime.get('description_zh') or anime.get('description', '精彩的动漫作品')
            rating = anime.get('average_score') or anime.get('rating')
            
            context_info = f"- 《{title}》: {description[:50]}"
            if rating:
                context_info += f" (评分: {rating})"
            context_parts.append(context_info)
        
        return "\n".join(context_parts)
    
    def _build_anime_recommendation_prompt(self, user_question: str, context: str) -> str:
        """构建动漫推荐专用的Prompt（支持图片信息）"""
        
        prompt = f"""请根据用户的问题和提供的动漫信息，生成一个专业、热情的动漫推荐回答。

用户问题：{user_question}

相关动漫信息：
{context}

请按以下要求回答：

1. **开场**：简短回应用户的问题
2. **推荐**：对每部动漫进行详细推荐，包括：
   - 作品亮点和特色
   - 为什么推荐给用户
   - 适合的观看人群
   - 如果有图片信息，请在推荐中提及"精美的视觉效果"或"经典的画面"
3. **额外建议**：如果有相关的其他推荐或观看建议
4. **结尾**：友好的结束语，询问是否需要更多信息

特殊要求：
- 如果动漫信息中包含图片URL，请在回答中提及该作品的视觉表现
- 如果有评分信息，请在推荐中体现
- 如果有制作公司和导演信息，可以作为推荐亮点
- 回答要热情、专业、有趣
- 使用表情符号增加趣味性
- 突出每部作品的独特之处
- 语言自然流畅，符合中文表达习惯
- 回答长度控制在300-500字之间

请开始你的推荐："""
        
        return prompt
    
    def _fallback_response(self, user_question: str, context: str) -> str:
        """API失败时的后备回答"""
        return f"""🎌 根据您的问题「{user_question}」，我为您推荐以下动漫作品：

{context}

💡 这些作品都是根据您的喜好精心挑选的，希望您会喜欢！如果需要更详细的介绍或其他推荐，请随时告诉我~"""

# 全局实例
qwen_client = None

def get_qwen_client() -> QwenAPI:
    """获取千问API客户端实例"""
    global qwen_client
    if qwen_client is None:
        try:
            qwen_client = QwenAPI()
        except ValueError as e:
            logger.error(f"千问API初始化失败: {e}")
            # 抛出更明确的异常，让上层处理
            raise RuntimeError(f"千问API配置错误: {e}")
    return qwen_client