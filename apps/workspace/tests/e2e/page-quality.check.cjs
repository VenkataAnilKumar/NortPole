/*
 * Page quality check (sandbox tool): for each page, in light and dark at 1280 and 390 pixels wide, records
 * horizontal overflow, boxes that end past the right edge (clipped), and WCAG 2.0/2.1 A and AA violations found by axe-core, and saves a screenshot.
 *   AXE_JS=/path/to/axe-core/axe.min.js BASE_URL=http://localhost:3100 NODE_PATH=<playwright> node page-quality.check.cjs <outdir>
 * Signs in as admin@example.com (a sandbox account). It does not check keyboard order or screen-reader output.
 */
const { chromium } = require('playwright');
const fs = require('fs');
const AXE = fs.readFileSync(process.env.AXE_JS, 'utf8'); // path to axe-core/axe.min.js (npm install axe-core)
const OUT = process.argv[2];
const PAGES = ['/app', '/admin/overview', '/admin/governance', '/app/packs', '/app/reviewed-tasks', '/app/inbox', '/app/libraries', '/admin/access-groups', '/admin/action-targets', '/admin/audit', '/admin/packs', '/admin/inventory', '/admin/route-policy'];
const MODES = [['light', 1280], ['dark', 1280], ['light', 390], ['dark', 390]];
(async () => {
  const b = await chromium.launch();
  const results = [];
  for (const [theme, width] of MODES) {
    const ctx = await b.newContext({ viewport: { width, height: 900 } });
    await ctx.addInitScript((t) => { try { localStorage.setItem('theme', t); } catch (e) {} }, theme);
    const p = await ctx.newPage();
    await p.goto('' + (process.env.BASE_URL || 'http://localhost:3100') + '/auth/login', { waitUntil: 'load', timeout: 200000 });
    await p.waitForSelector('input[type="email"], input[name="email"]', { timeout: 120000 });
    await p.fill('input[type="email"], input[name="email"]', 'admin@example.com');
    await p.fill('input[type="password"]', 'Passw0rd-test-123');
    await p.click('button:has-text("Sign In")'); await p.waitForTimeout(8000);
    for (const path of PAGES) {
      await p.goto('' + (process.env.BASE_URL || 'http://localhost:3100') + '' + path, { waitUntil: 'load', timeout: 200000 });
      await p.waitForTimeout(4500);
      const isDark = await p.evaluate(() => document.documentElement.classList.contains('dark') || document.documentElement.getAttribute('data-theme') === 'dark');
      const overflow = await p.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      // Content wider than the screen can be clipped by a parent without scrolling, so count visible boxes that end past the right edge (a table inside its own `overflow-x-auto` box is allowed to scroll).
      const clipped = await p.evaluate(() => [...document.querySelectorAll('main *, [data-testid] *')].filter((e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && r.right > window.innerWidth + 1 && getComputedStyle(e).visibility !== 'hidden' && !e.closest('[aria-hidden="true"], [hidden], nav[aria-label="Sidebar"], .overflow-x-auto'); }).length);
      await p.evaluate(AXE);
      const ax = await p.evaluate(async () => { const r = await window.axe.run(document, { runOnly: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'] }); return r.violations.map(v => ({ id: v.id, impact: v.impact, n: v.nodes.length, sample: (v.nodes[0] && v.nodes[0].target.join(' ')).slice(0, 80) })); });
      const name = `${path.replace(/\//g, '_')}-${theme}-${width}`;
      await p.screenshot({ path: `${OUT}/${name}.png`, fullPage: false });
      results.push({ path, theme, width, isDark, overflow, clipped, ax });
    }
    await ctx.close();
  }
  fs.writeFileSync(`${OUT}/results.json`, JSON.stringify(results, null, 1));
  console.log('done', results.length);
  await b.close();
})();
