#!/usr/bin/env python3
"""
测试新的流式推荐API端点
验证千问流式集成是否正常工作
"""

import asyncio
import aiohttp
import json
import time
from typing import AsyncGenerator

class StreamingAPITester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        
    async def test_qwen_streaming_basic(self):
        """测试基础千问流式API"""
        print("🧪 测试基础千问流式API")
        
        url = f"{self.base_url}/api/recommendations/qwen-streaming"
        payload = {"question": "推荐一些热血动漫"}
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        print(f"✅ 基础API调用成功")
                        print(f"   - 动漫数量: {result.get('total_found', 0)}")
                        print(f"   - 查询时间: {result.get('query_time', 0)}秒")
                        print(f"   - 动漫列表: {len(result.get('anime_list', []))}")
                        return True
                    else:
                        print(f"❌ API调用失败: {response.status}")
                        error_text = await response.text()
                        print(f"   错误详情: {error_text}")
                        return False
            except Exception as e:
                print(f"❌ 请求异常: {e}")
                return False
    
    async def test_sse_streaming(self):
        """测试Server-Sent Events流式API"""
        print("\n🌊 测试SSE流式API")
        
        url = f"{self.base_url}/api/recommendations/qwen-streaming-sse"
        payload = {"question": "推荐一些治愈系动漫"}
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        print("✅ SSE连接建立成功")
                        
                        text_chunks = []
                        image_triggers = []
                        
                        async for line in response.content:
                            line_str = line.decode('utf-8').strip()
                            
                            if line_str.startswith('data: '):
                                data_str = line_str[6:]  # 移除 'data: ' 前缀
                                try:
                                    data = json.loads(data_str)
                                    
                                    if data['type'] == 'anime_list':
                                        print(f"   📺 收到动漫列表: {len(data['content'])}部")
                                        
                                    elif data['type'] == 'text':
                                        text_content = data['content']
                                        text_chunks.append(text_content)
                                        print(f"   📝 文本片段: {text_content[:50]}...")
                                        
                                    elif data['type'] == 'image_trigger':
                                        trigger_info = data['content']
                                        image_triggers.append(trigger_info)
                                        print(f"   🖼️  图片触发: {trigger_info}")
                                        
                                    elif data['type'] == 'complete':
                                        print("   ✅ 流式传输完成")
                                        break
                                        
                                    elif data['type'] == 'error':
                                        print(f"   ❌ 流式错误: {data['content']}")
                                        break
                                        
                                except json.JSONDecodeError:
                                    print(f"   ⚠️  JSON解析失败: {data_str}")
                        
                        print(f"\n📊 SSE流式测试总结:")
                        print(f"   - 文本片段数: {len(text_chunks)}")
                        print(f"   - 图片触发数: {len(image_triggers)}")
                        print(f"   - 完整文本: {''.join(text_chunks)[:100]}...")
                        
                        return len(text_chunks) > 0
                        
                    else:
                        print(f"❌ SSE连接失败: {response.status}")
                        return False
                        
            except Exception as e:
                print(f"❌ SSE测试异常: {e}")
                return False
    
    async def test_realtime_streaming(self):
        """测试实时流式推荐API"""
        print("\n⚡ 测试实时流式推荐API")
        
        url = f"{self.base_url}/api/recommendations/realtime-streaming"
        payload = {
            "question": "推荐一些科幻动漫",
            "enable_image_triggers": True,
            "max_recommendations": 2
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                start_time = time.time()
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        print("✅ 实时流式连接建立")
                        
                        events = []
                        text_buffer = ""
                        
                        async for line in response.content:
                            line_str = line.decode('utf-8').strip()
                            
                            if line_str.startswith('data: '):
                                data_str = line_str[6:]
                                try:
                                    data = json.loads(data_str)
                                    events.append(data)
                                    
                                    event_type = data['type']
                                    
                                    if event_type == 'start':
                                        print(f"   🚀 {data.get('message', '开始')}")
                                        
                                    elif event_type == 'status':
                                        print(f"   📊 状态: {data.get('message', '')}")
                                        
                                    elif event_type == 'search_results':
                                        anime_count = len(data.get('anime_list', []))
                                        print(f"   🔍 搜索完成: 找到{anime_count}部动漫")
                                        
                                    elif event_type == 'text_chunk':
                                        chunk = data.get('content', '')
                                        text_buffer = data.get('buffer', text_buffer)
                                        print(f"   📝 文本: {chunk}", end='', flush=True)
                                        
                                    elif event_type == 'image_trigger':
                                        anime_uuid = data.get('anime_uuid', '')
                                        trigger_text = data.get('trigger_text', '')
                                        print(f"\n   🖼️  图片触发: {anime_uuid} - {trigger_text}")
                                        
                                    elif event_type == 'complete':
                                        elapsed = time.time() - start_time
                                        total_anime = data.get('total_anime', 0)
                                        print(f"\n   ✅ 完成! 耗时{elapsed:.2f}秒, 推荐{total_anime}部动漫")
                                        break
                                        
                                    elif event_type == 'error':
                                        print(f"\n   ❌ 错误: {data.get('content', '')}")
                                        break
                                        
                                except json.JSONDecodeError:
                                    print(f"   ⚠️  JSON解析错误: {data_str}")
                        
                        print(f"\n📈 实时流式测试统计:")
                        print(f"   - 事件总数: {len(events)}")
                        print(f"   - 文本长度: {len(text_buffer)}字符")
                        print(f"   - 处理时间: {time.time() - start_time:.2f}秒")
                        
                        return len(events) > 0
                        
                    else:
                        print(f"❌ 实时流式连接失败: {response.status}")
                        return False
                        
            except Exception as e:
                print(f"❌ 实时流式测试异常: {e}")
                return False

async def run_comprehensive_test():
    """运行综合测试"""
    print("🎯 开始综合流式API测试")
    print("=" * 60)
    
    tester = StreamingAPITester()
    
    # 测试序列
    tests = [
        ("基础千问流式API", tester.test_qwen_streaming_basic),
        ("SSE流式API", tester.test_sse_streaming),
        ("实时流式推荐API", tester.test_realtime_streaming),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            success = await test_func()
            results.append((test_name, success))
            print(f"结果: {'✅ 通过' if success else '❌ 失败'}")
        except Exception as e:
            print(f"❌ 测试异常: {e}")
            results.append((test_name, False))
    
    # 测试总结
    print(f"\n{'='*60}")
    print("📋 测试总结报告:")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"   {status} {test_name}")
    
    print(f"\n🎯 测试通过率: {passed}/{total} ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("🎉 所有流式API测试通过！新功能已成功集成。")
    else:
        print("⚠️  部分测试失败，请检查服务状态和配置。")

if __name__ == "__main__":
    print("🔧 流式推荐API测试工具")
    print("📝 此工具测试新集成的千问流式功能")
    print()
    
    try:
        asyncio.run(run_comprehensive_test())
    except KeyboardInterrupt:
        print("\n⏹️  测试被用户中断")
    except Exception as e:
        print(f"\n💥 测试过程异常: {e}")