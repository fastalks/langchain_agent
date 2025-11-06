"""
推荐系统配置管理
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
import yaml
import os


@dataclass
class DatabaseConfig:
    """数据库配置"""
    # Vector Database
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    
    # Relational Database  
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "anime_recommend"
    postgres_user: str = "postgres"
    postgres_password: str = "password"
    
    # Cache
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0


@dataclass
class ModelConfig:
    """模型配置"""
    # Embedding Model
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    embedding_dim: int = 512
    
    # LLM Model
    llm_model: str = "qwen-turbo"
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None
    
    # CF Model
    cf_model_path: Optional[str] = None
    
    # Ranking Model
    ranking_model_path: Optional[str] = None


@dataclass
class RecallConfig:
    """召回配置"""
    # 各种召回策略的候选数量
    vector_recall_k: int = 30
    cf_recall_k: int = 20
    tag_recall_k: int = 15
    popularity_recall_k: int = 10
    year_recall_k: int = 10
    
    # 总候选数量上限
    max_candidates: int = 100


@dataclass
class RankingConfig:
    """排序配置"""
    # 特征权重
    feature_weights: Dict[str, float] = None
    
    # LLM重排序配置
    use_llm_rerank: bool = True
    llm_rerank_top_k: int = 20
    llm_base_weight: float = 0.7
    llm_enhance_weight: float = 0.3
    
    def __post_init__(self):
        if self.feature_weights is None:
            self.feature_weights = {
                'base': 1.0,
                'year_match': 0.5,
                'tag_match': 0.3,
                'popularity': 0.2,
                'novelty': 0.1,
                'diversity': 0.1
            }


@dataclass
class RecommendationConfig:
    """推荐配置"""
    database: DatabaseConfig = None
    model: ModelConfig = None
    recall: RecallConfig = None
    ranking: RankingConfig = None
    
    # 业务配置
    default_num_recommendations: int = 10
    max_num_recommendations: int = 50
    
    # 缓存配置
    cache_ttl: int = 3600  # 1小时
    enable_cache: bool = True
    
    def __post_init__(self):
        if self.database is None:
            self.database = DatabaseConfig()
        if self.model is None:
            self.model = ModelConfig()
        if self.recall is None:
            self.recall = RecallConfig()
        if self.ranking is None:
            self.ranking = RankingConfig()


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "config/recommendation.yaml"
        self._config: Optional[RecommendationConfig] = None
    
    def load_config(self) -> RecommendationConfig:
        """加载配置"""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_dict = yaml.safe_load(f)
            self._config = self._dict_to_config(config_dict)
        else:
            # 使用默认配置
            self._config = RecommendationConfig()
            self.save_config()  # 保存默认配置
        
        return self._config
    
    def save_config(self, config: Optional[RecommendationConfig] = None):
        """保存配置"""
        if config is None:
            config = self._config
        
        if config is None:
            config = RecommendationConfig()
        
        config_dict = self._config_to_dict(config)
        
        # 确保目录存在
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_dict, f, default_flow_style=False, allow_unicode=True)
    
    def get_config(self) -> RecommendationConfig:
        """获取配置"""
        if self._config is None:
            self._config = self.load_config()
        return self._config
    
    def update_config(self, **kwargs):
        """更新配置"""
        config = self.get_config()
        
        # 支持嵌套更新
        for key, value in kwargs.items():
            if hasattr(config, key):
                if isinstance(getattr(config, key), object) and hasattr(getattr(config, key), '__dict__'):
                    # 嵌套对象
                    nested_obj = getattr(config, key)
                    if isinstance(value, dict):
                        for nested_key, nested_value in value.items():
                            if hasattr(nested_obj, nested_key):
                                setattr(nested_obj, nested_key, nested_value)
                else:
                    setattr(config, key, value)
        
        self.save_config(config)
    
    def _dict_to_config(self, config_dict: Dict) -> RecommendationConfig:
        """字典转配置对象"""
        database_dict = config_dict.get('database', {})
        model_dict = config_dict.get('model', {})
        recall_dict = config_dict.get('recall', {})
        ranking_dict = config_dict.get('ranking', {})
        
        # 处理ranking配置中的feature_weights
        if 'feature_weights' in ranking_dict:
            ranking_config = RankingConfig(**ranking_dict)
        else:
            ranking_config = RankingConfig()
            for key, value in ranking_dict.items():
                if hasattr(ranking_config, key):
                    setattr(ranking_config, key, value)
        
        config = RecommendationConfig(
            database=DatabaseConfig(**database_dict),
            model=ModelConfig(**model_dict),
            recall=RecallConfig(**recall_dict),
            ranking=ranking_config
        )
        
        # 设置其他顶级配置
        for key, value in config_dict.items():
            if key not in ['database', 'model', 'recall', 'ranking'] and hasattr(config, key):
                setattr(config, key, value)
        
        return config
    
    def _config_to_dict(self, config: RecommendationConfig) -> Dict:
        """配置对象转字典"""
        return {
            'database': {
                'qdrant_host': config.database.qdrant_host,
                'qdrant_port': config.database.qdrant_port,
                'postgres_host': config.database.postgres_host,
                'postgres_port': config.database.postgres_port,
                'postgres_db': config.database.postgres_db,
                'postgres_user': config.database.postgres_user,
                'postgres_password': config.database.postgres_password,
                'redis_host': config.database.redis_host,
                'redis_port': config.database.redis_port,
                'redis_db': config.database.redis_db,
            },
            'model': {
                'embedding_model': config.model.embedding_model,
                'embedding_dim': config.model.embedding_dim,
                'llm_model': config.model.llm_model,
                'llm_api_key': config.model.llm_api_key,
                'llm_base_url': config.model.llm_base_url,
                'cf_model_path': config.model.cf_model_path,
                'ranking_model_path': config.model.ranking_model_path,
            },
            'recall': {
                'vector_recall_k': config.recall.vector_recall_k,
                'cf_recall_k': config.recall.cf_recall_k,
                'tag_recall_k': config.recall.tag_recall_k,
                'popularity_recall_k': config.recall.popularity_recall_k,
                'year_recall_k': config.recall.year_recall_k,
                'max_candidates': config.recall.max_candidates,
            },
            'ranking': {
                'feature_weights': config.ranking.feature_weights,
                'use_llm_rerank': config.ranking.use_llm_rerank,
                'llm_rerank_top_k': config.ranking.llm_rerank_top_k,
                'llm_base_weight': config.ranking.llm_base_weight,
                'llm_enhance_weight': config.ranking.llm_enhance_weight,
            },
            'default_num_recommendations': config.default_num_recommendations,
            'max_num_recommendations': config.max_num_recommendations,
            'cache_ttl': config.cache_ttl,
            'enable_cache': config.enable_cache,
        }


# 全局配置管理器实例
config_manager = ConfigManager()

def get_config() -> RecommendationConfig:
    """获取全局配置"""
    return config_manager.get_config()

def update_config(**kwargs):
    """更新全局配置"""
    config_manager.update_config(**kwargs)