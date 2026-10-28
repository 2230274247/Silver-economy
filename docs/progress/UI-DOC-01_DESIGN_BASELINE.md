# UI-DOC-01 长期设计规范归档

时间：2026-10-28T11:08:16+08:00，Asia/Hong_Kong。

范围：将用户粘贴的 UI/UX V1.0 长期保留，明确 App 规范与 emilkowalski/skills 职责。先阅读 TASK_STATUS、当前 DEV-02 记录和 ADR-002，确认本次为独立文档任务，不启动全局 UI 实施。

完成检查：附件与归档 SHA-256 一致；项目入口可发现规范；AGENTS 要求后续开发阅读；职责、冲突处理、版本维护和未实施边界明确；相对文档链接有效；差异与安全扫描通过。

变更：docs/design 原件和执行入口、AGENTS、README、CHANGELOG、任务状态与提交日志。保留历史原件和既有适老化约定；未改代码、依赖或数据库。上游 README 已核对四个建议名称，未安装/执行第三方 Skills。

实际验证：附件与原件字节相等及 SHA-256 核验 PASS；AGENTS/README/设计入口共 21 个本地链接存在性检查 PASS；git diff --check PASS；.venv/Scripts/python.exe scripts/security_scan.py PASS。仅文档变更，不运行与本次无关的后端/UI 全套回归；不声称已验收九主题或真实设备。

提交、远端 SHA 与 CI：待实际提交后核验。


归档修正：首轮暂存检查发现原件的 8 处 Markdown 双空格换行触发 trailing-whitespace，且默认 text 规则会将 CRLF 归一化。首个提交 28075c593eed09d5a1f78197144bd7c9e1841b08 已推送并核对远端 SHA，保留历史；未将首轮暂存检查写为通过。修正沿用既有 docs/changes/*.source.md 规则，在 .gitattributes 对 docs/design/*.source.md 设置 -text whitespace=-blank-at-eol，原件内容不改。随后重新暂存并核验 Git blob 与附件字节及哈希，而非只检查工作区。
