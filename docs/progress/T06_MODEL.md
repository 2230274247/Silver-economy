# T06：真实 DeepSeek 聊天与额度门禁

- 日期：2026-10-26，Asia/Hong_Kong；真实短对话在 19:54 验证，20:00 后完成本地回归；本次 push/SHA/CI 待事后核验。
- 前项 UI-FIX-01：`2a3d4e1d533bd792c0ba733781608b031790c83a`，17:37:21 +08:00；push/SHA 一致，CI 40300983242 success。

## 功能与相关文件

- app/llm/providers.py：ModelProvider、明确标注的 MockProvider、官方 DeepSeek HTTP Provider；可配置模型/官方基址、单次25s读超时、5s连接超时、无自动重试、错误正文不返回。
- app/services/model_chat.py：有限历史上下文、共享香港日期预算、事务预留先于外部调用、用量/耗时/估算费元数据日志；调用结果与原消息绑定。
- app/api/v1/chat.py、schemas/chat.py：先 commit 原文+pending assistant，再调用；相同编号复用原记录与回复，内容冲突409。
- models/entities.py、t06_model 增量迁移：message.provider、usage 状态/预留/错误与唯一键、全局 model_budget；旧日志保留 legacy/0，无破坏性删除。
- config/.env.example、docs/operations/DEEPSEEK.md：服务端 SecretStr、本机被忽略 .env.deepseek。普通用户无 Key 配置，浏览器不接触 Key。
- mobile stores/chat、首页/AppHeader：明确 Mock/DeepSeek，生成中状态/头像；临时用户气泡标未确认保存，失败保留草稿；无语音/附件假能力。
- Playwright/Vite/CI：独立 5174→18000 强制 Mock，不复用 5173→8000；pytest 拒绝真实 HTTPTransport。CI 不提供真实 Key。
- prompts/chat-v1.txt、README：集中提示词与版本/用途/输入输出/测试/变更注册。
- 依赖：Windows 首测缺 IANA zoneinfo 数据，补 tzdata==2026.5（hash锁），其余版本不变；原文/迁移回归通过。
- 最终目标原件/差距审计/T10E1/E2 任务已同步，保留 CR-001 与已有历史。

## 成本与幂等行为

默认最多 256 输出 tokens，显式 disabled thinking，无搜索或工具。每次最多最近12条且约8000 UTF-8字节。
所有用户/API进程共享 MySQL 行锁日预算，默认10次/20000保守预留token。预留含输入字节/框架裕量/最大输出，不能当实际token统计。
缺 Key/预算不足不调用，原文仍保存，可在修正配置后点击原消息重试；不会重复建用户消息。
已发出的超时/服务错误/异常响应保留预留、记unknown；重复编号不再调用。崩溃遗留pending不自动重发，避免结果不明再次计费。
真实 Key 仅检查过非空，未显示/截图/上传。首次 smoke 有持久attempt保护，已有尝试时拒绝自动重复。

## 实际测试与证据

1. `python -m alembic upgrade head`：独立开发库增量升级成功；完整 pytest 在测试库 downgrade→upgrade→repeat→metadata check 通过。
2. `pytest -q --tb=short` 初轮发现 Windows tzdata 缺失及旧 scaffold 断言；修正后45 passed。新增脱敏日志测试后，最终 `python scripts/check.py` **46 passed**（21.48s），另5个扫描器测试，安全/YAML/Ruff/format/TS/lint/H5build/diff全部通过。
3. `npm run test:ui -- --max-failures=1`：最终 **27 passed，1.5m**，360/390/430覆盖真实MySQL+Mock聊天、生成中临时消息、刷新/重放/隔离、IME/多行/失败原编号、滚动/视口。增加临时气泡后暴露全页文本定位器与textarea计算节点重名，修为等待保存后草稿清空并限定气泡，保留相同ID和完整原文断言。
4. `SILVER_LIVE_SINGLE_REQUEST=1 node scripts/smoke-deepseek.cjs`（同时设置本项目 PLAYWRIGHT_BROWSERS_PATH）：一次真实H5→FastAPI→DeepSeek→MySQL→刷新通过。最初辅助脚本缺请求baseURL，在发送前失败，未调用模型；补baseURL后只发一次。
5. 真调用：deepseek-flash，输入97、输出13 tokens，1343ms，保守峰时cache-miss估算 **USD0.00004470**；预留1104token。账单以服务商为准，不把预留当实际使用。
6. 全部自动回归结束后数据库再查：真实 DeepSeek usage=1、global budget requests=1，证明回归未增加真实调用。
7. 证据：docs/demos/T06-deepseek-live-390.png（已视觉检查）、T06-live-metrics.json；本机详细 logs/t06-ui.log、logs/t06-check.log（忽略，不含原文/Key）；Mock三尺寸截图 T06-mock-*.png。

## 风险与下一任务

价格估算使用2026-10-26官方峰时未命中单价；不承诺缓存/优惠/后续定价。未知模型价格留空。
真实已接通的是文字聊天与持久化，不代表长期记忆/主动调度/Android已完成；未作批量真实API调用。
下一项T07按已明确表达事实抽取候选记忆并保存来源/时间/状态；T08召回、T09纠错删除、T10时间线及新增T10E1/E2固定评估依次推进。
