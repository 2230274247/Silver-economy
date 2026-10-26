export class ApiFailure extends Error {
  constructor(public code: string, message: string, public status = 0) { super(message); }
}

export function request<T>(path: string, method: 'GET' | 'POST' | 'DELETE' = 'GET', data?: object): Promise<T> {
  return new Promise((resolve, reject) => {
    uni.request({
      url: `/api/v1${path}`,
      method,
      data,
      withCredentials: true,
      timeout: 45000,
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
