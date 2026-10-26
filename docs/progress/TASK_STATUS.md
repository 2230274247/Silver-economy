# Demo V0.1 研发看板

- Repo: 2230274247/Silver-economy（Private）
- Default dev branch: dev/v0.1
- Current task: T06（真实首次联调通过，完成回归后 push/SHA/CI）
- 当前执行模式：用户最新指令恢复无人值守，取消人工逐任务确认门槛。
- Last remote-confirmed SHA: UI-FIX-01 `2a3d4e1d533bd792c0ba733781608b031790c83a`
- Last verified CI: PASS（run 40300983242，api/security/mobile 全部通过）
- 最后核验时间：2026-10-26 19:59:43 +08:00。
- 时间口径：Asia/Hong_Kong（UTC+08:00），具体提交时间见 COMMIT_LOG.md。

| ID | 状态 | 本地测试 | GitHub commit SHA | 推送验证 | CI | 备注 |
|---|---|---|---|---|---|---|
| T00 | DONE_PUSHED | 环境/权限/fetch/分支检查通过 | 291777e16c7848c5d50ba23a2e9ebf9f45fec720 | SHA 一致 | N/A | main 初始化历史保留 |
| T01 | DONE_PUSHED | 本地全部核心检查通过 | 9b512ac283eea4f8fc2e99ae2beb4d4bf2145691 | SHA 一致 | PASS | 依赖审计 KNOWN_ISSUES |
| T02 | DONE_PUSHED | 12 项浏览器测试、本地全门禁通过 | 功能 1a6920794eda17b9065353d3bb07734c7a7245db；修复 89c82eb4066a5416f75c1645c7b0a279e6625130 | SHA 一致 | PASS | 首轮失败已独立修复，历史保留 |
| CR-001 | DONE_PUSHED | 原件/暂存哈希、覆盖/安全校验、5 扫描测试和 3 API 测试通过 | cde000795374b63c9d6a93cb89ca2077b2e3d517 | SHA 一致 | PASS | 正式登记，不表示功能交付 |
| T03 | DONE_PUSHED | 12 后端/MySQL 测试 + 全项目门禁 PASS，health/ready 实跑 200 | 3aa87eee69790e7fc1cbce46fda8eb8f7315cdb3 | SHA 一致 | PASS | 2026-10-26 16:32:46 +08:00；仅本项目双库 |
| T04 | DONE_PUSHED | 20 后端测试、15 真实 UI 测试及全门禁 PASS | e967f4535b7222bf4d1c7051dd42c22eedaf8bcd | SHA 一致 | PASS | 2026-10-26 16:49:25 +08:00；见 T04_AUTH.md |
| T05 | DONE_PUSHED | 28 后端测试、18 实际 UI 测试、完整门禁 PASS | 2252da21c02510ced73d7061badb9418a6187ca3 | SHA 一致 | PASS | 见 T05_CHAT.md；模型尚未接入 |
| UI-FIX-01 | DONE_PUSHED | 27 UI、28 后端及全门禁 PASS | 2a3d4e1d533bd792c0ba733781608b031790c83a | SHA 一致 | PASS | T05 之后独立修复引导/IME/多行/交互，再启用 T06；不改写 T02 |
| T06 | TESTING | 真实 H5/DeepSeek 一次/刷新通过，回归见 T06_MODEL.md | 本次提交后补记 | 待执行 | 待运行 | 预算/Provider/Mock 隔离 |
| T07 | TODO | - | - | - | - | 记忆抽取与来源 |
| T08 | TODO | - | - | - | - | 跨会话检索 |
| T09 | TODO | - | - | - | - | 记忆纠错/删除 |
| T10 | TODO | - | - | - | - | 回忆时间线 |
| T10E1 | TODO | - | - | - | - | Synthetic 参数生成器，100/1000/10000 独立测试库 |
| T10E2 | TODO | - | - | - | - | 固定至少200题、召回/回答/冲突/隔离/删除/并发/资源，HTML+JSON报告 |
| T11 | TODO（汇总） | - | - | - | - | CR-001，A–E 全部独立验收 |
| T11A | TODO | - | - | - | - | 意图识别/追问/可编辑确认卡 |
| T11B | TODO | - | - | - | - | 高德地点、路线/天气，真实+Mock |
| T11C | TODO | - | - | - | - | 确定性时间计算、MySQL outbox、持久 Worker |
| T11D | TODO | - | - | - | - | Android 测试包、真机后台通知，外部配置准入 |
| T11E | TODO | - | - | - | - | 行程详情、导航、修改/取消/完成反馈 |
| T12 | TODO | - | - | - | - | 设置/隐私/导出 |
| T13 | TODO | - | - | - | - | 原 AC + CR-AC01–13、时间/隔离/重启/真机 |
| T14 | TODO | - | - | - | - | 真实闭环证据、Android 验收、限制、交付与 PR |

## CR-001 当前影响、依赖与外部准入

T00–T10 保持原任务顺序；最终目标新增 T10E1→E2；再 T11A→B→C→D→E→T12→T13→T14。
主业务仍 uni-app/FastAPI/MySQL；高德和 DeepSeek 在后端，持久 Worker + 服务端推送桥接。
数据库/API/计划/验收详见 docs/changes/CR-001-impact.md 与 ADR-003，不凭文档称建表或功能已完成。
DeepSeek 本机 Key 已配置且一次真实 H5 验证通过；高德/推送仍待配置，Android 真机未验证。
这些是后续 live/真机门禁，不阻塞当前文档及 Mock 开发；需要时由用户本机配置，不索取聊天中的密钥。
当前实际 DeepSeek 调用 1 次：97 input/13 output tokens，保守估算 USD 0.00004470（非账单）；高德/推送 0。自动回归只用 Mock；未经授权不购买或部署付费服务。
