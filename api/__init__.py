"""api —— HTTP 接口层

只做三件事：收请求 → 转成 Python 参数 → 调 rag.generate.answer() → 转成 JSON。
不写业务逻辑。这里出现业务判断，就说明分层写歪了。

与另外两个包并列：
  ingestion/  网页 → 干净的岗位数据
  rag/        岗位数据 → 能回答问题的知识
  api/        知识 → 能被调用的服务
"""
