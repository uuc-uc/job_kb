"""
loader.py —— 从 HTML 里挖出内嵌的初始状态

输入：data/raw/*.html（网页原文）
输出：state（一棵巨大的嵌套 dict）

职责单一：只做「HTML → Python 对象」这一步边界转换。
站点改版、换数据源，只改这个文件，下游 transform.py 不受影响。
"""

import json
from pathlib import Path

# data/ 在项目根目录（本文件在 ingestion/ 里，所以往上两层）
RAW_PATH = Path(__file__).resolve().parent.parent / "data" / "raw" / "nowcoder_p1.html"

html = RAW_PATH.read_text(encoding="utf-8")

start = html.find("__INITIAL_STATE__")      # 先找到变量名在哪
start = html.find("{", start)                # 从那儿往后找第一个 "{"，那才是 JSON 的起点

state, _ = json.JSONDecoder().raw_decode(html, start)
