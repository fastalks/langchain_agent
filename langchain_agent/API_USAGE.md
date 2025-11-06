# 动漫向量数据库 API 使用指南

## 概述

本项目提供了用于存储和查询动漫数据的向量数据库接口。支持单个和批量上传动漫数据。

## API 端点

### 1. 上传单个动漫数据

**端点**: `POST /api/anime/upload`

**请求体**:
```json
{
  "id": 12345,
  "name_cn": "你的名字",
  "name": "君の名は。",
  "type": "剧场版",
  "tags": ["爱情", "奇幻", "校园"],
  "description": "一部关于两个高中生通过梦境交换身体的爱情奇幻动画电影。"
}
```

**响应**:
```json
{
  "success": true,
  "message": "动漫数据上传成功",
  "count": 1
}
```

### 2. 批量上传动漫数据

**端点**: `POST /api/anime/bulk-upload`

**请求体**:
```json
{
  "animes": [
    {
      "id": 1,
      "name_cn": "千与千寻",
      "name": "千と千尋の神隠し",
      "type": "剧场版",
      "tags": ["奇幻", "冒险", "家庭"],
      "description": "宫崎骏执导的奇幻冒险动画电影，讲述了小女孩千寻在神秘世界的冒险故事。"
    },
    {
      "id": 2,
      "name_cn": "攻壳机动队",
      "name": "Ghost in the Shell",
      "type": "TV",
      "tags": ["科幻", "动作", "赛博朋克"],
      "description": "设定在2030年的近未来，描述了公安9课的故事。"
    }
  ]
}
```

**响应**:
```json
{
  "success": true,
  "message": "成功上传 2 条动漫数据",
  "count": 2
}
```

### 3. 问答接口（原有功能）

**端点**: `POST /api/answer`

**请求体**:
```json
{
  "question": "推荐一些好看的爱情动漫"
}
```

### 4. 健康检查

**端点**: `GET /health`

**响应**:
```json
{
  "status": "healthy",
  "message": "动漫向量数据库服务运行正常"
}
```

## 数据字段说明

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| id | int | 否 | 动漫ID，如果不提供会自动生成 |
| name_cn | string | 否 | 中文名称 |
| name | string | 否 | 原名（日文、英文等） |
| type | string | 否 | 类型（TV、剧场版、OVA等） |
| tags | array | 否 | 标签数组（如：["爱情", "校园", "青春"]） |
| description | string | 否 | 动漫简介描述 |

## 使用示例

### Python 示例

```python
import requests
import json

# 服务器地址
BASE_URL = "http://localhost:8000"

# 单个上传示例
anime_data = {
    "name_cn": "你的名字",
    "name": "君の名は。",
    "type": "剧场版",
    "tags": ["爱情", "奇幻", "校园"],
    "description": "一部关于两个高中生通过梦境交换身体的爱情奇幻动画电影。"
}

response = requests.post(f"{BASE_URL}/api/anime/upload", json=anime_data)
print(response.json())

# 批量上传示例
bulk_data = {
    "animes": [
        {
            "name_cn": "千与千寻",
            "name": "千と千尋の神隠し",
            "type": "剧场版",
            "tags": ["奇幻", "冒险", "家庭"],
            "description": "宫崎骏执导的奇幻冒险动画电影。"
        },
        {
            "name_cn": "攻壳机动队",
            "name": "Ghost in the Shell",
            "type": "TV",
            "tags": ["科幻", "动作", "赛博朋克"],
            "description": "设定在2030年的近未来的科幻动画。"
        }
    ]
}

response = requests.post(f"{BASE_URL}/api/anime/bulk-upload", json=bulk_data)
print(response.json())
```

### cURL 示例

```bash
# 单个上传
curl -X POST "http://localhost:8000/api/anime/upload" \
  -H "Content-Type: application/json" \
  -d '{
    "name_cn": "你的名字",
    "name": "君の名は。",
    "type": "剧场版",
    "tags": ["爱情", "奇幻", "校园"],
    "description": "一部关于两个高中生通过梦境交换身体的爱情奇幻动画电影。"
  }'

# 健康检查
curl -X GET "http://localhost:8000/health"
```

## 启动服务

```bash
cd langchain_agent
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

服务启动后，可以通过 http://localhost:8000/docs 访问 Swagger UI 进行接口测试。

## 注意事项

1. 确保 Qdrant 向量数据库服务正在运行（通常在 localhost:6333）
2. 所有字段都是可选的，但建议至少提供 `name_cn` 和 `description` 以获得更好的检索效果
3. `tags` 字段有助于提高搜索的准确性
4. 系统会自动为每条数据生成向量嵌入并存储到 Qdrant
5. 如果不提供 `id`，系统会自动生成唯一标识符