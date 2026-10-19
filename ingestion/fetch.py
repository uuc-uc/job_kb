import time
import requests
from pathlib import Path


url = "https://www.nowcoder.com/search/job?query=大模型"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
}

resp = requests.get(url, headers=HEADERS, timeout=20)

RAW_DIR = Path(r"E:\RAG\job_kb\data\raw")#"r"使字符串里的"\"不被当成转义符
RAW_DIR.mkdir(parents=True, exist_ok=True)#exist_ok=True 表示目录已存在也不报错

out_path = RAW_DIR / "nowcoder_p1.html"
if "__INITIAL_STATE__" not in resp.text:
    print("响应是空壳页，不写盘")
else:
    out_path.write_text(resp.text, encoding="utf-8")
    print(f"[已存]{out_path} ({out_path.stat().st_size} 字节)")

    pos = resp.text.find("__INITIAL_STATE__")
    print(f"[位置] 第 {pos} 个字符")
    print(f"[预览] {resp.text[pos:pos + 200]}")

time.sleep(1.5)

