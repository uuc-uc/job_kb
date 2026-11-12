"""embed.py —— 文本 → 向量（本地 BGE-M3）

输入: list[str]
输出: list[list[float]]

为什么只有一个入口:
  入库(28 片)和查询(用户问题)必须落在同一个向量空间。
  模型 / 维度 / 归一化任何一项不同 -> 向量不可比 -> 检索全是噪声，而且不报错。
  所以配置写死在模块里，调用方没有机会传错。

为什么用本地模型:
  API 按 token 计费，断网或欠费即不可用。BGE-M3 开源、可离线、中文强，
  且同一模型能同时输出 dense + sparse，后续做混合检索不必再单独实现 BM25。

维度与模型一旦变更，库里已有的旧向量全部作废，必须重建。
"""
import json
import os
import time
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")  # 模型已落盘，禁止任何联网检查

from sentence_transformers import SentenceTransformer  # noqa: E402

MODEL_NAME = "BAAI/bge-m3"
MODEL_CACHE = Path(r"E:\RAG\models")
EMBED_DIM = 1024
BATCH_SIZE = 32

BASE = Path(__file__).resolve().parent.parent

_model = None


def _get_model() -> SentenceTransformer:
    """懒加载：加载要 2 秒、常驻占约 2GB 内存，import 时不该付这个代价。"""
    global _model
    if _model is None:
        t0 = time.time()
        _model = SentenceTransformer(
            MODEL_NAME,
            cache_folder=str(MODEL_CACHE),
            local_files_only=True,
            device="cpu",
        )
        print(f"[模型] {MODEL_NAME} 加载完成 {time.time() - t0:.1f}s")
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """把一批文本变成等长向量，顺序与输入严格一一对应。"""
    if not texts:
        return []

    model = _get_model()
    vectors = model.encode(
        texts,
        batch_size=BATCH_SIZE,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    if vectors.shape[1] != EMBED_DIM:
        raise RuntimeError(f"维度 {vectors.shape[1]} != 期望 {EMBED_DIM}")
    if len(vectors) != len(texts):
        raise RuntimeError(f"返回 {len(vectors)} 条 != 输入 {len(texts)} 条")

    return vectors.tolist()


def cosine(a: list[float], b: list[float]) -> float:
    """手算余弦，不引 numpy——这一步只是自检，看得见就够了。"""
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if not na or not nb:
        return 0.0
    return dot / (na * nb)


def main():
    chunks = json.loads((BASE / "data" / "chunks.json").read_text(encoding="utf-8"))
    texts = [c["text"] for c in chunks]

    t0 = time.time()
    vectors = embed_texts(texts)
    cost = time.time() - t0

    print(f"[完成] {len(texts)} 片 -> {len(vectors)} 个向量，维度 {len(vectors[0])}，{cost:.1f}s")
    print(f"[字符] 共 {sum(len(t) for t in texts):,}")
    print(f"[模长] {sum(x * x for x in vectors[0]) ** 0.5:.6f}（归一化后应为 1.0）")
    print()

    queries = [
        "深圳有哪些要求 RAG 经验的岗位",
        "哪个岗位要求 985 硕士",
        "多模态大模型 Agent 开发",
    ]
    for q in queries:
        qv = embed_texts([q])[0]
        scored = sorted(
            ((cosine(qv, v), c) for v, c in zip(vectors, chunks)),
            key=lambda x: x[0],
            reverse=True,
        )
        print(f"查询：{q}")
        for score, c in scored[:3]:
            print(f"  {score:.4f}  {c['chunk_id']:<36} {c['company']} / {c['job_name']}")
        print()


if __name__ == "__main__":
    main()

