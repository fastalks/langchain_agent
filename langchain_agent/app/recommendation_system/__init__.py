"""
推荐系统包初始化文件
"""

from .core import (
    RecommendationEngine,
    RecallEngine, 
    RankingEngine,
    VectorRecallEngine,
    TagBasedRecallEngine,
    CollaborativeFilteringRecallEngine,
    WeightedFusionRankingEngine,
    LLMEnhancedRankingEngine,
    RecallStrategy,
    RankingStrategy,
    AnimeItem,
    UserProfile,
    RecommendationRequest,
    RecommendationResult
)

from .config import (
    RecommendationConfig,
    DatabaseConfig,
    ModelConfig,
    RecallConfig,
    RankingConfig,
    ConfigManager,
    get_config,
    update_config
)

from .database import (
    DatabaseManager,
    AnimeRepository
)

from .user_behavior import (
    UserBehaviorAnalyzer,
    UserBehaviorTracker,
    UserProfile,
    UserAction,
    ActionType,
    UserSegmentation
)

from .factory import (
    RecommendationSystemFactory,
    RecommendationSystemManager,
    get_recommendation_engine,
    initialize_recommendation_system,
    close_recommendation_system
)

__version__ = "2.0.0"
__author__ = "AI Assistant"
__description__ = "Advanced Anime Recommendation System with Multi-Strategy Recall and LLM Enhancement"

__all__ = [
    # Core components
    "RecommendationEngine",
    "RecallEngine",
    "RankingEngine", 
    "VectorRecallEngine",
    "TagBasedRecallEngine",
    "CollaborativeFilteringRecallEngine",
    "WeightedFusionRankingEngine",
    "LLMEnhancedRankingEngine",
    "RecallStrategy",
    "RankingStrategy",
    "AnimeItem",
    "UserProfile",
    "RecommendationRequest", 
    "RecommendationResult",
    
    # Configuration
    "RecommendationConfig",
    "DatabaseConfig",
    "ModelConfig", 
    "RecallConfig",
    "RankingConfig",
    "ConfigManager",
    "get_config",
    "update_config",
    
    # Database
    "DatabaseManager",
    "AnimeRepository",
    
    # User Behavior
    "UserBehaviorAnalyzer",
    "UserBehaviorTracker",
    "UserAction",
    "ActionType",
    "UserSegmentation",
    
    # Factory
    "RecommendationSystemFactory",
    "RecommendationSystemManager",
    "get_recommendation_engine",
    "initialize_recommendation_system",
    "close_recommendation_system",
]