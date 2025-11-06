#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对比测试：流式打字机效果 vs 普通返回方式
测试三种API接口的性能和用户体验
"""

import asyncio
import aiohttp
import json
import time
from typing import Dict, Any
import sys
sys.path.append('/Users/wangfaguo/Desktop/langchain_agent/langchain_agent')

async def test_api_endpoint(session: aiohttp.ClientSession, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """测试单个API端点"""
    start_time = time.time()
    
    try:
        async with session.post(endpoint, json=data) as response:
            if response.status == 200:
                result = await response.json()
                response_time = time.time() - start_time
                return {
                    "success": True,
                    "data": result,
                    "response_time": response_time,
                    "status": response.status
                }
            else:
                error_text = await response.text()
                return {
                    "success": False,
                    "error": error_text,
                    "response_time": time.time() - start_time,
                    "status": response.status
                }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "response_time": time.time() - start_time,
            "status": None
        }

async def simulate_typing_effect(answer_chunks: list, delay: float = 0.1):
    """模拟打字机效果"""
    print("\n" + "="*60)
    print("🎭 模拟打字机效果展示:")
    print("="*60)
    
    displayed_text = ""
    for i, chunk in enumerate(answer_chunks):
        displayed_text += chunk
        print(f"\r{displayed_text}", end="", flush=True)
        await asyncio.sleep(delay)
    
    print()  # 换行
    print("="*60)

async def analyze_response_structure(data: Dict[str, Any], endpoint_name: str):
    """分析返回数据结构"""
    print(f"\n📊 {endpoint_name} 数据结构分析:")
    print(f"   - 推荐数量: {data.get('total_found', 0)}")
    print(f"   - 查询时间: {data.get('query_time', 0):.3f}秒")
    
    # 分析回答内容
    if 'answer' in data:
        answer = data['answer']
        print(f"   - 回答字数: {len(answer)}")
        print(f"   - 回答预览: {answer[:50]}...")
    
    if 'answer_chunks' in data:
        chunks = data['answer_chunks']
        print(f"   - 分块数量: {len(chunks)}")
        print(f"   - 平均块大小: {sum(len(chunk) for chunk in chunks) / len(chunks):.1f}字符")
    
    # 分析推荐数据
    recommendations = data.get('recommendations', [])
    if recommendations:
        print(f"   - 第一个推荐:")
        first_rec = recommendations[0]
        print(f"     * 标题: {first_rec.get('title', 'N/A')}")
        print(f"     * 评分: {first_rec.get('score', 'N/A')}")
        similarity = first_rec.get('similarity', 'N/A')
        if isinstance(similarity, (int, float)):
            print(f"     * 相似度: {similarity:.3f}")
        else:
            print(f"     * 相似度: {similarity}")
        
        # 检查图片链接
        if 'image_large' in first_rec:
            print(f"     * 大图链接: {first_rec['image_large']}")

async def main():
    print("🧪 开始测试三种推荐API接口的对比")
    print("="*80)
    
    # 测试数据
    test_question = "推荐一些治愈系的动漫作品"
    base_url = "http://localhost:8000"
    
    endpoints = {
        "格式化推荐": f"{base_url}/api/recommendations",
        "简化推荐": f"{base_url}/api/recommendations/simple", 
        "流式推荐": f"{base_url}/api/recommendations/streaming"
    }
    
    request_data = {"question": test_question}
    
    async with aiohttp.ClientSession() as session:
        print(f"📝 测试问题: {test_question}")
        print("-" * 80)
        
        results = {}
        
        # 测试每个端点
        for name, endpoint in endpoints.items():
            print(f"\n🔍 测试 {name} 接口...")
            result = await test_api_endpoint(session, endpoint, request_data)
            results[name] = result
            
            if result["success"]:
                print(f"✅ 成功 - 响应时间: {result['response_time']:.3f}秒")
                await analyze_response_structure(result["data"], name)
                
                # 如果是流式推荐，演示打字机效果
                if name == "流式推荐" and "answer_chunks" in result["data"]:
                    chunks = result["data"]["answer_chunks"]
                    await simulate_typing_effect(chunks, delay=0.05)
                    
            else:
                print(f"❌ 失败 - {result['error']}")
        
        # 性能对比分析
        print("\n" + "="*80)
        print("📈 性能对比分析")
        print("="*80)
        
        for name, result in results.items():
            if result["success"]:
                data = result["data"]
                response_time = result["response_time"]
                query_time = data.get("query_time", 0)
                
                print(f"\n{name}:")
                print(f"  🕐 网络响应时间: {response_time:.3f}秒")
                print(f"  🔍 查询处理时间: {query_time:.3f}秒")
                print(f"  📊 数据传输大小: {len(json.dumps(data, ensure_ascii=False))} 字符")
                
                # 特殊分析
                if name == "流式推荐":
                    chunks = data.get("answer_chunks", [])
                    if chunks:
                        estimated_typing_time = len(chunks) * 0.1  # 假设每块0.1秒
                        print(f"  ⌨️  预估打字时间: {estimated_typing_time:.1f}秒")
        
        # 用户体验建议
        print("\n" + "="*80)
        print("💡 用户体验建议")
        print("="*80)
        
        streaming_result = results.get("流式推荐", {})
        if streaming_result.get("success"):
            data = streaming_result["data"]
            chunks = data.get("answer_chunks", [])
            
            print(f"🎯 打字机效果分析:")
            print(f"   - 分块质量: {'✅ 良好' if len(chunks) > 3 else '⚠️ 可优化'}")
            print(f"   - 语义完整性: {'✅ 保持' if all('。' in chunk or '！' in chunk or '？' in chunk for chunk in chunks[:-1]) else '⚠️ 需改进'}")
            print(f"   - 用户等待时间: {'✅ 可接受' if len(chunks) * 0.1 < 3 else '⚠️ 过长'}")
            
            print(f"\n🎭 实施建议:")
            if len(chunks) <= 5:
                print("   ✅ 推荐使用打字机效果 - 分块合理，用户体验佳")
            elif len(chunks) <= 10:
                print("   ⚠️ 可选使用打字机效果 - 建议加快打字速度")
            else:
                print("   ❌ 不推荐打字机效果 - 分块过多，用户等待时间长")
        
        print("\n🏁 测试完成！")

if __name__ == "__main__":
    asyncio.run(main())