import { expect, test } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { login } from './helpers';

test('settings explains authorization scope and exports only the current account', async ({ page }, info) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await login(page);
  await page.getByRole('button', { name: '打开个人设置' }).click();

  await expect(page.getByText('个人设置', { exact: true })).toBeVisible();
  await expect(page.getByText('位置只在你为本次出行草案明确开启后', { exact: false })).toBeVisible();
  await expect(page.getByText('当前没有已登记的 Android 通知设备。H5 页面不能替代 Android 后台通知验收。')).toBeVisible();
  await expect(page.getByText('编辑、删除尚未开放')).toHaveCount(0);

  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: '导出我的数据', exact: true }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/^silver-memory-data-\d{8}-\d{6}\.json$/);
  const downloadPath = await download.path();
  expect(downloadPath).not.toBeNull();
  const payload = JSON.parse(fs.readFileSync(downloadPath!, 'utf8'));
  expect(payload.schema_version).toBe('silver-memory-export/v1');
  expect(payload.account.login_name).toBe('ui_a');
  expect(payload.data).toEqual(expect.objectContaining({
    conversations: expect.any(Array),
    messages: expect.any(Array),
    memories: expect.any(Array),
    outing_tasks: expect.any(Array),
    notification_devices: expect.any(Array),
  }));
  expect(JSON.stringify(payload)).not.toContain('password_hash');
  expect(JSON.stringify(payload)).not.toContain('push_client_id_ciphertext');
  await expect(page.getByText('数据已导出')).toBeHidden({ timeout: 5_000 });
  await page.screenshot({ path: path.resolve(`../../.cache/ui-regression/privacy-${info.project.name}.png`) });

  await page.getByRole('button', { name: '管理记忆和来源', exact: true }).click();
  await expect(page.getByText('值得记住的，都在这里。', { exact: true })).toBeVisible();
  expect(errors).toEqual([]);
});

test('revoking a notification device calls the owner-only device endpoint', async ({ page }) => {
  await login(page);
  let deleteCalled = false;
  const device = {
    id: 'synthetic-device',
    platform: 'android',
    permission_status: 'granted',
    app_version: '0.1.0-synthetic',
    device_label: 'Synthetic Android',
    can_receive: true,
    last_seen_at: '2026-10-27T05:00:00+00:00',
    revoked_at: null,
  };
  await page.route('**/api/v1/notification-devices', async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items: [device] }),
    });
  });
  await page.route('**/api/v1/notification-devices/synthetic-device', async route => {
    expect(route.request().method()).toBe('DELETE');
    deleteCalled = true;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ...device,
        revoked_at: '2026-10-27T05:05:00+00:00',
        can_receive: false,
      }),
    });
  });

  await page.getByRole('button', { name: '打开个人设置' }).click();
  await expect(page.getByText('Synthetic Android', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: '撤回', exact: true }).click();
  await expect(page.getByText('撤回这台设备', { exact: true })).toBeVisible();
  await page.getByRole('dialog', { name: '撤回这台设备' }).getByRole('button', { name: '撤回', exact: true }).click();
  await expect(page.getByRole('button', { name: '已撤回', exact: true })).toBeDisabled();
  expect(deleteCalled).toBe(true);
});
