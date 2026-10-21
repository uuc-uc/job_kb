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


def split_by_paragraph(text: str, max_len: int = MAX_CHUNK_LEN, overlap: int = OVERLAP) -> list[str]:
    """
    超长文本按段落切，切口保留overlap字重叠

    两件事同时：
    1.段落优先————在\n\n断开,不从句子中间切
    2.长度兜底————单端超长，段内硬切
    """
    assert overlap < max_len, f"overlap({overlap}) 必须小于 max_len({max_len})" #使用断言防止步长step错误

    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    pieces = []
    buf = ""

    for p in paras:
        if len(p) > max_len:# 情况 1：单段自己就超长，段落边界救不了，只能硬切
            if buf:
                pieces.append(buf)
                buf = ""
            step = max_len - overlap
            for i in range(0, len(p), step):
                pieces.append(p[i:i + max_len])
            if len(pieces) >= 2 and len(pieces[-1]) < overlap:
                pieces[-2] += pieces[-1]
                pieces.pop()
            continue

        if not buf:# 情况 2：buf 还空着，直接放
            buf = p
        elif len(buf) + 2 + len(p) <= max_len:# 情况 3：放得下（+2 是 "\n\n"）
            buf = buf + "\n\n" + p
        else:# 情况 4：放不下，封箱 + 新片带重叠
            pieces.append(buf)
            tail = buf[-overlap:]
            if len(tail) + 2 + len(p) <= max_len:
                buf = tail + "\n\n" + p
            else:
                buf = p# 带了重叠就放不下，只能放弃重叠

    if buf:
        pieces.append(buf)
    return pieces


def split_section(record: dict, section: str, text: str) -> list[dict]:
    """
    一个小节->若干片
    pieces = ["1", "2"]
    enumerate(pieces, 1)产出(1, "1"), (2, "2"), 加上前面的for i, p, 则正好i对应1，p对应"1"
    赋值之后再进行make_chunk结果为最外层[]list
    """
    text = text.strip()
    if not text:
        return []
    if len(text) <= MAX_CHUNK_LEN:
        return  [make_chunk(record, section, text, 1)]
    pieces = split_by_paragraph(text, MAX_CHUNK_LEN, OVERLAP)
    return [make_chunk(record, section, p, i) for i,p in enumerate(pieces, 1)]


def build_chunks(records: list[dict]) -> list[dict]:
    """
    所有岗位->所有文本片
    一个record
    record = {
        'id': '30100000460627',
        'url': 'https://www.nowcoder.com/jobs/detail/460627',
        ......
        'content_parts': [
            {'section': '工作内容', 'text': '1、探索大模型与推荐算法结合的下一代推荐系统技术……'},
            {'section': '任职要求', 'text': '1、硕士及以上学历，计算机、人工智能……'}
        ],
        'content_len': 541,
        'processed_at': '2026-10-19'
    }
    """
    chunks = []
    for record in records:
        for part in record["content_parts"]:
            chunks.extend(split_section(record, part["section"], part["text"]))#将content_parts每段拆分进入split_section
    return chunks


def main():
    base = Path(__file__).resolve().parent.parent
    in_path = base / "data" / "jobs_clean.json"
    out_path = base / "data" / "chunks.json"

    """
    json.loads将json字符串变为python对象
    json.dumps将python对象变为json字符串
    """
    records = json.loads(in_path.read_text(encoding="utf-8"))
    # print(records)
    chunks = build_chunks(records)
    # print(json.dumps(chunks, ensure_ascii=False, indent=2))
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