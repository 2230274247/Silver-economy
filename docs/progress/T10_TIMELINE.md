# T10：有来源的回忆时间线

开发/本地验证：2026-10-27 00:00–00:08 +08:00；最终状态/运行环境复核：04:17:22 +08:00（Asia/Hong_Kong）。本次commit/push/SHA/CI在提交后确认。
前项T09 `2ce30e51ede2d7f901eb233b5f17f1ef21908f33`，2026-10-26 23:56:30 +08:00；远端一致，CI40354267818 api/security/mobile全部success。

## 范围与实现

把已有真实L1事实及其L0来源组织成按时间查看的事件视图；默认记忆列表、现有风格和控制能力保留。没有调用模型生成故事，没有补写未知经历或日期，没有新增摘要副本/缓存。

- `app/memory/timeline.py`：本人/模式/软删除/有实际原文来源的SQL过滤，发生时间优先、未知用记录时间排序；事件时间/记录时间/ID的稳定游标，来源数批量查询，避免每行查询。
- `api/v1/memories.py`、`schemas/memory.py`及`docs/api/openapi.json`：GET `/api/v1/memories/timeline`，limit 1–100（默认30）、before_id；返回items/next_cursor，MemoryOut加event_label/source_count。未知、其他用户、模式不符或已删除的游标404。
- `apps/mobile/src/pages/timeline/index.vue`：记忆列表/按时间查看、年份/月/日期精度与来源数、记录时间，复用原文与纠错控制。搜索切回列表；模式切换清除旧结果，失败可重读。纠错重取当前排序；删除重取游标，避免已删除锚点导致下一页错误。
- `test_memory_timeline.py`、`timeline.spec.ts`：时间精度/来源/分页/模式/隔离/纠错删除与三尺寸真实H5→API→MySQL回归。

数据库影响：无新增表、列、数据迁移或复制；现有`t09_update`仍为head。事件视图从已持久化事实和来源即时派生，纠错/删除直接生效，不存在待清理的旧摘要索引。`life_events`的高级聚合/长期叙事总结仍为可扩展项，不冒充已经生成；最终目标3.1明确允许L2进一步扩展。

月份/年份用日历锚点参与排序，界面只显示原精度；这不意味着确认了某一天或不同粗粒度记录的精确先后关系。“发生时间未明确”单独标示，不能把记录时间当成发生时间。

## 实际执行与结果

1. 项目Python，`services/api`执行`python -m pytest tests/test_memory_timeline.py -q`：5 passed，4.26s。
2. 根目录`python scripts/check.py`：134 passed，51.50s；5扫描器单测、安全/YAML/Ruff/format/TS/lint/H5 build/diff全通过，`logs/t10-check.log`。只有既有Starlette/httpx弃用提示。测试库迁移回退/再升级及metadata check同样通过。
3. `apps/mobile`执行`npm run test:ui`：45 passed，2.4m；`logs/t10-ui.log`。保留原42用例，加360/390/430时间线失败重试、未知时间、用户修改年份、分页显示/来源与删除验证，首轮整套通过。
4. 正在运行的运营H5 `http://127.0.0.1:5173/#/`：用既有演示账号只读查看2条Synthetic持久记录，浏览器阻断任何POST消息，实际发送0；显示事件时间/来源/控制正确。日志`logs/t10-persisted-view.log`，截图`T10-persisted-data-390.png`已视觉检查。
5. Mock截图`docs/demos/T10-timeline-mock-360/390/430.png`，390已检查：2019年仍是年份，不显示虚构的1月1日；原始聊天和用户修改的不同依据明确保留。
6. 04:16再次HTTP readyz为ready/t09_update；本机预览仍运行。时间线新建期间真实DeepSeek回执0，项目总回执仍6；`docs/demos/T10-validation.json`。自动测试Mock，不增加费用。

后端5项覆盖：年月/未知与记录时间不同、同一锚点7条limit2分页无重漏、A/B游标/已删除/无来源/Mock-live隔离、修改年份和删除立即反映、两个真实来源计数不重复。

## 演示与限制

登录→我的回忆→按时间查看→查看来源/返回原会话。可在同一卡纠错、失效或删除，时间线重新读取当前结果。刷新仍从MySQL读取；点击已保存数据不会调用DeepSeek，发送新聊天会走既有额度门禁。

本任务不证明万级性能或普遍语义准确率。下一项T10E1：独立测试库Synthetic参数化100/1000/10000生成与导入；然后T10E2固定至少200题、客观HTML/JSON与并发/资源报告。CR-001高德、确定性调度和Android真机通知仍需继续，不能宣布V0.1整体完成。

## 事后远端核验（T10E1固化）

2026-10-27 04:18:47 +08:00提交 `d7572f9b6f0f2b1c71e5db507bec126ebdc22fb8`，push/远端SHA一致；CI40394518915 api/security/mobile全部success。
