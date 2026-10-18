"""
transform.py —— 把原始 state 变成干净的岗位数据

输入：loader.state（HTML 里解析出来的原始嵌套结构）
输出：data/jobs_clean.json（结构化、可读、可喂给向量库）

设计要点：
  1. 用 pick_list 容错取数 —— 不写死 "app.194.jobList" 这种路径
  2. 兼容两种数据格式（牛客自有 / 第三方 moka），各自走一条支路
  3. 只保留有明确用途的字段，分四类：溯源 / 过滤展示 / 正文 / 质控
  4. 正文存成 content_parts（带小节结构），不压平成一整块字符串
"""

import json
import re
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup

from loader import state
from pathfinder import pick_list


# ---------------------------------------------------------------- 清洗工具

def clean_html_text(raw: str) -> str:
    """HTML 片段 -> 保留换行结构的纯文本"""
    if not raw:
        return ""
    # 提取 html 除标签外的纯文本，按换行划分
    text = BeautifulSoup(raw, "lxml").get_text(separator="\n")
    # r"\n{3,}" 代表三个以上的换行；sub 是 substitute 替换
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_job_name(raw: str) -> tuple:
    """
    '实习 | AI大模型应用实习生' -> ('AI大模型应用实习生', '实习')
    '大模型算法工程师'         -> ('大模型算法工程师', '')

    分离原因：岗位名前缀（实习/校招）属于元数据，混在名字里会污染检索。
    """
    if not raw:
        return "", ""
    if "|" in raw:
        # partition：按遇到的第一个 "|" 拆成三元组
        prefix, _, rest = raw.partition("|")
        return rest.strip(), prefix.strip()
    return raw.strip(), ""


# ---------------------------------------------------------------- 提正文

def extract_body(job: dict) -> tuple:
    """
    取出一条岗位正文，返回 (parts, fmt)

    parts 形如：
        [{"section": "工作内容", "text": "..."},
         {"section": "任职要求", "text": "..."}]

    两条支路：
      有 ext   -> 牛客自有格式，ext 是 JSON 字符串，二次解析取 infos + requirements
      无 ext   -> 第三方（moka）格式，正文在 data.description 里，是 HTML

    注意：这里只负责「识别格式」，决定这条要不要是 build_record 的事。
    """
    ext_str = job.get("ext")

    # ---- 支路 1：牛客自有格式 ----
    if isinstance(ext_str, str):
        try:
            ext = json.loads(ext_str)
        except json.JSONDecodeError:
            ext = {}

        infos = (ext.get("infos") or "").strip()
        reqs = (ext.get("requirements") or "").strip()

        parts = []
        if infos:
            parts.append({"section": "工作内容", "text": infos})
        if reqs:
            parts.append({"section": "任职要求", "text": reqs})
        return parts, "nowcoder"

    # ---- 支路 2：第三方 moka 格式 ----
    data = job.get("data") or {}
    desc = data.get("description") or ""
    text = clean_html_text(desc)
    parts = [{"section": "岗位描述", "text": text}] if text else []
    return parts, "moka"


# ---------------------------------------------------------------- 组装记录

def build_record(job: dict) -> dict | None:
    """
    一条原始岗位 dict -> 一条干净记录。
    返回 None 表示这条要丢弃（目前只保留牛客自有格式）。
    """
    entity_id = str(job.get("entityId") or "")
    data = job.get("data") or {}

    raw_name = job.get("jobName") or data.get("jobTitle") or ""
    job_name, job_type = split_job_name(raw_name)

    content_parts, fmt = extract_body(job)

    # 非牛客格式：显式丢弃（丢了几条由 main 统计并打印）
    if fmt != "nowcoder":
        return None

    job_id = job.get("id")
    url = f"https://www.nowcoder.com/jobs/detail/{job_id}" if job_id else ""

    return {
        # ---------- 溯源：回答时告诉用户"这话出自哪" ----------
        "id": entity_id,
        "url": url,
        "source": "nowcoder",

        # ---------- 过滤与展示 ----------
        "job_name": job_name,
        "job_type": job_type,
        "company": job.get("companyNameText") or data.get("companyName") or "",
        "city": job.get("jobCity") or "",
        "salary_text": job.get("salaryText") or data.get("salary") or "",
        "skills": [s.strip() for s in (job.get("jobKeys") or "").split(",") if s.strip()],
        "industry": job.get("companyIndustryText") or data.get("industry") or "",
        "graduation_year": job.get("graduationYear") or "",

        # 学历：原始编码含义未知（正文反推无规律），先原样保留；
        # 问答时以正文里的学历描述为准
        "education_code": job.get("eduLevel"),

        # ---------- 正文：会被切片、向量化、喂给大模型 ----------
        "content_parts": content_parts,
        "content_len": sum(len(p["text"]) for p in content_parts),

        # ---------- 质控 ----------
        "processed_at": date.today().isoformat(),
    }


# ---------------------------------------------------------------- 预览

def preview(records, n=1, chars=600):
    """
    把「即将送去切片 / 嵌入的文本」原样打印出来 —— 肉眼验数据质量。

    n      预览几条
    chars  每节最多显示多少字符
    """
    for r in records[:n]:
        print("=" * 72)
        print(f"岗位: {r['job_name']}")
        print(f"公司: {r['company']}    城市: {r['city']}    薪资: {r['salary_text']}")
        print(f"技能: {r['skills']}")
        print(f"正文: {r['content_len']} 字符 / {len(r['content_parts'])} 节")
        print("-" * 72)

        for p in r["content_parts"]:
            text = p["text"]
            print(f"【{p['section']}】({len(text)} 字符)")
            print(text[:chars])
            if len(text) > chars:
                print(f"... （还有 {len(text) - chars} 字符未显示）")
            print()

        joined = "\n".join(p["text"] for p in r["content_parts"])
        warns = []
        if "<" in joined or ">" in joined:
            warns.append("疑似 HTML 标签残留")
        if "&nbsp;" in joined or "&#" in joined:
            warns.append("疑似 HTML 实体残留")
        if "  " in joined.replace("\n", ""):
            warns.append("存在连续空格")
        if warns:
            print("质量提示:", " / ".join(warns))
        print()


# ---------------------------------------------------------------- 主流程

def main(preview_n: int = 1) -> None:
    # 1) 取数（容错：路径变了也能活）
    #    故意只要求 jobName，不要求 ext —— 否则 moka 那条会被提前滤掉，丢了几条就看不见了
    jobs = pick_list(state, "jobList", required_keys=("jobName",))
    if not jobs:
        print("[中止] 没取到岗位数据，流程结束")
        return

    # 2) 逐条转换：None 表示这条被丢弃
    records = []
    dropped = []
    for job in jobs:
        rec = build_record(job)
        if rec is None:
            dropped.append(str(job.get("entityId") or "?"))
        else:
            records.append(rec)

    # 3) 落盘
    out_path = Path(__file__).parent / "data" / "jobs_clean.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 4) 质检报告
    total = len(records)
    empty = [r for r in records if r["content_len"] == 0]
    no_req = [r for r in records if all(p["section"] != "任职要求" for p in r["content_parts"])]

    section_count = {}
    for r in records:
        for p in r["content_parts"]:
            section_count[p["section"]] = section_count.get(p["section"], 0) + 1

    print(f"[完成] {total} 条 -> {out_path}")
    print(f"  正文总长        : {sum(r['content_len'] for r in records):,} 字符")
    print(f"  正文为空的      : {len(empty)} 条" + (f"  <- {[r['id'] for r in empty]}" if empty else ""))
    print(f"  缺「任职要求」  : {len(no_req)} 条" + (f"  <- {[r['id'] for r in no_req]}" if no_req else ""))
    print(f"  小节分布        : {section_count}")
    print(f"  带技能标签的    : {len([r for r in records if r['skills']])}/{total} 条")
    print(f"  城市分布        : {sorted({r['city'] for r in records if r['city']})}")
    print(f"  丢弃(非牛客格式): {len(dropped)} 条" + (f"  <- {dropped}" if dropped else ""))

    # 5) 样本预览：直接看即将送去嵌入的文本
    if preview_n:
        preview(records, n=preview_n)


if __name__ == "__main__":
    main()
