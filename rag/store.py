"""
只要在向量入库之后，再将问题向量化后去query就能使用top-k排序查询返回distance
此模块将用get_collection懒加载向量库对象，对数据库进行操作
build_metadatas将chunk中的一些字段变成元数据的列表，并且将city多值拆分，方便查询
最后store函数使用collection操作对象对整理好的数据以及元数据upsert插入数据库，仅补全不add
"""
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
#note:1.HNSW 算完距离，返回 label（[3, 17, 21]）2.查 embeddings：label → chunk_id（3 → '30100000464672_工作内容_1'）
    #3.用 id=3 查 embedding_metadata（返回 8 行 key-value）4.拼成一条完整记录（{chunk_id, text, city, company, …}）