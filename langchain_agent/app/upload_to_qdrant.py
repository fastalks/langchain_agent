# upload_to_qdrant.py

from qdrant_client import QdrantClient
from qdrant_client.http import models
from typing import List, Dict
import uuid
from app.embedding_utils import get_embedding

def prepare_works_for_langchain(works: List[Dict]) -> List[Dict]:
    data = []
    for work in works:
        # ===== 标题处理（支持多语言） =====
        title_zh = work.get('title_zh') or work.get('name_cn', '') or ''
        title_en = work.get('title_en') or work.get('name', '') or ''
        title_jp = work.get('title_jp', '') or ''
        title_romaji = work.get('title_romaji', '') or ''
        
        # ===== 基础信息 =====
        work_id = work.get('id') 
        anilist_id = work.get('anilist_id')
        mal_id = work.get('mal_id')
        bangumi_id = work.get('bangumi_id')
        
        # ===== 简介处理 =====
        description_zh = work.get('description_zh') or work.get('description', '') or ''
        description_en = work.get('description_en', '') or ''
        
        # ===== 媒体类型和状态 =====
        media_type = work.get('media_type') or work.get('format') or work.get('type', '') or ''
        status = work.get('status', '') or ''
        
        # ===== 分类信息 =====
        genres = work.get('genres', []) or []
        tags = work.get('tags', []) or []  # 兼容字段
        
        # ===== 播出信息 =====
        episodes = work.get('episodes')
        duration = work.get('duration')
        year = work.get('year') or work.get('season_year') or work.get('release_year')
        season = work.get('season', '') or ''
        
        # ===== 评分信息 =====
        average_score = work.get('average_score')
        rating = work.get('rating')  # 兼容字段
        popularity = work.get('popularity')
        favourites = work.get('favourites')
        
        # ===== 制作信息 =====
        studios_json = work.get('studios_json', {})
        studio = work.get('studio', '') or ''  # 兼容字段
        source_type = work.get('source_type', '') or ''
        country_of_origin = work.get('country_of_origin', 'JP') or 'JP'
        
        # ===== 图片信息处理 =====
        image_large = work.get('image_large', '') or ''
        image_medium = work.get('image_medium', '') or ''
        image_small = work.get('image_small', '') or ''
        image_grid = work.get('image_grid', '') or ''
        image_common = work.get('image_common', '') or ''
        
        # 兼容字段
        poster_url = work.get('poster_url', '') or ''  # 兼容字段
        cover_url = work.get('cover_url', '') or ''    # 兼容字段
        screenshots = work.get('screenshots', []) or []
        thumbnail_url = work.get('thumbnail_url', '') or ''
        
        # ===== 其他信息 =====
        is_adult = work.get('is_adult', False)
        data_source = work.get('data_source', 'manual') or 'manual'
        director = work.get('director', '') or ''  # 兼容字段
        
        # ===== 构建用于嵌入的文本（多语言优化） =====
        text_parts = []
        
        # 标题信息
        if title_zh:
            text_parts.append(f"中文标题：{title_zh}")
        if title_en and title_en != title_zh:
            text_parts.append(f"英文标题：{title_en}")
        if title_jp and title_jp != title_zh:
            text_parts.append(f"日文标题：{title_jp}")
        if title_romaji and title_romaji not in [title_zh, title_en]:
            text_parts.append(f"罗马音：{title_romaji}")
        
        # 基础信息
        if media_type:
            text_parts.append(f"类型：{media_type}")
        if status:
            text_parts.append(f"状态：{status}")
        
        # 简介信息
        if description_zh:
            text_parts.append(f"简介：{description_zh}")
        elif description_en:
            text_parts.append(f"简介：{description_en}")
        
        # 分类信息
        if genres:
            text_parts.append(f"流派：{', '.join(genres)}")
        if tags:
            text_parts.append(f"标签：{', '.join(tags)}")
        
        # 播出信息
        if year:
            text_parts.append(f"年份：{year}")
        if season:
            text_parts.append(f"季节：{season}")
        if episodes:
            text_parts.append(f"集数：{episodes}集")
        
        # 制作信息
        if studio:
            text_parts.append(f"制作公司：{studio}")
        elif studios_json and 'main' in studios_json:
            main_studios = [s.get('name', '') for s in studios_json.get('main', []) if s.get('name')]
            if main_studios:
                text_parts.append(f"制作公司：{', '.join(main_studios)}")
        
        if source_type:
            text_parts.append(f"原作：{source_type}")
        if director:
            text_parts.append(f"导演：{director}")
        
        
        # 国家信息
        if country_of_origin and country_of_origin != 'JP':
            text_parts.append(f"国家：{country_of_origin}")
            
        text = "，".join(text_parts)
        
        # 使用中文简介作为主要内容，如果为空则使用完整文本
        page_content = description_zh if description_zh.strip() else (description_en if description_en.strip() else text)
        
        # 构建完整的元数据（新版本支持更多字段）
        metadata = {
            # ===== 主键与唯一标识 =====
            "id": work_id,
            "anilist_id": anilist_id,
            "mal_id": mal_id,
            "bangumi_id": bangumi_id,
            
            # ===== 多语言标题 =====
            "title_zh": title_zh,
            "title_en": title_en,
            "title_jp": title_jp,
            "title_romaji": title_romaji,
            
            # 兼容字段
            "name_cn": title_zh,  # 向后兼容
            "name": title_en,     # 向后兼容
            
            # ===== 简介 =====
            "description_zh": description_zh,
            "description_en": description_en,
            "description": description_zh or description_en,  # 兼容字段
            
            # ===== 基础信息 =====
            "media_type": media_type,
            "format": media_type,  # 同义字段
            "type": media_type,    # 兼容字段
            "status": status,
            
            # ===== 分类 =====
            "genres": genres,
            "tags": tags,  # 兼容字段
            
            # ===== 播出信息 =====
            "episodes": episodes,
            "duration": duration,
            "year": year,
            "season": season,
            "release_year": year,  # 兼容字段
            
            # ===== 评分 =====
            "average_score": average_score,
            "rating": rating or average_score,  # 兼容字段
            "popularity": popularity,
            "favourites": favourites,
            
            # ===== 制作信息 =====
            "studios_json": studios_json,
            "studio": studio,  # 兼容字段
            "source_type": source_type,
            "country_of_origin": country_of_origin,
            "director": director,  # 兼容字段
            
            # ===== 图片信息 =====
            "image_large": image_large,
            "image_medium": image_medium,
            "image_small": image_small,
            "image_grid": image_grid,
            "image_common": image_common,
            
            # 兼容字段
            "poster_url": poster_url,  # 兼容字段
            "cover_url": cover_url,    # 兼容字段
            "screenshots": screenshots,
            "thumbnail_url": thumbnail_url,
            
            # ===== 其他 =====
            "is_adult": is_adult,
            "data_source": data_source,
            "full_text": text
        }
        
        # 移除空值，减少存储空间
        metadata = {k: v for k, v in metadata.items() if v is not None and v != '' and v != []}
        
        data.append({
            "page_content": page_content,
            "metadata": metadata
        })
        
    return data

def upload_to_qdrant_using_langchain(works_data: List[Dict]):
    """
    直接使用 Qdrant 客户端上传数据，支持基于 UUID 的更新
    """
    # 根据环境选择主机名
    import os
    host = os.getenv("QDRANT_HOST", "localhost")  # 默认本地，Docker环境可以设置为"qdrant"
    
    client = QdrantClient(host=host, port=6333)
    collection_name = "anime_collections"

    try:
        # 检查集合是否存在
        collections = client.get_collections()
        collection_exists = any(col.name == collection_name for col in collections.collections)
        
        if not collection_exists:
            # 创建集合
            client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(size=512, distance=models.Distance.COSINE)
            )
            print(f"✅ 创建了新的集合: {collection_name}")
        
        # 处理每个作品数据
        points_to_upsert = []
        for work_data in works_data:
            metadata = work_data.get("metadata", {})
            page_content = work_data.get("page_content", "")
            
            # 获取唯一标识符 - 优先使用 UUID
            point_id = metadata.get("uuid") or metadata.get("id")
            
            # 如果没有 UUID，生成一个新的
            if not point_id:
                import uuid
                point_id = str(uuid.uuid4())
                metadata["uuid"] = point_id
                print(f"🆔 为作品生成新的 UUID: {point_id}")
            
            # 检查是否已存在（基于 UUID 查询）
            existing_point = None
            if isinstance(point_id, str):
                try:
                    # 尝试通过 UUID 查找现有点
                    search_result = client.scroll(
                        collection_name=collection_name,
                        scroll_filter=models.Filter(
                            must=[
                                models.FieldCondition(
                                    key="uuid",
                                    match=models.MatchValue(value=point_id)
                                )
                            ]
                        ),
                        limit=1
                    )
                    if search_result[0]:  # 如果找到现有记录
                        existing_point = search_result[0][0]
                        print(f"🔄 发现现有记录，将更新 UUID: {point_id}")
                except Exception as e:
                    print(f"⚠️ 查询现有记录时出错: {e}")
            
            # 生成向量嵌入
            try:
                vector = get_embedding(page_content)
            except Exception as e:
                print(f"❌ 生成向量嵌入失败: {e}")
                continue
            
            # 使用 UUID 作为点 ID（确保唯一性）
            try:
                # 如果 point_id 是字符串 UUID，需要转换为合适的格式
                if isinstance(point_id, str):
                    # 使用 UUID 的哈希作为整数 ID
                    import hashlib
                    numeric_id = int(hashlib.md5(point_id.encode()).hexdigest()[:8], 16)
                else:
                    numeric_id = int(point_id)
                
                point = models.PointStruct(
                    id=numeric_id,
                    vector=vector,
                    payload=metadata
                )
                points_to_upsert.append(point)
                
                action = "更新" if existing_point else "新增"
                print(f"📝 准备{action}作品: {metadata.get('title_zh') or metadata.get('name_cn', '未知')}")
                
            except Exception as e:
                print(f"❌ 处理点数据时出错: {e}")
                continue
        
        # 批量执行 upsert 操作
        if points_to_upsert:
            try:
                client.upsert(
                    collection_name=collection_name,
                    points=points_to_upsert
                )
                print(f"✅ 成功处理 {len(points_to_upsert)} 条数据到 Qdrant")
            except Exception as e:
                print(f"❌ 批量上传失败: {e}")
                raise
        else:
            print("⚠️ 没有有效的数据需要上传")

    except Exception as e:
        print(f"⚠️ 集合操作警告: {e}")
        # 如果出错，尝试重新创建
        try:
            client.recreate_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(size=512, distance=models.Distance.COSINE)
            )
            print(f"✅ 重新创建了集合: {collection_name}")
            
            # 重新执行上传
            if 'points_to_upsert' in locals() and points_to_upsert:
                client.upsert(
                    collection_name=collection_name,
                    points=points_to_upsert
                )
                print(f"✅ 重新上传成功: {len(points_to_upsert)} 条数据")
        except Exception as e2:
            print(f"❌ 无法创建集合: {e2}")
            raise

# 保持向后兼容的函数名
def upload_to_qdrant_using_direct_client(works_data: List[Dict]):
    """
    备用函数名，功能相同
    """
    return upload_to_qdrant_using_langchain(works_data)