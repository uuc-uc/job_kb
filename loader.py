import json

html = open(r"E:\RAG\job_kb\data\raw\nowcoder_p1.html", encoding="utf-8").read()

start = html.find("__INITIAL_STATE__")      # 先找到变量名在哪
start = html.find("{", start)                # 从那儿往后找第一个 "{"，那才是 JSON 的起点

state, end = json.JSONDecoder().raw_decode(html, start)


def show_tree(node, depth=0, max_depth=3, max_items=8, name="root"):
    """把嵌套结构打印成缩进目录树；max_depth/max_items 防止刷屏"""
    pad = "    " * depth

    if isinstance(node, dict):
        keys = list(node.items())
        print(f"{pad}{name}: dict({len(keys)} 键)")
        if depth < max_depth:
            for k, v in keys[:max_items]:
                show_tree(v, depth + 1, max_depth, max_items, k)
            if len(keys) > max_items:
                print(f"{pad}    ... 还有 {len(keys) - max_items} 个键")

    elif isinstance(node, list):
        print(f"{pad}{name}: list({len(node)} 项)")
        if depth < max_depth and node:
            show_tree(node[0], depth + 1, max_depth, max_items, "[0]")

    else:
        print(f"{pad}{name} = {str(node)[:60]}")


# records = []
# seen = set()
#
# def walk(node):
#     if isinstance(node, dict):
#         eid = node.get("entityId")
#         if eid and eid not in seen:
#             seen.add(eid)
#             records.append(node)
#         for value in node.values():
#             walk(value)
#     elif isinstance(node, list):
#         for item in node:
#             walk(item)



if __name__ == "__main__":
    # print("解析成功 ✓")
    # print("顶层键:", list(state.keys()))
    # print("消耗字符数:", end - start)
    #
    # print("岗位数:", len(records))
    # print(records)
    # walk(state)

    show_tree(state)

    pos = html.find("\"ext\"")
    print(pos)
    print(html[pos - 200: pos + 2000])

