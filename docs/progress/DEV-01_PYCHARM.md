# DEV-01 PyCharm共享运行配置与聊天阶段日志

时间：2026-10-27T16:51:56+08:00，Asia/Hong_Kong。用户希望在PyCharm点击Run/Debug后，通过H5发消息观察完整后台处理。范围限定共享运行配置、脱敏阶段日志、操作手册。

新增.run/三个Python模块配置：Silver API - Mock、Silver API - Live、Silver Worker - Mock；固定项目.venv解释器与services/api工作目录，无reload/多worker。Mock覆盖LLM/地图/通知Provider；Live沿用本机安全配置。加入.idea/忽略规则但不改动现有IDE文件。

model_chat增加context_ready/request_persisted/weather_ready/model_call_started/model_call_returned/reply_persisted阶段，按client_request_id串联，只记数量、状态、耗时和token，不打印正文/Prompt/密钥。原日志隐私测试扩充阶段完整性断言；未改变聊天、预算、调度、数据库结构或超时逻辑。

实跑命令：services/api下 ../../.venv/Scripts/python.exe -m pytest -q tests/test_models.py tests/test_chat_assistant.py --tb=short，35通过；Ruff检查/格式、安全扫描通过。XML配置解析与Mock启动/HTTP持久聊天/幂等/五阶段/无正文日志实测通过，证据DEV-01-config-smoke.json；仅临时8001进程启动并关闭，现有8000/H5不重启，0新增付费调用。未验证IDE内真实点击Debug，操作手册明确这一边界以及45秒网页超时与副作用求值风险。

CHAT-05 fe4942e2a7663e4346a18c48f1521a463be754df的两个CI40473225092/40473233834全部success。本次dev/v0.1提交/推送/远端SHA/CI事后核对；高德和Android外部验收仍未完成。
