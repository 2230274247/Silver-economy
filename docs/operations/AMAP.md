# 高德后端配置与额度

本机管理员入口：项目根目录`.env.amap`，受Git忽略。普通用户界面不填写Key，不向聊天发送Key，不放Vue、浏览器环境变量、命令行参数或截图。`.env.example`仅空字段。首次未配置默认disabled；本机演示文件显式mock，结果全标Mock/Synthetic。

```dotenv
MAPS_PROVIDER=mock
AMAP_WEB_SERVICE_KEY=
AMAP_DAILY_REQUEST_LIMIT=20
```

真实查询由管理员在本机填写高德Web服务类型Key、核实所需接口权限/账户配额及使用许可，然后将MAPS_PROVIDER改为amap并重启API。配置存在不等于连通，只有实际成功收据/受控H5演示才能确认相应接口。未配置/被拒绝不会自动降为假装真实的Mock。禁止绕过权限、采购配额或付费部署。

每个香港日全账户共享20次真实HTTP上限；设0可停用真实查询。一次搜索调用1次；一次预览至多路线和天气各1次，路线失败不追加天气。相同幂等请求不重发，15分钟同条件缓存不占新配额。reserved/unknown预留不自动退还，崩溃/超时不盲目重试；先核对服务商记录。这里只统计请求数，未取得账户单价，不填虚假0费用。

地点、坐标只从本人明确选择的服务端候选取；用户同意后才发出具体查询。拒绝/撤回时不调用外部服务，撤回清理坐标和查询结果；原聊天和草案文字仍保留。无需设备GPS，不偷偷读长期记忆中的家庭地址。更全面的数据删除/导出在T12完成。

自动测试：pytest强制MAPS_PROVIDER=mock并拒绝真实HTTP，Provider合同使用httpx.MockTransport；Playwright独占5174/18000 Mock服务与ui_a/ui_b，不注入Key。运营H5为5173/8000，界面模式标注不混淆真实DeepSeek与Mock地图。

`node scripts/smoke-map-preview.cjs`仅接受Mock地图，用已有Synthetic任务草案通过H5选地点/预览/刷新，拦截所有发送消息POST，新增模型/真实地图调用0。首次有持久标记防止覆盖未知位置工作；再次只读验证，不重复查询。真实高德需单独受控样本，目前尚未验证，不能用该脚本替代live验收。

证据和功能范围见`docs/progress/T11B_MAP_WEATHER.md`；信息确认/路线快照均not_scheduled。建议出门时间、提前提醒与持久Worker仍待T11C，Android真机通知待T11D。
