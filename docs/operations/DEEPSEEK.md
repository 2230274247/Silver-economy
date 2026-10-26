# DeepSeek 运营配置与费用控制

配置入口为项目根目录本机 `.env.deepseek`（Git 忽略）；普通用户界面无 Key 输入。
管理员在本机编辑 `DEEPSEEK_API_KEY`，切换 `LLM_PROVIDER=deepseek` 后重启 API；`mock` 不请求官方服务。
不要将 Key 发到聊天、命令参数、截图或 Git。`.env.example` 仅保存空字段。

默认 `deepseek-flash`、官方 HTTPS 地址 `https://api.deepseek.com`，也支持官方 `/v1` 基址；任意外域会被拒绝。
模型可通过 `DEEPSEEK_MODEL` 配置；名称可用性/价格以官方当日文档和账户为准。

- 单次 `DEEPSEEK_MAX_OUTPUT_TOKENS=256`，显式关闭 thinking，不提供搜索/工具，最多最近 12 条且约 8000 UTF-8 字节上下文。
- 全部用户/API 进程共享香港日期的 MySQL 预算：每日最多 10 次、20000 预留 token。设任一 limit 为 0 可停用真实调用。
- 发送前按文本 UTF-8 字节、消息框架裕量和最大输出预留保守预算；预留累计可能高于真实用量，是有意控制额度，不是假定精确 tokenizer。
- 原文/待回复和预留先 commit，再执行一次外部调用，无 SDK 自动重试。相同请求编号复用既有消息/结果。
- 超时、异常响应、服务错误都保留预留并标 unknown，不自动重发；进程崩溃遗留 pending 同理。先核对服务商账单/记录再处理，V0.1 不自动清空这些额度。
- 缺 Key 或预算不足在外部调用前拒绝；只对这两类未调用情况提供人工点击重试，仍复用原文编号，不重复建消息。
- 用量表记录 provider/model/request_id/status/token/latency/estimated_cost，日志只记元数据，不记录 Key/原文/供应商错误正文。
- 默认模型估算使用峰时 cache-miss 上界：输入 $0.3/百万 token、输出 $1.2/百万 token（2026-10-26 核验），并非实际账单；未知模型价格留空。当前文档价格应在运营时再次核验。

官方依据：[定价](https://api-docs.deepseek.com/quick_start/pricing/)、[thinking 开关](https://api-docs.deepseek.com/guides/thinking_mode/)、[聊天 API](https://api-docs.deepseek.com/api/create-chat-completion)。

自动测试强制 Mock：pytest 禁止真实 HTTPTransport；Playwright 使用独占 5174→18000 Mock 服务，不复用运营 5173→8000。CI 不注入 Key。
首次真实验证最多一条合成短输入，失败不重试；通过真实 H5 登录→发送→刷新检查历史，记录实际 token/耗时/估算费用。缺 Key 记录 LIVE_NOT_VERIFIED，不能将 Mock 截图当真模型。
