// Inspect an offline, Synthetic-only report in an isolated test browser.
const fs = require('node:fs')
const path = require('node:path')
const { pathToFileURL } = require('node:url')
const localBrowsers = path.resolve(__dirname, '../.cache/browsers')
if (!process.env.PLAYWRIGHT_BROWSERS_PATH && fs.existsSync(localBrowsers)) {
  process.env.PLAYWRIGHT_BROWSERS_PATH = localBrowsers
}
const { chromium } = require('../apps/mobile/node_modules/@playwright/test')

async function main() {
  const label = process.argv[2]
  if (!/^[a-z0-9-]{1,40}$/.test(label || '')) throw new Error('Use a report run label')
  const root = path.resolve(__dirname, '..')
  const report = path.join(root, 'docs/testing/memory-eval-v1', `${label}.html`)
  const output = path.join(root, 'docs/testing/memory-eval-v1', `${label}-browser.json`)
  if (fs.existsSync(output)) throw new Error('Preserve prior browser evidence; use a new run label')
  const results = []
  const browser = await chromium.launch({ headless: true })
  try {
    for (const width of [1440, 390]) {
      const page = await browser.newPage({ viewport: { width, height: 1050 } })
      const errors = []
      const external = []
      page.on('pageerror', error => errors.push(error.name))
      await page.route(/^https?:/, route => {
        external.push(new URL(route.request().url()).origin)
        return route.abort()
      })
      await page.goto(pathToFileURL(report).href)
      if (await page.locator('h1').innerText() !== '长期记忆质量与性能评估') {
        throw new Error('Missing report heading')
      }
      const overflow = await page.evaluate(() =>
        document.documentElement.scrollWidth > window.innerWidth + 1)
      const count = await page.locator('section.scale:visible').count()
      if (!count || overflow || errors.length || external.length) {
        throw new Error('Report layout, script or offline check failed')
      }
      const screenshot = path.join(root, 'docs/demos', `T10E2-${label}-${width}.png`)
      await page.screenshot({ path: screenshot })
      await page.locator('#scale').selectOption('20000')
      if (await page.locator('section.scale:visible').count() !== 1) {
        throw new Error('Scale selector did not hide other results')
      }
      results.push({ width, errors, external_requests: external.length,
        body_overflow: overflow, scale_selector: 'passed', initial_scale_sections: count,
        screenshot: path.relative(root, screenshot).replaceAll('\\', '/') })
      await page.close()
    }
  } finally {
    await browser.close()
  }
  fs.writeFileSync(output, JSON.stringify({ report: label, results }, null, 2) + '\n',
    { flag: 'wx' })
  console.log(JSON.stringify({ report: label, checks: 'passed', viewports: [1440, 390] }))
}

main().catch(error => { console.error(error.message); process.exitCode = 1 })
