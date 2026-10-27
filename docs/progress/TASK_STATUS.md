# Demo V0.1 研发看板

- Repo: 2230274247/Silver-economy（Private）
- Default dev branch: dev/v0.1
- Current task: T11B（地点、路线与天气；本地Mock/合同验证通过，待提交/远端/CI）
- 当前执行模式：用户最新指令恢复无人值守，取消人工逐任务确认门槛。
- Last remote-confirmed SHA: T11A修复 `67f9235be1c501cc00567b2ed4272ccbea91d345`
- Last verified CI: PASS（run 40442118042；api/security/mobile全部success；首轮失败保留）
- 最后核验时间：2026-10-27T11:08:52+08:00。
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
| T06 | DONE_PUSHED | 真实 H5/DeepSeek/刷新、46 后端/27 UI/全门禁 PASS | e8861218fa6a6244e657b1713befc98d6db6a667 | SHA 一致 | PASS | 预算/Provider/Mock 隔离 |
| T07 | DONE_PUSHED | 75 后端/33 UI/6专项、真实单次合并抽取/来源/刷新 PASS | ab54cf99cf432aca15d32477b1b61a1b1e879a97 | SHA 一致 | PASS | 候选/授权/时间精度/去重/Prompt溯源；T08召回未实现 |
| T08 | DONE_PUSHED | 100 后端、36 UI、真实新登录/新会话/引用/刷新与全门禁 PASS | d205546532360551ed35f8aad396eb60ae250e22 | SHA一致 | PASS（40346315913） | SQL基线、最多5条/12KB、授权状态过滤、搜索与来源；万级效果尚待T10E2 |
| T09 | DONE_PUSHED | 129后端、42UI、全门禁PASS；真实当前状态召回/刷新PASS（首次失败与规则修复保留） | 2ce30e51ede2d7f901eb233b5f17f1ef21908f33 | SHA一致 | PASS（40354267818） | 确认/纠错/审计/权限/失效/删除、明确身体状态；详见T09_MEMORY_CONTROL.md |
| T10 | DONE_PUSHED | 134后端/45UI/全门禁PASS，运营预览只读持久数据PASS，真实模型新增0 | d7572f9b6f0f2b1c71e5db507bec126ebdc22fb8 | SHA一致 | PASS（40394518915） | 来源关联的确定性时间线，时间精度/纠错删除即时同步；未生成推测摘要 |
| T10E1 | DONE_PUSHED | 164后端/完整门禁、100/1000/10000真实SQL计数/重复导入PASS，新增模型0 | 423ff6cf37cc12a82eb7027c939b487874d7a5d4 | SHA一致 | PASS（40400713021） | 2026-10-27 05:00:51 +08:00；Synthetic入库不替代召回验收 |
| T10E2 | DONE_PUSHED | 197后端、48UI及四档310题/SQL/资源报告PASS | 功能b3903deb40e87d6b43f50b2b814bc7ac53697cd0；修复e38b2c173c55c127db90dd975fc72587468d38d9 | SHA一致 | PASS（40417316422）；首轮失败保留 | 2026-10-27 07:05:37+08:00；修复仅测试同步，生产评分不变 |
| T11 | TODO（汇总） | - | - | - | - | CR-001，A–E 全部独立验收 |
| T11A | DONE_PUSHED | 230后端/57UI/全门禁/真实1次/四档310题PASS；输入反例先失败后通过，返修57UI PASS | 功能829bbc6530784175878f3eba0cd11df388c0251d；修复67f9235be1c501cc00567b2ed4272ccbea91d345 | SHA一致 | PASS（40442118042）；首轮40440860292失败保留 | 信息确认not_scheduled，调度仍待T11C；2026-10-27 11:04:33+08:00 |
| T11B | LOCAL_VERIFIED_MOCK | 263后端完整门禁/63UI；最终34地图/6专项三视口复测PASS；迁移/运营H5/用量审计PASS | 本次提交待核验 | 待推送 | 待运行 | 高德Provider/合同已实现；真实Key未配置，LIVE_NOT_VERIFIED，不能用Mock当真实验收 |
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
当前实际 DeepSeek 累计调用7次，3218输入/376输出tokens，保守估算合计USD0.00141660（非账单）。T11A只新增1次927/115tokens、1827ms、估算USD0.00041610，H5编辑/确认/刷新无额外调用；失败历史全部保留。高德/推送0。自动回归只用Mock；未经授权不购买或部署付费服务。
