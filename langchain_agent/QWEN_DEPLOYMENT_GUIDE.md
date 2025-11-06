# 千问API集成部署指南

## 🚀 快速开始

### 1. 获取千问API密钥

1. 访问 [阿里云DashScope](https://dashscope.aliyun.com/)
2. 注册/登录账号
3. 创建API密钥
4. 复制密钥备用

### 2. 环境配置

```bash
# 1. 复制配置文件
cp .env.example .env

# 2. 编辑配置文件，添加你的API密钥
vim .env
# 或者
nano .env
```

在 `.env` 文件中设置：
```bash
DASHSCOPE_API_KEY=sk-your-actual-api-key-here
```

### 3. 安装依赖

```bash
# 更新依赖
pip install -r requirements.txt

# 或者单独安装新增的包
pip install dashscope httpx
```

### 4. 启动服务

```bash
# 确保 Qdrant 正在运行
docker-compose up qdrant -d

# 启动 API 服务
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 或者使用启动脚本
./start_service.sh
```

### 5. 测试功能

```bash
# 运行完整测试
python test_api.py

# 或者单独测试智能问答
curl -X POST "http://localhost:8000/api/answer" \
  -H "Content-Type: application/json" \
  -d '{"question": "推荐一些校园恋爱动漫"}'
```

## 📊 功能对比

### 集成前
```
用户: "推荐爱情动漫"
系统: "你的名字，类型：剧场版，标签：爱情，简介：..."
```

### 集成后
```
用户: "推荐爱情动漫"
AI: "🌸 根据您对爱情动漫的喜好，我为您推荐以下几部经典作品：

💕 **你的名字** - 新海诚的代表作，唯美的画面配上感人的跨越时空爱情故事，绝对是爱情动漫的必看之选！

✨ 推荐理由：这部作品完美结合了奇幻元素和现实情感，画面美轮美奂，音乐催人泪下，是近年来最受欢迎的爱情动漫之一。

希望这些推荐能让您感受到动漫中的美好爱情故事！还想了解其他类型的动漫吗？"
```

## 🔧 技术架构

### 简化后的架构
```
用户请求 → FastAPI → 向量检索(Qdrant直接) → 千问API → 智能回答
```

### 移除的组件
- ❌ `langchain_qdrant.QdrantVectorStore`
- ❌ `langchain_ollama.OllamaLLM`
- ❌ 复杂的 LangChain 链式调用

### 保留的组件
- ✅ Qdrant 直接客户端（高效）
- ✅ Sentence Transformers（向量生成）
- ✅ FastAPI（Web服务）
- ✅ 新增：千问API（智能对话）

## 💰 成本估算

### 千问API价格（参考）
- qwen-turbo: ~0.008元/1k tokens
- qwen-plus: ~0.02元/1k tokens
- qwen-max: ~0.12元/1k tokens

### 实际使用成本
- 单次对话: 100-300 tokens
- 日均1000次对话: ~2-6元
- 月度成本: ~60-180元

### 优化建议
1. 使用 qwen-turbo（性价比最高）
2. 实现智能缓存减少重复调用
3. 优化 Prompt 长度
4. 监控API使用量

## 🚨 注意事项

1. **API密钥安全**
   - 不要将密钥提交到代码仓库
   - 使用环境变量存储
   - 定期更换密钥

2. **错误处理**
   - API调用失败时有备用方案
   - 设置合理的超时时间
   - 记录错误日志便于调试

3. **性能优化**
   - 可考虑添加本地缓存
   - 异步处理提高并发
   - 监控响应时间

## 🔍 故障排除

### 常见问题

1. **API密钥错误**
   ```
   错误: Authentication failed
   解决: 检查 .env 文件中的 DASHSCOPE_API_KEY
   ```

2. **网络连接问题**
   ```
   错误: Connection timeout
   解决: 检查网络连接，可能需要代理
   ```

3. **依赖包问题**
   ```
   错误: ModuleNotFoundError
   解决: pip install -r requirements.txt
   ```

### 测试命令
```bash
# 测试环境变量
python -c "import os; print(os.getenv('DASHSCOPE_API_KEY'))"

# 测试API连通性
python -c "import httpx; print(httpx.get('https://dashscope.aliyun.com').status_code)"

# 测试完整功能
python test_api.py
```

## 🎯 下一步优化

1. **对话记忆**: 实现多轮对话上下文
2. **用户画像**: 记录用户偏好，个性化推荐
3. **推荐学习**: 根据用户反馈优化推荐算法
4. **多模态**: 支持图片和文字结合的推荐