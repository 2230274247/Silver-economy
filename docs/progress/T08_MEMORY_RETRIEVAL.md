# T08：跨会话检索与可追溯回复

- 日期：2026-10-26（Asia/Hong_Kong）；本地及单次真实召回通过，当前commit/push/SHA/CI待事后核验。
- 前项T07：ab54cf99cf432aca15d32477b1b61a1b1e879a97，21:50:05 +08:00；远端一致；CI40334086929三项success。

## 实现范围与文件

- memory/retriever.py、context.py、references.py：MemoryRetriever SQL基线、ContextBuilder预算选择、批量来源映射、精度/合成标记，默认最多5条，不调用额外模型。
- models/entities与t08_retrieval：仅新增memory_uses表与归属/来源/幂等约束，复用既有来源唯一键，未修改历史迁移/原数据。开发库upgrade、独立测试库空库/重复/回退/再升级与metadata check通过。
- services/model_chat、llm/provider、chat/memories API/schema：受许可/状态/模式约束地组装上下文，同次JSON回复/候选/短引用；真实引用持久化并随历史读取，伪造编号、在途修改/删除/撤回则拒绝正文，保留真实用量且不自动重试。
- mobile聊天引用卡/原会话入口、记忆库搜索/未知空态；搜索复用平台输入绑定，保护IME/完整输入；Mock/Synthetic来源明确标记。
- Prompt chat-memory/v2保留v1，注册输入输出/测试/变更；上下文扩为硬限12KB以完整保留2000字符Unicode消息，其余旧历史/证据删减，不把全部记忆进Prompt。

## 实际测试

1. `python scripts/check.py`：100后端（32.23s，最终回归）、5扫描器、安全/YAML/Ruff/format/TS/lint/H5build/diff全部PASS；新增精确信息/年精度、三种工作改写、未知指定日期餐食、授权/模式/多用户/失效/删除/有效期、无来源不抢占Top5、完整Unicode/上下文上限、重登录新会话/重放/来源、在途修改/删除/撤回、伪造引用/外键与字面通配符测试。
2. `npm run test:ui -- --max-failures=1`：36 passed，2.0m，最后代码冻结后再次36 passed/1.8m，360/390/430实际H5→API→MySQL+Mock。新用例分别登录退出A、新会话召回/刷新引用/原会话、库搜索/未知词，B开启记忆仍不能看A引用/来源。
3. 专项 retrieval.spec.ts：3 passed，47.3s；全回归前保持所有失败断言并修复。
4. 首轮UI把实际searchbox当textbox造成超时，修正语义定位和测试独立偏好清理；下一轮在前个请求未完成时搜索，改为等待真实响应和忙碌结束。
5. 仍失败的未知词断言揭示真实算法问题：长英文词被拆成双字母，误匹配Synthetic；改为英文整词，仅中文长串分词，保留原失败词/断言并新增后端回归，通过后全套复跑。
6. 旧8KB限制暴露最长Unicode当前消息可能遗漏，修为12KB总限且预留完整当前输入；2000个emoji原文进入上下文、总限/最多5条真实测试通过。查询问题不再被当新事实重复导入。补充完整分句保留否定/不确定措辞、问号疑问拒绝、无证据Mock明确不知道和实际Prompt版本记录的回归，未重发真实请求。

## 真实单次验证与成本

22:41使用新浏览器/新登录/新会话，输入“你还记得我的膝盖之前发生了什么事吗？”；系统只从持久化T07记忆检索，没有重发原始受伤输入。DeepSeek返回受伤事实，并明确合成测试性质，引用准确指向T07原消息；刷新后正文和引用仍在。
`SILVER_LIVE_RETRIEVAL_REQUEST=1 node scripts/smoke-memory-retrieval.cjs`仅1次；已有attempt保护，`SILVER_VERIFY_EXISTING_RETRIEVAL=1`只读复核路径不会再发送。
本任务421输入/40输出tokens，生成链路1453ms，峰时cache-miss保守估算USD0.00017430；项目累计3次，估算USD0.00038250（非账单）。预算预留与实际tokens分别记录，自动回归不新增真实调用。
证据：docs/demos/T08-retrieval-live-390.png（已视觉检查）、T08-live-metrics.json、T08-retrieval-mock-360/390/430.png；本机logs/t08-check-final.log、t08-ui-final.log、t08-retrieval-ui.log。

## 限制与下一项

这是SQL/词汇与结构化基线，不凭少量用例宣称通用语义准确率或万级性能达到目标；固定至少200题/100–10000规模报告尚待T10E1/E2。
T09继续用户确认/纠错/失效/删除、状态冲突和当前/历史区分；T10时间线后执行正式规模评估。主动任务与Android通知仍为CR-001后续任务，不因记忆闭环跳过。

## 事后远端核验（T09固化）

2026-10-26 23:08:00 +08:00 提交 `d205546532360551ed35f8aad396eb60ae250e22`；push与远端SHA一致；CI40346315913 api/security/mobile全部success（mobile于23:20:31完成）。
