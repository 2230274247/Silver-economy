# PyCharm Run / Debug 消息处理

2026-10-28新增推荐入口：根目录main.py一次Run/Debug启动API、H5、Worker并自动开网页；停止时托管子进程同步退出。详见[一键启动与侧边浏览器](ONE_CLICK_PYCHARM.md)。以下分项配置继续保留，单独调试时可用；一键入口的H5开发请求等待为10分钟，分项默认45秒。

直接打开Silver-economy根目录。共享配置在.run/，沿用.venv/Scripts/python.exe（本机实际Python3.12），不使用新建的其他解释器。保留已有.idea文件，.idea仅本机使用不提交。PyCharm支持共享项目运行配置：https://www.jetbrains.com/help/pycharm/run-debug-configuration.html 。

## 操作

1. Docker Desktop及本项目MySQL先运行。需要时在项目根目录执行 .\.venv\Scripts\python.exe scripts/init-dev-db.py 。
2. H5继续使用5173网页；未运行时在PyCharm Terminal执行 .\scripts\start-dev.ps1 -Target h5 。
3. Run配置下拉选择Silver API - Mock；若没有自动显示，重新打开项目，在Run > Edit Configurations核对。配置已明确指定模块uvicorn、工作目录services/api和项目解释器。
4. 先停止原有8000后端，确保同端口只启动一个。Run（绿色三角）可以看阶段日志；要在代码暂停与查看变量，点击Debug（小虫子/Shift+F9，默认Windows键位）。没有使用reload/多worker，避免断点落在其他进程。
5. 在API代码行号左边设置断点，回到H5发送一条明确标Synthetic的消息。页面请求进入这个Python进程，PyCharm暂停并显示Frames/Variables。F8单步跳过，F7进入函数，F9继续。
6. 熟悉后切换Silver API - Live（先停止Mock）。Live读取本机.env和.env.deepseek，若已配置DeepSeek则按现有预算真实调用；Mock不会调用模型或地图付费接口，两者的回复/合成记忆有明确区分。
7. Silver Worker - Mock为独立的提醒扫描配置，可选；它会处理已确认任务但通知渠道强制Mock，不代表真实手机推送成功。已有Worker运行时不要额外重复启动。

这不是“一键启动数据库/前后端全部进程”的新启动器；这些配置用于直接Run/Debug Python API及可选Worker，网页与MySQL保持现有启动方式。不改变业务模式或正常请求超时。

## 建议断点与变量

| 文件/位置 | 看什么 |
|---|---|
| services/api/app/api/v1/chat.py，send_message中的owned_conversation调用（约192行） | payload.content、payload.client_request_id；会话归属、幂等检查 |
| services/api/app/api/v1/chat.py，generate_reply调用（约245行） | 原消息与待回复已保存，item.id |
| services/api/app/services/model_chat.py，MemoryRetriever().retrieve调用 | 当前用户允许使用的记忆，F8后看retrieved；未授权时此分支不执行 |
| 同文件，prompts = context_messages之后 | selected、task、prompts，查看本轮究竟提供哪些历史与记忆 |
| 同文件，result = model.complete调用附近 | 调用前的上下文；F8越过调用后看result.content/token数 |
| 同文件，parse_envelope调用之后 | envelope、plain_reply，模型返回格式与辅助降级 |
| 同文件，save_task_candidates调用之后 | drafts，提醒草案与缺项；不是已调度通知 |
| 同文件，finally中db.commit之后 | assistant.status/error_code/content、item.memory_status，实际落库结果 |

行号会随代码更新，优先按函数名/语句搜索。settings是配置对象，包含密钥；不要展开/求值get_secret_value或截图分享密钥。prompts与原模型回复含私人内容，只在本机查看，不上传GitHub。

## 不打断点也能看到的阶段

同一条消息按request_id关联：

- context_ready：记忆是否授权、选中条数、是否任务意图、上下文消息数。
- request_persisted：原消息/待回复和用量预留已持久化，reserved_tokens。
- weather_ready：仅天气路径有，搜索状态。
- model_call_started：即将调用当前Provider（Mock也用相同链路）。
- model_call_returned：模型返回输入/输出token数量。
- reply_persisted：回复状态、错误码、记忆状态、耗时及用量。

这些日志不打印聊天正文、记忆正文、Prompt或API Key。要看细节，在断点变量里查看。model_call_started之后没有returned而最后failed，结合error_code定位上游问题；预算/缺Key在调用前失败则不会出现started。

## 断点超时与防止重复扣费

网页原请求超时45秒，断点停太久会让网页先提示网络失败，后端恢复后仍可能完成。此时先F9恢复、刷新读历史，不要连续重发。只有Live实际越过model.complete才会产生真实调用；不要在Evaluate/Watches中执行model.complete、generate_reply、send_message或db.commit，这些都有副作用。重复查看result.content、selected、assistant.status等已有变量不会再次调用模型。

需要长时间单步时优先Mock；也可通过本地API /docs登录并发送请求观察后端，避开H5固定45秒超时，但数据库事务和上游调用仍不宜长时间停住。浏览器前端Vue代码若要断点，使用浏览器开发者工具Sources；本次配置针对Python后端。

## 本次验证

本次配置已解析XML并实际启动模块，临时端口8001避免影响现有8000。Mock真实HTTP登录/发Synthetic消息/保存/读取/幂等通过，五阶段齐全且日志无正文；未执行PyCharm UI中的实际Debug断点操作，不能据此宣称IDE点击验收已通过。

35项模型/助手专项通过；Ruff、安全扫描通过；0新增真实模型调用。证据docs/testing/DEV-01-config-smoke.json，日志logs/dev-01-config-smoke.log及logs/dev-01-pycharm-tests.log。服务模式、数据库结构、既有用户数据不变。临时Mock验证只新增明确Synthetic的Mock会话，不清理真实历史。
