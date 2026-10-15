"""
transform.py —— 把原始 state 变成干净的岗位数据

输入：loader.state（HTML 里解析出来的原始嵌套结构）
输出：data/jobs_clean.json（结构化、可读、可喂给向量库）

设计要点：
  1. 用 pick_list 容错取数 —— 不写死 "app.194.jobList" 这种路径
  2. 兼容两种数据格式（牛客自有 / 第三方 moka），各自走一条支路
  3. 只保留有明确用途的字段，分三类：溯源 / 过滤展示 / 正文
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
    text = BeautifulSoup(raw, "lxml").get_text(separator="\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_job_name(raw: str) -> tuple:
    """
    '实习 | AI大模型应用实习生'  ->  ('AI大模型应用实习生', '实习')
    '大模型算法工程师'          ->  ('大模型算法工程师', '')

    为什么要剥：前缀是招聘类型（实习/校招），属于元数据，
    混在岗位名里会污染检索。
    """
    if not raw:
        return "", ""
    if "|" in raw:
        prefix, _, rest = raw.partition("|")
        return rest.strip(), prefix.strip()
    return raw.strip(), ""


def extract_body(job: dict) -> tuple:
    """
    取出一条岗位的正文，返回 (content, format, has_ext)

    两条支路：
      有 ext   -> 牛客自有格式，ext 是 JSON 字符串，二次解析取 infos + requirements
      无 ext   -> 第三方（moka）格式，正文在 data.description 里，是 HTML
    """
    ext_str = job.get("ext")

    if isinstance(ext_str, str):
        try:
            ext = json.loads(ext_str)
        except json.JSONDecodeError:
            ext = {}
        infos = (ext.get("infos") or "").strip()
        reqs = (ext.get("requirements") or "").strip()

        parts = []
        if infos:
            parts.append("【工作内容】\n" + infos)
        if reqs:
            parts.append("【任职要求】\n" + reqs)
        return "\n\n".join(parts), "nowcoder", True

    data = job.get("data") or {}
    desc = data.get("description") or ""
    return clean_html_text(desc), "moka", False


# ---------------------------------------------------------------- 组装记录

def build_record(job: dict) -> dict:
    """一条原始岗位 dict -> 一条干净记录"""

    entity_id = str(job.get("entityId") or "")
    data = job.get("data") or {}

    raw_name = job.get("jobName") or data.get("jobTitle") or ""
    job_name, job_type = split_job_name(raw_name)

    content, fmt, has_ext = extract_body(job)

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

        # 学历：原始编码含义未知（正文反推无规律，前端映射表不在数据里）
        # 先原样保留，将来查到映射表再补；问答时以 content 里的学历描述为准
        "education_code": job.get("eduLevel"),

        # ---------- 正文：会被切片、向量化、喂给大模型 ----------
        "content": content,
        "content_len": len(content),

        # ---------- 质控 ----------
        "format": fmt,
        "has_ext": has_ext,
        "processed_at": date.today().isoformat(),
    }


# ---------------------------------------------------------------- 主流程

def main() -> None:
    # 1) 取数（容错：路径变了也能活）
    jobs = pick_list(state, "jobList", required_keys=("jobName",))
    if not jobs:
        print("[中止] 没取到岗位数据，流程结束")
        return

    # 2) 逐条转换
    records = [build_record(j) for j in jobs]

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
    moka = [r for r in records if r["format"] == "moka"]
    with_skills = [r for r in records if r["skills"]]

    print(f"[完成] {total} 条 -> {out_path}")
    print(f"  正文总长        : {sum(r['content_len'] for r in records):,} 字符")
    print(f"  正文为空的      : {len(empty)} 条" + (f"  <- {[r['id'] for r in empty]}" if empty else ""))
    print(f"  第三方(moka)格式: {len(moka)} 条")
    print(f"  带技能标签的    : {len(with_skills)}/{total} 条")
    print(f"  城市分布        : {sorted({r['city'] for r in records if r['city']})}")


if __name__ == "__main__":
    main()
