import chromadb

from rag.embed import BASE, embed_texts

COLLECTION_NAME = "job_chunks"
DEFAULT_K = 10#检索返回几条
PRINT_LIMIT = 10#终端打印几条(限制刷屏)

_collection = None


def get_collection():
    """懒加载，避免import时打开sqlite"""
    global _collection
    # 不写 global，赋值会创建局部变量，函数外的 _collection 永远是 None 每次都新建一个
    if _collection is None:
        client = chromadb.PersistentClient(path=str(BASE / "chroma_db"))
        _collection = client.get_collection(COLLECTION_NAME)
    return _collection


def build_where(city: str | None = None, job_type: str | None = None):
    """chroma数据库限制查询语句构建，无条件时返回 None。"""
    conds = []
    if city:
        conds.append({"city": {"$contains": city}})
    if job_type:
        conds.append({"job_type": job_type})

    if not conds:# 0 个 → 不过滤
        return None
    if len(conds) == 1:# 1 个 → 直接返回，不包 $and
        return conds[0]
    return {"$and": conds}#如果 $and 被当成 $or，后续查询结果一定为28
                          #{"$and": [条件1, 条件2, 条件3]}


def search(query: str, city: str | None = None, job_type: str | None = None, k: int = DEFAULT_K) -> list[dict]:
    """返回时按相似度降序片段"""
    qv = embed_texts([query])[0]
    #embed_texts([q])->list[list[float]],向量的列表
    #embed_texts([q])[0]->list[float],第一条向量,一条1024(float)维
    res = get_collection().query(
        query_embeddings=[qv],
        n_results=k,
        where=build_where(city, job_type),
        include=["documents", "metadatas", "distances"],
    )

    rows = []
    for cid, doc, meta, dist in zip(
        res["ids"][0],
        res["documents"][0],
        res["metadatas"][0],
        res["distances"][0],
    ):
        rows.append(
            {
                "chunk_id": cid,
                "score": round(1 - dist, 4),
                "text": doc,
                **meta,
            }
        )
    return rows


def main():
    q = "多模态大模型Agent开发"
    cases = [
        ("不带过滤", {}),
        ("city=北京", {"city": "北京"}),
        ("job_type=实习", {"job_type": "实习"}),
        ("city=北京 + 实习", {"city": "北京", "job_type": "实习"}),
        ("city=深圳", {"city": "深圳"}),
    ]

    for label, kwargs in cases:
        rows = search(q, **kwargs)
        print(f"\n[{label}] 返回 {len(rows)} 条")
        for i, r in enumerate(rows[:PRINT_LIMIT], 1):
            print(
                f"  {i}. {r['score']:.4f}  {r['company']} / {r['job_name']}"
                f"  ({r['job_type']}, {r['city']})"
            )

if __name__ == "__main__":
    main()