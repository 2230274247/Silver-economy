import { test, expect } from '@playwright/test';
import path from 'node:path';
import { login, resetHealthState } from './helpers';

test('timeline retains time precision, edit authority, raw sources and deletion across refresh', async ({ page }, info) => {
  await login(page); await resetHealthState(page);
  try {
    await page.request.post('/api/v1/memory-consent', { data: { enabled: true } });
    const text = `我的膝盖受伤了（Synthetic-timeline-${info.project.name}-${Date.now()}）`;
    const conversation = await (await page.request.post('/api/v1/conversations')).json();
    expect((await page.request.post(`/api/v1/conversations/${conversation.id}/messages`, { data: { content: text, client_request_id: crypto.randomUUID() } })).ok()).toBe(true);
    const memory = (await (await page.request.get('/api/v1/memories')).json()).items.find((m: { value: string }) => m.value === text);
    expect(memory).toBeTruthy();
    await page.getByRole('button', { name: '我的回忆', exact: true }).click();
    await page.route('**/api/v1/memories/timeline', route => route.abort(), { times: 1 });
    await page.getByRole('button', { name: '按时间查看', exact: true }).click();
    await expect(page.getByRole('alert')).toContainText('网络连接失败');
    await page.getByRole('button', { name: '重新读取', exact: true }).click();
    const card = page.locator(`#memory-${memory.id}`);
    await expect(card.locator('.event-label')).toHaveText('发生时间未明确');
    await expect(card).toContainText('1 段原文依据 · 记录于');
    const correction = `2019年我去过苏州旅游（Synthetic-${info.project.name}-${Date.now()}）`;
    expect((await page.request.post(`/api/v1/memories/${memory.id}/correct`, { data: { expected_revision: memory.revision, kind: 'travel', key: '苏州', value: correction, time_expression: '2019年' } })).ok()).toBe(true);
    await page.reload();
    await page.getByRole('button', { name: '按时间查看', exact: true }).click();
    await expect(page.getByText('正在读取记忆…', { exact: true })).toHaveCount(0);
    for (let i = 0; i < 20 && await card.count() === 0; i++) {
      const more = page.getByRole('button', { name: '查看更多记忆', exact: true });
      await expect(more).toBeVisible(); await more.click();
      await expect(page.getByText('正在读取记忆…', { exact: true })).toHaveCount(0);
    }
    await expect(card.locator('.event-label')).toHaveText('2019年');
    await expect(card).toContainText('用户亲自修改');
    await expect(card.locator('.memory-value')).toHaveText(correction);
    await card.getByRole('button', { name: '查看来源', exact: true }).click();
    await expect(card.locator('.source-card')).toContainText(text);
    await card.locator('.event-label').scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.resolve(`../../.cache/ui-regression/timeline-${info.project.name}.png`) });
    await card.getByRole('button', { name: '删除记忆', exact: true }).click();
    await page.getByText('删除记忆', { exact: true }).last().click();
    await expect(card).toHaveCount(0);
    const timeline = await (await page.request.get('/api/v1/memories/timeline?limit=100')).json();
    expect(timeline.items.some((m: { id: string }) => m.id === memory.id)).toBe(false);
  } finally {
    await page.request.post('/api/v1/memory-consent', { data: { enabled: false } });
  }
});
