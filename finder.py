import json
from loader import state
import re


def clean_html_text(raw: str) -> str:
    # 第 1 步：把"块级标签"换成换行符 —— 这一步是灵魂
    text = re.sub(r"<br\s*/?>|</p>|</div>|</h[1-6]>", "\n", raw, flags=re.I)

    # 第 2 步：剩下的标签（<p>、<span>、class 属性…）统统删掉
    text = re.sub(r"<[^>]+>", "", text)

    # 第 3 步：压掉连续空行，最多留一个空行
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


job_list = state["app"]["194"]["jobList"]

for job in job_list:
    if job.get("ext"):
        jobName = job["jobName"]
        ext_str = job.get("ext")
        try:
            ext = json.loads(ext_str)
        except:
            print("jsonloads_error")

        print(jobName)
        print(ext.get("requirements"))
        print("--------infos--------")
        print(ext.get("infos"))
        print("=====================================================")
    else:
        jobName = job["data"]["jobTitle"]
        ext_str = job["data"]["description"]

        print(jobName)
        print(clean_html_text(ext_str))
        print("!!!!!=====================================================")

print(list(ext.keys()))