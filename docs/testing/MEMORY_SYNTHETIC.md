# Synthetic 记忆生成与测试库导入

本工具不调用模型、地图或其他外部API；完整语料只保存在本项目忽略目录`.cache/memory-eval/`。Git保留生成器、8条固定样例及实际验证报告，不提交完整语料或数据库导出。

在项目根目录使用项目Python：

```powershell
.\.venv\Scripts\python.exe scripts/memory-synthetic.py generate --memories 10000 --users 2 --seed 20261027
.\.venv\Scripts\python.exe scripts/memory-synthetic.py import --input ".cache/memory-eval/10000-d0852eb5-3e9e-58d6-a007-3c4bb1592ee5.jsonl"
.\.venv\Scripts\python.exe scripts/memory-synthetic.py presets
```

`presets`依次生成并导入100/1000/10000条，命令重复执行会校验已有原文/事实并返回`already_present=true, inserted_memories=0`。内容或状态已被修改时拒绝覆盖，不恢复已删除/失效记忆。所有导入均在单个事务内，失败整体回滚。

| 参数 | 默认值/含义 |
|---|---|
| --users | 2；每个用户必须分到事实，冲突对属于同一用户 |
| --memories | 100；**整个语料的L1总数**，不是每用户数量；1–100000 |
| --seed | 20261027；影响内容和标识，可复现 |
| --start-year / --end-year | 2006 / 2026；已知事件时间范围，结束年不能晚于参考年 |
| --reference-date | 2026-10-26；固定以避免运行日期改变语料；相对月份使用对应原文的时间 |
| --categories | relationship,work,habit,interest,travel,date,health,event,place；非空且不重复 |
| --duplicate-ratio | 0.1；额外重复原文观察数/L1数，同事实增加来源，不增加事实行 |
| --conflict-ratio | 0.1；预标注的before/after冲突记录数/L1数，向下取完整双记录对 |
| --invalid-ratio | 0.1；删除/失效/禁止AI使用/过期记录数/L1数；不与预标注冲突重叠 |
| --output | 可选；仅generate使用，只能在项目`.cache/memory-eval/`内；已有不同内容拒绝覆盖 |

例如自定义参数，真实执行过并验证时间范围：

```powershell
.\.venv\Scripts\python.exe scripts/memory-synthetic.py generate --memories 100 --users 3 --seed 17 --start-year 2000 --end-year 2010 --categories work,place --duplicate-ratio 0.2 --conflict-ratio 0.2 --invalid-ratio 0.2
```

比例按记录数取整；冲突与无效比例之和不能大于1。默认万级语料有两用户各5000条，9类内容、1000条预标注冲突记录（500对）和1000条无效记录；额外1000段重复来源使原文/来源总数11000。报告会列出每用户实际数量及各状态，不能仅用总行数宣称质量。

## 数据合同与保护

JSONL首行是带版本/完整参数/数据集ID的manifest，后续每行一个结构化事实及其原文来源。UUID、内容和顺序由参数与种子复现；读取/导入会重新生成并逐行比对，拒绝截断、额外行、篡改、非Synthetic和归属变动。小样例`tests/memory_eval/fixtures/synthetic-v1-small.jsonl`可逐字节复现，测试会检查。

每条事实与原文都标Synthetic，保留真实对应的模拟用户、会话、消息和来源ID。重复来源有不同消息ID，原文相同、事实不重复。年份/月/日期保持精度；“很多年前”和未给时间保留未知，不补造日期。JSONL中的无偏移ISO时间按内部UTC解释，事件显示时使用Asia/Hong_Kong；年/月锚点不是精确发生日。

导入只读取本机`TEST_DATABASE_URL`，严格限制`mysql+pymysql`、`silver_demo`、本机13306及`silver_memory_demo_v01_test`；命令没有任意数据库URL参数。连接/迁移和写入入口均检查测试库，不能导入开发库、ALE_AI_MySQL或其他项目库。数据库结构仍由现有Alembic管理，本任务没有新表或迁移。

导入创建单独的`syn-...`合成用户及随机不可知密码哈希，不修改demo/ui用户或普通用户配置。生成与导入错误不会回显凭据/输入全文。不要将测试库接到生产用户。

完整回归包含测试库清空/降级/再升级，所以该库可丢弃。先跑`python scripts/check.py`，再执行`presets`准备评估；不要把测试库当备份。未做清库时，反复导入保持幂等。

## 验证证据与限制

实际报告`T10E1-generation-import.json`包含参数、文件SHA256、数据库独立计数、来源归属/内容检查、导入/重复校验耗时及代码UTF-8/LF哈希。默认三档各有100/1000/10000条不同内容，来源为110/1100/11000；重导入新增0，模型使用行0。

冲突比例是预标注合成场景比例，不是模型冲突识别正确率。随机常见人名及不确定时间可能存在额外语义歧义，固定评估必须独立定义答案或澄清预期。导入耗时不是检索P95；Recall@5、答案准确率、幻觉、并发、资源及HTML报告属于下一项T10E2，不能凭本任务报告宣称通过。
