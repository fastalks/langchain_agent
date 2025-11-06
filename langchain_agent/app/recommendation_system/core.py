"""
推荐系统核心架构
支持多种召回策略和排序算法的可扩展框架
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Union, Tuple
from dataclasses import dataclass
import numpy as np
from enum import Enum


class RecallStrategy(Enum):
    """召回策略枚举"""
    VECTOR_SIMILARITY = "vector_similarity"
    COLLABORATIVE_FILTERING = "collaborative_filtering" 
    CONTENT_BASED = "content_based"
    POPULARITY = "popularity"
    TAG_BASED = "tag_based"
    YEAR_BASED = "year_based"


class RankingStrategy(Enum):
    """排序策略枚举"""
    WEIGHTED_FUSION = "weighted_fusion"
    DEEP_LEARNING = "deep_learning"
    GRADIENT_BOOSTING = "gradient_boosting"
    LLM_ENHANCED = "llm_enhanced"


@dataclass
class AnimeItem:
    """动漫项目数据结构"""
    id: str
    title: str
    title_zh: str
    year: int
    genres: List[str]
    tags: List[str]
    description: str
    rating: float
    embedding: Optional[np.ndarray] = None
    features: Optional[Dict] = None


@dataclass
class UserProfile:
    """用户画像数据结构"""
    user_id: str
    preferences: Dict[str, float]  # genre/tag偏好权重
    behavior_history: List[Dict]   # 行为历史
    demographic: Dict              # 人口统计学特征
    embeddings: Optional[np.ndarray] = None


@dataclass
class RecommendationRequest:
    """推荐请求"""
    user_id: Optional[str] = None
    query: Optional[str] = None
    filters: Optional[Dict] = None
    num_recommendations: int = 10
    context: Optional[Dict] = None


@dataclass
class RecommendationResult:
    """推荐结果"""
    items: List[AnimeItem]
    scores: List[float]
    explanations: List[str]
    recall_info: Dict
    ranking_info: Dict


class RecallEngine(ABC):
    """召回引擎抽象基类"""
    
    @abstractmethod
    async def recall(self, request: RecommendationRequest, k: int = 100) -> List[Tuple[AnimeItem, float]]:
        """召回候选集"""
        pass


class VectorRecallEngine(RecallEngine):
    """向量召回引擎"""
    
    def __init__(self, vector_store, embedding_model):
        self.vector_store = vector_store
        self.embedding_model = embedding_model
    
    async def recall(self, request: RecommendationRequest, k: int = 100) -> List[Tuple[AnimeItem, float]]:
        """基于向量相似度召回"""
        if request.query:
            query_embedding = await self.embedding_model.encode(request.query)
            candidates = await self.vector_store.search(query_embedding, k)
            return [(item, score) for item, score in candidates]
        return []


class TagBasedRecallEngine(RecallEngine):
    """基于标签的召回引擎"""
    
    def __init__(self, tag_index):
        self.tag_index = tag_index
    
    async def recall(self, request: RecommendationRequest, k: int = 100) -> List[Tuple[AnimeItem, float]]:
        """基于标签匹配召回"""
        if request.query:
            detected_tags = self._extract_tags(request.query)
            candidates = []
            for tag in detected_tags:
                items = self.tag_index.get(tag, [])
                for item in items:
                    score = self._calculate_tag_score(item, detected_tags)
                    candidates.append((item, score))
            
            # 去重并排序
            candidates = sorted(set(candidates), key=lambda x: x[1], reverse=True)
            return candidates[:k]
        return []
    
    def _extract_tags(self, query: str) -> List[str]:
        """从查询中提取标签"""
        # 实现标签提取逻辑
        tag_keywords = {
            "动作": ["Action", "动作", "战斗"],
            "爱情": ["Romance", "爱情", "恋爱"],
            # ... 更多标签映射
        }
        detected = []
        for tag, keywords in tag_keywords.items():
            if any(kw in query for kw in keywords):
                detected.append(tag)
        return detected
    
    def _calculate_tag_score(self, item: AnimeItem, query_tags: List[str]) -> float:
        """计算标签匹配分数"""
        match_count = sum(1 for tag in query_tags if tag in item.tags)
        return match_count / len(query_tags) if query_tags else 0


class CollaborativeFilteringRecallEngine(RecallEngine):
    """协同过滤召回引擎"""
    
    def __init__(self, user_item_matrix, similarity_matrix):
        self.user_item_matrix = user_item_matrix
        self.similarity_matrix = similarity_matrix
    
    async def recall(self, request: RecommendationRequest, k: int = 100) -> List[Tuple[AnimeItem, float]]:
        """基于协同过滤召回"""
        if request.user_id:
            # 基于用户相似度或物品相似度召回
            similar_users = self._get_similar_users(request.user_id)
            candidates = self._get_recommendations_from_similar_users(similar_users)
            return candidates[:k]
        return []
    
    def _get_similar_users(self, user_id: str) -> List[str]:
        """获取相似用户"""
        # 实现用户相似度计算
        pass
    
    def _get_recommendations_from_similar_users(self, similar_users: List[str]) -> List[Tuple[AnimeItem, float]]:
        """从相似用户获取推荐"""
        # 实现推荐逻辑
        pass


class RankingEngine(ABC):
    """排序引擎抽象基类"""
    
    @abstractmethod
    async def rank(self, candidates: List[Tuple[AnimeItem, float]], 
                   request: RecommendationRequest) -> List[Tuple[AnimeItem, float]]:
        """对候选集进行排序"""
        pass


class WeightedFusionRankingEngine(RankingEngine):
    """加权融合排序引擎"""
    
    def __init__(self, weights: Dict[str, float]):
        self.weights = weights
    
    async def rank(self, candidates: List[Tuple[AnimeItem, float]], 
                   request: RecommendationRequest) -> List[Tuple[AnimeItem, float]]:
        """基于多个特征的加权融合排序"""
        ranked_candidates = []
        
        for item, base_score in candidates:
            # 计算多维度特征分数
            features = self._extract_features(item, request)
            
            # 加权融合
            final_score = base_score * self.weights.get('base', 1.0)
            for feature_name, feature_value in features.items():
                weight = self.weights.get(feature_name, 0.0)
                final_score += feature_value * weight
            
            ranked_candidates.append((item, final_score))
        
        # 按分数排序
        ranked_candidates.sort(key=lambda x: x[1], reverse=True)
        return ranked_candidates
    
    def _extract_features(self, item: AnimeItem, request: RecommendationRequest) -> Dict[str, float]:
        """提取排序特征"""
        features = {}
        
        # 年份匹配特征
        if request.query:
            year_match = self._calculate_year_match(item, request.query)
            features['year_match'] = year_match
        
        # 流行度特征
        features['popularity'] = item.rating / 10.0
        
        # 新颖性特征
        features['novelty'] = self._calculate_novelty(item)
        
        return features
    
    def _calculate_year_match(self, item: AnimeItem, query: str) -> float:
        """计算年份匹配分数"""
        import re
        years = re.findall(r'(19|20)\d{2}', query)
        if years and str(item.year) in years:
            return 1.0
        return 0.0
    
    def _calculate_novelty(self, item: AnimeItem) -> float:
        """计算新颖性分数"""
        # 基于发布时间等计算新颖性
        current_year = 2024
        years_ago = current_year - item.year
        return max(0, (20 - years_ago) / 20)


class LLMEnhancedRankingEngine(RankingEngine):
    """大模型增强排序引擎"""
    
    def __init__(self, llm_client, base_ranker: RankingEngine):
        self.llm_client = llm_client
        self.base_ranker = base_ranker
    
    async def rank(self, candidates: List[Tuple[AnimeItem, float]], 
                   request: RecommendationRequest) -> List[Tuple[AnimeItem, float]]:
        """使用大模型增强排序"""
        # 先用基础排序
        base_ranked = await self.base_ranker.rank(candidates, request)
        
        # 大模型重排序（只对top candidates）
        top_candidates = base_ranked[:20]  # 只对前20个用LLM重排序
        
        if request.query and top_candidates:
            llm_scores = await self._llm_rerank(top_candidates, request.query)
            
            # 融合基础分数和LLM分数
            final_ranked = []
            for i, (item, base_score) in enumerate(top_candidates):
                llm_score = llm_scores[i]
                # 加权融合
                final_score = 0.7 * base_score + 0.3 * llm_score
                final_ranked.append((item, final_score))
            
            # 重新排序
            final_ranked.sort(key=lambda x: x[1], reverse=True)
            
            # 合并剩余的候选
            return final_ranked + base_ranked[20:]
        
        return base_ranked
    
    async def _llm_rerank(self, candidates: List[Tuple[AnimeItem, float]], query: str) -> List[float]:
        """使用大模型重新打分"""
        prompt = self._build_rerank_prompt(candidates, query)
        response = await self.llm_client.generate(prompt)
        scores = self._parse_llm_scores(response)
        return scores
    
    def _build_rerank_prompt(self, candidates: List[Tuple[AnimeItem, float]], query: str) -> str:
        """构建重排序提示"""
        candidate_list = ""
        for i, (item, score) in enumerate(candidates):
            candidate_list += f"{i+1}. {item.title_zh} - {item.description[:100]}...\n"
        
        prompt = f"""
        用户查询：{query}
        
        候选动漫列表：
        {candidate_list}
        
        请根据用户查询的意图，为每部动漫给出0-1的相关性分数。
        只返回分数列表，用逗号分隔，如：0.9,0.8,0.7,0.6...
        """
        return prompt
    
    def _parse_llm_scores(self, response: str) -> List[float]:
        """解析大模型返回的分数"""
        try:
            scores = [float(s.strip()) for s in response.split(',')]
            return scores
        except:
            # 如果解析失败，返回平均分数
            return [0.5] * 20


class RecommendationEngine:
    """推荐引擎主类"""
    
    def __init__(self):
        self.recall_engines: Dict[RecallStrategy, RecallEngine] = {}
        self.ranking_engine: Optional[RankingEngine] = None
        self.llm_client = None
    
    def register_recall_engine(self, strategy: RecallStrategy, engine: RecallEngine):
        """注册召回引擎"""
        self.recall_engines[strategy] = engine
    
    def set_ranking_engine(self, engine: RankingEngine):
        """设置排序引擎"""
        self.ranking_engine = engine
    
    def set_llm_client(self, client):
        """设置大模型客户端"""
        self.llm_client = client
    
    async def recommend(self, request: RecommendationRequest) -> RecommendationResult:
        """执行推荐"""
        # 1. 多路召回
        all_candidates = []
        recall_info = {}
        
        for strategy, engine in self.recall_engines.items():
            candidates = await engine.recall(request, k=50)
            all_candidates.extend(candidates)
            recall_info[strategy.value] = len(candidates)
        
        # 去重
        unique_candidates = self._deduplicate_candidates(all_candidates)
        
        # 2. 排序
        if self.ranking_engine:
            ranked_candidates = await self.ranking_engine.rank(unique_candidates, request)
        else:
            ranked_candidates = unique_candidates
        
        # 3. 截取结果
        final_items = ranked_candidates[:request.num_recommendations]
        
        # 4. 生成解释（如果有LLM）
        explanations = []
        if self.llm_client:
            explanations = await self._generate_explanations(final_items, request)
        
        return RecommendationResult(
            items=[item for item, score in final_items],
            scores=[score for item, score in final_items],
            explanations=explanations,
            recall_info=recall_info,
            ranking_info={'total_candidates': len(unique_candidates)}
        )
    
    def _deduplicate_candidates(self, candidates: List[Tuple[AnimeItem, float]]) -> List[Tuple[AnimeItem, float]]:
        """候选去重"""
        seen = set()
        unique = []
        for item, score in candidates:
            if item.id not in seen:
                seen.add(item.id)
                unique.append((item, score))
        return unique
    
    async def _generate_explanations(self, recommendations: List[Tuple[AnimeItem, float]], 
                                   request: RecommendationRequest) -> List[str]:
        """生成推荐解释"""
        explanations = []
        for item, score in recommendations:
            prompt = f"""
            为什么推荐《{item.title_zh}》给用户？
            用户查询：{request.query}
            动漫信息：{item.description}
            请生成一句简洁的推荐理由。
            """
            explanation = await self.llm_client.generate(prompt)
            explanations.append(explanation)
        return explanations