"""
pathfinder.py —— 数据探查工具箱

两类能力，别混用：

  发现型（discovery）—— 我什么都不知道，先看这里有什么
      show_tree(node)                    看结构形状
      profile_keys(items)                看字段全貌：覆盖率 / 类型 / 样例值
      profile_json_string(items, field)  展开 ext 这类 JSON 字符串字段

  验证型（verification）—— 我知道要找什么，去确认它在不在
      find_paths(...)                    找某个键名的所有位置
      pick_list(...)                     容错取出可用的列表
      describe_hits(...)                 把命中结果打印成人能读的样子

为什么要分开：验证型工具要求你先知道键名，拿它去发现未知字段是鸡生蛋。
之前只用验证型，所以 80 多个字段里你只看见手挑的那几个。
"""

import json
from collections import Counter


# ================================================================ 发现型

def show_tree(node, depth=0, max_depth=4, max_items=10, name="root"):
    """
    把嵌套结构打印成缩进目录树 —— 用来看「整体长什么形状」。

    参数必须配合着调：
        max_depth   最多往下钻几层
        max_items   每层 dict 最多显示几个键

    想看 jobList 里的岗位字段，至少 max_depth=4
    （root → app → 194 → jobList → [0]），且 max_items >= 10，否则键会被截断。
    """
    pad = "    " * depth

    if isinstance(node, dict):
        items = list(node.items())
        print(f"{pad}{name}: dict({len(items)} 键)")
        if depth < max_depth:
            for k, v in items[:max_items]:
                show_tree(v, depth + 1, max_depth, max_items, k)
            if len(items) > max_items:
                print(f"{pad}    ... 还有 {len(items) - max_items} 个键（调大 max_items 可看全）")

    elif isinstance(node, list):
        print(f"{pad}{name}: list({len(node)} 项)")
        if depth < max_depth and node:
            show_tree(node[0], depth + 1, max_depth, max_items, "[0]")

    else:
        print(f"{pad}{name} = {str(node)[:60]}")


def profile_keys(items, sample_len=40):
    """
    给一批 dict 做字段画像 —— 发现型工具的主力。

    items       list[dict]，例如 pick_list(state, "jobList", ...)
    sample_len  样例值截断长度

    读覆盖率：
        15/15   必有字段，可以直接取
        14/15   绝大多数有，必须 .get() + 默认值
        1/15    不是「偶有」，是另一个数据源 —— 这条会自动打标记
    """
    total = len(items)
    if not total:
        print("    (空列表，没有字段可画像)")
        return

    cnt, sample, kind = Counter(), {}, {}
    for item in items:
        if not isinstance(item, dict):
            continue
        for k, v in item.items():
            cnt[k] += 1
            if k not in sample:
                sample[k], kind[k] = v, type(v).__name__

    print(f"{'字段名':<28}{'覆盖率':<10}{'类型':<12}样例值")
    print("-" * 100)
    for k, c in cnt.most_common():
        flag = "   <- 覆盖率低，可能来自另一个数据源" if c * 2 < total else ""
        s = str(sample[k]).replace("\n", " ")[:sample_len]
        print(f"{k:<28}{c:>2}/{total}    {kind[k]:<12}{s}{flag}")


def profile_json_string(items, field, sample_len=30):
    """
    某个字段是「JSON 字符串」时，展开看它内部的键。

    典型场景：牛客的 ext —— 整条记录被塞进一个 JSON 字符串，
    顶层只有 ext 一个键，真正的 requirements / infos 藏在里面。
    """
    total = len(items)
    parsed = failed = skipped = 0
    inner = Counter()
    first = {}

    for item in items:
        raw = item.get(field) if isinstance(item, dict) else None
        if not isinstance(raw, str):
            skipped += 1
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            failed += 1
            continue
        if isinstance(data, dict):
            parsed += 1
            inner.update(data.keys())
            for k, v in data.items():
                first.setdefault(k, v)

    print(f"字段「{field}」: 共 {total} 条，{parsed} 条可解析，{failed} 条解析失败，{skipped} 条没有该字段")
    if not inner:
        print("    (内部没有可展示的键)")
        return

    print(f"  {'内部键':<26}{'出现次数':<10}样例值")
    print("  " + "-" * 88)
    for k, c in inner.most_common():
        s = str(first[k]).replace("\n", " ")[:sample_len]
        print(f"  {k:<26}{c:<10}{s}")



def find_paths(node, target_key, path="root", max_list_scan=1,
               _depth=0, _max_depth=10):
    """
    递归找出所有名为 target_key 的位置。

    参数：
        node           要搜索的对象（dict / list / 其他）
        target_key     要找的键名，比如 "jobList"
        path           当前路径字符串（递归时自动拼）
        max_list_scan  每个 list 只扫前几个元素（默认 1）
                       —— 同一批数据结构通常一致，扫 [0] 就够；
                          扫全部会让输出呈倍数爆炸
        _depth/_max_depth  内部使用，防止无限递归

    返回：
        [(路径字符串, 值), ...]
    """
    hits = []

    if _depth > _max_depth:
        return hits

    if isinstance(node, dict):
        for key, value in node.items():
            child_path = f"{path}.{key}"
            if key == target_key:
                hits.append((child_path, value))
            hits.extend(find_paths(value, target_key, child_path,
                                   max_list_scan, _depth + 1, _max_depth))

    elif isinstance(node, list):
        # 关键：只扫前 max_list_scan 个，否则 15 个元素各展开一遍会刷屏
        for i, item in enumerate(node[:max_list_scan]):
            hits.extend(find_paths(item, target_key, f"{path}[{i}]",
                                   max_list_scan, _depth + 1, _max_depth))

    return hits


def pick_list(state, target_key, required_keys=()):
    """
    从状态树里取出**可用的**列表 —— 生产代码用这个。

    三重验证，避免拿到"看起来像但其实不对"的东西：
        1. 类型是 list
        2. 非空
        3. 第一个元素是 dict，且包含 required_keys 里的所有键

    取不到时返回 []，**永不抛异常**。
    """
    for path, value in find_paths(state, target_key):
        if not isinstance(value, list) or not value:
            continue
        first = value[0]
        if not isinstance(first, dict):
            continue
        if required_keys and not all(k in first for k in required_keys):
            continue
        return value
    return []



if __name__ == "__main__":
    from loader import state

    jobs = pick_list(state, "jobList", required_keys=("jobName",))

    print("=== 1) 字段画像：这 15 条到底有哪些字段 ===")
    profile_keys(jobs)

    print("\n=== 2) 展开 ext：正文藏在哪 ===")
    profile_json_string(jobs, "ext")
