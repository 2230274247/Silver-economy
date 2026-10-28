# CHAT-05 共用聊天链路空回复与引用误拦截修复

时间：2026-10-27T16:23:08+08:00（Asia/Hong_Kong）。用户要求泛化修复所有聊天，而不是只修截图中的单条请求。范围：所有走DeepSeekProvider的普通聊天、记忆聊天、天气生成、提醒对话；不增加第二次抽取调用或自动付费重试。

## 根因与证据

1. 截图对应旧请求为MODEL_EMPTY_RESPONSE，实际922输入/44输出token，管理员输出上限1024。不是配额不足或输出达到上限。没有正文，不能凭空恢复。CHAT-04仅分类了错误，未移除触发路径。
2. 项目在启用长期记忆或任务时，对每次生成强制设置response_format=json_object。DeepSeek官方文档明确说明JSON模式可能返回空内容：https://api-docs.deepseek.com/guides/json_mode/ 。因此该模式是有官方证据的触发风险；不能从单次记录断言它是上游所有空回复的唯一原因。
3. 第一次本轮真实Synthetic联调已不空，正常生成99输出token的自然reply，但模型凭空附上M1（当前根本没有提供记忆来源）。MEMORY_UNSUPPORTED_REFERENCE又把完整聊天清空。这个新现场反例促成引用层的进一步解耦，而不是把首轮失败藏掉。

## 实现方案与边界

- DeepSeekProvider统一使用默认text传输，不再强制json_object。既有Prompt仍指导输出reply/memories/memory_refs/outings，同一请求中抽取，不增加调用次数。保留thinking disabled、token上限、超时、日预算、幂等以及未知结果不自动重试。
- 共用parse_envelope兼容JSON对象与完整Markdown JSON围栏。模型返回正常自然语言时保留原文；记忆状态failed_schema、用量completed_partial，明确本次辅助提取未完成。任务自然语言没有有效草案时，明确未安排通知；不虚构卡片或后台job。破损JSON仍不得把字段原样泄露为聊天。
- 错误引用格式/未知编号跳过引用，不能据编号访问任何新记录。只有从本人已授权检索结果选择的真实标签才可生成MemoryUse。未知引用登记MEMORY_REFERENCE_IGNORED/partial，不再清空自然回复。
- 所有已提供给模型的记忆，不论模型是否正确附编号，都在显示前重新检查归属、授权状态、删除/失效与证据版本。撤回/变更保护仍可拒绝展示，防止用降级绕过真实隐私撤回；不是放开跨用户数据。
- 空回复日志仅记录实际模型、finish_reason和token数，不记录对话、原始HTTP正文或密钥。若上游完全无正文/网络故障，仍诚实报告失败；不能保证第三方永远可用，也不能以硬编码话术伪装DeepSeek成功。
- 无数据库迁移，没有修改既有用户聊天、原raw或失败回执；没有访问ALE_AI_MySQL。

## 实际命令与结果

在services/api执行：

../../.venv/Scripts/python.exe -m pytest -q tests/test_chat_assistant.py tests/test_models.py tests/test_task_drafts.py tests/test_memory_extraction.py tests/test_memory_retrieval.py tests/test_memory_updates.py --tb=short

初轮153通过，引用误拦截修正后160通过（logs/chat-05-final.log）。最终将“全体提供的记忆重检”固定为共用行为后，额外只复核引用/撤回相关10项（logs/chat-05-reference-final.log），不重复无关全套测试。

覆盖：四入口均不发送response_format；围栏JSON解析；普通分享、相对提醒与自然语言降级；错误引用形态与未知编号不生成来源记录；刷新保留；幂等不重复调用；B无法读A；有真实记忆标签/纯文本/错误标签的生成期间纠错、删除和撤回均阻断旧内容。Ruff检查/格式、安全扫描通过。前端无代码改动，不重复TS/H5全构建；真实H5页面另有实测。

## 两次真实调用与保留的失败

仅执行本机ignored .cache/chat-05-live.cjs及第二个未发送样本的单次续跑；持久guard禁止重发首条或第三次调用。全部明确标Synthetic，不把合成事项当真实个人事实。

- 第1条普通分享：模型正常输出，但旧引用层拒绝；失败和原usage/raw保持。以保存结果离线分析，当前过滤引用的反例已进入回归，没有重发付费请求。不能把这条原失败回执改写为真实通过。
- 第2条半小时提醒：最终实现下真实DeepSeek completed，81字符可见回复、1条待核对草案、target_at精确为原消息+1800秒、not_scheduled、刷新后持久存在。没有按确认调度，也没有触发真实通知。
- 合计1409输入/211输出tokens；估算USD0.00067590（非账单），搜索0，自动重试0。第一条484/99、第二条925/112；见docs/testing/CHAT-05-usage.json。
- 页面证据docs/demos/CHAT-05-live-390.png；逐次状态docs/testing/CHAT-05-live.json（首轮失败明确保留）。脚本和凭据不上传；截图仅本次Synthetic草案，已视觉检查。

## 交付与未验收

本次针对共有链路修复，不能从两条付费样本外推为第三方故障率0。普通分享最终路径由离线回归和原结果重解析验证，没有额外付费重跑。复杂损坏输出、上游网络/空响应仍可能诚实失败；不增加扣费重试，不称永不失败。真实高德、Android后台通知及其他V0.1开放验收保持。

CHAT-04提交9a87657ddbd31b9687505eea7b8e44c8ac2f7853的两个CI40471287566/40471293311均success。本次修复仅推dev/v0.1，保留历史，SHA/远端/CI提交后核对。
