# 银发记忆 V0.1 开发约束

进入仓库先阅读 docs/progress/TASK_STATUS.md，再阅读当前任务记录。
任务书：用户提供的《银发记忆 Demo V0.1 Codex 开发任务书》。已在 T00 读取，原下载路径在 T01 不再可读，未伪造原件副本；执行要点保存在本文件和任务记录中。

- 严格 T00 → T14，每次只实施当前任务；先定义完成检查再写代码。
- 代码、依赖、文档、日志和产物限于本项目目录。禁止使用或修改 ALE_AI_MySQL。
- 只在 dev/v0.1 自动提交和推送；origin 必须是 https://github.com/2230274247/Silver-economy.git。
- 每任务：实际测试 → 安全扫描 → 更新 CHANGELOG/任务状态/记录 → 精确 git add 路径 → git diff --cached --check → commit → push → ls-remote SHA 对比 → 检查 CI → 用户报告。
- 不把 commit 成功当 push 成功；CI 失败标 PUSHED_CI_FAILED，修复另建提交，不重写历史。
- 当次提交的 SHA、远端与 CI 确认结果通过下一任务或单独状态同步提交固化，不能预先写 DONE_PUSHED。
- 禁止 force push、reset --hard、git clean、覆盖未知修改、直接推 main、擅自合并/发布。
- 权限拒绝或归属不清先暂停；不得绕过分支保护或索取聊天中的密钥。
- 只使用合成测试数据；禁止提交 .env、凭据、数据库、照片和真实私密对话。
- H5 首先运行，uni-app/Vue3/TypeScript + FastAPI + 独立 MySQL/Alembic；平台能力封装，不在业务代码直接使用浏览器全局。
- Mock 必须可见标注；未真实验证的模型/提醒/跨端能力不得报告成功。
- 阅读 docs/changes/CR-001.source.md、CR-001-impact.md 与 ADR-003：主动出行助理并列 P0，T11 拆成 A–E 独立任务。最终必须 Android 真机后台通知，浏览器只是中间验证；覆盖 ADR-002 的 PC-only 旧决定。高德/推送凭据只在本机服务端配置，缺配置可 Mock，但不能冒充 live/真机通过。
- GitHub 日志必须详实：每次提交正文记录香港时间、完成的功能、修复的问题、实际测试命令/结果、未完成项与下一步；更新 CHANGELOG、专项记录及 docs/progress/COMMIT_LOG.md。已推送历史不 amend/重写，失败与修复分别保留。
- CR-001 原件副本和冻结基线不得改写；后续调整另建变更或 ADR。
- 只做当前范围内必要改动；不引入微服务、向量库或多 Agent。
- 冻结 V1.0 基线原件不得改写；未提供时记录缺失。

常规检查：python scripts/check.py；只测试后端时进入 services/api 使用项目 .venv 的 pytest/ruff。
