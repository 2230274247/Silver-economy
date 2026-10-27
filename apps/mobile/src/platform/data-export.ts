function exportFilename(disposition: string | null): string {
  const match = disposition?.match(/filename="?([^";]+)"?/i);
  return match?.[1] || 'silver-memory-data.json';
}

// #ifdef H5
async function downloadH5Export(): Promise<void> {
  const response = await fetch('/api/v1/account/export', {
    credentials: 'include',
    cache: 'no-store',
  });
  if (!response.ok) throw new Error('数据导出失败，请重新登录后再试');
  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = objectUrl;
  anchor.download = exportFilename(response.headers.get('content-disposition'));
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
}
// #endif

// #ifndef H5
function downloadNativeExport(): Promise<void> {
  return new Promise((resolve, reject) => {
    uni.downloadFile({
      url: '/api/v1/account/export',
      success(result) {
        if (result.statusCode !== 200) {
          reject(new Error('数据导出失败，请重新登录后再试'));
          return;
        }
        uni.saveFile({
          tempFilePath: result.tempFilePath,
          success(saved) {
            uni.showModal({ title: '导出完成', content: `文件已保存到：${saved.savedFilePath}`, showCancel: false });
            resolve();
          },
          fail() {
            reject(new Error('导出文件保存失败，请检查设备存储空间'));
          },
        });
      },
      fail() {
        reject(new Error('网络连接失败，数据未导出'));
      },
    });
  });
}
// #endif

export function downloadAccountExport(): Promise<void> {
  // #ifdef H5
  return downloadH5Export();
  // #endif
  // #ifndef H5
  return downloadNativeExport();
  // #endif
}
