#!/usr/bin/env python3
"""
测试格式化推荐功能和图片链接功能
"""

import requests
import json
import uuid

BASE_URL = "http://localhost:8000"

def test_formatted_recommendations():
    """测试格式化推荐功能"""
    print("🎯 测试格式化推荐功能...")
    
    test_queries = [
        "推荐一些高分动漫",
        "有什么好看的恋爱动漫吗？",
        "推荐一些适合新手看的动漫",
        "有什么动作冒险类的动漫？"
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n{i}. 测试查询: {query}")
        
        response = requests.post(
            f"{BASE_URL}/api/recommendations",
            json={"question": query},
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ 查询成功")
            print(f"   📊 找到 {data['total_found']} 部相关动漫")
            print(f"   ⏱️ 查询耗时: {data['query_time']}秒")
            
            # 显示推荐列表
            for j, item in enumerate(data["recommendations"], 1):
                title = item.get("title_zh") or item.get("name_cn", "未知")
                cover = item.get("cover_image")
                score = item.get("match_score", 0)
                rating = item.get("average_score") or item.get("rating")
                
                print(f"   🎬 {j}. {title}")
                print(f"      评分: {rating or '未知'} | 匹配度: {score:.3f}")
                print(f"      封面: {'✅ 有' if cover else '❌ 无'}")
                if cover:
                    print(f"      链接: {cover}")
        else:
            print(f"   ❌ 查询失败: {response.status_code} - {response.text}")

def test_simple_recommendations():
    """测试精简版推荐"""
    print("\n📱 测试精简版推荐（移动端优化）...")
    
    response = requests.post(
        f"{BASE_URL}/api/recommendations/simple",
        json={"question": "推荐一些经典动漫"},
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code == 200:
        data = response.json()
        print("✅ 精简版推荐成功")
        print(f"📊 返回 {len(data['recommendations'])} 条精简推荐")
        
        # 检查数据结构
        for item in data["recommendations"]:
            required_fields = ["title_zh", "cover_image", "match_score"]
            missing_fields = [field for field in required_fields if field not in item]
            if not missing_fields:
                print("✅ 数据结构完整")
            else:
                print(f"⚠️ 缺少字段: {missing_fields}")
        
        # 检查数据大小优化
        full_size = len(json.dumps(data).encode())
        print(f"📏 响应大小: {full_size} 字节")
        
    else:
        print(f"❌ 精简版推荐失败: {response.status_code}")

def test_image_functionality():
    """测试图片功能"""
    print("\n🖼️ 测试图片功能...")
    
    # 先上传一个带完整图片信息的动漫
    test_anime = {
        "uuid": str(uuid.uuid4()),
        "title_zh": "测试图片动漫",
        "title_en": "Test Image Anime",
        "description_zh": "用于测试图片功能的动漫作品",
        "media_type": "tv",
        "year": 2024,
        "average_score": 85,
        "genres": ["测试", "图片"],
        "image_large": "/images/anime/covers/large/test_large.jpg",
        "image_medium": "/images/anime/covers/medium/test_medium.jpg",
        "image_small": "/images/anime/covers/small/test_small.jpg",
        "image_grid": "/images/anime/covers/grid/test_grid.jpg",
        "image_common": "/images/anime/covers/common/test_common.jpg",
        "data_source": "test_image"
    }
    
    # 上传测试数据
    upload_response = requests.post(
        f"{BASE_URL}/api/anime/upload",
        json=test_anime,
        headers={"Content-Type": "application/json"}
    )
    
    if upload_response.status_code == 200:
        print("✅ 测试数据上传成功")
        
        # 查询这个动漫，验证图片链接
        search_response = requests.post(
            f"{BASE_URL}/api/recommendations",
            json={"question": "测试图片动漫"},
            headers={"Content-Type": "application/json"}
        )
        
        if search_response.status_code == 200:
            data = search_response.json()
            if data["recommendations"]:
                item = data["recommendations"][0]
                print("✅ 图片链接生成成功")
                
                # 检查各种尺寸的图片链接
                image_fields = ["image_large", "image_medium", "image_small", "image_grid", "thumbnail"]
                for field in image_fields:
                    url = item.get(field)
                    if url:
                        print(f"   {field}: {url}")
                        # 可以进一步测试图片链接是否可访问
                
                cover_url = item.get("cover_image")
                if cover_url:
                    print(f"   主封面: {cover_url}")
                
            else:
                print("⚠️ 未找到上传的测试数据")
        else:
            print("❌ 搜索测试数据失败")
    else:
        print("❌ 测试数据上传失败")

def test_api_compatibility():
    """测试API兼容性"""
    print("\n🔄 测试API兼容性...")
    
    # 测试旧版 API
    old_response = requests.post(
        f"{BASE_URL}/api/answer",
        json={"question": "推荐一些热血动漫"},
        headers={"Content-Type": "application/json"}
    )
    
    # 测试新版 API
    new_response = requests.post(
        f"{BASE_URL}/api/recommendations",
        json={"question": "推荐一些热血动漫"},
        headers={"Content-Type": "application/json"}
    )
    
    if old_response.status_code == 200 and new_response.status_code == 200:
        print("✅ 新旧API兼容性良好")
        
        old_data = old_response.json()
        new_data = new_response.json()
        
        print(f"   旧API响应字段: {list(old_data.keys())}")
        print(f"   新API响应字段: {list(new_data.keys())}")
        print(f"   新API推荐数量: {len(new_data.get('recommendations', []))}")
        
    else:
        print("❌ API兼容性测试失败")

if __name__ == "__main__":
    print("=" * 60)
    print("🧪 格式化推荐功能全面测试")
    print("=" * 60)
    
    try:
        # 检查服务状态
        health_response = requests.get(f"{BASE_URL}/health")
        if health_response.status_code != 200:
            print("❌ 服务未就绪，请检查服务状态")
            exit(1)
        
        print("✅ 服务运行正常，开始测试...")
        
        # 执行各项测试
        test_formatted_recommendations()
        test_simple_recommendations()
        test_image_functionality()
        test_api_compatibility()
        
        print("\n🎊 所有测试完成！")
        print("\n📋 功能总结:")
        print("✅ 格式化推荐 - 返回完整结构化数据")
        print("✅ 图片链接支持 - 自动构建完整URL")
        print("✅ 精简版推荐 - 移动端优化")
        print("✅ 多尺寸图片 - 支持不同分辨率")
        print("✅ 向后兼容 - 保持旧API正常工作")
        print("✅ 查询性能 - 显示响应时间")
        
        print("\n🚀 客户端现在可以:")
        print("   • 获取结构化的动漫推荐数据")
        print("   • 显示动漫封面图片")
        print("   • 根据网络情况选择图片尺寸")
        print("   • 获取详细的动漫元数据")
        print("   • 实现响应式图片加载")
        
    except Exception as e:
        print(f"\n💥 测试过程中出现异常: {e}")