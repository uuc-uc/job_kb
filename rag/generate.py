import os
from pathlib import Path


from dotenv import load_dotenv
from openai import OpenAI

from rag.retrieve import search
from rag.query import parse as parse_query


BASE = Path(__file__).resolve().parent.parent
load_dotenv(BASE / ".env", override=True)

MODEL = "deepseek-flash"
BASE_URL = "https://api.deepseek.com"
MAX_CONTENT_CHARS = 3000
TEMPERATURE = 0.3

_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        key = os.environ.get("DEEPSEEK_API_KEY")
        if not key:
            raise RuntimeError(
                "缺少deepseek_api_key\n"
            )
        _client = OpenAI(api_key=key, base_url=BASE_URL)
    return _client


def build_context(rows: list[dict]) -> str:
    blocks, used = [], 0
    for i, r in enumerate(rows, 1):
        head = (
            f"[{i}] 岗位：{r['job_name']} | 公司：{r['company']} | 城市：{'/'.join(r['city'])} | "
            f"类型：{r['job_type']} | 小节：{r['section']}"
        )
        block = f"{head}\n{r['text']}"
        if used + len(block) > MAX_CONTENT_CHARS:
            break
        blocks.append(block)
        used += len(block)
    return "\n\n".join(blocks)


SYSTEM_PROMPT = """你是计算机专业学生的就业顾问。
只依据「参考资料」回答，不要使用资料之外的知识。
资料不足以回答时，直接说"资料里没有相关信息"，不要猜测。
回答时用 [1] [2] 这样的编号标注依据。"""


def build_messages(query: str, rows: list[dict]) -> list[dict]:
    user = f"参考资料：\n{build_context(rows)}\n\n问题：{query}"
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def answer(query: str, city: str | None = None, job_type: str | None = None, k: int = 5) -> dict:
    """p为self-query组件，search()为retrieve组件"""
    p = parse_query(query, city, job_type)
    rows = search(p["semantic"], k=k, extra_where=p["where"])

    if not rows:
        return {
            "answer": "没有找到符合条件的岗位。可以换个城市，或放宽筛选条件再试试。",
            "sources": [],
        }

    resp = _get_client().chat.completions.create(
        model=MODEL,
        messages=build_messages(query, rows),
        temperature=TEMPERATURE,
    )
    return {"answer": resp.choices[0].message.content, "sources": rows}


def main():
    cases = [
        ("正常问题", "哪个岗位要求 985 硕士", {}),
        ("带过滤", "北京有哪些多模态大模型的实习岗", {"city": "北京", "job_type": "实习"}),
        ("空结果", "深圳有哪些岗位", {"city": "深圳"}),
        ("库里没有", "这个岗位的年终奖发几个月", {}),
    ]
    for label, q, kw in cases:
        r = answer(q, **kw)
        # print(r)
        print(f"\n{'=' * 60}\n[{label}] {q}")
        print(f"回答：{r['answer']}")
        print(f"来源：{len(r['sources'])} 条")


if __name__ == "__main__":
    main()