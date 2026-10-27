# T11B：地点核实、路线和天气

状态：LOCAL_VERIFIED_MOCK（待本次commit/push/SHA/CI）。T11A修复67f9235be1c501cc00567b2ed4272ccbea91d345远端一致，CI40442118042全部success。高德Key尚未配置，LIVE_NOT_VERIFIED；不以Mock作为真实出行验收。

## 目标与边界

在既有草案上明确同意位置用途、查询城市和地点、由用户选择具体起终点，再主动请求一轮路线/天气，展示来源、获取时刻、单位及过期/失败状态。不能把“我家/张阿姨家”直接当确定地址，不能默认选第一项。

沿用H5紧凑卡及Python Provider；地图天气不经过DeepSeek，不做额外模型分类。高德Web服务Key仅管理员本机服务端配置，普通用户没有密钥表单；先核查本项目配置存在与否，不扫描其他项目凭据。缺配置用明确Mock完成测试，真实查询仍标待验证。

## 预计实现文件与数据影响

- `app/maps/` Provider/查询服务、`schemas/`与`api/v1/`位置和路线天气合同，现有任务卡/状态及平台网络适配；不重建页面。
- config、`.env.example`、本机配置说明，真实密钥不入库/Git/浏览器/日志。固定高德域名及路径，不接受模型任意URL，注意HTTP库不能记录含query key的URL。
- 新增Alembic保存用户选择的地点、路线天气快照和外部请求/预算登记；具体列与索引随合同测试冻结。现有任务信息与原聊天不删除；只连接本项目双库，开发库只增量升级并核对旧数据。
- 后端Mock/HTTP transport固定响应测试、H5三视口、来源/权限/错误/频控测试、API/运营文档及进度日志。

## 假设、风险和验收

当前H5先明确输入城市/地址并选候选；不强取设备GPS，不从长期记忆偷偷使用家庭地址。出行交通支持现有五类；打车车程只作驾车路线估计，等车等缓冲由T11C另算。天气是行政区/日期预报，超范围或失败必须显示未知，不制造逐分钟确定雨情。

所有外部查询只在显式按钮触发，输入时不自动查；有每账户共享日限、幂等请求与有限有效期快照，无SDK自动重试，额度/未知结果保留。安全与频控必须测试，不能为真实查询反复扣费。

验收包含：拒绝位置用途时零外部请求；歧义地点可选且A/B隔离；路线米/秒与天气日期/来源正确；超时/错误/无数据/超预报范围明确降级；修改草案使旧预览失效；Mock标记可见；三视口真实API联调、增量迁移、适用门禁、commit/push/SHA/CI。T11C再计算出门/提醒时刻、获得新的调度确认并建持久job，本任务不自动安排旧信息草案。

已核验[路线2.0](https://lbs.amap.com/api/webservice/guide/api/newroute)的v5路径/cost/duration秒/distance米/公交citycode字段。旧天气高级文档链接超时，改从官方搜索找到可读的[天气基础文档](https://lbs.amap.com/api/webservice/guide/api/weatherinfo)确认adcode、extensions=all、日期/发布时刻。地点用[POI搜索](https://lbs.amap.com/api/webservice/guide/api/search/)或[完整地址编码](https://lbs.amap.com/api/webservice/guide/api/georegeo)，避免仅输入提示缺少城市码再追加查询；每次选择一种明确搜索模式，最多5候选、无坐标/模糊地区丢弃。官方文档/MockTransport通过不等于Key真实接通。

## 实现与证据

- `app/maps/providers.py/service.py`：Mock/Amap可替换，固定官方端点，无重定向/自动重试，有限响应，坐标/单位/天气日期/发布时刻验证；结果/上下文归属、UUID幂等、15分钟缓存、日限20、未知收据防重启重发。地图不调用DeepSeek。
- Alembic`t11b_maps`：仅给task_drafts增加位置同意/两个地点/预览JSON，新增map_requests/map_budget。开发库原有messages1036、memory_facts180、conversations508、model_usage496、task_drafts44的所有旧列哈希前后一致；`docs/testing/T11B-migration.json`，Alembic check通过，不触碰ALE_AI_MySQL。
- 任务卡折叠MapPreviewPanel、明确用途同意、名称或地址模式、手动选候选、路线天气来源/时刻/Mock标记、错误保留与防重。选完两个地点收起搜索；不重做首页和输入条。修改草案失效旧预览；撤回清理坐标/结果，包括暂不安排后；信息确认不调度。
- 初次后端31例通过，扩展场景时两个测试导入缺失修正（不称产品缺陷）。完整`python scripts/check.py`在新增跨阶段反例前263后端/5扫描器/Ruff/TS/Lint/H5构建PASS，`logs/t11b-check-v2.log`；初轮lint因新测试缺json导入停止，保留日志，修正后才通过。
- `npm run test:ui`：63例/4.4m PASS，360/390/430，`logs/t11b-ui-final.log`。新功能涵盖明确候选/刷新、查询失败保留输入、挂起请求与重复点击只发一次、禁止并行编辑。`docs/demos/T11B-mock-{360,390,430}.png`为Mock截图。
- 追加反例：路线完成后、天气请求前修改草案，旧实现继续调用天气；`logs/t11b-between-queries-red.log`实际失败。修复每个外部阶段重新获取用户锁并核对最初revision/授权，在额度预留前停止过期请求。最终maps34例PASS，`logs/t11b-maps-final.log`；最新代码6项三视口地图复测PASS，`logs/t11b-ui-maps-final.log`；独立测试TypeScript PASS。
- 运营5173/8000用已有Synthetic草案执行`node scripts/smoke-map-preview.cjs`，实际H5选地点/查Mock路线天气/刷新持久化PASS，`docs/testing/T11B-preview.json`、`docs/demos/T11B-operator-mock-390.png`。严格拦截消息发送，新增模型/真实地图请求0；未以DeepSeek页头冒充地图真实。
- 本机`.env.amap`仅空Key、显式Mock；保留已有DeepSeek配置。真实高德/推送/Android仍待准入，当前天气/路线只作Synthetic工程验证；提醒状态始终not_scheduled。
- `docs/testing/T11B-usage.json`只读开发库审计：累计真实DeepSeek仍7次，与T11A相同；真实地图收据0、Key未配置。最终API重新启动，已有预览再次只读刷新核验；版本管理和远端/CI在实际提交后记录，不预先宣称成功。
- 针对高德32位Key赋值补安全扫描规则；合成Key反例原扫描器失败，修复后6项扫描器测试通过（`logs/t11b-amap-secret-red.log/green.log`），空`.env.example`仍允许；没有读取忽略文件或输出真实密钥。原全门禁5扫描器之后的这项增量单独复验。

## 后续与限制

真实高德Key/接口权限、实际地理结果和路线/预报需后续受控样本核验；目前不能证明真实服务可用。不能宣称真正带伞建议/车程已验证或提醒已安排。T11C按CR计算出门/提醒时刻、重新确认并事务调度，缺外部配置可继续Mock；T11D仍需实际Android后台通知。

本次没有改Prompt、固定记忆题集、评分或检索代码，不重新付费LLM联调，不把T10E2旧成绩冒充本任务新测。核心依赖/最终验收目标保持完整。
