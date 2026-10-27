# MySQL逻辑备份与独立测试库恢复

范围：本项目MySQL 8.4、loopback:13306、silver_demo账号。自动工具只接受开发/测试双库，不连接ALE_AI_MySQL。真实.env、SQL备份与manifest均不入Git。

## 备份

从项目根目录运行，使用新的文件名；已有文件不会被覆盖：

```powershell
$backupStamp = Get-Date -Format 'yyyyMMdd-HHmmss'
.\.venv\Scripts\python.exe scripts/database-backup.py backup --schema dev --output "backups/silver-$backupStamp.sql"
```

测试库使用--schema test。工具核对.env中的URL、账号/密码匹配、13306端口、本项目Compose容器标签及实际127.0.0.1:13306绑定；从已运行容器内执行mysqldump，凭据不出现在命令参数或输出中。

采用single-transaction/skip-lock-tables/no-tablespaces和关闭GTID导出；不导出CREATE DATABASE/USE语句。备份期间不做DDL迁移。先写.sql.partial，成功后形成.sql及同名.manifest.json，记录来源库/香港时间/SHA256。失败留下partial用于本机诊断，不冒充成功备份。

SQL是完整业务备份，可能包含私有聊天、认证哈希和加密设备字段；保存在项目backups受限本机目录，不能上传到Git或公开分享。环境文件和设备加密密钥需单独保管，它们不在数据库dump内。丢失设备加密密钥不能靠SQL恢复解密能力。

## 恢复演练（只允许可丢弃测试库）

确认没有pytest、记忆批量评估或测试API正在使用silver_memory_demo_v01_test后：

```powershell
.\.venv\Scripts\python.exe scripts/database-backup.py restore-test --input backups/选定备份.sql --replace-test-data
```

必须提供显式replace-test-data参数；校验manifest格式/来源库/文件SHA256后，仅向silver_memory_demo_v01_test导入。目录越界、未知数据库、文件被修改、容器不匹配均拒绝。此操作会替换测试库里备份所包含的表，只用于Synthetic/可丢弃测试环境；不会清理未知的额外表，也不会自动启动Worker。

**该工具没有恢复覆盖开发库的命令。** 开发库若需灾难恢复，先保全当前数据、停止自己的API/Worker写入、确认备份时间与环境配置，在测试库核对后再制定明确的维护恢复操作；本次未对有数据的开发库执行覆盖恢复。

## 恢复后检查

1. 对比Alembic head、20张表的行数及内容摘要，检查消息原文、memory_sources关联与用户归属；不能只检查SQL导入退出码。
2. 已提交供应商的通知状态必须保留，Worker重启扫描不应自动重发；相同确认幂等键应返回同一个任务，不新增job。
3. 备份落后于实际第三方发送时，SQL不能证明外部结果。先保留/核对outbox和供应商记录，结果不明标unknown；不要直接恢复后启动真实推送Worker。
4. 当前工具验证的是MySQL逻辑恢复和Mock调度，不代表真实推送灾难恢复的exactly-once。开发库恢复与真实服务对账仍未验收。

## 2026-10-27实际演练

仅在原为空的silver_memory_demo_v01_test建立Synthetic用户、聊天/健康记忆与来源、一条已提交Mock通知、一个待提醒行程。备份后修改合成账户字段，恢复后20张表的行数及内容SHA256完全一致；恢复后的Worker领取0条，已提交通知状态保留；重复确认返回同一任务，job数量不增加。

命令与结果见docs/testing/T14-backup-restore.json，详细本机日志logs/t14-backup-restore.log。SQL与manifest留在被Git忽略的backups目录。会议演示开发库与其API/Worker没有重启或改写，新增真实DeepSeek/高德/推送调用0。
