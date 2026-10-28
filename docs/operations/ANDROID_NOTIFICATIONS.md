# Android 通知、设备登记与推送桥接

日期：2026-10-27（Asia/Hong_Kong）。状态：工程合同与 Mock 测试已完成，真实 Android 后台通知为 `BLOCKED_PROVIDER_CONFIGURATION`，尚未验证手机送达。

## 已实现的边界

- H5 只显示页面和调用后端，不能登记为 Android 设备。
- Android 平台适配器通过 `uni.getPushClientId` 取得推送标识；用户拒绝权限时传 `denied`，页面必须提示离开应用后可能收不到提醒。
- `POST /api/v1/notification-devices` 只接收已登录用户本人的设备。推送标识由服务端 Fernet 加密保存，另以带密钥 HMAC 生成设备指纹；公开 API 不返回密文、指纹或完整客户端 ID。
- 同一物理设备改绑其他账户时，服务端先撤销旧账户的绑定；`DELETE /api/v1/notification-devices/{id}` 只允许本人撤回。
- Worker 领取到期 job 时只选择当前用户、未撤销且权限为 `granted`/`provisional` 的最近活跃设备，并把 `device_id` 持久绑定到该次发送尝试。
- 无可用设备时不调用桥接、不生成成功回执，并记录 `NO_ACTIVE_DEVICE`。

## 本机配置

真实设备标识加密密钥只放在项目根目录受 Git 忽略的 `.env.notifications`，不得写入前端、日志、命令参数或聊天：

```dotenv
NOTIFICATIONS_PROVIDER=unipush_bridge
NOTIFICATION_DEVICE_ENCRYPTION_KEY=
UNI_PUSH_BRIDGE_URL=https://operator-owned.example/push
UNI_PUSH_BRIDGE_TOKEN=
```

生成加密密钥时只输出到本机安全配置入口：

```powershell
.\.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

`UNI_PUSH_BRIDGE_URL` 必须为 HTTPS；桥接令牌只由 Python Worker 放在 Authorization 头。默认 `NOTIFICATIONS_PROVIDER=mock`，Mock 只是 outbox 合同，不能证明任何设备收到。

## 桥接合同

Worker 只发送最少内容，不把任务标题、地址、健康或聊天原文放进锁屏通知：

```json
{
  "client_id": "server-decrypted device push ID",
  "request_id": "notification job idempotency key",
  "notification": {
    "title": "时光有声提醒",
    "body": "您有一项已确认的行程提醒，点按查看详情。",
    "data": {
      "route": "/pages/reminders/index",
      "outing_task_id": "opaque task id"
    }
  }
}
```

桥接成功返回 `{"message_id":"provider id"}`。HTTP 429/5xx 可作为暂时失败有限重试；明确 4xx 不接受；超时/连接中断进入 unknown，不盲目重发。服务商接受仅记为 `submitted_to_provider`，不等于 `delivered`。

## 当前外部阻塞与真机验收前置

2026-10-27 本机审计结果：

- `adb`、`java`、`gradle`、`keytool` 均不在 PATH；
- `ANDROID_HOME`、`ANDROID_SDK_ROOT`、`JAVA_HOME`、`HBUILDERX_HOME` 均未设置；
- 已检查的 HBuilderX 常见安装路径均不存在；
- 前端未安装 uni-app app-plus 构建依赖，`manifest.json` 的 DCloud `appid` 为空；
- 未发现推送应用配置或已连接的真实 Android 设备。

因此没有生成或伪造 APK，也没有填写 AppID、厂商通道、签名或服务器凭据。完成 CR-AC10 还需要运营方在本机配置 DCloud AppID、Android 包名/签名、uni-push 厂商参数、HTTPS 桥接与设备加密密钥，并提供一台允许通知权限的 Android 真机。验收时必须保留合成任务、设备/包版本/系统、实际观察时间以及对应 job 的受限证据。
