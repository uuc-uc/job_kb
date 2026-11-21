"""main.py —— FastAPI 应用与路由

启动（必须在项目根 E:\\RAG\\job_kb 下，否则 import 不到 rag 包）：
  E:\\env\\rag\\.venv\\Scripts\\python.exe -m uvicorn api.main:app --reload --port 8000

接口文档：http://127.0.0.1:8000/docs
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api.schemas import AskRequest, AskResponse
from rag.embed import embed_texts
from rag.generate import answer
from rag.embed import BASE, embed_texts


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时预热模型，避免第一个真是请求等加载"""
    print("预热模型嵌入模型。。。")
    embed_texts(["预热"])
    print("就绪可以接受请求")
    yield


app = FastAPI(title="就业知识问答系统", lifespan=lifespan)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/ask", response_model=AskResponse)
def ask(req: AskRequest) -> dict:
    return answer(req.query, city=req.city, job_type=req.job_type, k=req.k)


#必须放最后“/”会匹配所有路径
app.mount("/", StaticFiles(directory=str(BASE / "web"), html=True), name="web")
