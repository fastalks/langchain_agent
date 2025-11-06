"""
用户行为数据管理模块
"""

from typing import Dict, List, Optional, Union
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import json
import asyncio
from collections import defaultdict, Counter
import numpy as np


class ActionType(Enum):
    """用户行为类型"""
    VIEW = "view"           # 浏览
    LIKE = "like"           # 点赞
    DISLIKE = "dislike"     # 不喜欢
    FAVORITE = "favorite"   # 收藏
    SHARE = "share"         # 分享
    COMMENT = "comment"     # 评论
    RATE = "rate"          # 评分
    SEARCH = "search"      # 搜索
    CLICK = "click"        # 点击推荐


@dataclass
class UserAction:
    """用户行为记录"""
    user_id: str
    item_id: str
    action_type: ActionType
    timestamp: datetime
    value: Optional[Union[float, str]] = None  # 评分值或评论内容
    context: Optional[Dict] = None             # 上下文信息


@dataclass
class UserProfile:
    """用户画像"""
    user_id: str
    preferences: Dict[str, float]              # 偏好权重
    genre_preferences: Dict[str, float]        # 类型偏好
    tag_preferences: Dict[str, float]          # 标签偏好
    year_preferences: Dict[int, float]         # 年代偏好
    rating_bias: float                         # 评分偏好
    activity_level: str                        # 活跃度：low/medium/high
    last_active: datetime
    created_at: datetime


class UserBehaviorAnalyzer:
    """用户行为分析器"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.action_weights = {
            ActionType.VIEW: 0.1,
            ActionType.LIKE: 0.8,
            ActionType.DISLIKE: -0.5,
            ActionType.FAVORITE: 1.0,
            ActionType.SHARE: 0.9,
            ActionType.COMMENT: 0.7,
            ActionType.RATE: 0.6,
            ActionType.SEARCH: 0.2,
            ActionType.CLICK: 0.3,
        }
    
    async def analyze_user_preferences(self, user_id: str, 
                                     days: int = 30) -> UserProfile:
        """分析用户偏好"""
        # 获取用户行为数据
        actions = await self.get_user_actions(user_id, days)
        
        if not actions:
            # 新用户，返回默认画像
            return self._create_default_profile(user_id)
        
        # 分析各维度偏好
        genre_prefs = await self._analyze_genre_preferences(actions)
        tag_prefs = await self._analyze_tag_preferences(actions)
        year_prefs = await self._analyze_year_preferences(actions)
        rating_bias = self._analyze_rating_bias(actions)
        activity_level = self._analyze_activity_level(actions)
        
        # 构建用户画像
        profile = UserProfile(
            user_id=user_id,
            preferences=self._build_general_preferences(actions),
            genre_preferences=genre_prefs,
            tag_preferences=tag_prefs,
            year_preferences=year_prefs,
            rating_bias=rating_bias,
            activity_level=activity_level,
            last_active=max(action.timestamp for action in actions),
            created_at=min(action.timestamp for action in actions)
        )
        
        return profile
    
    async def get_user_actions(self, user_id: str, days: int = 30) -> List[UserAction]:
        """获取用户行为数据"""
        since_date = datetime.now() - timedelta(days=days)
        
        # 从数据库查询用户行为
        query = """
        SELECT user_id, item_id, action_type, timestamp, value, context
        FROM user_actions 
        WHERE user_id = %s AND timestamp >= %s
        ORDER BY timestamp DESC
        """
        
        rows = await self.db_manager.fetch_all(query, (user_id, since_date))
        
        actions = []
        for row in rows:
            context = json.loads(row['context']) if row['context'] else None
            action = UserAction(
                user_id=row['user_id'],
                item_id=row['item_id'],
                action_type=ActionType(row['action_type']),
                timestamp=row['timestamp'],
                value=row['value'],
                context=context
            )
            actions.append(action)
        
        return actions
    
    async def _analyze_genre_preferences(self, actions: List[UserAction]) -> Dict[str, float]:
        """分析类型偏好"""
        genre_scores = defaultdict(float)
        genre_counts = defaultdict(int)
        
        for action in actions:
            # 获取物品的类型信息
            item_genres = await self._get_item_genres(action.item_id)
            weight = self.action_weights.get(action.action_type, 0.0)
            
            for genre in item_genres:
                genre_scores[genre] += weight
                genre_counts[genre] += 1
        
        # 归一化
        genre_prefs = {}
        for genre, score in genre_scores.items():
            count = genre_counts[genre]
            if count > 0:
                genre_prefs[genre] = score / count
        
        return self._normalize_preferences(genre_prefs)
    
    async def _analyze_tag_preferences(self, actions: List[UserAction]) -> Dict[str, float]:
        """分析标签偏好"""
        tag_scores = defaultdict(float)
        tag_counts = defaultdict(int)
        
        for action in actions:
            item_tags = await self._get_item_tags(action.item_id)
            weight = self.action_weights.get(action.action_type, 0.0)
            
            for tag in item_tags:
                tag_scores[tag] += weight
                tag_counts[tag] += 1
        
        # 归一化
        tag_prefs = {}
        for tag, score in tag_scores.items():
            count = tag_counts[tag]
            if count > 0:
                tag_prefs[tag] = score / count
        
        return self._normalize_preferences(tag_prefs)
    
    async def _analyze_year_preferences(self, actions: List[UserAction]) -> Dict[int, float]:
        """分析年代偏好"""
        year_scores = defaultdict(float)
        year_counts = defaultdict(int)
        
        for action in actions:
            item_year = await self._get_item_year(action.item_id)
            weight = self.action_weights.get(action.action_type, 0.0)
            
            if item_year:
                year_scores[item_year] += weight
                year_counts[item_year] += 1
        
        # 归一化
        year_prefs = {}
        for year, score in year_scores.items():
            count = year_counts[year]
            if count > 0:
                year_prefs[year] = score / count
        
        return year_prefs
    
    def _analyze_rating_bias(self, actions: List[UserAction]) -> float:
        """分析评分偏好"""
        ratings = []
        for action in actions:
            if action.action_type == ActionType.RATE and action.value:
                try:
                    rating = float(action.value)
                    ratings.append(rating)
                except:
                    continue
        
        if ratings:
            return sum(ratings) / len(ratings)
        return 5.0  # 默认中性评分
    
    def _analyze_activity_level(self, actions: List[UserAction]) -> str:
        """分析活跃度"""
        if not actions:
            return "low"
        
        days_span = (max(action.timestamp for action in actions) - 
                    min(action.timestamp for action in actions)).days
        
        if days_span == 0:
            days_span = 1
        
        actions_per_day = len(actions) / days_span
        
        if actions_per_day >= 5:
            return "high"
        elif actions_per_day >= 2:
            return "medium"
        else:
            return "low"
    
    def _build_general_preferences(self, actions: List[UserAction]) -> Dict[str, float]:
        """构建通用偏好"""
        # 基于行为类型统计
        action_counts = Counter(action.action_type for action in actions)
        total_actions = len(actions)
        
        prefs = {}
        for action_type, count in action_counts.items():
            prefs[action_type.value] = count / total_actions
        
        return prefs
    
    def _normalize_preferences(self, prefs: Dict[str, float]) -> Dict[str, float]:
        """归一化偏好分数"""
        if not prefs:
            return {}
        
        values = list(prefs.values())
        min_val = min(values)
        max_val = max(values)
        
        if max_val == min_val:
            return {k: 0.5 for k in prefs.keys()}
        
        normalized = {}
        for k, v in prefs.items():
            normalized[k] = (v - min_val) / (max_val - min_val)
        
        return normalized
    
    def _create_default_profile(self, user_id: str) -> UserProfile:
        """创建默认用户画像"""
        return UserProfile(
            user_id=user_id,
            preferences={},
            genre_preferences={},
            tag_preferences={},
            year_preferences={},
            rating_bias=5.0,
            activity_level="low",
            last_active=datetime.now(),
            created_at=datetime.now()
        )
    
    async def _get_item_genres(self, item_id: str) -> List[str]:
        """获取物品类型"""
        query = "SELECT genres FROM anime_items WHERE id = %s"
        result = await self.db_manager.fetch_one(query, (item_id,))
        
        if result and result['genres']:
            return json.loads(result['genres'])
        return []
    
    async def _get_item_tags(self, item_id: str) -> List[str]:
        """获取物品标签"""
        query = "SELECT tags FROM anime_items WHERE id = %s"
        result = await self.db_manager.fetch_one(query, (item_id,))
        
        if result and result['tags']:
            return json.loads(result['tags'])
        return []
    
    async def _get_item_year(self, item_id: str) -> Optional[int]:
        """获取物品年代"""
        query = "SELECT year FROM anime_items WHERE id = %s"
        result = await self.db_manager.fetch_one(query, (item_id,))
        
        if result and result['year']:
            return int(result['year'])
        return None


class UserBehaviorTracker:
    """用户行为跟踪器"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.batch_actions = []
        self.batch_size = 100
    
    async def track_action(self, user_id: str, item_id: str, 
                          action_type: ActionType, value: Optional[Union[float, str]] = None,
                          context: Optional[Dict] = None):
        """跟踪用户行为"""
        action = UserAction(
            user_id=user_id,
            item_id=item_id,
            action_type=action_type,
            timestamp=datetime.now(),
            value=value,
            context=context
        )
        
        # 批量处理
        self.batch_actions.append(action)
        
        if len(self.batch_actions) >= self.batch_size:
            await self._flush_batch()
    
    async def _flush_batch(self):
        """批量写入数据库"""
        if not self.batch_actions:
            return
        
        query = """
        INSERT INTO user_actions (user_id, item_id, action_type, timestamp, value, context)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        
        values = []
        for action in self.batch_actions:
            context_json = json.dumps(action.context) if action.context else None
            values.append((
                action.user_id,
                action.item_id,
                action.action_type.value,
                action.timestamp,
                action.value,
                context_json
            ))
        
        await self.db_manager.execute_many(query, values)
        self.batch_actions.clear()
    
    async def flush(self):
        """强制刷新批量数据"""
        await self._flush_batch()


class UserSegmentation:
    """用户分群"""
    
    def __init__(self, behavior_analyzer: UserBehaviorAnalyzer):
        self.behavior_analyzer = behavior_analyzer
    
    async def segment_users(self, user_ids: List[str]) -> Dict[str, List[str]]:
        """用户分群"""
        segments = {
            'new_users': [],        # 新用户
            'active_users': [],     # 活跃用户  
            'casual_users': [],     # 一般用户
            'power_users': [],      # 重度用户
            'dormant_users': []     # 沉默用户
        }
        
        for user_id in user_ids:
            profile = await self.behavior_analyzer.analyze_user_preferences(user_id)
            segment = self._classify_user(profile)
            segments[segment].append(user_id)
        
        return segments
    
    def _classify_user(self, profile: UserProfile) -> str:
        """用户分类"""
        # 新用户：注册时间小于7天
        if (datetime.now() - profile.created_at).days < 7:
            return 'new_users'
        
        # 沉默用户：最后活跃时间超过30天
        if (datetime.now() - profile.last_active).days > 30:
            return 'dormant_users'
        
        # 根据活跃度分类
        if profile.activity_level == 'high':
            return 'power_users'
        elif profile.activity_level == 'medium':
            return 'active_users'
        else:
            return 'casual_users'