# qwen_api.py - 千问API集成模块

import os
import httpx
import json
from typing import List, Dict, Optional
import logging

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
        qwen_client = QwenAPI()
    return qwen_client