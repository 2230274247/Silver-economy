# Prompt 注册表

| ID/版本 | 用途/输入 | 输出/Schema | 测试 | 变更 |
|---|---|---|---|---|
| chat/v1 | 对话；当前用户最近有限消息 | 中文文本 / ModelReply | test_models.py、test_chat.py | 2026-10-26 首版，禁止虚构与假提醒承诺 |
| chat-memory/v1 | 已授权用户的回复及候选抽取；有限历史、最新用户消息 | JSON reply+memories / MemoryEnvelope、MemoryCandidate | test_memory_extraction.py、memory.spec.ts | 2026-10-26 单次请求合并抽取；字段逐字原文校验，不生成日期细节 |
| chat-memory/v2 | 已授权回复/候选/检索引用；当前消息、有限历史与最多5条已筛选证据 | MemoryAnswerEnvelope / memory_refs只允许本次M编号 | test_memory_retrieval.py、retrieval.spec.ts | 2026-10-26 增加未知/冲突/合成标记约束与可追溯引用；v1保留。原提取回归及新增召回回归重跑，万级固定评估尚待T10E2，不宣称效果率 |
| chat-memory/v3 | 同v2，增加用户纠错权威与历史/当前状态区分、恢复对象追问 | MemoryAnswerEnvelope，authority/revision由ContextBuilder提供 | test_memory_updates.py及原抽取/召回回归、memory-controls.spec.ts | 2026-10-26 T09；v2原件保留，不预宣称质量提升；固定200题评估仍待T10E2 |
| task-intent/v1 | 主动任务组件；最新用户原文及当前会话最多3条本人待补全草案，含id/revision快照 | TaskCandidate；逐字来源、时间/地点原文，最多3条outings | test_task_drafts.py、task-drafts.spec.ts | 2026-10-27 T11A；不猜地址、到达/出发、车程、天气，不直接调度 |
| chat-task/v1 | chat-memory/v3 + task-intent/v1 + 授权标记；一次请求合并回复/当前事实/任务 | TaskEnvelope（reply、memories、memory_refs、outings）；任务路径memory_refs为空 | 单次Provider/预算拒绝/Unicode/混合事实与未来计划/历史回忆回归 | 2026-10-27 T11A；普通chat-memory/v3文件不变；服务端生成缺项追问，确认仅保存信息，不承诺通知 |

后续 memory-extract、memory-conflict、memory-answer、task-intent、安全约束在对应任务注册版本、输入/输出 Schema 和固定用例；未实现项不能标已完成。
保留旧版文件；修改记忆相关 Prompt 必须重跑固定记忆评估，记录结果比较，不凭模型自评宣布提升。

T09 提取流水线标识 `chat-memory/v3+state-rule/v1`：Prompt v3 加有限确定性身体状态规则；原始模型JSON保留，不把规则补全说成LLM已抽取。定价回执在隐私过滤前记录，拒绝展示不意味着没有产生费用。

## CHAT-02版本（2026-10-27T15:23:05+08:00）

- chat/v2：自然回答与公开模型信息；天气必须来自WEATHER_SEARCH_CONTEXT_JSON，禁止补造实时资料，保留chat/v1原件。
- chat-memory/v4：MemoryAnswerEnvelope不变，相关性选择由DeepSeek结合当前话题完成；允许一般知识与公开模型名，保留来源/授权/状态/纠错/未知/合成约束，保留v3原件。
- task-intent/v2与chat-task/v2：TaskEnvelope不变；正常reply不再被后端整条模板替换；会议等未来日程生成待确认卡，已授权的相关记忆可引用，记忆地址不能默认为本次确认地点。
- weather-search/v1：当前明确城市与今明后天日期→官方Search最多3个有限结果，状态/来源/查询时间进入上下文；失败不编造、一次搜索和一次生成均计预算。
- 验证：test_chat_assistant.py、原草案/抽取/更新/检索专项；310固定题100事实档无回归，原题集/旧版/历史失败保留。真实H5天气与模型名只用1次Search+1次生成，见CHAT-02专项记录。
