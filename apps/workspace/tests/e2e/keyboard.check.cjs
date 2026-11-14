/*
 * Keyboard check (sandbox tool): on each page, Tab through up to 120 focus stops (the sidebar comes first) and report controls inside the page
 * that take focus with no visible focus indicator (outline or ring, on the control or its parent), and the page's main
 * actions that Tab never reaches. Disabled buttons are skipped by Tab by design, so an action that starts disabled
 * shows as "not reached". Signs in as admin@example.com (a sandbox account).
 *   BASE_URL=http://localhost:3100 NODE_PATH=<playwright> node keyboard.check.cjs
 */
const { chromium } = require('playwright');
const B = process.env.BASE_URL || 'http://localhost:3100';
const PAGES = {
  '/app/workflows': ['Start a draft', 'Schedule'],
  '/app/workflows/scheduled': ['New schedule'],
  '/app/workflows/drafts': ['New draft'],
  '/app/inbox': ['To approve', 'To review', 'Updates'],
  '/app/sources/discover': ['Request'],
  '/app/sources/plugins': [],
  '/app/knowledge': [],
  '/admin/approvals': ['Save rules'],
  '/admin/scheduling': ['Save', 'Run what is due now'],
  '/admin/quality': [],
};
(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext({ viewport: { width: 1280, height: 900 } });
  const p = await ctx.newPage();
  await p.goto(B + '/auth/login', { waitUntil: 'load', timeout: 240000 });
  await p.waitForSelector('input[type="email"], input[name="email"]', { timeout: 200000 });
  await p.fill('input[type="email"], input[name="email"]', 'admin@example.com'); await p.fill('input[type="password"]', 'Passw0rd-test-123');
  await p.click('button:has-text("Sign In")'); await p.waitForTimeout(9000);
  for (const [path, wanted] of Object.entries(PAGES)) {
    await p.goto(B + path, { waitUntil: 'load', timeout: 240000 }); await p.waitForTimeout(5000);
    await p.evaluate(() => document.activeElement && document.activeElement.blur());
    const seen = [], invisible = [];
    for (let i = 0; i < 120; i++) {
      await p.keyboard.press('Tab');
      const info = await p.evaluate(() => {
        const e = document.activeElement;
        if (!e || e === document.body) return null;
        const cs = getComputedStyle(e);
        const outline = cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0;
        const shadow = cs.boxShadow && cs.boxShadow !== 'none';
        // Some controls show focus on a wrapper (focus-within); accept a visible change on the parent too.
        const parent = e.parentElement ? getComputedStyle(e.parentElement) : null;
        const pOutline = parent && parent.outlineStyle !== 'none' && parseFloat(parent.outlineWidth) > 0;
        const r = e.getBoundingClientRect();
        const name = (e.getAttribute('aria-label') || e.innerText || e.getAttribute('title') || e.getAttribute('name') || e.tagName).trim().replace(/\s+/g, ' ').slice(0, 40);
        return { name, tag: e.tagName, visibleFocus: outline || shadow || pOutline, onScreen: r.width > 0 && r.height > 0, inMain: !!e.closest('main, [data-testid$="-page"]') };
      });
      if (!info) continue;
      seen.push(info.name);
      if (info.inMain && info.onScreen && !info.visibleFocus) invisible.push(`${info.tag}:${info.name}`);
    }
    const missing = wanted.filter((w) => !seen.some((s) => s.includes(w)));
    console.log(`${path} | focus stops: ${new Set(seen).size} | no visible focus (in page): ${[...new Set(invisible)].join(', ') || 'none'} | main actions not reached: ${missing.join(', ') || 'none'}`);
  }
  await b.close();
})();
