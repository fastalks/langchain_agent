from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app.langchain_agent import answer_question  # 导入你的核心逻辑

app = FastAPI(title="LangChain Anime Agent API", version="1.0")

# 请求模型
class QuestionRequest(BaseModel):
    question: str

# 响应模型（可选）
class QuestionResponse(BaseModel):
    answer: str

# API 路由
@app.post("/api/answer", response_model=QuestionResponse)
async def chat_with_agent(request: QuestionRequest):
    try:
        answer = await answer_question(request.question, k=3)  # 检索 3 个相关作品
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"问答服务出错：{str(e)}")