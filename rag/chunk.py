"""chunk.py —— 把岗位记录切成可检索的文本片

输入：data/jobs_clean.json
输出：data/chunks.json

切片策略：
1.一节一片
2.单节超过800，节内按段落且，切口重叠50字
"""

import json
from pathlib import Path


MAX_CHUNK_LEN = 800
OVERLAP = 50


def make_chunk(record: dict, section: str, text: str, idx: int) -> dict:
    """组装一片idx从1开始，表示这是该节第几片"""
    return {
        "chunk_id": f"{record['id']}_{section}_{idx}",
        "job_id": record["id"],
        "job_name": record["job_name"],
        "company": record["company"],
        "city": record["city"],
        "section": section,
        "text": text,
        "char_len": len(text),
    }


def split_section(record: dict, section: str, text: str) -> list[dict]:
    """一个小节->若干片"""
    text = text.strip()
    if not text:
        return []
    return [make_chunk(record, section, text, 1)]


def build_chunks(records: list[dict]) -> list[dict]:
    """所有岗位->所有文本片"""
    chunks = []
    for record in records:
        for part in record["content_parts"]:
            chunks.extend(split_section(record, part["section"], part["text"]))
    return chunks


def main():
    base = Path(__file__).resolve().parent.parent
    in_path = base / "data" / "jobs_clean.json"
    out_path = base / "data" / "chunks.json"

    records = json.loads(in_path.read_text(encoding="utf-8"))
    chunks = build_chunks(records)
    out_path.write_text(
        json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"[完成]{len(records)}条岗位->{len(chunks)}片")
    print(f"[长度] 最长 {max(c['char_len'] for c in chunks)} / "
          f"最短 {min(c['char_len'] for c in chunks)}")
    print()
    c = chunks[0]
    print("抽查第一片:", c["chunk_id"])
    print("  job_name =", c["job_name"])
    print("  company  =", c["company"], "| city =", c["city"])
    print("  text     =", repr(c["text"][:120]))

if __name__ == "__main__":
    main()