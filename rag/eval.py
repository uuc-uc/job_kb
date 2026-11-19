"""eval.py —— 检索评测

输入: data/eval_set.json
输出: 每题的名次 + 汇总 Hit@5 / MRR

两类题:
  - relevant 非空: 看正确答案排第几（k 取全量，否则只知道"没进前 5"）
  - relevant 为空: 不可答题，正确行为是候选集为空
"""
import json

from rag.embed import BASE
from rag.retrieve import build_where, get_collection, search

EVAL_PATH = BASE / "data" / "eval_set.json"
FULL_K = 100
HIT_K = 5


def count_candidates(**filters) -> int:
    """筛出多少条候选（不算距离）。"""
    return len(get_collection().get(where=build_where(**filters))["ids"])


def run_case(case: dict) -> dict:
    q = case["query"]
    filters = case.get("filters") or {}
    relevant = set(case.get("relevant") or [])

    pool = count_candidates(**filters)
    rows = search(q, k=FULL_K, **filters)

    if not relevant:
        return {
            "query": q, "type": case.get("type", ""), "pool": pool,
            "n_rel": 0, "found": 0, "best": None,
            "hit5": pool == 0, "rr": 0.0,
        }

    ranks = [i + 1 for i, r in enumerate(rows) if r["chunk_id"] in relevant]
    best = min(ranks) if ranks else None
    return {
        "query": q, "type": case.get("type", ""), "pool": pool,
        "n_rel": len(relevant), "found": len(ranks), "best": best,
        "hit5": best is not None and best <= HIT_K,
        "rr": 1.0 / best if best else 0.0,
    }


def cjk_len(s: str) -> int:
    return sum(2 if ord(ch) > 127 else 1 for ch in s)


def pad(s: str, width: int) -> str:
    return s + " " * max(0, width - cjk_len(s))


def main():
    cases = json.loads(EVAL_PATH.read_text(encoding="utf-8"))
    results = [run_case(c) for c in cases]

    w = max(cjk_len(r["query"]) for r in results) + 2
    print(pad("问题", w) + pad("类型", 8) + pad("候选", 6) + pad("相关", 6)
          + pad("命中", 6) + pad("最好", 6) + pad("Hit@5", 8) + "RR")
    print("-" * 74)
    for r in results:
        best = str(r["best"]) if r["best"] else "-"
        print(pad(r["query"], w) + pad(r["type"], 8) + pad(str(r["pool"]), 6)
              + pad(str(r["n_rel"]), 6) + pad(str(r["found"]), 6) + pad(best, 6)
              + pad("OK" if r["hit5"] else "MISS", 8) + f"{r['rr']:.3f}")

    scored = [r for r in results if r["n_rel"] > 0]
    hits = sum(1 for r in scored if r["hit5"])
    mrr = sum(r["rr"] for r in scored) / len(scored)
    print("-" * 74)
    print(f"可评 {len(scored)} 题 | Hit@5 = {hits}/{len(scored)} = {hits / len(scored):.0%} | MRR = {mrr:.3f}")

    empty = [r for r in results if r["n_rel"] == 0]
    if empty:
        ok = sum(1 for r in empty if r["hit5"])
        print(f"不可答 {len(empty)} 题 | 正确返回空 = {ok}/{len(empty)}")


if __name__ == "__main__":
    main()
