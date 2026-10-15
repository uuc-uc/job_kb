"""
pathfinder.py —— 通用路径探针

解决两个不同的问题：
  1. find_paths()  开发期：在嵌套结构里找出某个键名的**所有位置**
  2. pick_list()   生产期：按键名取出可用的列表，**不依赖写死的路径**

核心思想：锚在「键名」（业务概念）上，不要锚在「路径」（实现细节）上。
    state["app"]["194"]["jobList"]   ← 194 是页面模块编号，改版就会变
    find_paths(state, "jobList")     ← jobList 是业务概念，相对稳定
"""


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


def describe_hits(hits, limit=10):
    """把 find_paths 的结果打印成人能读的样子"""
    if not hits:
        print("    (没有命中)")
        return
    for path, value in hits[:limit]:
        if isinstance(value, list):
            info = f"list，{len(value)} 项"
        elif isinstance(value, dict):
            info = f"dict，{len(value)} 个键"
        elif isinstance(value, str):
            info = f"str，{len(value)} 字符"
        else:
            info = f"{type(value).__name__} = {str(value)[:30]}"
        print(f"    {path}")
        print(f"        └─ {info}")
    if len(hits) > limit:
        print(f"    ... 还有 {len(hits) - limit} 处")


if __name__ == "__main__":
    from loader import state

    for target in ["jobList", "jobName", "ext", "salaryText"]:
        print(f"=== 搜索键名「{target}」 ===")
        describe_hits(find_paths(state, target))
        print()

    print("=== pick_list 容错取值 ===")
    jobs = pick_list(state, "jobList", required_keys=("jobName", "ext"))
    print(f"    pick_list(state, 'jobList', required_keys=('jobName','ext')) -> {len(jobs)} 条")

    bad = pick_list(state, "thisKeyDoesNotExist")
    print(f"    pick_list(state, 'thisKeyDoesNotExist')                     -> {len(bad)} 条（不报错）")

    wrong_type = pick_list(state, "query", required_keys=("jobName",))
    print(f"    pick_list(state, 'query', required_keys=('jobName',))       -> {len(wrong_type)} 条（类型不符，被过滤）")
