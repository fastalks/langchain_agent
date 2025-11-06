#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对比测试三种流式推荐方案的用户体验
1. 标准流式：文本流式 + 图片一次性显示
2. 渐进式：文案与图片同步显示  
3. 普通推荐：无流式效果
"""

import asyncio
import aiohttp
import json
import time
from typing import Dict, Any, List

async def simulate_typing_effect(text: str, delay: float = 0.05, name: str = ""):
    """模拟打字机效果"""
    print(f"\n{name}:")
    print("-" * 50)
    displayed_text = ""
    for char in text:
        displayed_text += char
        print(f"\r{displayed_text}", end="", flush=True)
        await asyncio.sleep(delay)
    print()  # 换行

async def simulate_chunked_typing(chunks: List[str], delay: float = 0.1, name: str = ""):
    """模拟分块打字机效果"""
    print(f"\n{name}:")
    print("-" * 50)
    displayed_text = ""
    for i, chunk in enumerate(chunks):
        print(f"[块 {i+1}/{len(chunks)}] ", end="", flush=True)
        for char in chunk:
            displayed_text += char
            print(f"\r{displayed_text}", end="", flush=True)
            await asyncio.sleep(delay / len(chunk))  # 均匀分布时间
        await asyncio.sleep(delay)  # 块间停顿
    print()

async def simulate_progressive_display(progressive_items: List[Dict], name: str = ""):
    """模拟渐进式显示效果"""
    print(f"\n{name}:")
    print("-" * 50)
    
    for item in progressive_items:
        item_type = item.get("type", "unknown")
        text = item.get("text", "")
        anime = item.get("anime")
        delay = item.get("delay", 0.5)
        
        # 显示文本内容
        print(f"\n[{item_type.upper()}]", end=" ")
        for char in text:
            print(char, end="", flush=True)
            await asyncio.sleep(0.03)  # 较快的打字速度
        
        # 如果有动漫数据，显示图片信息
        if anime:
            await asyncio.sleep(0.3)  # 短暂停顿
            title = anime.get('title_zh') or anime.get('name_cn', '未知')
            cover = anime.get('cover_image')
            rating = anime.get('average_score') or anime.get('rating')
            
            print(f"\n   📷 封面图片: {'✅ 加载' if cover else '❌ 无'}")
            if cover:
                print(f"   🔗 {cover}")
            if rating:
                print(f"   ⭐ 评分: {rating}")
        
        await asyncio.sleep(delay)  # 项目间停顿

async def test_api_and_simulate(session: aiohttp.ClientSession, endpoint: str, data: Dict[str, Any], simulation_name: str):
    """测试API并模拟显示效果"""
    print(f"\n{'='*60}")
    print(f"🎯 测试：{simulation_name}")
    print(f"📡 接口：{endpoint}")
    print('='*60)
    
    start_time = time.time()
    
    try:
        async with session.post(endpoint, json=data) as response:
            if response.status == 200:
                result = await response.json()
                response_time = time.time() - start_time
                
                print(f"✅ API响应成功 - 耗时: {response_time:.3f}秒")
                print(f"📊 数据大小: {len(json.dumps(result).encode())} 字节")
                
                # 根据不同的响应类型模拟显示效果
                if "answer_chunks" in result:
                    # 标准流式推荐
                    chunks = result["answer_chunks"]
                    recommendations = result.get("recommendations", [])
                    
                    print(f"📝 文本分为 {len(chunks)} 块")
                    await simulate_chunked_typing(chunks, delay=0.8, name="📝 打字机效果模拟")
                    
                    print(f"\n🖼️ 显示 {len(recommendations)} 个推荐项的图片:")
                    for i, anime in enumerate(recommendations, 1):
                        title = anime.get('title_zh') or anime.get('name_cn', f'动漫{i}')
                        cover = anime.get('cover_image')
                        print(f"   {i}. {title} - {'✅ 有图片' if cover else '❌ 无图片'}")
                    
                elif "progressive_items" in result:
                    # 渐进式推荐
                    items = result["progressive_items"]
                    estimated_duration = result.get("estimated_duration", 0)
                    
                    print(f"🎬 渐进式显示 {len(items)} 个项目")
                    print(f"⏱️ 预估总时长: {estimated_duration:.1f}秒")
                    await simulate_progressive_display(items, name="🎬 渐进式显示模拟")
                    
                else:
                    # 普通推荐
                    answer = result.get("answer", "")
                    recommendations = result.get("recommendations", [])
                    
                    print("⚡ 一次性显示全部内容:")
                    print(f"📝 回答: {answer[:100]}...")
                    print(f"🖼️ 同时显示 {len(recommendations)} 张图片")
                
                # 显示性能数据
                query_time = result.get("query_time", 0)
                print(f"\n📈 性能分析:")
                print(f"   🔍 查询处理: {query_time:.3f}秒")
                print(f"   🌐 网络传输: {response_time:.3f}秒")
                print(f"   💾 数据量: {len(json.dumps(result).encode())} 字节")
                
                return {
                    "success": True,
                    "data": result,
                    "response_time": response_time,
                    "data_size": len(json.dumps(result).encode())
                }
            else:
                error_text = await response.text()
                print(f"❌ API调用失败: {response.status} - {error_text}")
                return {"success": False, "error": error_text}
                
    except Exception as e:
        print(f"💥 异常: {str(e)}")
        return {"success": False, "error": str(e)}

async def main():
    print("🧪 流式推荐方案对比测试")
    print("="*80)
    
    # 测试配置
    base_url = "http://localhost:8000"
    test_question = "推荐一些治愈系的动漫作品"
    request_data = {"question": test_question}
    
    # 三种方案的测试配置
    test_scenarios = [
        {
            "name": "标准流式推荐（文本流式 + 图片一次性）",
            "endpoint": f"{base_url}/api/recommendations/streaming",
            "description": "文字逐块显示，所有图片同时加载"
        },
        {
            "name": "渐进式推荐（文案图片同步）", 
            "endpoint": f"{base_url}/api/recommendations/progressive",
            "description": "文案和对应图片逐步显示"
        },
        {
            "name": "普通推荐（无流式效果）",
            "endpoint": f"{base_url}/api/recommendations",
            "description": "所有内容一次性显示"
        }
    ]
    
    results = []
    
    async with aiohttp.ClientSession() as session:
        print(f"📝 测试问题: {test_question}")
        
        # 依次测试每种方案
        for scenario in test_scenarios:
            result = await test_api_and_simulate(
                session=session,
                endpoint=scenario["endpoint"], 
                data=request_data,
                simulation_name=scenario["name"]
            )
            
            result["scenario"] = scenario
            results.append(result)
            
            # 方案间的停顿
            await asyncio.sleep(2)
    
    # 生成对比报告
    print("\n" + "="*80)
    print("📊 综合对比报告")
    print("="*80)
    
    # 性能对比
    print("\n🚀 性能对比:")
    for result in results:
        if result["success"]:
            scenario_name = result["scenario"]["name"]
            response_time = result["response_time"]
            data_size = result["data_size"]
            
            print(f"\n{scenario_name}:")
            print(f"   ⏱️ 响应时间: {response_time:.3f}秒")
            print(f"   💾 数据大小: {data_size} 字节")
            print(f"   📱 移动端友好: {'✅' if data_size < 2000 else '⚠️' if data_size < 5000 else '❌'}")
    
    # 用户体验分析
    print(f"\n🎭 用户体验分析:")
    
    streaming_result = next((r for r in results if "streaming" in r["scenario"]["endpoint"]), None)
    progressive_result = next((r for r in results if "progressive" in r["scenario"]["endpoint"]), None)
    normal_result = next((r for r in results if r["scenario"]["endpoint"].endswith("/recommendations")), None)
    
    print(f"\n💡 推荐方案选择:")
    
    if streaming_result and streaming_result["success"]:
        chunks_count = len(streaming_result["data"].get("answer_chunks", []))
        print(f"📝 标准流式 - 分块数: {chunks_count}")
        if chunks_count <= 5:
            print("   ✅ 推荐：分块合理，体验良好")
        elif chunks_count <= 10:
            print("   ⚠️ 一般：可考虑优化分块策略")
        else:
            print("   ❌ 不推荐：分块过多，等待时间长")
    
    if progressive_result and progressive_result["success"]:
        items_count = len(progressive_result["data"].get("progressive_items", []))
        estimated_duration = progressive_result["data"].get("estimated_duration", 0)
        print(f"🎬 渐进式 - 项目数: {items_count}, 预估时长: {estimated_duration:.1f}秒")
        if estimated_duration <= 8:
            print("   ✅ 推荐：沉浸感强，时长合理")
        elif estimated_duration <= 15:
            print("   ⚠️ 一般：体验不错，但较耗时")
        else:
            print("   ❌ 不推荐：等待时间过长")
    
    if normal_result and normal_result["success"]:
        data_size = normal_result["data_size"]
        print(f"⚡ 普通推荐 - 数据量: {data_size} 字节")
        if data_size <= 3000:
            print("   ✅ 推荐：快速响应，适合急需结果")
        else:
            print("   ⚠️ 一般：数据量较大，但响应直接")
    
    # 使用建议
    print(f"\n🎯 使用场景建议:")
    print("📱 移动端/慢网络 → 标准流式推荐")
    print("🖥️ PC端/展示场景 → 渐进式推荐") 
    print("⚡ 快速查询/API调用 → 普通推荐")
    print("🎮 游戏化体验 → 渐进式推荐")
    print("📊 数据展示 → 普通推荐")
    
    print(f"\n🏁 测试完成！")

if __name__ == "__main__":
    asyncio.run(main())