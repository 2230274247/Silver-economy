import { test, expect, type Page } from '@playwright/test';
import path from 'node:path';
import { freshChat, login } from './helpers';

async function send(page: Page, text: string) {
  await page.getByLabel('想对小忆说的话', { exact: true }).fill(text);
  const response = page.waitForResponse(r => r.request().method() === 'POST' && /\/messages$/.test(new URL(r.url()).pathname));
  await page.getByRole('button', { name: '发送消息', exact: true }).click();
  const result = await (await response).json();
  expect(result.assistant_message.status).toBe('completed');
  return result.assistant_message.task_drafts[0];
}

async function pick(page: Page, field: 'origin' | 'destination') {
  const panel = page.locator('.map-panel');
  await panel.getByRole('button', { name: field === 'origin' ? '搜索出发地' : '搜索目的地', exact: true }).click();
  await panel.getByLabel('地点所在城市', { exact: true }).fill('北京');
  await panel.getByLabel('具体地点或完整地址', { exact: true }).fill(field === 'origin' ? '合成广场' : '合成书屋');
  const result = page.waitForResponse(r => r.url().endsWith('/places/search'));
  await panel.getByRole('button', { name: '查询地点候选', exact: true }).click();
  const data = await (await result).json();
  const chosen = page.waitForResponse(r => r.url().endsWith('/places/select'));
  await panel.locator('.map-candidate').first().click();
  expect((await (await chosen).json())[`${field}_place`].id).toBe(data.items[0].id);
}

async function confirmedOuting(page: Page) {
  const draft = await send(page, '明天上午十点到张阿姨家，从我家出发，打车，提醒我');
  const panel = page.locator('.map-panel');
  await panel.getByRole('button', { name: '核实地点、路线和天气', exact: true }).click();
  await panel.getByRole('button', { name: '同意本次行程的位置查询用途', exact: true }).click();
  await pick(page, 'origin');
  await pick(page, 'destination');
  const mapPreview = page.waitForResponse(r => r.url().endsWith('/map-preview'));
  await panel.getByRole('button', { name: '查询路线和天气', exact: true }).click();
  await mapPreview;
  const card = page.locator('.task-card');
  const confirmed = page.waitForResponse(r => /\/task-drafts\/[^/]+\/actions$/.test(new URL(r.url()).pathname));
  await card.getByRole('button', { name: '确认信息', exact: true }).click();
  await confirmed;
  return { draftId: draft.id, card };
}

test('route-based schedule is previewed, explicitly confirmed, persisted at 09:00/08:30 and cancellable', async ({ page }, info) => {
  await login(page);
  await freshChat(page);
  const { draftId, card } = await confirmedOuting(page);
  const schedule = page.locator('.schedule-panel');
  await expect(schedule).toContainText('信息确认不会自动安排提醒');
  await expect(schedule.getByRole('button', { name: '确认并安排提醒', exact: true })).toBeDisabled();
  await schedule.getByLabel('接驳或步行缓冲分钟数', { exact: true }).fill('10');
  await schedule.getByLabel('弹性缓冲分钟数', { exact: true }).fill('15');
  await schedule.getByLabel('出门前提前多久提醒（分钟）', { exact: true }).fill('30');
  const previewResponse = page.waitForResponse(r => r.url().endsWith('/schedule-preview'));
  await schedule.getByRole('button', { name: '生成提醒预览', exact: true }).click();
  const preview = await (await previewResponse).json();
  expect(preview.schedule_preview.departure_at).toMatch(/T01:00:00\+00:00$/);
  expect(preview.schedule_preview.reminder_at).toMatch(/T00:30:00\+00:00$/);
  await expect(schedule).toContainText('09:00');
  await expect(schedule).toContainText('08:30');
  await expect(schedule).toContainText('已从到达时间扣除');

  await page.route('**/api/v1/task-drafts/*/schedule', route => route.fulfill({
    status: 503,
    contentType: 'application/json',
    body: JSON.stringify({ error: { code: 'SYNTHETIC_FAILURE', message: '合成安排失败' } }),
  }), { times: 1 });
  await schedule.getByRole('button', { name: '确认并安排提醒', exact: true }).click();
  await expect(schedule.getByRole('alert')).toContainText('合成安排失败');
  await expect(schedule.getByRole('button', { name: '确认并安排提醒', exact: true })).toHaveAttribute('aria-busy', 'false');

  const created = page.waitForResponse(r => r.request().method() === 'POST'
    && new URL(r.url()).pathname.endsWith(`/task-drafts/${draftId}/schedule`));
  await schedule.getByRole('button', { name: '确认并安排提醒', exact: true }).click();
  const response = await created;
  expect(response.status()).toBe(201);
  const task = await response.json();
  expect(task.status).toBe('scheduled');
  expect(task.notifications[0].status).toBe('queued');
  expect(task.notifications[0].is_mock).toBe(true);
  await expect(card).toContainText('提醒已安排');
  await expect(card).toContainText('不能证明手机后台已收到');

  await page.reload();
  await expect(page.locator('.task-card')).toContainText('提醒已安排');
  await page.getByRole('button', { name: '提醒', exact: true }).click();
  const reminder = page.locator(`[data-task-id="${task.id}"]`);
  await expect(reminder).toContainText('待提醒');
  await expect(reminder).toContainText('08:30');
  await reminder.scrollIntoViewIfNeeded();
  await page.screenshot({ path: path.resolve(`../../docs/demos/T11C-scheduled-${info.project.name}.png`) });
  const cancelled = page.waitForResponse(r => r.url().endsWith(`/outing-tasks/${task.id}/cancel`));
  await reminder.getByRole('button', { name: '取消提醒', exact: true }).click();
  await cancelled;
  await expect(reminder).toContainText('已取消');
  await expect(reminder.getByRole('button', { name: '取消提醒', exact: true })).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1)).toBe(false);
});

test('plain reminder fallback is independently confirmed without inventing route or weather facts', async ({ page }, info) => {
  await login(page);
  await freshChat(page);
  const title = `整理药盒 ${info.project.name}`;
  await send(page, `明天上午九点提醒我${title}`);
  const card = page.locator('.task-card');
  await card.getByRole('button', { name: '确认信息', exact: true }).click();
  const schedule = card.locator('.schedule-panel');
  await expect(schedule.getByLabel('接驳或步行缓冲分钟数', { exact: true })).toHaveCount(0);
  await schedule.getByLabel('事项前提前多久提醒（分钟）', { exact: true }).fill('15');
  const previewResponse = page.waitForResponse(r => r.url().endsWith('/schedule-preview'));
  await schedule.getByRole('button', { name: '生成提醒预览', exact: true }).click();
  const preview = await (await previewResponse).json();
  expect(preview.schedule_preview.route_duration_seconds).toBeNull();
  expect(preview.schedule_preview.route_reference_status).toBe('not_applicable');
  expect(preview.schedule_preview.weather_advice).toBeNull();
  await expect(schedule).toContainText('没有可用的当日天气依据');
  const created = page.waitForResponse(r => r.url().endsWith('/schedule'));
  await schedule.getByRole('button', { name: '确认并安排提醒', exact: true }).click();
  const task = await (await created).json();
  expect(task.kind).toBe('reminder');
  expect(task.route_snapshot).toBeNull();
  expect(task.weather_snapshot).toBeNull();
  await page.getByRole('button', { name: '提醒', exact: true }).click();
  const reminder = page.locator(`[data-task-id="${task.id}"]`);
  await expect(reminder).toContainText('时间提醒');
  await expect(reminder).toContainText(/Mock\s*通知/);
});

test('trip detail supports source inspection, time edit, navigation entry, feedback and departure lifecycle', async ({ page }, info) => {
  await login(page);
  await freshChat(page);
  const { card } = await confirmedOuting(page);
  const schedule = page.locator('.schedule-panel');
  const previewResponse = page.waitForResponse(r => r.url().endsWith('/schedule-preview'));
  await schedule.getByRole('button', { name: '生成提醒预览', exact: true }).click();
  await previewResponse;
  const created = page.waitForResponse(r => r.request().method() === 'POST'
    && new URL(r.url()).pathname.endsWith('/schedule'));
  await schedule.getByRole('button', { name: '确认并安排提醒', exact: true }).click();
  const task = await (await created).json();

  await page.getByRole('button', { name: '提醒', exact: true }).click();
  const reminder = page.locator(`[data-task-id="${task.id}"]`);
  await reminder.getByRole('button', { name: '查看行程详情', exact: true }).click();
  const detail = reminder.locator('[data-trip-detail]');
  await expect(detail).toContainText('路线与来源');
  await expect(detail).toContainText('Synthetic / Mock');
  await expect(detail).toContainText('Mock 站内通知');
  await expect(detail.getByRole('button', { name: '打开高德地图查找目的地', exact: true })).toBeVisible();

  await detail.getByRole('button', { name: '修改行程', exact: true }).click();
  await detail.getByLabel('行程名称', { exact: true }).locator('input')
    .fill(`修改后的合成行程 ${info.project.name}`);
  const nextTarget = new Date(task.target_at);
  nextTarget.setUTCDate(nextTarget.getUTCDate() + 1);
  const nextParts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Hong_Kong',
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hour12: false,
  }).formatToParts(nextTarget);
  const inputValue = (type: string) => nextParts.find(part => part.type === type)?.value ?? '';
  const targetInput = `${inputValue('year')}-${inputValue('month')}-${inputValue('day')}T${inputValue('hour')}:${inputValue('minute')}`;
  await detail.getByLabel('新的到达或出发时间', { exact: true }).locator('input')
    .fill(targetInput);
  const modifiedResponse = page.waitForResponse(r => r.request().method() === 'PATCH'
    && new URL(r.url()).pathname.endsWith(`/outing-tasks/${task.id}`));
  await detail.getByRole('button', { name: '保存行程修改', exact: true }).click();
  const modified = await (await modifiedResponse).json();
  expect(modified.revision).toBe(task.revision + 1);
  expect(modified.notifications.some((item: { status: string }) => item.status === 'cancelled')).toBe(true);
  await expect(reminder).toContainText('修改后的合成行程');

  const feedback = page.waitForResponse(r => r.url().endsWith(`/outing-tasks/${task.id}/feedback`));
  await detail.getByRole('button', { name: '提醒有帮助', exact: true }).click();
  await feedback;
  await expect(detail).toContainText('已记录：提醒有帮助');

  await reminder.scrollIntoViewIfNeeded();
  await page.screenshot({ path: path.resolve(`../../docs/demos/T11E-trip-${info.project.name}.png`) });
  const departed = page.waitForResponse(r => r.url().endsWith(`/outing-tasks/${task.id}/depart`));
  await reminder.getByRole('button', { name: '我已出发', exact: true }).click();
  await departed;
  await expect(reminder).toContainText('已出发');
  await expect(reminder.getByRole('button', { name: '取消提醒', exact: true })).toHaveCount(0);
  const completed = page.waitForResponse(r => r.url().endsWith(`/outing-tasks/${task.id}/complete`));
  await reminder.getByRole('button', { name: '标记完成', exact: true }).click();
  await completed;
  await expect(reminder).toContainText('已完成');
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1)).toBe(false);
});
