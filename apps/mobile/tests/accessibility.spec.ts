import { expect, test, type Page } from '@playwright/test';

async function auditData(page: Page) {
  const memory = {
    id: 'synthetic-a11y-memory', kind: 'event', key: '合成回忆', value: '合成家庭出游记录',
    status: 'candidate', event_precision: 'unknown', time_expression: null,
    revision: 3, retrieval_allowed: false, extractor_provider: 'mock', is_synthetic: true,
  };
  let task = {
    id: 'synthetic-a11y-trip', draft_id: 'synthetic-draft', kind: 'outing', title: '合成出游',
    status: 'scheduled', revision: 4, time_semantics: 'arrival',
    target_at: '2026-11-01T03:00:00Z', departure_at: '2026-11-01T02:00:00Z',
    reminder_at: '2026-11-01T01:00:00Z', confirmed_at: '2026-10-28T03:00:00Z',
    origin: '合成广场', destination: '合成书屋', notifications: [], is_synthetic: true,
    calculation_basis: { inputs: { access_buffer_minutes: 10, contingency_buffer_minutes: 15, lead_minutes: 30 } },
  };
  const device = { id: 'synthetic-a11y-device', device_label: '合成通知设备',
    platform: 'android', permission_status: 'granted', can_receive: true, revoked_at: null };
  const state = { deletes: 0, consents: 0, revokes: 0, patches: [] as Record<string, unknown>[],
    enabled: false, failSave: false };
  await page.route('**/api/v1/**', async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    let data: unknown = { items: [], next_cursor: null };
    if (path.endsWith('/me')) data = { id: 'synthetic-a11y-user', login_name: 'Synthetic' };
    else if (path.endsWith('/model-status')) data = { provider: 'mock', configured: true };
    else if (path.endsWith('/memory-consent')) {
      if (request.method() === 'POST') { state.consents++; state.enabled = request.postDataJSON().enabled; }
      data = { enabled: state.enabled };
    } else if (path.endsWith('/notification-devices')) data = { items: [device] };
    else if (path.endsWith(`/${device.id}`)) {
      expect(request.method()).toBe('DELETE'); state.revokes++;
      data = { ...device, revoked_at: '2026-10-28T03:00:00Z', can_receive: false };
    } else if (path.endsWith('/memories')) data = { items: state.deletes ? [] : [memory], next_cursor: null };
    else if (path.endsWith(`/${memory.id}`)) {
      expect(request.method()).toBe('DELETE');
      expect(request.postDataJSON()).toEqual({ expected_revision: 3 });
      state.deletes++;
      await route.fulfill({ status: 204 }); return;
    } else if (path.endsWith('/outing-tasks')) data = { items: [task] };
    else if (path.endsWith(`/${task.id}`)) {
      expect(request.method()).toBe('PATCH');
      const payload = request.postDataJSON(); state.patches.push(payload);
      if (state.failSave) {
        await route.fulfill({ status: 409, json: { error: { code: 'CONFLICT', message: '合成版本冲突，请重新核对' } } });
        return;
      }
      task = { ...task, title: payload.title, target_at: payload.target_at, revision: task.revision + 1,
        calculation_basis: { inputs: { access_buffer_minutes: payload.access_buffer_minutes,
          contingency_buffer_minutes: payload.contingency_buffer_minutes, lead_minutes: payload.lead_minutes } } };
      data = task;
    } else {
      expect(request.method(), `unexpected mutation ${path}`).toBe('GET');
    }
    await route.fulfill({ status: 200, json: data });
  });
  await page.goto('/#/pages/index/index');
  await expect(page.locator('.mode-note')).toContainText('Mock');
  return state;
}

test('memory confirmation contains focus, supports keyboard cancellation and confirms once', async ({ page }) => {
  const state = await auditData(page);
  await page.getByRole('button', { name: '我的回忆', exact: true }).click();
  const trigger = page.locator('#memory-synthetic-a11y-memory').getByRole('button', {
    name: '删除记忆', exact: true, includeHidden: true,
  });
  const dialog = page.getByRole('dialog', { name: '删除这条长期记忆？' });
  await trigger.focus(); await trigger.press('Enter');
  await expect(dialog).toBeVisible();
  await expect(dialog).toHaveAttribute('aria-modal', 'true');
  await expect(dialog).toHaveAccessibleDescription(/原始聊天和既有回复仍保留/);
  const cancel = dialog.getByRole('button', { name: '保留', exact: true });
  const confirm = dialog.getByRole('button', { name: '删除记忆', exact: true });
  await expect(cancel).toBeFocused();
  for (const button of [cancel, confirm]) {
    const bounds = await button.boundingBox();
    expect(bounds!.width).toBeGreaterThanOrEqual(44);
    expect(bounds!.height).toBeGreaterThanOrEqual(44);
  }
  await trigger.evaluate(element => (element as HTMLElement).focus());
  await expect(cancel).toBeFocused();
  await page.keyboard.press('Shift+Tab'); await expect(confirm).toBeFocused();
  await page.keyboard.press('Tab'); await expect(cancel).toBeFocused();
  await page.keyboard.press('Tab'); await expect(confirm).toBeFocused();
  await page.keyboard.press('Shift+Tab'); await expect(cancel).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(dialog).toHaveCount(0); await expect(trigger).toBeFocused();
  expect(state.deletes).toBe(0);
  await trigger.press('Space'); await expect(cancel).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(dialog).toHaveCount(0); await expect(trigger).toBeFocused();
  expect(state.deletes).toBe(0);
  await trigger.press('Enter'); await page.keyboard.press('Tab'); await page.keyboard.press('Space');
  await expect(page.locator('#memory-synthetic-a11y-memory')).toHaveCount(0);
  expect(state.deletes).toBe(1);
});

test('memory authorization and device withdrawal preserve cancel and confirm behavior', async ({ page }) => {
  const state = await auditData(page);
  await page.getByRole('button', { name: '打开个人设置' }).click();
  const enable = page.getByRole('button', { name: '开启长期记忆', exact: true });
  await expect(enable).toBeEnabled();
  await enable.focus(); await enable.press('Enter');
  const consent = page.getByRole('dialog', { name: '开启长期记忆' });
  await expect(consent.getByRole('button', { name: '暂不', exact: true })).toBeFocused();
  await page.keyboard.press('Space'); await expect(enable).toBeFocused();
  expect(state.consents).toBe(0);
  await enable.press('Enter');
  await consent.getByRole('button', { name: '允许', exact: true }).press('Enter');
  await expect(page.getByRole('button', { name: '关闭长期记忆', exact: true })).toBeVisible();
  expect(state.consents).toBe(1);
  const revoke = page.getByRole('button', { name: '撤回', exact: true });
  await revoke.focus(); await revoke.press('Enter');
  const withdrawal = page.getByRole('dialog', { name: '撤回这台设备' });
  await expect(withdrawal.getByRole('button', { name: '暂不', exact: true })).toBeFocused();
  await page.keyboard.press('Escape'); await expect(revoke).toBeFocused();
  expect(state.revokes).toBe(0);
  await revoke.press('Enter');
  await withdrawal.getByRole('button', { name: '撤回', exact: true }).press('Space');
  await expect(page.getByRole('button', { name: '已撤回', exact: true })).toBeDisabled();
  expect(state.revokes).toBe(1);
});

test('trip fields have native names after reopening and preserve cancel, validation and save', async ({ page }) => {
  const state = await auditData(page);
  await page.getByRole('button', { name: '提醒', exact: true }).click();
  const detail = page.locator('.trip-detail');
  await detail.getByRole('button', { name: '查看行程详情', exact: true }).click();
  const threshold = detail.getByRole('spinbutton', { name: '车程变化通知阈值（分钟）', exact: true });
  await expect(threshold).toHaveValue('10');
  await detail.getByRole('button', { name: '修改行程', exact: true }).click();
  const title = detail.getByRole('textbox', { name: '行程名称', exact: true });
  const time = detail.getByRole('textbox', { name: '新的时间（北京时间）', exact: true });
  const access = detail.getByRole('spinbutton', { name: '接驳缓冲（分钟）', exact: true });
  const contingency = detail.getByRole('spinbutton', { name: '弹性缓冲（分钟）', exact: true });
  const lead = detail.getByRole('spinbutton', { name: '提前提醒（分钟）', exact: true });
  for (const input of [threshold, title, time, access, contingency, lead]) {
    await expect(input).toBeVisible();
    expect(await input.evaluate(element => element.tagName)).toBe('INPUT');
    const labelId = await input.getAttribute('aria-labelledby');
    expect(labelId).toBeTruthy();
    await expect(page.locator(`[id="${labelId}"]`)).toBeVisible();
  }
  await title.fill('未保存的中文修改');
  await detail.getByRole('button', { name: '放弃修改', exact: true }).click();
  expect(state.patches).toHaveLength(0);
  await detail.getByRole('button', { name: '收起行程详情', exact: true }).click();
  await detail.getByRole('button', { name: '查看行程详情', exact: true }).click();
  await expect(threshold).toBeVisible();
  await detail.getByRole('button', { name: '修改行程', exact: true }).click();
  await expect(title).toHaveValue('合成出游');
  for (const input of [time, access, contingency, lead]) await expect(input).toBeVisible();
  await time.fill('无效时间');
  await detail.getByRole('button', { name: '保存行程修改', exact: true }).click();
  await expect(detail.getByRole('alert')).toContainText('请选择有效的北京时间');
  expect(state.patches).toHaveLength(0);
  await title.fill('中文出游修改');
  await time.fill('2026-11-02T11:00');
  await access.fill('12'); await contingency.fill('18'); await lead.fill('20');
  state.failSave = true;
  await detail.getByRole('button', { name: '保存行程修改', exact: true }).click();
  await expect(detail.getByRole('alert')).toContainText('合成版本冲突');
  await expect(title).toHaveValue('中文出游修改');
  state.failSave = false;
  await detail.getByRole('button', { name: '保存行程修改', exact: true }).click();
  await expect(detail.getByRole('button', { name: '修改行程', exact: true })).toBeVisible();
  expect(state.patches).toHaveLength(2);
  expect(state.patches[1]).toEqual({ expected_revision: 4, title: '中文出游修改',
    target_at: '2026-11-02T03:00:00.000Z', access_buffer_minutes: 12,
    contingency_buffer_minutes: 18, lead_minutes: 20 });
});

test('reading sizes persist and confirmation uses the selected size', async ({ page }) => {
  await auditData(page);
  await page.getByRole('button', { name: '打开个人设置' }).click();
  for (const [name, size] of [['标准', '18px'], ['大号', '20px'], ['特大', '22px']] as const) {
    await page.getByRole('button', { name, exact: true }).click();
    await page.reload();
    await expect(page.getByRole('button', { name, exact: true })).toHaveAttribute('aria-pressed', 'true');
    await expect(page.locator('.phone-shell')).toHaveCSS('font-size', size);
    const trigger = page.getByRole('button', { name: '开启长期记忆', exact: true });
    await expect(trigger).toBeEnabled(); await trigger.focus(); await trigger.press('Enter');
    await expect(page.getByRole('dialog')).toHaveCSS('font-size', size);
    await page.keyboard.press('Escape'); await expect(trigger).toBeFocused();
  }
});
