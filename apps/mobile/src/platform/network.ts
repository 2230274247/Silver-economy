export class ApiFailure extends Error {
  constructor(public code: string, message: string, public status = 0) { super(message); }
}

// The one-click dev launcher allows time at Python breakpoints. Builds retain 45s.
const devTimeout = Number(import.meta.env.VITE_DEV_REQUEST_TIMEOUT_MS);
const requestTimeout = import.meta.env.DEV && Number.isInteger(devTimeout)
  && devTimeout >= 45000 && devTimeout <= 600000 ? devTimeout : 45000;

export function request<T>(path: string, method: 'GET' | 'POST' | 'PATCH' | 'DELETE' = 'GET', data?: object): Promise<T> {
  return new Promise((resolve, reject) => {
    uni.request({
      url: `/api/v1${path}`,
      // uni-app's typings lag the H5 runtime, which supports PATCH.
      method: method as unknown as 'GET',
      data,
      withCredentials: true,
      timeout: requestTimeout,
      success(response) {
        if (response.statusCode >= 200 && response.statusCode < 300) {
          resolve(response.data as T);
        } else {
          const body = response.data as { error?: { code?: string; message?: string } };
          reject(new ApiFailure(body.error?.code ?? 'REQUEST_FAILED', body.error?.message ?? '请求失败，请重试', response.statusCode));
        }
      },
      fail() { reject(new ApiFailure('NETWORK_ERROR', '网络连接失败，请检查服务后重试')); },
    });
  });
}
