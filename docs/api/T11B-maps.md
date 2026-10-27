# T11B：位置用途、地点选择与路线天气

2026-10-27，所有私有接口取登录身份，不接受user_id、任意供应商URL、用户提交的坐标/车程/天气。跨用户资源404。模型不直接调用这些接口。

| 接口 | 输入/输出与行为 |
|---|---|
| GET /api/v1/maps-status | 只读配置，provider=disabled/mock/amap、configured；live_connection_verified=false表示本接口不主动探测外部连接，不能用配置存在宣称已连通 |
| POST /task-drafts/{id}/location-consent | expected_revision、enabled；本次草案的位置用途单独同意。撤回清除所选坐标、预览及该草案全部查询缓存结果/上下文，原始聊天/草案文字仍保留；暂不安排后仍可撤回 |
| POST /task-drafts/{id}/places/search | expected_revision、client_request_id(UUID)、field(origin/destination)、query(2–100)、city(2–40)、search_kind(poi/address)。返回query_id、最多5条有坐标/行政区的候选、来源/时间/有效期；不默认选第一项 |
| POST /task-drafts/{id}/places/select | expected_revision、field、query_id、candidate_id；只选当前用户/草案/字段的未过期结果；文字或模式已改变则409，客户端不能伪造坐标 |
| POST /task-drafts/{id}/map-preview | expected_revision、client_request_id；需未来时刻、时间含义、交通及两个明确所选地点。保存路线/天气快照，不增加草案信息revision，不创建调度 |

编辑或聊天补充会清除旧预览；地点文字改变还会清除对应坐标。候选选择使草案重新待核对；信息确认只推进元数据修订，不假装提醒已安排。快照返回draft_revision、expires_at及读取时expired标记；T11C必须再次验证有效期并另获调度确认。

地图查询收据MapRequest记录本人草案、幂等键/操作、条件指纹、状态/耗时及规范化结果，不含Key。相同UUID/操作/条件复用原结果，换条件复用UUID拒绝409。15分钟内本人同草案同条件复用缓存；只读/缓存不耗外部额度。保留reserved/unknown，重启后不盲目重发；失败缓存期间不反复扣费。每个外部阶段都重新锁定用户并核对原版本/授权，路线后已修改则停止天气查询。

高德共享香港日限默认20次，每次真实HTTP前持久预留。DeepSeek预算独立且本模块没有模型调用。一次地点搜索1次外部请求，一轮预览最多路线+天气各1次；路线失败不再查询天气。Mock为固定Synthetic，外部请求0。

路线distance_m单位米、duration_seconds单位秒，v5需show_fields=cost；打车用驾车估计，不含等车。公交需citycode，缺失时在外部调用前拒绝。路线为查询时条件参考，不伪装未来路况/班次预测。天气用目的地区域adcode和目标日期匹配实际返回预报，注明reporttime；超范围/过旧/失败显示未知，不编造带伞结论。

AMapProvider固定官方HTTPS端点、拒绝重定向、响应上限512KiB、超时8秒（HTTP阶段）、无自动重试；供应商错误正文和含Key的URL不输出。抑制httpx/httpcore请求URL日志，应用只记录请求ID/状态/耗时。Key只在忽略的本机.env.amap中由管理员配置。

合同和HTTPTransport测试不等于真实供应商验证；当前真实高德仍LIVE_NOT_VERIFIED。依据：[POI搜索](https://lbs.amap.com/api/webservice/guide/api/search/)、[地址编码](https://lbs.amap.com/api/webservice/guide/api/georegeo)、[路线2.0](https://lbs.amap.com/api/webservice/guide/api/newroute)、[天气](https://lbs.amap.com/api/webservice/guide/api/weatherinfo)。
