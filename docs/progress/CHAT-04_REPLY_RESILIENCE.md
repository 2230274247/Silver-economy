# CHAT-04 聊天与辅助校验解耦修复

时间：2026-10-27T16:05:57+08:00，Asia/Hong_Kong。用户要求适当放宽误拦截边界，并将全部项目代码上传GitHub；不取消账号隔离、授权撤回和真实调度检查。

## 现场证据与边界

只读检查用户指定截图对应的本机记录：天气、相对提醒及后续消息为MODEL_INVALID_RESPONSE_UNKNOWN，原raw为空。旧Provider把空内容、异常响应结构和用量解析失败合并，无法从旧记录确定具体上游原因。不能宣称这些全部是安全锁问题，也不能恢复不存在的回复。天气搜索来源成功不代表模型生成成功。

DeepSeek官方JSON Output文档说明JSON模式可能偶发空内容：https://api-docs.deepseek.com/guides/json_mode/ 。本次保留单次有界调用，不增加自动重试，不谎称已根治上游空结果。

另有确定性问题：失败的旧用户问题仍进入下一轮上下文，使新话题可能补答旧问题。旧任务Schema/编号错误也会使正常自然reply丢弃。

## 修改及数据库影响

- model_chat.py：失败消息仍在数据库与历史中保留，但不再将对应旧提问自动传入下一轮。正常reply与辅助条目分开处理，缺省/错误memories、额外顶层元数据、单个坏任务条目不再使整条聊天消失；合法条目继续持久化。
- 提醒编号、版本等校验仍拒绝写入错误对象，但错误仅降级该轮任务操作；原自然回复保留，追加明确“尚未安排通知”，用量记录completed_partial及原因。多草案保存仍有savepoint，不半途落库。无后台任务不得当作执行成功。
- 记忆引用不存在、撤回、删除、内容在生成期间变化仍严格阻断；不能以放宽格式为由展示已撤回私有内容。无有效reply/损坏JSON仍失败，不拼凑模型未返回的回答。
- providers.py：新增MODEL_EMPTY_RESPONSE错误分类，在上游有合法usage但空回答时保留实际token数；不自动重试。格式校验失败也登记completed_rejected和原因，避免流水显示成功。
- time_parse.py/intent.py：半小时后、整数小时/分钟后按原消息created_at确定性计算，范围1分钟至7天；提醒默认lead=0，不再把半小时后误当缺日期。保留卡片确认，不新增实际通知。明确时刻混用、复杂多段相对时长等未泛化保证。
- H5：区分空返回、格式异常、记忆权限变化和普通上游异常；记忆部分候选跳过有单独提示。
- 无数据库结构迁移；未更改演示库聊天、原raw、失败回执或历史；未访问ALE_AI_MySQL。

## 实际验证

命令在services/api执行：../../.venv/Scripts/python.exe -m pytest -q tests/test_chat_assistant.py tests/test_models.py tests/test_task_drafts.py tests/test_memory_extraction.py tests/test_memory_retrieval.py tests/test_memory_updates.py --tb=short

结果144通过，1条既有Starlette弃用警告。覆盖坏辅助字段保留reply/合法任务、失败旧问不串下一轮、相对时长锚点、未知任务编号不写入、授权/删除/引用保护。原未知编号测试改为验证正常聊天保留且无任务写入，并非取消权限断言。

首轮130通过/14失败：独立测试库遗留此前Synthetic评估及备份演练记录，导致旧测试全表计数和无条件scalar断言取到旧记录。先使用scripts/database-backup.py备份至ignored backups/chat-04-test-before.sql，再仅清理严格校验的silver_memory_demo_v01_test测试夹具重跑。开发库未清理；未为通过测试删减安全断言。重跑日志logs/chat-04-focused.log，备份不上传。

其他实跑：npm.cmd run typecheck、npm.cmd run lint、npm.cmd run build:h5；Python Ruff检查/格式与scripts/security_scan.py。API重启加载修复，H5继续5173；健康与就绪检查另附JSON。最后新增失败格式usage登记用单项回归复核。

本次新增真实模型/搜索调用0；自动测试使用Mock/合成数据且禁止真实网络。未使用付费重复请求“验证”上游可靠性，Android真机、高德真实接入及完整V0.1验收仍开放。未改写main或历史，SHA/远端/CI在提交后核对。
