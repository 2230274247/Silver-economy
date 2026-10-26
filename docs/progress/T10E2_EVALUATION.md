# T10E2：固定题集、客观记忆评估及失败修复

日期：2026-10-27，Asia/Hong_Kong。本地四档最终复测及来源快照核对已通过；push/SHA/CI按规则在提交后核验。
前项T10E1：`423ff6cf37cc12a82eb7027c939b487874d7a5d4`，05:00:51+08:00；远端一致，CI40400713021全部success。

## 目标、实现范围与数据库影响

在已有工程上冻结独立事实/来源/答案，在真实测试MySQL和真实聊天API上测310题、四档规模，保存基线、失败迭代、最终HTML/JSON及性能/并发/资源结果。
批量运行全部Mock，拒绝真实HTTP，不重建工程或更换既有模型/数据库框架。

- `scripts/build-memory-eval-fixture.py`、`tests/memory_eval/fixtures/suite-v1.*`：310题、246种不同文本，100条受控事实；首次排名前冻结，SHA见测试说明。没有从检索结果反推答案。
- `memory/eval_dataset.py`：确定性ID、测试库白名单、原文/事实/来源、真实控制服务生命周期、幂等快照和禁止覆盖已有变化。
- `memory/evaluator.py`：实际登录/会话/发送/刷新、来源及纠错版本计分、SQL/延迟/并发/内存/CPU、数据漂移与门禁。
- `scripts/evaluate-memory.py`：强制Mock、阻断真实HTTP、唯一输出标签、实际代码哈希/运行环境、失败/中止状态及增量结果保留。
- `query.py`、`retriever.py`、`context.py`、`extractor.py`：以下实测失败的通用、有限规则修复。没有题号、答案表或基准人物姓名查找代码进入生产检索。
- `eval_report.py`、`audit-memory-results.py`、`inspect-memory-report.cjs`：离线HTML、独立只读SQL统计/快照复核、真实浏览器离线/布局/选择器检查。
- `test_memory_evaluator.py`、`test_memory_eval_report.py`、`test_memory_evidence_queries.py`及既有检索测试：独立反例、评分/错误/来源/版本/未知、HTML转义/不可覆盖、实际SQL关系约束。
- `test_auth.py`：两个既有测试改为查询本测试用户的会话，避免拿基准账号的第一行会话做断言；身份与过期断言不变。
- 操作配置说明更新为T06之后实际已实现的额度保护，不修改限额或读取/回显Key。

数据库结构不变，Alembic仍`t09_update`。评估仅操作`silver_memory_demo_v01_test`中的Synthetic账号；完整迁移测试按既有逻辑清空并重建可丢弃测试schema，固定输入和来源快照可复现。
开发库只读核对历史模型用量；没有修改ALE_AI_MySQL、其他项目或运营记忆。所有评估原文与人物均合成，凭据留在忽略目录。

## 失败、修复与可核对证据

1. 原始`baseline-v3`实际跑完四档。万条/两万条的Recall@5为88.8889%、Top-1为88.3333%、冲突75%、Mock回答56.7742%、未知题无依据回答代理79.2308%；未达到门禁。跨用户/删除召回均0。保留完整JSON，不以通过后的结果覆盖。
2. 独立反例先得到4失败：最新状态被“那次”误判成历史、短中文词项丢失、住址被当面积、跨逗号提问被存成受伤事实。日志`logs/t10e2-counterexamples-red.log`。
3. 修复短词/停用词、有限同义词、必要字段/人物/场馆约束、最新状态优先、真实吃饭证据、复合问句完整验证；Mock只引用满足必要条件的实际来源，否则明确承认未知。
4. `rules-v1`100档仍有14失败：人名吃掉“同去/过生日”中的字、月季漏归花卉、未覆盖“吃过哪道”、场馆串用、门牌未知误答。停止后续规模，保留首档原始结果；这个旧运行留下`running`历史字段，实际已中止，不能当作仍运行或已通过。
5. `rules-v2`100档全部通过；1000档仍有5失败：三个旅行同行人物未严格匹配、两个“同事”被当作“隔壁同事”。停止后续规模并保留`interrupted`结果，补充独立同行/邻居SQL反例，再运行同一冻结题集。
6. 首次完整门禁180通过/2失败：基准账号持久会话揭示旧鉴权测试无user_id条件、误取全表第一行。修复测试归属条件后182通过，再补强关系与报告测试；没有放宽原有安全断言。
7. 统计复核发现`scale/2`只是人均，不能标为每人的真实条数。冲突对同属一人，使1000档A501/B499、万条档A5001/B4999。修正显示为人均或真实SQL分布；最终以只读审计补充逐人计数、核对初始/最终来源快照，原始指标、题集、语料和代码测量哈希不改写。

## 实际命令与运行记录

- `.venv\Scripts\python.exe scripts/check.py`：最终生产检索修复后196后端测试/53.46s，5扫描器、安全、YAML、Ruff/format、TypeScript、ESLint、H5构建、diff全部通过；`logs/t10e2-check-v3-final.log`。
- 新增人数展示反例后，`pytest -q services/api/tests/test_memory_eval_report.py`：4通过；`logs/t10e2-population-metadata.log`。这是无数据库/无真实调用的报告检查。
- `npm.cmd run test:ui`（项目`.cache/browsers`）：360/390/430视口共45项实际UI通过/2.3分钟，`logs/t10e2-ui.log`。使用18000独立Mock服务及ui_a/ui_b，未动运营账号授权。
- `scripts/evaluate-memory.py --label baseline-v3 --scales 100 1000 10000 20000`：四档实际基线，`logs/t10e2-baseline-v3.log`。
- 同命令`--label rules-v1/rules-v2 --require-targets`：上述真实失败，未对失败题换答案。日志`logs/t10e2-rules-v1.log`、`logs/t10e2-rules-v2.log`。
- `scripts/evaluate-memory.py --label rules-v3 --scales 100 1000 10000 20000 --require-targets`：最终复测，`logs/t10e2-rules-v3.log`；具体指标以完成后的JSON为准。
- `.venv\Scripts\python.exe scripts/audit-memory-results.py rules-v3`：真实SQL分布与原始初始/最终来源快照一致，新增独立核验副本，保留原始JSON SHA；没有修改指标或评分。随后用`write_report`生成`rules-v3-verified.html`。
- `node scripts/inspect-memory-report.cjs rules-v3-verified`：1440/390实际浏览器检查通过，外部请求0、JS错误0、正文溢出0、规模切换通过；两张截图已实际打开检查。
- 重启仅归属本项目的8000后端，readyz 200；登录读取T09已保存真实回复及当前来源引用，退出，授权状态不变；新发送消息0，见`preview-readonly.json`。
- 详细复现、计分分母、资源范围及保守规则限制见`docs/testing/MEMORY_EVALUATION.md`。

首个12题试运行曾遇到“没有冲突用例时None比较”错误，修复评估器的空分组处理；12题不算完整题集通过。HTML模板长行采用局部E501样式豁免，其余Ruff/format及实际功能门禁通过，早期格式错误日志保留。
报告浏览器检查首次未找到全局Chromium；改用本项目已有`.cache/browsers`，没有重新下载浏览器或调用模型。
旧人数标签的HTML/截图移到本项目`.cache/eval-report-before-population-label-fix`保留，原始基线JSON未变。

## 最终固定题集结果

每档310题，同一题集SHA、同一受控事实与生成参数。基线/最终四档初始事实及来源快照逐一相同，未替换题目或答案。

| L1总数 | SQL实际 A/B | Recall@5 | Top-1 | Mock回答/冲突正确率 | 未知代理 | 检索P95 | Mock聊天API P95 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 100 | 50 / 50 | 100% | 100% | 100% / 100% | 0% | 127.911ms | 236.144ms |
| 1000 | 501 / 499 | 100% | 100% | 100% / 100% | 0% | 94.514ms | 250.038ms |
| 10000 | 5001 / 4999 | 100% | 100% | 100% / 100% | 0% | 187.656ms | 354.867ms |
| 20000 | 10001 / 9999 | 100% | 100% | 100% / 100% | 0% | 277.841ms | 439.759ms |

各档180正例、130未知题，零跨用户泄漏、零删除召回、零API错误、无事实漂移；最大上下文3389 UTF-8字节/5条，远低于12000字节门槛。
每档4线程/80次检索，并发泄漏0；两万条档并发P95 445.991ms，6.554秒完成80次。
两万条档评估墙钟213.764秒、Python CPU 98秒、增量分配峰值3997188 bytes、进程生命周期最高工作集241152000 bytes；SQL累计1834次/50558.643ms，仅指检索部分。
完整资源、逐题、初始/最终来源哈希和实际代码哈希见JSON；“100%”仅是该有限Synthetic+Mock题集结果，不是对真实模型开放式回答或未知生活信息的保证。

原始报告`rules-v3.json`保留原运行代码哈希；测量后只新增实际人数元数据统计，`rules-v3-verified.json`记录原报告SHA及只读审计方法，计分逻辑未变。
`run-index.json`逐一保留基线、试运行、中止及最终报告哈希和真实状态，不把早期`running`文件当成功。
报告JSON在Windows含CRLF，Git属性只针对该报告目录关闭行尾归一化，保留原始字节SHA；其余代码和冻结题集继续LF规则。提交前核对Git暂存blob与本机报告/题集SHA相同。

## 额度、局限及下一项

本任务新增真实DeepSeek调用0。独立只读台账核对：既有6次、2291输入/261输出token，见`docs/testing/memory-eval-v1/usage-audit.json`；不是新请求或服务商账单。
每日10次/20000预留token、单次默认256输出、无自动重试、请求幂等、Key仅后端和Git忽略规则保持。

结果仅代表固定Synthetic题集、SQL检索及Mock闭环；Mock未知代理不是DeepSeek通用幻觉率，不把旧的6次真实样本当成新批量验证。
有限同义词、人物/字段规则可能保守漏掉多人物、多事实与未列出的表达；未声称通用复杂语义冲突已经解决。
没有新前端业务页面；报告不是普通用户产品页。原H5布局与历史保留，Android真机/高德/持久提醒尚未完成。

下一任务T11A：在既有聊天和用户归属上实现出行意图、必要追问及可编辑确认草案；用户确认后才能进入真正保存/调度流程，不能只作口头承诺。
