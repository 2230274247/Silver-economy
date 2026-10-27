# T14 初步演示交付记录

时间：2026-10-27T14:41:56+08:00。状态：DEMO_READY_FINAL_ACCEPTANCE_PENDING。
按用户最新要求先交可用版本，不继续非必要扩展或重复回归。T14不是正式完成，P05/P06等开放项留待续办。

本次运行：独立MySQL已存在且readyz返回t13_proactive_updates；启动FastAPI(8000)、uni-app H5(5173)、独立Python Worker；登录demo_a并读取会话、记忆、任务和Provider状态；无新增模型调用。真实模型已配置，地图/通知Mock。
启动只读结果与截图见testing/T14-demo-startup.json、demos/T14-running-390.png；本次读到30条会话列表/2条记忆/0个已安排任务。存在持久草案不等于已安排任务。

完成：更新过时README、会议演示步骤、模块/数据库说明、未验收台账；start-dev.ps1补worker目标，现有api/h5入口保留。保留main历史，dev/v0.1独立提交并核远端，准备draft PR，不合并或发布Tag。
验证：只执行启动/登录/已认证只读检查、PowerShell语法与提交敏感信息检查；复用T13已通过的必要回归，不重复整套测试。配置和启动不调用DeepSeek。

未执行：备份恢复、首次克隆单独复现、完整最新付费A–E再演示、真实高德与Android真机。均明确写入V01_PENDING_ACCEPTANCE.md，不伪造通过。用户导出不是数据库备份；CI干净checkout不能替代P06完整交付演练。

修复：独立Worker日志时间曾为本地时刻却标UTC；统一使用gmtime，重启本项目Worker验证UTC输出。没有更改调度时间或用户数据。
