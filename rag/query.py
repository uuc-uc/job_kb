import json


SYSTEM_PROMPT = """你是招聘检索的查询解析器。把用户问题拆成两部分，只输出 JSON。

输出格式：
{"semantic": "用于语义检索的短语或 null", "filters": {"cities": [], "city_not": [], "job_types": [], "job_type_not": []}}

字段说明：
- semantic：问题里"要什么内容"的部分，去掉城市、类型这些约束词后剩下的内容。
  必须是用户问题里出现过的词，不要自己补全。
  如果去掉约束词后没有剩下有意义的内容，填 null。
- cities：用户明确要求的城市（字符串数组）。说一个填一个，"北京和杭州"填两个。
- city_not：用户明确排除的城市（字符串数组）
- job_types：用户明确要求的岗位类型（数组，取值只能是"实习"或"校招"）
- job_type_not：用户明确排除的类型（数组）

规则：
- 没提到的填 null 或 []
- 出现"不要 / 除了 / 不考虑 / 非"这类否定词时，填到 *_not 里
- 只输出 JSON，不要任何解释

示例：
问题：北京有哪些大模型岗位
输出：{"semantic": "大模型", "filters": {"cities": ["北京"], "city_not": [], "job_types": [], "job_type_not": []}}

问题：北京和杭州的大模型岗位
输出：{"semantic": "大模型", "filters": {"cities": ["北京", "杭州"], "city_not": [], "job_types": [], "job_type_not": []}}

问题：北京有哪些大模型实习或者校招岗位
输出：{"semantic": "大模型", "filters": {"cities": ["北京"], "city_not": [], "job_types": ["实习", "校招"], "job_type_not": []}}

问题：广州有什么岗位
输出：{"semantic": null, "filters": {"cities": ["广州"], "city_not": [], "job_types": [], "job_type_not": []}}

问题：有没有不要实习的岗位
输出：{"semantic": null, "filters": {"cities": [], "city_not": [], "job_types": [], "job_type_not": ["实习"]}}

问题：除了北京以外的校招岗
输出：{"semantic": "校招岗位", "filters": {"cities": [], "city_not": ["北京"], "job_types": ["校招"], "job_type_not": []}}
"""



def _parse_by_llm(query: str) -> dict:
    """延迟导入，避免query与generate循环依赖"""
    from rag.generate import MODEL, _get_client

    resp = _get_client().chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    return json.loads(resp.choices[0].message.content)


def build_extra_where(filters: dict) -> dict | None:
    conds = []

    cities = filters.get("cities") or []
    if len(cities) == 1:
        conds.append({"city": {"$contains": cities[0]}})
    elif len(cities) > 1:
        conds.append({"$or": [{"city": {"$contains": c}} for c in cities]})#{"city": {"$contains": c}}数组用$contains

    for c in filters.get("city_not") or []:
        conds.append({"city": {"$not_contains": c}})

    job_types = filters.get("job_types") or []
    if len(job_types) == 1:
        conds.append({"job_type": job_types[0]})
    elif len(job_types) > 1:
        conds.append({"$or": [{"job_type": t} for t in job_types]})#{"job_type": t}直接用值

    for t in filters.get("job_type_not") or []:
        conds.append({"job_type": {"$ne": t}})

    if not conds:
        return None
    if len(conds) == 1:
        return conds[0]
    return {"$and": conds}


def parse(query: str, city: str | None = None, job_type: str | None = None) -> dict:
    """问题 → {"semantic", "where", "raw"}。失败退化为纯语义检索。"""
    try:
        raw = _parse_by_llm(query)
        filters = raw.get("filters") or {}
        if city:
            filters["cities"], filters["city_not"] = [city], []
        if job_type:
            filters["job_types"], filters["job_type_not"] = [job_type], []
        return {
            "semantic": (raw.get("semantic") or query).strip(),
            "where": build_extra_where(filters),
            "raw": raw,
        }
    except Exception as exc:
        print(f"[warn] 查询解析失败，退化为纯语义检索：{type(exc).__name__}: {exc}")
        return {"semantic": query, "where": None, "raw": {}}