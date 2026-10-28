# CHAT-02 自然聊天、联网天气与管理员

时间：2026-10-27T15:23:05+08:00（Asia/Hong_Kong）。用户展示义乌天气、模型名拒绝和会议空模板问题，并要求独立管理员。

## 目标与实现

- 普通对话和任务路径都保留DeepSeek reply，任务卡另承载缺项/确认/调度状态；不再用draft_reply固定模板覆盖整条模型回复。草案仍不能冒充已调度，追加明确确认提示并清理虚假执行承诺。
- 记忆检索后最多5条/12KB选上下文，DeepSeek根据当前问题决定是否有必要提起并返回实际来源引用。日程路径也可参考相关记忆，但记忆地址不能自动当成已确认出发地或目的地。
- 公开模型名称/当前时区日期进入公共模型上下文，不再把“你用什么模型”当敏感配置。密钥、内部提示和他人信息继续保护。
- 通过DeepSeek官方Search API按需搜索天气，沿用既有后端Key，不要求新地图Key。只发送用户明确城市/目标日期形成的查询，不发送检索到的个人记忆；缺城市追问，后续城市回答沿用先前目标日期。查询失败/余额不足/额度不足不伪造天气。
- 联网资料有限截断，附来源/日期/查询时间后交给原DeepSeek模型组织自然回复；来源可展开点击。网页搜索参考不等于高德正式天气/路线快照，不把旧预报当实况。
- 新增独立admin账号，role只由本机运维脚本创建，普通登录不能自授予管理员。默认100请求/200000预留tokens/1024输出tokens，独立管理员预算池；可通过ADMIN_DAILY_REQUEST_LIMIT/ADMIN_DAILY_TOKEN_LIMIT/ADMIN_MAX_OUTPUT_TOKENS调整。不是无限消费或权限绕过。
- 管理员设置页显示实际模型/联网开关/额度/已用次数；不公开API Key。普通用户10次/20000的既有池保留，与管理员分开。
- 加法迁移t14_chat_assistant：users.is_admin、messages.search_context、admin_model_budget；原数据/分支/历史保留。用户导出包含本人的联网来源。

## 官方依据与成本

官方文档https://api-docs.deepseek.com/guides/search/确认Search为POST /v1/tools/search，与模型API使用同一Bearer Key。聊天API不会因只调用/chat/completions就自动具备官网所有工具；本次明确接了天气搜索。
官方公布Search单价USD0.75/1000次成功有结果请求；服务可能存在当前免费期/账户差异，本项目按每成功请求USD0.00075保守估算，不称实际账单。每次天气最多一次搜索+一次模型生成，无自动重试，相同消息编号复用原回复，不重复扣费。两次请求都计入本角色共享MySQL预算；管理员不会借普通池越限。

## 实际验证

- 102项相关后端通过，1项会议“开个会”反例失败后修复；随后39项草案/权限/导出专项、59项抽取/更新专项、最终4项新功能/隔离/追问/幂等专项通过。
- 首轮6项失败来自前一恢复演练遗留的Synthetic数据与旧测试的全表计数；将既有可丢弃测试库迁移往返先执行后消除，没有删除测试。实际会议“开个会”漏识别单独修正，失败日志保留。
- 固定310题、100事实档实际SQL/Mock复测：Recall@5/Top1/Mock回答/Mock冲突100%，零跨用户/删除召回/接口错误，检索P95 146.615ms。题集不变，新增真实调用0；既有万级报告保留，本次未重复所有规模。
- 实际H5管理员登录→“今天义乌的天气怎么样？另外，你用的是什么模型？”→官方Search→DeepSeek→MySQL→刷新完成。1353输入/117输出tokens，模型管线2844ms（含搜索），搜索781ms；估算模型USD0.00054630+搜索USD0.00075000，非账单。
- 只做1次模型生成+1次搜索。首轮浏览器文本断言因空白归一化失败，未重发；改为读取已保存API原文逐字比对和页面来源/管理员状态检查，0新增付费调用。不能把这次辅助断言失败写成模型失败。
- TypeScript/ESLint/H5 build及Ruff/格式通过。只执行相关必要验证，不重复整套本地UI。
- 证据：testing/CHAT-02-live.json、CHAT-02-usage.json，demos/CHAT-02-weather-live-390.png、CHAT-02-admin-390.png，testing/memory-eval-v1/chat-v4-100-verified.json/html。详细本机日志logs/chat-admin-focused-final.log、chat-admin-final.log、chat-v4-extraction.log、chat-admin-final-four.log、chat-v4-evaluation.log。

## 使用与未验收边界

刷新H5，退出旧demo账号，登录admin。随机密码仅本机.cache/admin-account.json；真实Key仍仅.env.deepseek，未写Git或普通用户界面。
管理员并不自动读取其他账户的私有聊天/记忆/任务；模型回复仍不能替代用户确认真实调度。天气搜索是目前已接通的工具，任意通用联网检索、上传文件、语音等官网能力不因使用同一模型自动具备；复杂城市/日期表达仍需补充验证。
高德路线/天气的正式Provider仍Mock，Android后台送达和原生权限仍待验收；本次天气搜索不能替代CR-AC10或高德路线验收。完整V0.1不据此标全完成。
本提交SHA、push与CI在实际提交后核验，不预填成功。
