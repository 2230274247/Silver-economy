import { test, expect } from '@playwright/test';
import path from 'node:path';
import { accounts, freshChat, login } from './helpers';

async function resetConsent(page: import('@playwright/test').Page) {
  for (const account of accounts) {
    expect((await page.request.post('/api/v1/auth/login', { data: { login_name: account.login_name, password: account.password } })).ok()).toBe(true);
    expect((await page.request.post('/api/v1/memory-consent', { data: { enabled: false } })).ok()).toBe(true);
  }
}
test.beforeEach(async ({ page }) => { await resetConsent(page); });
test.afterEach(async ({ page }) => { await resetConsent(page); });

test('relogin and new chat retrieve sourced memory; search and user isolation remain real', async ({ page }, info) => {
  await login(page);
  const nonce = `Synthetic-${info.project.name}-${Date.now()}`;
  const text = `上个月我膝盖受伤了（${nonce}）`;
  try {
    await page.getByRole('button', { name: '打开个人设置' }).click();
    await page.getByRole('button', { name: '开启长期记忆', exact: true }).click();
    await page.getByText('允许', { exact: true }).click();
    await expect(page.getByRole('button', { name: '关闭长期记忆', exact: true })).toBeVisible();
    await page.getByRole('button', { name: '聊天', exact: true }).click();
    await freshChat(page);
    await page.getByLabel('想对小忆说的话', { exact: true }).fill(text);
    const stored = page.waitForResponse(r => r.request().method() === 'POST' && /\/messages$/.test(r.url()));
    await page.getByRole('button', { name: '发送消息', exact: true }).click();
    const original = (await (await stored).json()).user_message;
    const library = (await (await page.request.get('/api/v1/memories?limit=100')).json()).items;
    const fact = library.find((item: { value: string }) => item.value === text);
    expect(fact).toBeTruthy();
    await page.getByRole('button', { name: '打开个人设置' }).click();
    await page.getByRole('button', { name: '退出登录', exact: true }).click();
    await login(page); await freshChat(page);
    await page.getByLabel('想对小忆说的话', { exact: true }).fill(`你还记得${nonce}那次膝盖受伤的事吗？`);
    const recalled = page.waitForResponse(r => r.request().method() === 'POST' && /\/messages$/.test(r.url()));
    await page.getByRole('button', { name: '发送消息', exact: true }).click();
    const answer = (await (await recalled).json()).assistant_message;
    expect(answer.memory_refs.some((ref: { source_message_id: string }) => ref.source_message_id === original.id)).toBe(true);
    await expect(page.locator('.memory-reference')).toContainText(text);
    await page.reload();
    await expect(page.locator('.memory-reference')).toContainText(text);
    await page.screenshot({ path: path.resolve(`../../.cache/ui-regression/retrieval-${info.project.name}.png`) });
    await page.locator('.memory-reference').getByRole('button', { name: '打开原会话', exact: true }).click();
    await expect(page.locator('.message-row.user .message')).toHaveText(text);
    await page.getByRole('button', { name: '我的回忆', exact: true }).click();
    const search = page.getByRole('searchbox', { name: '搜索我的记忆', exact: true });
    await search.fill(nonce);
    const searched = page.waitForResponse(r => new URL(r.url()).pathname.endsWith('/memories/search') && new URL(r.url()).searchParams.get('q') === nonce);
    await search.press('Enter'); await searched;
    await expect(page.getByRole('button', { name: '搜索', exact: true })).toHaveAttribute('aria-busy', 'false');
    await expect(page.getByText(`搜索“${nonce}”，最多显示30条相关结果。`, { exact: false })).toBeVisible();
    await expect(page.locator('.memory-card').filter({ hasText: text }).locator('.memory-value')).toBeVisible();
    const missing = `zzabsent${Date.now().toString(36).replace(/[0-9]/g, 'x')}zz`;
    await search.fill(missing);
    const empty = page.waitForResponse(r => new URL(r.url()).pathname.endsWith('/memories/search') && new URL(r.url()).searchParams.get('q') === missing);
    await search.press('Enter'); await empty;
    await expect(page.getByText('没有找到相关记忆', { exact: true })).toBeVisible();
    // Restore A's preference before switching accounts; the underlying memory remains.
    expect((await page.request.post('/api/v1/memory-consent', { data: { enabled: false } })).ok()).toBe(true);
    await page.getByRole('button', { name: '打开个人设置' }).click();
    await page.getByRole('button', { name: '退出登录', exact: true }).click();
    await login(page, 1);
    expect((await page.request.post('/api/v1/memory-consent', { data: { enabled: true } })).ok()).toBe(true);
    await freshChat(page);
    await page.getByLabel('想对小忆说的话', { exact: true }).fill(`你记得${nonce}的膝盖经历吗？`);
    const denied = page.waitForResponse(r => r.request().method() === 'POST' && /\/messages$/.test(r.url()));
    await page.getByRole('button', { name: '发送消息', exact: true }).click();
    expect((await (await denied).json()).assistant_message.memory_refs).toEqual([]);
    expect((await page.request.get(`/api/v1/memories/${fact.id}/sources`)).status()).toBe(404);
  } finally {
    const restored = await page.request.post('/api/v1/memory-consent', { data: { enabled: false } });
    if (restored.status() !== 401) expect(restored.ok()).toBe(true);
  }
});
