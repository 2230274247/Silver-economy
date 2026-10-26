# T10E1：参数化Synthetic生成、三档导入与保护验证

日期：2026-10-27，Asia/Hong_Kong。远端已确认：`423ff6cf37cc12a82eb7027c939b487874d7a5d4`，
提交时间05:00:51 +08:00；origin/dev/v0.1一致；CI40400713021的api/security/mobile全部success。
前项T10：`d7572f9b6f0f2b1c71e5db507bec126ebdc22fb8`，04:18:47 +08:00；远端一致；CI40394518915全部success。

## 实现文件、方案和数据库影响

- `services/api/app/memory/synthetic_data.py`：固定版本/参数/种子的纯生成器，9类模拟事实、原文/归属/来源、时间精度、before/after预标注场景、四种无效状态、额外重复观察及逐行manifest校验。
- `synthetic_import.py`：写入前测试库检查、已存在数据保护、500行批次、来源/事实同事务；幂等时核对内容、归属、时间、状态、许可、来源，不覆盖修改或删除。L0消息与L1事实分别保存。
- `scripts/memory-synthetic.py`：generate/import/presets命令，所有语料文件限定项目忽略目录，不接受任意数据库地址；错误不回显输入或凭据。
- `services/api/tests/test_synthetic_memory.py`：30项生成/配置/真实MySQL/回滚/幂等/篡改/归属/时间跨度检查，使用既有禁止真实HTTP的Mock测试环境。
- `tests/memory_eval/fixtures/synthetic-v1-small.jsonl`：8条可逐字节复现样例；完整版留在`.cache`。操作说明`docs/testing/MEMORY_SYNTHETIC.md`，实际结果`T10E1-generation-import.json`。

不改数据库结构/旧迁移；仅向已有`silver_memory_demo_v01_test`导入单独Synthetic用户的数据。默认开发库、运营/ui用户、ALE_AI_MySQL及其他项目均未修改。模拟事实不是LLM已抽取的真实生活记录，也不表示自动冲突识别已验证。

## 实际命令与结果

1. 初轮`python -m pytest tests/test_synthetic_memory.py -q`：27 passed /8.14s；补强独立归属篡改断言后，全门禁162 passed /53.83s。
2. 边界审计新增`-k custom_time_span`：先复现2失败，日志`logs/t10e1-span-reproduction.log`。旧结束年份时“上个月”错误用当前参考年；一月开始范围会落到前一年。修复相对原文时间及边界回退，未更换失败条件。
3. 最终`python scripts/check.py`：164 passed /54.55s、5扫描器、安全/YAML/Ruff/format/类型/lint/H5 build/diff全部PASS；`logs/t10e1-check-final.log`。早期import排序lint在pytest前已修正，未绕过门禁。既有Starlette/httpx弃用提示仍在。
4. `python scripts/memory-synthetic.py presets`：实际生成并导入100、1000、10000条不同内容。最终导入0.625s /3.094s /21.516s；这些是导入时间，不是检索延迟。
5. 相同命令再执行：各档`inserted_memories=0`，校验0.250s /0.641s /4.359s。独立SQL计数分别100/1000/10000事实、110/1100/11000原文/来源；全部Synthetic，不同值数量等于事实数，跨归属/来源内容不一致0，模型使用行0。
6. 时间修复前后默认语料SHA未改变；最终报告保留文件SHA256和实际代码UTF-8/LF哈希。第一次导入/重复、最终重建/重复日志均保留，未用入库日志代替数据库核验。
7. 另实际执行3用户、seed17、2000–2010年、work/place两类、各20%比例的generate命令；100事实/120原文、34/33/33每用户、已知事件年范围2000–2010，未导入该额外样例。

没有前端修改，未重复此前45项UI回归；本次实际命令行、真实SQL及全部后端/构建门禁覆盖改动。运营H5仍为已有工程，没有将万级假数据混进用户记录。

## 规模、费用与质量边界

| 档位（总L1） | 用户分布 | 原文/来源 | 重导入新增事实 | 最终导入秒数 |
|---|---|---:|---:|---:|
| 100 | 51 /49 | 110 | 0 | 0.625 |
| 1000 | 500 /500 | 1100 | 0 | 3.094 |
| 10000 | 5000 /5000 | 11000 | 0 | 21.516 |

默认万级9类，1000条预标注冲突记录（500对）、1000条无效记录；259删除、258失效、240禁止使用、243过期，未知精度3332条。全部真实调用0、成本新增0，运营DeepSeek累计仍6次；未提高额度限制。

预标注冲突、随机重复人名和模糊时间不等于所有自然语言语义已被客观识别，报告明确这一限制。下一项T10E2必须冻结至少200题、独立标准答案/来源、在三档语料上实际评估召回/答案/冲突/删除/隔离/性能/并发/资源，并生成HTML+JSON；不能将本任务数量当作最终记忆有效性验收。
