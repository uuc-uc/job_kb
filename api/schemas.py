"""schemas.py —— 接口的请求 / 响应模型

Pydantic 模型在这里承担三件事：
  1. 校验：类型、必填、长度范围。不合法直接 422，代码还没跑到业务逻辑
  2. 文档：FastAPI 用它们生成 /docs 的接口说明
  3. 契约：字段漏了 / 改名了立刻报错，而不是静默返回残缺 JSON

"""
from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    """POST /api/ask 的请求体。"""
    query: str = Field(..., min_length=1, max_length=200)
    city: str | None = None
    job_type: str | None = None
    k: int = Field(default=5, ge=1, le=20)


class Source(BaseModel):
    """一条来源，字段要对上 rag/retrieve.py 里 search() 返回的 dict。"""
    chunk_id: str
    job_name: str
    company: str
    city: list[str]
    job_type: str
    section: str
    url: str
    score: float
    text: str


class AskResponse(BaseModel):
    """POST /api/ask 的响应体。"""
    answer: str
    sources: list[Source]