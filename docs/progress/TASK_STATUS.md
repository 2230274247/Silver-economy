# Demo V0.1 研发看板

- Repo: 2230274247/Silver-economy（Private）
- Default dev branch: dev/v0.1
- Current task: UI-P0-01 第一阶段无障碍修复；T14开放项保留
- 当前执行模式：用户最新指令恢复无人值守，取消人工逐任务确认门槛。
- Last remote-confirmed SHA: UI-DOC-01 `68d63a3139c8f26b93d4ed5f0b0673b9f2523642`
- Last verified CI: PASS（run 40625222710/40625228373；api/security/mobile全部success）
- 最后核验日期：2026-10-28（UI-P0-01 基线核验，Asia/Hong_Kong）。
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
| T11 | ENGINEERING_DONE_EXTERNAL_BLOCKED（汇总） | A–E 工程测试通过 | A–E 各自 SHA | 各功能 SHA 一致 | PASS | CR-001 工程闭环完成；T11D Android真机仍为外部阻塞 |
| T11A | DONE_PUSHED | 230后端/57UI/全门禁/真实1次/四档310题PASS；输入反例先失败后通过，返修57UI PASS | 功能829bbc6530784175878f3eba0cd11df388c0251d；修复67f9235be1c501cc00567b2ed4272ccbea91d345 | SHA一致 | PASS（40442118042）；首轮40440860292失败保留 | 信息确认not_scheduled，调度仍待T11C；2026-10-27 11:04:33+08:00 |
| T11B | IMPLEMENTED_PUSHED（LIVE_PENDING） | 本地263完整门禁+最终34地图/6UI专项；完整63UI；CI264后端/63UI PASS | c44766fa863f968463099976faab6f4c35e8cc01 | SHA一致 | PASS（40445595994） | 2026-10-27 11:41:42+08:00；Mock/合同/实现通过，真实Key未配置，LIVE_NOT_VERIFIED，不能当真实验收 |
| T11C | DONE_PUSHED | 271后端/69UI/全门禁/独立Worker实进程PASS | `742283e0a6358aa89a193177270eb5576e62b24b` | SHA一致 | PASS（40451532189） | 确定性时间、独立确认、MySQL outbox、租约/重启/取消/隔离；新增模型0、高德0、真实推送0；Mock不能替代真机 |
| T11D | IMPLEMENTED_BLOCKED_PROVIDER_CONFIGURATION | 275后端/全门禁/10迁移+设备专项PASS | `b82819707813e706ffd6a3ef8fb75be4a9075710` | SHA一致 | PASS（40452632424） | 加密设备登记/撤回/改绑、Worker归属复核、HTTPS桥接与最小通知；0真实推送；缺SDK/HBuilderX/AppID/厂商配置/真机，CR-AC10未通过 |
| T11E | DONE_PUSHED | 276后端/72UI/全门禁/迁移PASS | `135aa2837f914b00bf0acd7ff5abc66d11c09788` | SHA一致 | PASS（40454654272） | 行程详情、目的地搜索入口、修改/出发/完成、反馈与通知回看；真实高德/推送仍为0 |
| T12 | DONE_PUSHED | 278后端、6专项后端、78完整UI、6专项UI及全门禁PASS | `56ce42b336c49400e3845b2ae75c3cf232a16f99` | SHA一致 | PASS（40457533355） | 设置/隐私/本人导出与设备撤回；无迁移；详见T12_PRIVACY_EXPORT.md |
| T13 | ENGINEERING_PUSHED_ACCEPTANCE_GAPS | 294后端/78完整UI/12调度UI/全门禁PASS | `048ace16e3521a0afce298a75523b9f8a3ff873a` | SHA一致 | PASS（40462088539） | 变化刷新/地点替换/时区/可靠性修复；原AC条文及真实高德/Android未验收，见QA_REPORT |
| T14 | DEMO_READY_FINAL_ACCEPTANCE_PENDING | 本机启动/登录/只读检查、脚本语法PASS；不重复全套 | `71c345244c33d11edfb341298c502f37631cdb64` | SHA一致 | PASS（40462849750） | 按用户最新指令先会议演示；P01–P10留续办，备份恢复/首次克隆/真机等未验收 |

## CR-001 当前影响、依赖与外部准入

T00–T10 保持原任务顺序；最终目标新增 T10E1→E2；再 T11A→B→C→D→E→T12→T13→T14。
主业务仍 uni-app/FastAPI/MySQL；高德和 DeepSeek 在后端，持久 Worker + 服务端推送桥接。
数据库/API/计划/验收详见 docs/changes/CR-001-impact.md 与 ADR-003，不凭文档称建表或功能已完成。
DeepSeek 本机 Key 已配置且一次真实 H5 验证通过；高德/推送仍待配置，Android 真机未验证。
这些是后续 live/真机门禁，不阻塞当前文档及 Mock 开发；需要时由用户本机配置，不索取聊天中的密钥。
当前实际 DeepSeek 累计调用7次，3218输入/376输出tokens，保守估算合计USD0.00141660（非账单）。T11A只新增1次927/115tokens、1827ms、估算USD0.00041610，H5编辑/确认/刷新无额外调用；失败历史全部保留。高德/推送0。自动回归只用Mock；未经授权不购买或部署付费服务。

## 2026-10-27 会议演示交付决定

用户明确先用现有功能进行初步展示、未验收内容登记后续继续。运行页面http://127.0.0.1:5173/#/，真实DeepSeek配置有效；地图/通知Mock。T14不标正式完成；开放项与具体续办证据见V01_PENDING_ACCEPTANCE.md，演示步骤见operations/MEETING_DEMO.md。停止非必要重复回归，不删除失败测试或伪造通过。

T14交付提交已远端核验：71c345244c33d11edfb341298c502f37631cdb64；PR #1为Draft、未合并。CI40462849750最后观察IN_PROGRESS（2026-10-27T14:47:01+08:00），最终以GitHub Checks终态为准；演示已运行不等于最终验收完成。

2026-10-27T14:55:21+08:00：T14现有交付/同步CI已全部success；P05独立测试库备份恢复与任务幂等实测通过，开发库覆盖恢复仍未验收。新增脚本/说明/测试结果单独提交，不重复全套回归，不影响当前会议页面。

## CHAT-02本地验证（2026-10-27T15:23:05+08:00）

自然模型回复不再整条替换为任务模板，公开模型名称、日程记忆引用、常见天气联网与独立管理员已实现；迁移t14_chat_assistant已应用开发库。相关后端专项、310题100档、TS/Lint/H5与一次真实天气/模型名/刷新验证通过；新增真实Search1次+生成1次，详见CHAT-02_CHAT_WEATHER_ADMIN.md。admin账号凭据仅本机文件，普通用户角色/数据隔离保持。真实高德路线/Android等仍未验收，SHA/CI事后核验。

CHAT-03（2026-10-27T15:45:21+08:00）：修复新任务占位编号与复合日期，39相关测试通过；用户指定失败回复由保存结果恢复，0新增付费调用，仍待用户给具体时刻/确认调度。CHAT-02 e4220e9两项CI run全部success；本次修复待push/SHA/CI核验。完整Muse快选/日历及Android外部验收未据此标完成。

CHAT-04（2026-10-27T16:05:57+08:00）：144专项通过；聊天保留与辅助候选降级、失败旧问上下文隔离、相对提醒时间与上游空回复分类，真实付费新增0。TS/Lint/H5通过，详见CHAT-04_REPLY_RESILIENCE.md；按用户要求上传全部项目代码，排除密钥/私有数据。当前SHA/push/CI提交后核验。

CHAT-05（2026-10-27T16:23:08+08:00）：移除共用聊天强制JSON模式；自然语言降级与无效引用不再清空reply；真实记忆撤回/证据版本保护保留。160相关回归通过，最终引用保护另10项复核；真实两次（一失败促成引用修复、一提醒通过），1409/211 tokens，估算USD0.00067590，0自动重试。详见CHAT-05_EMPTY_RESPONSE.md；未宣称第三方永不故障或全V0.1完成，当前SHA/push/CI事后核验。

DEV-01（2026-10-27T16:51:56+08:00）：PyCharm共享Mock/Live API和Mock Worker配置、脱敏聊天阶段日志与断点手册；35专项及XML/临时8001实际Mock聊天持久/幂等通过，0付费调用，无迁移。未验证IDE实际断点，保留现有.idea及当前服务；详见DEV-01_PYCHARM.md，当前提交SHA/CI事后核验。

DEV-02（2026-10-28T10:47:51+08:00）：根main.py一键启动API/H5/Worker及浏览器，API同进程支持断点，Windows Job强制停止后业务子进程全退出；MySQL持久保留。10单元（含-S）/实际正常及强停/前端类型Lint构建/Ruff安全通过，0付费。GBrowser指引已核对，IDE插件实际操作未验收；详见DEV-02_ONE_CLICK.md。当前SHA/push/CI事后核验。

UI-DOC-01（2026-10-28T11:08:16+08:00）：用户 UI/UX V1.0 原件按字节归档至 docs/design，建立职责分工、版本维护与后续验收入口，并接入 AGENTS/README。保留适老化字号与现有业务约束。仅文档；未安装 Skills，未实现或验收全局 UI/九主题/AI 生图。验证与远端结果见 UI-DOC-01_DESIGN_BASELINE.md，当前 commit/push/SHA/CI 提交后核验。

UI-DOC-01 归档修正（2026-10-28，Asia/Hong_Kong）：28075c5 已远端核验；补充原件 Git 属性以保留 CRLF 与 Markdown 换行空格，首轮暂存检查失败保留记录；修正后核验 Git blob 与附件，CI 以实际终态为准。

UI-P0-01（2026-10-28，Asia/Hong_Kong）：两项旧实现失败已先复现；仅修复 H5 确认弹窗和行程六字段标签，保留原生调用与业务/字号。基线 68d63a3 两项 CI success；本次验证、提交与远端状态见 UI-P0-01_ACCESSIBILITY.md，未预填已推送。

UI-P0-01 本地验收：相关三视口 63 passed；补充断言并修正同名按钮定位后专项 12 passed；typecheck/lint/build:h5、安全与差异检查通过；APP-PLUS 预处理与系统弹窗委托检查通过。原生真机/系统读屏未验收；0新增真实付费调用。工作区排除回归自动重生成的历史演示截图。当前提交及远端/CI待实际核验。
