# T05：真实持久化聊天与历史

- 日期：2026-10-26，Asia/Hong_Kong；本地验收通过，待本次 push/SHA/CI。
- 前项 T04：e967f4535b7222bf4d1c7051dd42c22eedaf8bcd，2026-10-26 16:49:25 +08:00；远端一致，CI 40294959392 PASS。

## 实现与文件

- app/api/v1/chat.py、schemas/chat.py：真实会话创建/分页/详情、消息保存/历史游标、幂等冲突与回复关联，强类型响应与 OpenAPI。
- 使用 T03 已迁移的 conversations/messages，无新增表，无破坏性迁移；会话行锁、唯一键和微秒顺序保证单条请求可靠写入。
- mobile stores/chat、platform/ids、首页/历史页：H5 调用真实 API，显示读取/发送/失败/重试、保存后刷新和历史回看；输入失败保留，换号和过期请求结果隔离。
- 移除运行页面静态对话/模拟来源入口，未实现语音明确禁用、附件隐藏；保留 T02 视觉/提交/截图证据。
- 公共测试 fixture 移至 conftest，以复用真实 A/B 测试，不改鉴权策略。

## 实际测试

- pytest -q：28 passed（9.75s，完整检查再次 9.04s），含原 20 项及 8 个聊天保存/分页/幂等/越权/参数用例。
- 新增 Pydantic 响应 schema 后再跑 test_chat.py：8 passed，5.02s。
- npm run test:ui：18 passed，41.2s；3 种宽度均经真实 H5→API→MySQL 保存、重试（消息数仍 2）、刷新后找回，再登录 B 验证不见 A 原文且访问 A 路径 404。
- python scripts/check.py：安全/5 扫描测试、CI YAML、ruff、28 后端测试、前端 typecheck/lint/build、git diff PASS。
- 真实截图 docs/demos/T05-persisted-360/390/430.png；每条内容均合成，失败状态有明确标注。

## 发现与修复

首次浏览器“刷新消息仍在”失败：新会话 URL 还保留 new=1，刷新再次清空界面。
修复为首次保存成功后定位真实会话 id；保持原刷新断言，复测通过，没有删用例降低标准。
读取指定旧会话改为按 ID 单独请求，不再受最近 100 条列表截断影响。
切换用户/新读取以 epoch 隔离旧异步结果，避免旧用户结果晚到后写入新界面。

## 未完成与下一步

模型尚未接入，assistant 只记录失败，不填任何假回复；DeepSeek 请求/新增费用仍 0。
UI-FIX-01 将独立完成空态建议、IME/多行、软键盘/滚动与交互状态测试，再接 T06 Provider 和额度门禁。
记忆 T07–T10、CR-001 主动任务 T11A–E 均未冒充已完成。未连接/修改 ALE_AI_MySQL，未上传本机凭据。
