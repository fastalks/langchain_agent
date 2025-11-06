"""
推荐系统工厂类
用于构建和配置完整的推荐系统
"""

from typing import Dict, List, Optional
import asyncio
from .core import (
    RecommendationEngine, RecallEngine, RankingEngine,
    VectorRecallEngine, TagBasedRecallEngine, CollaborativeFilteringRecallEngine,
    WeightedFusionRankingEngine, LLMEnhancedRankingEngine,
    RecallStrategy, RankingStrategy
)
from .config import RecommendationConfig, get_config
from .database import DatabaseManager, AnimeRepository
from .user_behavior import UserBehaviorAnalyzer, UserBehaviorTracker
import logging

logger = logging.getLogger(__name__)


class RecommendationSystemFactory:
    """推荐系统工厂类"""
    
    def __init__(self, config: Optional[RecommendationConfig] = None):
        self.config = config or get_config()
        self.db_manager: Optional[DatabaseManager] = None
        self.anime_repo: Optional[AnimeRepository] = None
        self.behavior_analyzer: Optional[UserBehaviorAnalyzer] = None
        self.behavior_tracker: Optional[UserBehaviorTracker] = None
        self.recommendation_engine: Optional[RecommendationEngine] = None
    
    async def initialize(self) -> RecommendationEngine:
        """初始化整个推荐系统"""
        logger.info("开始初始化推荐系统...")
        
        # 1. 初始化数据库管理器
        await self._init_database()
        
        # 2. 初始化数据仓库
        await self._init_repositories()
        
        # 3. 初始化用户行为分析
        await self._init_user_behavior()
        
        # 4. 初始化推荐引擎
        await self._init_recommendation_engine()
        
        logger.info("推荐系统初始化完成")
        return self.recommendation_engine
    
    async def _init_database(self):
        """初始化数据库"""
        self.db_manager = DatabaseManager(self.config)
        await self.db_manager.initialize()
        logger.info("数据库管理器初始化完成")
    
    async def _init_repositories(self):
        """初始化数据仓库"""
        self.anime_repo = AnimeRepository(self.db_manager)
        logger.info("数据仓库初始化完成")
    
    async def _init_user_behavior(self):
        """初始化用户行为模块"""
        self.behavior_analyzer = UserBehaviorAnalyzer(self.db_manager)
        self.behavior_tracker = UserBehaviorTracker(self.db_manager)
        logger.info("用户行为模块初始化完成")
    
    async def _init_recommendation_engine(self):
        """初始化推荐引擎"""
        self.recommendation_engine = RecommendationEngine()
        
        # 注册召回引擎
        await self._register_recall_engines()
        
        # 设置排序引擎
        await self._setup_ranking_engine()
        
        logger.info("推荐引擎初始化完成")
    
    async def _register_recall_engines(self):
        """注册召回引擎"""
        # 向量召回引擎
        if self.config.recall.vector_recall_k > 0:
            vector_engine = await self._create_vector_recall_engine()
            self.recommendation_engine.register_recall_engine(
                RecallStrategy.VECTOR_SIMILARITY, vector_engine
            )
            logger.info("向量召回引擎注册完成")
        
        # 标签召回引擎
        if self.config.recall.tag_recall_k > 0:
            tag_engine = await self._create_tag_recall_engine()
            self.recommendation_engine.register_recall_engine(
                RecallStrategy.TAG_BASED, tag_engine
            )
            logger.info("标签召回引擎注册完成")
        
        # 协同过滤召回引擎（如果有用户行为数据）
        if self.config.recall.cf_recall_k > 0:
            cf_engine = await self._create_cf_recall_engine()
            if cf_engine:
                self.recommendation_engine.register_recall_engine(
                    RecallStrategy.COLLABORATIVE_FILTERING, cf_engine
                )
                logger.info("协同过滤召回引擎注册完成")
    
    async def _create_vector_recall_engine(self) -> VectorRecallEngine:
        """创建向量召回引擎"""
        # 这里需要集成实际的向量存储和嵌入模型
        class MockVectorStore:
            async def search(self, query_vector, k):
                # 模拟向量搜索
                return []
        
        class MockEmbeddingModel:
            async def encode(self, text):
                # 模拟文本编码
                return [0.0] * self.config.model.embedding_dim
        
        vector_store = MockVectorStore()
        embedding_model = MockEmbeddingModel()
        
        return VectorRecallEngine(vector_store, embedding_model)
    
    async def _create_tag_recall_engine(self) -> TagBasedRecallEngine:
        """创建标签召回引擎"""
        # 构建标签索引
        tag_index = await self._build_tag_index()
        return TagBasedRecallEngine(tag_index)
    
    async def _build_tag_index(self) -> Dict:
        """构建标签索引"""
        # 从数据库获取所有动漫的标签信息
        anime_list = await self.anime_repo.search_anime({}, limit=10000)
        
        tag_index = {}
        for anime in anime_list:
            tags = anime.get('tags', [])
            for tag in tags:
                if tag not in tag_index:
                    tag_index[tag] = []
                tag_index[tag].append(anime)
        
        logger.info(f"标签索引构建完成，共 {len(tag_index)} 个标签")
        return tag_index
    
    async def _create_cf_recall_engine(self) -> Optional[CollaborativeFilteringRecallEngine]:
        """创建协同过滤召回引擎"""
        # 检查是否有足够的用户行为数据
        action_count_query = "SELECT COUNT(*) as count FROM user_actions"
        result = await self.db_manager.fetch_one(action_count_query)
        
        if result['count'] < 100:  # 如果行为数据太少，不启用CF
            logger.warning("用户行为数据不足，跳过协同过滤召回引擎")
            return None
        
        # 构建用户-物品矩阵（这里简化处理）
        user_item_matrix = {}
        similarity_matrix = {}
        
        return CollaborativeFilteringRecallEngine(user_item_matrix, similarity_matrix)
    
    async def _setup_ranking_engine(self):
        """设置排序引擎"""
        # 基础加权融合排序引擎
        base_ranking_engine = WeightedFusionRankingEngine(
            weights=self.config.ranking.feature_weights
        )
        
        # 如果启用LLM增强排序
        if self.config.ranking.use_llm_rerank:
            llm_client = await self._create_llm_client()
            if llm_client:
                ranking_engine = LLMEnhancedRankingEngine(llm_client, base_ranking_engine)
                self.recommendation_engine.set_ranking_engine(ranking_engine)
                self.recommendation_engine.set_llm_client(llm_client)
                logger.info("LLM增强排序引擎设置完成")
                return
        
        # 使用基础排序引擎
        self.recommendation_engine.set_ranking_engine(base_ranking_engine)
        logger.info("基础排序引擎设置完成")
    
    async def _create_llm_client(self):
        """创建LLM客户端"""
        # 这里需要根据配置创建实际的LLM客户端
        class MockLLMClient:
            async def generate(self, prompt):
                # 模拟LLM生成
                return "0.9,0.8,0.7,0.6,0.5"
        
        if self.config.model.llm_api_key:
            return MockLLMClient()
        
        logger.warning("未配置LLM API密钥，跳过LLM增强功能")
        return None
    
    async def close(self):
        """关闭推荐系统"""
        if self.behavior_tracker:
            await self.behavior_tracker.flush()
        
        if self.db_manager:
            await self.db_manager.close()
        
        logger.info("推荐系统已关闭")


class RecommendationSystemManager:
    """推荐系统管理器（单例）"""
    
    _instance: Optional['RecommendationSystemManager'] = None
    _recommendation_engine: Optional[RecommendationEngine] = None
    _factory: Optional[RecommendationSystemFactory] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def initialize(self, config: Optional[RecommendationConfig] = None) -> RecommendationEngine:
        """初始化推荐系统"""
        if self._recommendation_engine is None:
            self._factory = RecommendationSystemFactory(config)
            self._recommendation_engine = await self._factory.initialize()
        
        return self._recommendation_engine
    
    def get_engine(self) -> Optional[RecommendationEngine]:
        """获取推荐引擎"""
        return self._recommendation_engine
    
    async def close(self):
        """关闭推荐系统"""
        if self._factory:
            await self._factory.close()
        
        self._recommendation_engine = None
        self._factory = None


# 全局推荐系统管理器
recommendation_manager = RecommendationSystemManager()


async def get_recommendation_engine() -> RecommendationEngine:
    """获取全局推荐引擎"""
    engine = recommendation_manager.get_engine()
    if engine is None:
        engine = await recommendation_manager.initialize()
    return engine


async def initialize_recommendation_system(config: Optional[RecommendationConfig] = None) -> RecommendationEngine:
    """初始化推荐系统"""
    return await recommendation_manager.initialize(config)


async def close_recommendation_system():
    """关闭推荐系统"""
    await recommendation_manager.close()