import json
from pathlib import Path

import chromadb

from rag.embed import embed_texts


BASE = Path(__file__).resolve().parent.parent
CHROMA_DIR = BASE / "chroma_db"
DATA_PATH = BASE / "data" / "chunks.json"
COLLECTION_NAME = "job_chunks"
BATCH_SIZE = 100


def get_collection():
    """打开或新建集合持久化到chroma_db/,进程退出不丢"""
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))#client绑定chroma_db/目录
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def build_metadatas(chunks: list[dict]) -> list[dict]:
    """chunk的八个字段变成chroma的metadata

    id用chunk_id,正文用text(document),其余为metadata
    """
    metas = []
    for c in chunks:
        cities = [x.strip() for x in (c.get("city") or "").split(",") if x.strip()]
        #这里要将多值拆分因为在检索时需要一一对应“北京”对应不了“北京，杭州”
        metas.append(
            {
                "job_id": c["job_id"],
                "job_name": c["job_name"],
                "company": c["company"] or "",
                "city": cities,
                "section": c["section"],
                "char_len": c["char_len"],
                "job_type": c["job_type"],
                "url": c["url"],
            }
        )
    return metas


def store(chunks: list[dict], collection, batch_size: int = BATCH_SIZE) -> int:
    """编码 + 分批upsert, 返回写入条数"""
    ids = [c["chunk_id"] for c in chunks]
    docs = [c["text"] for c in chunks]
    metas = build_metadatas(chunks)
    vectors = embed_texts(docs)

    for start in range(0, len(chunks), batch_size):
        end = start + batch_size
        collection.upsert(
            ids=ids[start:end],
            embeddings=vectors[start:end],
            documents=docs[start:end],
            metadatas=metas[start:end],
        )
    return len(ids)


def main():
    chunks = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    collection = get_collection()

    written = store(chunks, collection)
    print(f"[写入] {written} 片 -> {CHROMA_DIR}")
    print(f"[总数] 集合内共 {collection.count()} 条")

    q = "哪个岗位要求 985 硕士"
    qv = embed_texts([q])[0]#query vector
    res = collection.query(query_embeddings=[qv], n_results=3)
    print(f"\n[自检] 查询「{q}」")
    for i, (cid, dist, meta) in enumerate(
            zip(res["ids"][0], res["distances"][0], res["metadatas"][0]), 1
    ):
        print(f"  {i}. 距离 {dist:.4f}  {meta['company']} / {meta['job_name']}  ({meta['section']})")


if __name__ == "__main__":
    main()