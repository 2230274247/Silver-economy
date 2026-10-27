/** Local operator preview using the existing Synthetic draft. No message/model calls. */
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
if (!process.env.PLAYWRIGHT_BROWSERS_PATH) process.env.PLAYWRIGHT_BROWSERS_PATH = path.join(root, '.cache/browsers');
const { chromium, expect } = require('../apps/mobile/node_modules/@playwright/test');
const marker = path.join(root, '.cache/t11b-preview.json');

async function main() {
  const source = JSON.parse(fs.readFileSync(path.join(root, 'docs/testing/T11A-live.json'), 'utf8'));
  const accounts = JSON.parse(fs.readFileSync(path.join(root, '.cache/demo-accounts.json'), 'utf8'));
  const browser = await chromium.launch();
  let modelCalls = 0;
  try {
    const page = await browser.newPage({ baseURL: 'http://127.0.0.1:5173', viewport: { width: 390, height: 844 } });
    await page.route('**/api/v1/conversations/*/messages', route => {
      if (route.request().method() === 'POST') { modelCalls++; return route.abort(); }
      return route.continue();
    });
    await page.goto('/#/pages/login/index');
    await page.getByLabel('演示账号', { exact: true }).fill(accounts[0].login_name);
    await page.getByLabel('密码', { exact: true }).fill(accounts[0].password);
    await page.getByRole('button', { name: '登录', exact: true }).click();
    await expect(page.getByRole('button', { name: '查看聊天记录' })).toBeVisible();
    const mode = await (await page.request.get('/api/v1/maps-status')).json();
    if (mode.provider !== 'mock') throw new Error('This preview only runs with explicit Mock maps; never spends real provider quota');
    const current = await (await page.request.get(`/api/v1/task-drafts/${source.draft_id}`)).json();
    if (!current.is_synthetic) throw new Error('Only the existing Synthetic draft may be used');
    await page.goto(`/#/pages/index/index?id=${source.conversation_id}`);
    const panel = page.locator('.map-panel');
    await panel.getByRole('button', { name: '核实地点、路线和天气', exact: true }).click();
    if (!fs.existsSync(marker)) {
      if (current.location_consent || current.origin_place || current.destination_place) throw new Error('Existing location work detected; preserve it');
      fs.writeFileSync(marker, JSON.stringify({ status: 'started', synthetic: true }));
      await panel.getByRole('button', { name: '同意本次行程的位置查询用途', exact: true }).click();
      for (const field of ['origin', 'destination']) {
        await panel.getByRole('button', { name: field === 'origin' ? '搜索出发地' : '搜索目的地', exact: true }).click();
        await panel.getByLabel('地点所在城市', { exact: true }).fill('北京');
        await panel.getByLabel('具体地点或完整地址', { exact: true }).fill(field === 'origin' ? '合成广场' : '合成书屋');
        await panel.getByRole('button', { name: '查询地点候选', exact: true }).click();
        await panel.locator('.map-candidate').nth(field === 'origin' ? 1 : 0).click();
        await expect(panel.locator('.map-candidate')).toHaveCount(0);
      }
      await panel.getByRole('button', { name: '查询路线和天气', exact: true }).click();
      await expect(panel.locator('.map-result')).toContainText('Mock / Synthetic出行参考');
    }
    await page.reload();
    await page.getByRole('button', { name: '核实地点、路线和天气', exact: true }).click();
    await expect(panel.locator('.map-result')).toContainText('12.0 公里 · 约 35 分钟');
    const saved = await (await page.request.get(`/api/v1/task-drafts/${source.draft_id}`)).json();
    if (!saved.map_snapshot?.is_synthetic || modelCalls) throw new Error('Preview must remain Synthetic with zero model requests');
    await panel.locator('.map-result').scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(root, 'docs/demos/T11B-operator-mock-390.png') });
    const outcome = { status: 'passed', checked_at: new Date().toISOString(), synthetic: true, maps_provider: mode.provider,
      live_amap_verified: false, new_real_model_calls: modelCalls, real_map_calls: 0,
      conversation_id: source.conversation_id, draft_id: source.draft_id, persisted_after_reload: true, scheduling_status: saved.scheduling_status };
    fs.writeFileSync(marker, JSON.stringify(outcome, null, 2));
    fs.writeFileSync(path.join(root, 'docs/testing/T11B-preview.json'), JSON.stringify(outcome, null, 2) + '\n');
    console.log(JSON.stringify(outcome));
  } finally { await browser.close(); }
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
