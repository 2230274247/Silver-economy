# Prompt 注册表

| ID/版本 | 用途/输入 | 输出/Schema | 测试 | 变更 |
|---|---|---|---|---|
| chat/v1 | 对话；当前用户最近有限消息 | 中文文本 / ModelReply | test_models.py、test_chat.py | 2026-10-26 首版，禁止虚构与假提醒承诺 |
| chat-memory/v1 | 已授权用户的回复及候选抽取；有限历史、最新用户消息 | JSON reply+memories / MemoryEnvelope、MemoryCandidate | test_memory_extraction.py、memory.spec.ts | 2026-10-26 单次请求合并抽取；字段逐字原文校验，不生成日期细节 |
| chat-memory/v2 | 已授权回复/候选/检索引用；当前消息、有限历史与最多5条已筛选证据 | MemoryAnswerEnvelope / memory_refs只允许本次M编号 | test_memory_retrieval.py、retrieval.spec.ts | 2026-10-26 增加未知/冲突/合成标记约束与可追溯引用；v1保留。原提取回归及新增召回回归重跑，万级固定评估尚待T10E2，不宣称效果率 |
| chat-memory/v3 | 同v2，增加用户纠错权威与历史/当前状态区分、恢复对象追问 | MemoryAnswerEnvelope，authority/revision由ContextBuilder提供 | test_memory_updates.py及原抽取/召回回归、memory-controls.spec.ts | 2026-10-26 T09；v2原件保留，不预宣称质量提升；固定200题评估仍待T10E2 |

后续 memory-extract、memory-conflict、memory-answer、task-intent、安全约束在对应任务注册版本、输入/输出 Schema 和固定用例；未实现项不能标已完成。
保留旧版文件；修改记忆相关 Prompt 必须重跑固定记忆评估，记录结果比较，不凭模型自评宣布提升。

T09 提取流水线标识 `chat-memory/v3+state-rule/v1`：Prompt v3 加有限确定性身体状态规则；原始模型JSON保留，不把规则补全说成LLM已抽取。定价回执在隐私过滤前记录，拒绝展示不意味着没有产生费用。
