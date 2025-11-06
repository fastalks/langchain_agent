# 推荐系统新架构实现指南

## 系统架构概览

### 1. 分层架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                    API层 (FastAPI)                         │
├─────────────────────────────────────────────────────────────┤
│                  推荐引擎层 (Core)                          │
├─────────────────────────────────────────────────────────────┤
│     召回层 (Recall)    │      排序层 (Ranking)              │
├─────────────────────────────────────────────────────────────┤
│               用户行为分析层 (User Behavior)                │
├─────────────────────────────────────────────────────────────┤
│     数据层 (PostgreSQL + Redis + Qdrant)                   │
└─────────────────────────────────────────────────────────────┘
```

### 2. 核心组件说明

#### 📊 数据层 (Data Layer)
- **PostgreSQL**: 存储结构化数据（动漫信息、用户行为、画像）
- **Redis**: 缓存热点数据和推荐结果
- **Qdrant**: 向量数据库，存储动漫embedding

#### 🎯 召回层 (Recall Layer)
- **向量召回**: 基于embedding相似度召回
- **标签召回**: 基于标签匹配召回
- **协同过滤**: 基于用户行为的协同过滤召回
- **流行度召回**: 基于热度和评分召回

#### 🏆 排序层 (Ranking Layer)
- **特征工程**: 提取多维度特征
- **加权融合**: 多种信号的加权组合
- **LLM增强**: 大模型重排序和解释生成

#### 👤 用户层 (User Layer)
- **行为跟踪**: 实时记录用户行为
- **画像构建**: 分析用户偏好和特征
- **个性化**: 基于用户画像的个性化推荐

## 实现步骤

### 步骤1: 数据库初始化

```bash
# 启动新的推荐系统服务（开发模式）
cd /Users/wangfaguo/Desktop/langchain_agent/langchain_agent
python -m app.enhanced_main
```

### 步骤2: 配置管理

系统会自动生成配置文件：`config/recommendation.yaml`

```yaml
database:
  qdrant_host: localhost
  qdrant_port: 6333
  postgres_host: localhost
  postgres_port: 5432
  postgres_db: anime_recommend
  postgres_user: postgres
  postgres_password: password
  redis_host: localhost
  redis_port: 6379

model:
  embedding_model: BAAI/bge-small-zh-v1.5
  embedding_dim: 512
  llm_model: qwen-turbo

recall:
  vector_recall_k: 30
  cf_recall_k: 20
  tag_recall_k: 15
  max_candidates: 100

ranking:
  feature_weights:
    base: 1.0
    year_match: 0.5
    tag_match: 0.3
    popularity: 0.2
  use_llm_rerank: true
```

### 步骤3: API使用示例

#### 基础推荐API
```bash
curl -X POST "http://localhost:8001/api/v2/recommendations" \
-H "Content-Type: application/json" \
-d '{
  "query": "推荐一些2011年的动漫",
  "user_id": "user123",
  "num_recommendations": 10
}'
```

#### 流式推荐API
```bash
curl -X POST "http://localhost:8001/api/v2/recommendations/stream" \
-H "Content-Type: application/json" \
-d '{
  "query": "推荐一些科幻动漫",
  "user_id": "user123",
  "stream": true
}'
```

#### 用户行为记录
```bash
curl -X POST "http://localhost:8001/api/v2/user/action" \
-H "Content-Type: application/json" \
-d '{
  "user_id": "user123",
  "item_id": "anime_001", 
  "action_type": "like",
  "context": {"source": "recommendation"}
}'
```

## 与现有系统的集成

### 1. 数据迁移

从现有Qdrant迁移数据到新的多数据库架构：

```python
# 迁移脚本示例
async def migrate_data():
    # 从现有Qdrant读取数据
    old_data = await old_qdrant_client.scroll(collection_name="anime_collections")
    
    # 写入新的数据库
    for point in old_data:
        # 写入PostgreSQL
        await anime_repo.create_anime(point.payload)
        
        # 写入新Qdrant
        await db_manager.vector_upsert("anime_embeddings", [point])
```

### 2. API兼容性

新系统保持对现有API的兼容：

```python
# 兼容性包装器
@app.post("/api/recommendations/qwen-streaming-sse")
async def legacy_streaming_api(request: dict):
    # 转换为新格式
    new_request = RecommendRequest(
        query=request.get("query", ""),
        stream=True
    )
    # 调用新API
    return await stream_recommendations(new_request)
```

## 性能优化策略

### 1. 缓存策略
- 热门查询结果缓存（Redis）
- 用户画像缓存
- 向量搜索结果缓存

### 2. 批处理
- 用户行为批量写入
- 向量批量更新
- 特征批量计算

### 3. 异步处理
- 非阻塞的推荐计算
- 后台用户画像更新
- 异步日志记录

## 监控和调优

### 1. 系统监控
```bash
# 检查系统状态
curl http://localhost:8001/api/v2/system/status

# 查看配置
curl http://localhost:8001/api/v2/config
```

### 2. 性能指标
- 推荐响应时间
- 召回率和精确率
- 用户行为覆盖率
- 缓存命中率

### 3. A/B测试支持
- 不同召回策略对比
- 排序算法效果评估
- LLM增强效果验证

## 扩展计划

### 短期扩展
1. **实时特征**: 添加实时特征计算
2. **深度学习**: 集成深度学习排序模型
3. **多样性**: 增加推荐多样性算法

### 长期扩展
1. **图神经网络**: 基于知识图谱的推荐
2. **强化学习**: 基于反馈的在线学习
3. **多模态**: 整合文本、图像、音频特征

## 部署建议

### 开发环境
```bash
# 使用Docker Compose启动完整环境
docker-compose up -d

# 启动新推荐系统
python -m app.enhanced_main
```

### 生产环境
```bash
# 使用Kubernetes部署
kubectl apply -f k8s/recommendation-system.yaml

# 或使用Docker Swarm
docker stack deploy -c docker-stack.yml recommendation
```

这个新架构提供了更强的扩展性、更好的性能和更丰富的功能，能够支持从简单的标签匹配到复杂的深度学习推荐的全谱系算法。