"""
数据库管理模块
支持PostgreSQL、Redis和Qdrant的统一管理
"""

import asyncio
import asyncpg
import redis.asyncio as redis
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models
from typing import Dict, List, Optional, Any, Union
import json
import numpy as np
from contextlib import asynccontextmanager
import logging

logger = logging.getLogger(__name__)


class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self, config):
        self.config = config
        self.pg_pool: Optional[asyncpg.Pool] = None
        self.redis_client: Optional[redis.Redis] = None
        self.qdrant_client: Optional[AsyncQdrantClient] = None
    
    async def initialize(self):
        """初始化所有数据库连接"""
        await self._init_postgresql()
        await self._init_redis()
        await self._init_qdrant()
        await self._create_tables()
    
    async def _init_postgresql(self):
        """初始化PostgreSQL连接池"""
        try:
            self.pg_pool = await asyncpg.create_pool(
                host=self.config.database.postgres_host,
                port=self.config.database.postgres_port,
                database=self.config.database.postgres_db,
                user=self.config.database.postgres_user,
                password=self.config.database.postgres_password,
                min_size=5,
                max_size=20
            )
            logger.info("PostgreSQL连接池初始化成功")
        except Exception as e:
            logger.error(f"PostgreSQL连接失败: {e}")
            raise
    
    async def _init_redis(self):
        """初始化Redis连接"""
        try:
            self.redis_client = redis.Redis(
                host=self.config.database.redis_host,
                port=self.config.database.redis_port,
                db=self.config.database.redis_db,
                decode_responses=True
            )
            # 测试连接
            await self.redis_client.ping()
            logger.info("Redis连接初始化成功")
        except Exception as e:
            logger.error(f"Redis连接失败: {e}")
            raise
    
    async def _init_qdrant(self):
        """初始化Qdrant连接"""
        try:
            self.qdrant_client = AsyncQdrantClient(
                host=self.config.database.qdrant_host,
                port=self.config.database.qdrant_port
            )
            # 测试连接
            await self.qdrant_client.get_collections()
            logger.info("Qdrant连接初始化成功")
        except Exception as e:
            logger.error(f"Qdrant连接失败: {e}")
            raise
    
    async def _create_tables(self):
        """创建必要的数据表"""
        tables_sql = [
            # 动漫信息表
            """
            CREATE TABLE IF NOT EXISTS anime_items (
                id VARCHAR(255) PRIMARY KEY,
                title VARCHAR(500) NOT NULL,
                title_zh VARCHAR(500),
                year INTEGER,
                genres JSONB,
                tags JSONB,
                description TEXT,
                rating FLOAT,
                image_url VARCHAR(1000),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,
            
            # 用户行为表
            """
            CREATE TABLE IF NOT EXISTS user_actions (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR(255) NOT NULL,
                item_id VARCHAR(255) NOT NULL,
                action_type VARCHAR(50) NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                value VARCHAR(1000),
                context JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,
            
            # 用户画像表
            """
            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id VARCHAR(255) PRIMARY KEY,
                preferences JSONB,
                genre_preferences JSONB,
                tag_preferences JSONB,
                year_preferences JSONB,
                rating_bias FLOAT,
                activity_level VARCHAR(20),
                last_active TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,
            
            # 推荐结果缓存表
            """
            CREATE TABLE IF NOT EXISTS recommendation_cache (
                id SERIAL PRIMARY KEY,
                cache_key VARCHAR(500) NOT NULL,
                user_id VARCHAR(255),
                query_hash VARCHAR(100),
                results JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP
            );
            """,
            
            # 推荐日志表
            """
            CREATE TABLE IF NOT EXISTS recommendation_logs (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR(255),
                query TEXT,
                results JSONB,
                recall_info JSONB,
                ranking_info JSONB,
                response_time FLOAT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        ]
        
        # 索引创建
        indexes_sql = [
            "CREATE INDEX IF NOT EXISTS idx_user_actions_user_id ON user_actions(user_id);",
            "CREATE INDEX IF NOT EXISTS idx_user_actions_timestamp ON user_actions(timestamp);",
            "CREATE INDEX IF NOT EXISTS idx_anime_items_year ON anime_items(year);",
            "CREATE INDEX IF NOT EXISTS idx_anime_items_rating ON anime_items(rating);",
            "CREATE INDEX IF NOT EXISTS idx_recommendation_cache_key ON recommendation_cache(cache_key);",
            "CREATE INDEX IF NOT EXISTS idx_recommendation_cache_expires ON recommendation_cache(expires_at);",
        ]
        
        async with self.pg_pool.acquire() as conn:
            for sql in tables_sql + indexes_sql:
                try:
                    await conn.execute(sql)
                    logger.info(f"执行SQL成功: {sql[:50]}...")
                except Exception as e:
                    logger.error(f"执行SQL失败: {e}")
    
    @asynccontextmanager
    async def get_pg_connection(self):
        """获取PostgreSQL连接"""
        async with self.pg_pool.acquire() as conn:
            yield conn
    
    async def fetch_one(self, query: str, params: tuple = ()) -> Optional[Dict]:
        """查询单条记录"""
        async with self.get_pg_connection() as conn:
            row = await conn.fetchrow(query, *params)
            return dict(row) if row else None
    
    async def fetch_all(self, query: str, params: tuple = ()) -> List[Dict]:
        """查询多条记录"""
        async with self.get_pg_connection() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]
    
    async def execute(self, query: str, params: tuple = ()) -> str:
        """执行SQL"""
        async with self.get_pg_connection() as conn:
            return await conn.execute(query, *params)
    
    async def execute_many(self, query: str, params_list: List[tuple]) -> None:
        """批量执行SQL"""
        async with self.get_pg_connection() as conn:
            await conn.executemany(query, params_list)
    
    # Redis操作方法
    async def cache_set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """设置缓存"""
        try:
            serialized = json.dumps(value, ensure_ascii=False)
            await self.redis_client.setex(key, ttl, serialized)
            return True
        except Exception as e:
            logger.error(f"缓存设置失败: {e}")
            return False
    
    async def cache_get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        try:
            value = await self.redis_client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"缓存获取失败: {e}")
            return None
    
    async def cache_delete(self, key: str) -> bool:
        """删除缓存"""
        try:
            await self.redis_client.delete(key)
            return True
        except Exception as e:
            logger.error(f"缓存删除失败: {e}")
            return False
    
    async def cache_exists(self, key: str) -> bool:
        """检查缓存是否存在"""
        try:
            return bool(await self.redis_client.exists(key))
        except Exception as e:
            logger.error(f"缓存检查失败: {e}")
            return False
    
    # Qdrant操作方法
    async def vector_search(self, collection_name: str, query_vector: List[float], 
                           limit: int = 10, score_threshold: float = 0.5) -> List[Dict]:
        """向量搜索"""
        try:
            results = await self.qdrant_client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=limit,
                score_threshold=score_threshold,
                with_payload=True
            )
            
            return [
                {
                    'id': result.id,
                    'score': result.score,
                    'payload': result.payload
                }
                for result in results
            ]
        except Exception as e:
            logger.error(f"向量搜索失败: {e}")
            return []
    
    async def vector_upsert(self, collection_name: str, points: List[Dict]) -> bool:
        """批量插入/更新向量"""
        try:
            qdrant_points = []
            for point in points:
                qdrant_point = models.PointStruct(
                    id=point['id'],
                    vector=point['vector'],
                    payload=point.get('payload', {})
                )
                qdrant_points.append(qdrant_point)
            
            await self.qdrant_client.upsert(
                collection_name=collection_name,
                points=qdrant_points
            )
            return True
        except Exception as e:
            logger.error(f"向量插入失败: {e}")
            return False
    
    async def ensure_collection(self, collection_name: str, vector_size: int):
        """确保集合存在"""
        try:
            collections = await self.qdrant_client.get_collections()
            collection_names = [col.name for col in collections.collections]
            
            if collection_name not in collection_names:
                await self.qdrant_client.create_collection(
                    collection_name=collection_name,
                    vectors_config=models.VectorParams(
                        size=vector_size,
                        distance=models.Distance.COSINE
                    )
                )
                logger.info(f"创建集合成功: {collection_name}")
        except Exception as e:
            logger.error(f"集合创建失败: {e}")
            raise
    
    async def close(self):
        """关闭所有连接"""
        if self.pg_pool:
            await self.pg_pool.close()
        
        if self.redis_client:
            await self.redis_client.close()
        
        if self.qdrant_client:
            await self.qdrant_client.close()


class AnimeRepository:
    """动漫数据仓库"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    async def create_anime(self, anime_data: Dict) -> str:
        """创建动漫记录"""
        query = """
        INSERT INTO anime_items (id, title, title_zh, year, genres, tags, description, rating, image_url)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        ON CONFLICT (id) DO UPDATE SET
            title = EXCLUDED.title,
            title_zh = EXCLUDED.title_zh,
            year = EXCLUDED.year,
            genres = EXCLUDED.genres,
            tags = EXCLUDED.tags,
            description = EXCLUDED.description,
            rating = EXCLUDED.rating,
            image_url = EXCLUDED.image_url,
            updated_at = CURRENT_TIMESTAMP
        RETURNING id
        """
        
        params = (
            anime_data['id'],
            anime_data['title'],
            anime_data.get('title_zh'),
            anime_data.get('year'),
            json.dumps(anime_data.get('genres', [])),
            json.dumps(anime_data.get('tags', [])),
            anime_data.get('description'),
            anime_data.get('rating'),
            anime_data.get('image_url')
        )
        
        result = await self.db.fetch_one(query, params)
        return result['id'] if result else None
    
    async def get_anime_by_id(self, anime_id: str) -> Optional[Dict]:
        """根据ID获取动漫"""
        query = "SELECT * FROM anime_items WHERE id = $1"
        result = await self.db.fetch_one(query, (anime_id,))
        
        if result:
            # 解析JSON字段
            result['genres'] = json.loads(result['genres']) if result['genres'] else []
            result['tags'] = json.loads(result['tags']) if result['tags'] else []
        
        return result
    
    async def search_anime(self, filters: Dict, limit: int = 100) -> List[Dict]:
        """搜索动漫"""
        conditions = []
        params = []
        param_count = 0
        
        if 'year' in filters:
            param_count += 1
            conditions.append(f"year = ${param_count}")
            params.append(filters['year'])
        
        if 'genres' in filters:
            param_count += 1
            conditions.append(f"genres @> ${param_count}")
            params.append(json.dumps(filters['genres']))
        
        if 'rating_min' in filters:
            param_count += 1
            conditions.append(f"rating >= ${param_count}")
            params.append(filters['rating_min'])
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        param_count += 1
        query = f"""
        SELECT * FROM anime_items 
        WHERE {where_clause}
        ORDER BY rating DESC
        LIMIT ${param_count}
        """
        params.append(limit)
        
        results = await self.db.fetch_all(query, params)
        
        # 解析JSON字段
        for result in results:
            result['genres'] = json.loads(result['genres']) if result['genres'] else []
            result['tags'] = json.loads(result['tags']) if result['tags'] else []
        
        return results
    
    async def batch_create_anime(self, anime_list: List[Dict]) -> int:
        """批量创建动漫"""
        query = """
        INSERT INTO anime_items (id, title, title_zh, year, genres, tags, description, rating, image_url)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        ON CONFLICT (id) DO UPDATE SET
            title = EXCLUDED.title,
            title_zh = EXCLUDED.title_zh,
            year = EXCLUDED.year,
            genres = EXCLUDED.genres,
            tags = EXCLUDED.tags,
            description = EXCLUDED.description,
            rating = EXCLUDED.rating,
            image_url = EXCLUDED.image_url,
            updated_at = CURRENT_TIMESTAMP
        """
        
        params_list = []
        for anime in anime_list:
            params = (
                anime['id'],
                anime['title'],
                anime.get('title_zh'),
                anime.get('year'),
                json.dumps(anime.get('genres', [])),
                json.dumps(anime.get('tags', [])),
                anime.get('description'),
                anime.get('rating'),
                anime.get('image_url')
            )
            params_list.append(params)
        
        await self.db.execute_many(query, params_list)
        return len(params_list)