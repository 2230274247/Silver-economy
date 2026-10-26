# Prompt 注册表

| ID/版本 | 用途/输入 | 输出/Schema | 测试 | 变更 |
|---|---|---|---|---|
| chat/v1 | 对话；当前用户最近有限消息 | 中文文本 / ModelReply | test_models.py、test_chat.py | 2026-10-26 首版，禁止虚构与假提醒承诺 |

后续 memory-extract、memory-conflict、memory-answer、task-intent、安全约束在对应任务注册版本、输入/输出 Schema 和固定用例；未实现项不能标已完成。
保留旧版文件；修改记忆相关 Prompt 必须重跑固定记忆评估，记录结果比较，不凭模型自评宣布提升。
