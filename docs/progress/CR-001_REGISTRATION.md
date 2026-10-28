# CR-001 正式登记执行记录

- 记录时间：2026-10-26 16:03:52 +08:00（Asia/Hong_Kong）
- 当前结果：需求/设计/任务调整完成，本次提交前本地检查通过；push/SHA/CI 等待实际执行。
- 前项 T02 最终提交：89c82eb4066a5416f75c1645c7b0a279e6625130；远端 SHA 一致，CI run 40288604220 全部通过。

## 完成内容

1. 原样保存 CR-001 附件，SHA256 与原件一致。
2. 将主动出行执行闭环与长期记忆并列 P0；Android 真机后台通知覆盖旧 PC-only 验收。
3. 新增 ADR-003、数据库/API 设计、13 项扩展验收及外部准入/成本边界。
4. T11 拆为 T11A–T11E，明确依赖、独立测试/提交/推送要求；T00–T10 顺序保留。
5. 补 T00–T02 实际香港提交时间、功能/修复及测试/SHA/CI 日志；后续提交正文采用详细格式。

## 修正与边界

- 修正现行 README/看板中的 PC-only 最终验收和旧站内提醒口径；旧 ADR 保留历史并标明已被覆盖。
- 没有新建业务数据库表，没有实现/部署地图、天气、调度、推送或 Android 包；不能将文档完成当功能完成。
- 未连接或修改 ALE_AI_MySQL，未改 main，未重写已推送 Git 历史。
- 所查环境及本项目 .env 未发现外部服务配置；不代表用户没有账户。后续可 Mock 开发，live/真机门禁单列。

## 实际验证

- 原件 SHA256 对比：PASS。
- T11A–T11E 看板覆盖、CR-AC01–13 验收编号及设计文档存在检查：PASS。
- python scripts/security_scan.py：PASS。
- python -m unittest discover -s scripts -p test_*.py：5 passed。
- python scripts/validate_workflow.py：PASS。
- services/api 中 pytest -q：3 passed，现有上游 httpx 弃用警告一条。
- git diff --check：PASS。
- 暂存检查首次发现附件原件的 Markdown 行尾双空格（原作者用于硬换行）；为保持原件字节不变，仅对 *.source.md 配置不归一化文本/不报行尾空格，其余文件继续检查。随后校验暂存原件 SHA256 与原件一致。
- 本次只改文档，不把重复前端构建冒充新增功能验证；远端 CI 仍会执行完整前端/后端/安全/UI 检查。
- 真实 DeepSeek/高德/推送请求 0，新增外部 API 实际费用 0；报价/额度待真实账号核验。

## 下一步

本次安全提交、推送并核对 SHA/CI 后进入 T03 独立 MySQL 与迁移基础。
本次最终 SHA 与远端结果通过后续日志提交固化，不预写成功。

## 事后核验（通过后续日志提交固化）

- 实际提交时间：2026-10-26 16:04:25 +08:00；正文准备时间 16:03:52 +08:00。
- Commit：cde000795374b63c9d6a93cb89ca2077b2e3d517。
- Git push origin/dev/v0.1：成功；git ls-remote 与 HEAD 一致。
- CI：run 40289773428，security/api/mobile 全部 PASS。
- 2026-10-26 16:06:04 +08:00 再次读取 GitHub Commit API 与 Actions 核验：PASS。
- CR-001 需求登记任务状态：DONE_PUSHED；实际功能仍按 T03–T14/T11A–E 实施。
