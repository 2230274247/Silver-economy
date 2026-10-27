import { test, expect, type Page } from '@playwright/test';
import path from 'node:path';
import { login, freshChat } from './helpers';

async function setup(page: Page) {
  await login(page); await freshChat(page);
  await page.getByLabel('想对小忆说的话', { exact: true }).fill('明天上午十点到张阿姨家，从我家出发，打车，提醒我');
  const saved = page.waitForResponse(r => r.request().method() === 'POST' && /\/messages$/.test(new URL(r.url()).pathname));
  await page.getByRole('button', { name: '发送消息', exact: true }).click();
  const draft = (await (await saved).json()).assistant_message.task_drafts[0];
  const panel = page.locator('.map-panel');
  await panel.getByRole('button', { name: '核实地点、路线和天气', exact: true }).click();
  await expect(panel).toContainText('Mock / Synthetic');
  return { draft, panel };
}

async function pick(page: Page, field: 'origin' | 'destination', number: number) {
  const panel = page.locator('.map-panel');
  await panel.getByRole('button', { name: field === 'origin' ? '搜索出发地' : '搜索目的地', exact: true }).click();
  await panel.getByLabel('地点所在城市', { exact: true }).fill('北京');
  await panel.getByLabel('具体地点或完整地址', { exact: true }).fill(field === 'origin' ? '合成广场' : '合成书屋');
  const result = page.waitForResponse(r => r.url().endsWith('/places/search'));
  await panel.getByRole('button', { name: '查询地点候选', exact: true }).click();
  const choices = await (await result).json();
  await expect(panel.locator('.map-candidate')).toHaveCount(2);
  const chosen = page.waitForResponse(r => r.url().endsWith('/places/select'));
  await panel.locator('.map-candidate').nth(number).click();
  expect((await (await chosen).json())[`${field}_place`].id).toBe(choices.items[number].id);
}

test('location consent, explicit second choice, route/weather provenance and refresh use actual API persistence', async ({ page }, info) => {
  let externalActions = 0;
  page.on('request', r => { if (/places\/search|map-preview/.test(r.url())) externalActions++; });
  const { draft, panel } = await setup(page);
  expect(externalActions).toBe(0);
  await expect(panel.getByRole('button', { name: '查询地点候选', exact: true })).toHaveCount(0);
  await panel.getByRole('button', { name: '同意本次行程的位置查询用途', exact: true }).click();
  await expect(panel.getByLabel('地点所在城市', { exact: true })).toBeVisible();
  expect((await (await page.request.get(`/api/v1/task-drafts/${draft.id}`)).json()).origin_place).toBeNull();
  await pick(page, 'origin', 1); await pick(page, 'destination', 0);
  await expect(panel.getByLabel('地点所在城市', { exact: true })).toHaveCount(0);
  const preview = page.waitForResponse(r => r.url().endsWith('/map-preview'));
  await panel.getByRole('button', { name: '查询路线和天气', exact: true }).click();
  const data = await (await preview).json();
  expect(data.map_snapshot.route.duration_seconds).toBe(2100);
  expect(data.scheduling_status).toBe('not_scheduled');
  await expect(panel.locator('.map-result')).toContainText('12.0 公里 · 约 35 分钟');
  await expect(panel.locator('.map-result')).toContainText('Mock示例：建议带伞，非真实预报');
  await page.reload();
  await page.getByRole('button', { name: '核实地点、路线和天气', exact: true }).click();
  await expect(panel.locator('.map-result')).toContainText('Mock / Synthetic出行参考');
  const restored = await (await page.request.get(`/api/v1/task-drafts/${draft.id}`)).json();
  expect(restored.map_snapshot.route).toEqual(data.map_snapshot.route);
  expect(externalActions).toBe(3); // Two searches and one preview; no queries on opening or reload.
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1)).toBe(false);
  await panel.locator('.map-result').scrollIntoViewIfNeeded();
  await page.screenshot({ path: path.resolve(`../../docs/demos/T11B-mock-${info.project.name}.png`) });
  await panel.getByRole('button', { name: '撤回位置用途并清理查询结果', exact: true }).click();
  await expect(panel.locator('.map-result')).toHaveCount(0);
  const withdrawn = await (await page.request.get(`/api/v1/task-drafts/${draft.id}`)).json();
  expect(withdrawn.location_consent).toBe(false); expect(withdrawn.origin_place).toBeNull();
});

test('search failure preserves fields and a held query prevents duplicate clicks and parallel edits', async ({ page }) => {
  const { panel } = await setup(page);
  await panel.getByRole('button', { name: '同意本次行程的位置查询用途', exact: true }).click();
  await panel.getByLabel('地点所在城市', { exact: true }).fill('北京');
  await panel.getByLabel('具体地点或完整地址', { exact: true }).fill('合成地址2号');
  await page.route('**/places/search', route => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ error: { code: 'SYNTHETIC_FAILURE', message: '合成查询失败' } }) }), { times: 1 });
  await panel.getByRole('button', { name: '查询地点候选', exact: true }).click();
  await expect(panel.getByRole('alert')).toContainText('合成查询失败');
  await expect(panel.getByLabel('具体地点或完整地址', { exact: true })).toHaveValue('合成地址2号');
  let release = () => {};
  const gate = new Promise<void>(resolve => { release = resolve; });
  let requests = 0;
  page.on('request', r => { if (r.url().endsWith('/places/search')) requests++; });
  await page.route('**/places/search', async route => { await gate; await route.continue(); }, { times: 1 });
  const began = page.waitForRequest(r => r.url().endsWith('/places/search'));
  const result = page.waitForResponse(r => r.url().endsWith('/places/search'));
  const button = panel.getByRole('button', { name: '查询地点候选', exact: true });
  await button.click(); await began;
  await expect(page.getByRole('button', { name: '补充或修改信息', exact: true })).toBeDisabled();
  await button.dispatchEvent('click'); release();
  expect((await result).status()).toBe(200);
  await expect(panel.locator('.map-candidate')).toHaveCount(2); expect(requests).toBe(1);
});
