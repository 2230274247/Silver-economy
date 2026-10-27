# T11D：Android 设备登记与推送桥接

状态：IMPLEMENTED_BLOCKED_PROVIDER_CONFIGURATION。设备与桥接工程合同已完成测试；本机缺 Android SDK/HBuilderX/AppID/厂商推送配置/真机，CR-AC10 尚未通过，不能宣称后台通知已交付。

## 完成内容

- 增量迁移 `t11d_devices` 新增 `notification_devices`，并给 `notification_jobs.device_id` 增加同用户复合外键。
- 新增设备登记、列表、逐人撤回、通知记录和通知能力状态 API。推送客户端 ID 使用 Fernet 加密，HMAC 指纹用于服务端识别；响应不含密文、指纹或完整客户端 ID。
- 同一设备改绑其他用户时撤销旧归属。Worker 发送前只选本人当前有效设备，并把选中设备绑定到 job。
- 新增 `unipush_bridge` Provider：HTTPS、Bearer 鉴权、固定最小通知内容、请求幂等键、无重定向、超时、明确/暂时失败与未知结果边界。
- Android 平台适配器封装 `uni.getPushClientId` 与权限请求；H5 明确返回不支持设备后台推送。`manifest.json` 声明 Android 13 `POST_NOTIFICATIONS`，但未伪造 DCloud AppID、厂商参数或签名。

## 测试

- `pytest -q tests/test_notifications.py tests/test_scheduling.py`：11/11 通过。
- `pytest -q tests/test_database.py tests/test_notifications.py`：10/10 通过，含空库升级/降级/再升级和新表检查。
- `scripts/check.py`：安全、工作流、Ruff、275 后端测试、前端 typecheck/ESLint/H5 build 全部通过；保留一条既有 Starlette/httpx 弃用警告。
- 专项验证了加密存储、公开响应不含客户端 ID、跨用户撤回拒绝、设备改绑撤销、denied 设备不发送、桥接只接收服务端解密 ID、最小化通知正文、无设备时 `NO_ACTIVE_DEVICE`、用户通知列表隔离。
- 自动测试未调用真实 DeepSeek、高德、uni-push 或 Android 网络；真实 Android 实际送达 0。

## 环境审计

`adb`、`java`、`gradle`、`keytool`、`ANDROID_HOME`、`ANDROID_SDK_ROOT`、`JAVA_HOME`、`HBUILDERX_HOME` 均未发现；常见 HBuilderX 安装路径不存在；`@dcloudio/uni-app-plus` 未安装；DCloud `appid` 为空。详细配置和桥接合同见 [ANDROID_NOTIFICATIONS.md](../operations/ANDROID_NOTIFICATIONS.md)。

## 未完成与下一项

T11D 的工程实现已完成，但真实后台通知仍为 `BLOCKED_PROVIDER_CONFIGURATION`。下一项 T11E 继续实现行程详情、修改/出发/完成、导航入口及通知状态回看，可在 Mock/合同层推进；不得把 T11E 页面结果升级为真机证据。
