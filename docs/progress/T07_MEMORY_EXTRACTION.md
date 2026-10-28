# T07：授权后的候选记忆与来源

- 日期：2026-10-26，Asia/Hong_Kong；本地功能/真实抽取/回归通过，当前提交推送与 CI 待事后核验。
- 前项 T06：e8861218fa6a6244e657b1713befc98d6db6a667，21:07:45 +08:00；远端一致，CI 40327943073 mobile/api/security 全部 success。

## 实现与文件

- memory/extractor.py / repository.py：MemoryExtractor、MemoryRepository，Pydantic候选校验、逐字证据约束、精确重复去重/多来源、UTC锚点与精度、原文保留。
- llm/providers.py、services/model_chat.py：已授权时同一次模型请求输出 JSON reply+memories，JSON mode/256输出上限/禁thinking与既有预算继续生效；无额外提取请求。
- models/entities、t07_memory/t07_prompt：全局授权默认false、message处理状态/原始输出、候选时间/许可/Provider/Prompt版本/Synthetic、用量Prompt版本。增量添加；不回退或删除开发库数据。
- api/v1/memories.py、schemas/memory.py：授权读取/更新、本人记忆和来源游标分页、类型响应，默认Mock/live列表分开；user_id只来自鉴权。
- mobile me/timeline/index：明确授权/取消/关闭、读取失败禁用并可重试、候选/来源/返回原会话、空/加载/错误、Mock/Synthetic标记；聊天显示本条提取状态。编辑/删除/跨会话使用明确未开放。
- prompts/chat-memory-v1 与注册表、MEMORY_LAYERS、OpenAPI/候选JSON schema；Prompt版本落库，不散落大量业务字符串。
- 来源按钮视觉检查发现secondary悬停误用primary深色背景造成低对比，修为独立浅底，并改用aria-disabled选择器；3种视口加入实际悬停颜色断言。

## 实际测试

1. 开发库 `alembic upgrade head`：两条增量升级成功；测试库空库升级/重复升级/降级/再升级/metadata check均通过，未碰 ALE_AI_MySQL。
2. 完整 `python scripts/check.py`：75后端测试（22.64s），5扫描器测试、安全/YAML/Ruff/format/TS/lint/H5build/diff PASS。Prompt溯源增量后完整pytest再次75 passed（22.68s）。
3. `npm run test:ui -- --max-failures=1`：33 passed，1.4m，360/390/430；含授权失败重试、取消不发授权写入、真实MySQL+Mock候选/来源/刷新/原会话、原聊天与隔离/IME等回归。最后来源/状态细节再执行 tests/memory.spec.ts 专项：6 passed，40.3s。
4. Memory专项覆盖：无授权只存L0；逐字来源/未说出的医院、日期、严重性拒绝；假设/否定/拒绝记录；月份跨年/当地跨月/闰日；模糊时间不补造；重复不重建事实但保留两来源；B越权和游标拒绝；在途撤回；Schema失败原文保留且不重试；列表/来源分页；Mock/live分离；混合有效/无依据候选只保存有依据项。
5. `SILVER_LIVE_MEMORY_REQUEST=1 node scripts/smoke-memory.cjs`：21:29仅一次真实合成输入，真实DeepSeek回复+记忆落库/来源/月份通过。辅助脚本遇到相似Mock文本定位不唯一，界面复核未过；修为按记忆ID定位后用 `SILVER_VERIFY_EXISTING_MEMORY=1` 只读重验刷新/来源，**没有重新调用模型**。
6. 本任务真实用量：deepseek-flash，293输入/63输出tokens，生成链路1610ms，峰时cache-miss保守估算USD0.00016350；预留1867token。项目累计2次真实调用、估算USD0.00020820，实际账单以服务商为准。
7. 该确切合成验收候选标记Synthetic，补记已知chat-memory/v1溯源；未修改原文、候选内容、状态、来源和token/耗时结果。既有未知版本留空。
8. 证据：docs/demos/T07-memory-live-390.png、T07-live-metrics.json、T07-memory-mock-360/390/430.png；本机 logs/t07-check-final.log、t07-backend-final.log、t07-ui-final.log、t07-memory-ui.log。截图已视觉检查，真实/Mock分开。

## 能力边界与下一项

当前验证的是候选提取/保存/溯源，不是跨会话召回、纠错删除、万级效果或真实主动提醒。不能据Mock膝盖fixture推断一般抽取准确率。
只对已明确时间表达解析，其他保留unknown；保守假设/否定拦截可能漏掉复杂混合事实，T10E2固定评估如实测量。
下一项T08：MemoryRetriever/ContextBuilder、授权/状态/用户/模式过滤、有限上下文和跨会话来源引用；继续Mock批量回归，真实验证只用少量必要请求。
