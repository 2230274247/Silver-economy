export interface PushCapability {
  supported: boolean;
  platform: string;
  reason: string;
}

export interface PushPermissionResult {
  granted: boolean;
  clientId: string | null;
  message: string;
}

type PushUni = typeof uni & {
  getPushClientId?: (options: {
    success: (result: { pushClientId?: string; cid?: string }) => void;
    fail: (error: unknown) => void;
  }) => void;
  requestPushPermission?: (options: {
    success: (result: { granted?: boolean }) => void;
    fail: (error: unknown) => void;
  }) => void;
};

export function pushCapability(): PushCapability {
  // #ifdef APP-PLUS
  const platform = uni.getSystemInfoSync().platform;
  return {
    supported: platform === 'android',
    platform,
    reason: platform === 'android'
      ? 'Android 原生通道可用，仍需配置厂商推送参数和签名包。'
      : '当前原生平台不支持本项目 V0.1 的 Android 推送验收。',
  };
  // #endif
  // #ifndef APP-PLUS
  return {
    supported: false,
    platform: 'h5',
    reason: 'H5 只能作页面与接口验证，不能登记为 Android 后台通知设备。',
  };
  // #endif
}

function clientId(api: PushUni): Promise<string> {
  return new Promise((resolve, reject) => {
    if (!api.getPushClientId) {
      reject(new Error('当前构建未启用 uni-push 客户端模块。'));
      return;
    }
    api.getPushClientId({
      success(result) {
        const payload = result as unknown as Record<string, string | undefined>;
        const value = payload.pushClientId ?? payload.cid ?? '';
        if (value) resolve(value);
        else reject(new Error('推送服务未返回设备标识。'));
      },
      fail() {
        reject(new Error('无法取得推送设备标识，请检查推送模块和网络。'));
      },
    });
  });
}

export async function requestAndroidPushAccess(): Promise<PushPermissionResult> {
  const capability = pushCapability();
  if (!capability.supported) {
    return {
      granted: false,
      clientId: null,
      message: capability.reason,
    };
  }
  // #ifdef APP-PLUS
  const api = uni as PushUni;
  try {
    const pushClientId = await clientId(api);
    if (api.requestPushPermission) {
      const permission = await new Promise<boolean>((resolve, reject) => {
        api.requestPushPermission?.({
          success(result) { resolve(result.granted === true); },
          fail() { reject(new Error('系统通知权限请求失败。')); },
        });
      });
      if (!permission) {
        return {
          granted: false,
          clientId: null,
          message: '通知权限未允许。离开应用后可能无法收到提醒。',
        };
      }
    }
    return {
      granted: true,
      clientId: pushClientId,
      message: '设备已取得推送标识；实际后台送达仍需真机验收。',
    };
  } catch (error) {
    return {
      granted: false,
      clientId: null,
      message: error instanceof Error ? error.message : '推送设备初始化失败。',
    };
  }
  // #endif
}
