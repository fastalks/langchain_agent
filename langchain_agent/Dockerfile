# Dockerfile

# 使用官方 Python 轻量镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 先拷贝依赖文件，有利于缓存
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 再拷贝项目代码
COPY ./app ./app

# 暴露 FastAPI 默认端口
EXPOSE 8000

# 启动 FastAPI 服务（使用 uvicorn）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]