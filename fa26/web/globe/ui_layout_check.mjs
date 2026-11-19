// Layout guardrail for the Atlas page: the globe must never cover text, at any common screen size.
//
//   python fa26/web/server.py                                  # or any URL serving fa26/web/static
//   cd fa26/web/globe && npm install && npx playwright install chromium   (once)
//   npm run check:layout -- http://127.0.0.1:8080
//
// For every viewport in VIEWPORTS it checks, after the globe settles:
//   1. hero: each text block (headline, lead, ask box, buttons, stats) keeps MIN_GAP px from the globe disc
//   2. hotspots: each active story card keeps MIN_GAP px from the globe disc
//   3. the page never scrolls sideways
//   4. every visible button, link and library trigger in #engine and #live is hit-testable, and the globe canvas is
//      never the top element anywhere in those sections (an invisible layer on top shows a grab cursor and eats clicks)
// The globe disc comes from the page itself (window.__atlasGlobe.layout(): solved centre and radius in px), so the
// check measures what the layout code decided, not a guess. Exit code 1 on any failure; screenshots of failures go
// to ./ui-check-out/.
import {createRequire} from 'module';
import fs from 'fs';
const {chromium} = createRequire(import.meta.url)('playwright');

const URL = process.argv[2] || 'http://127.0.0.1:8080/';
const MIN_GAP = 16;
const VIEWPORTS = [
  [390, 844], [768, 1024], [1024, 768], [1210, 756], [1280, 720], [1366, 768],
  [1440, 900], [1512, 982], [1728, 1117], [1920, 1080], [2560, 1440],
];
const HERO_BLOCKS = ['.hero h1', '.hero .lead', '.hero .askbox', '.hero .hbtns', '.hero .stats'];

function gap(c, b) {   // px between a circle and a rectangle; negative means overlap
  const dx = Math.max(b.left - c.cx, 0, c.cx - b.right), dy = Math.max(b.top - c.cy, 0, c.cy - b.bottom);
  return Math.hypot(dx, dy) - c.r;
}

const browser = await chromium.launch({args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist']});
const rows = []; let failed = 0;
fs.mkdirSync('ui-check-out', {recursive: true});
for (const [w, h] of VIEWPORTS) {
  const page = await browser.newPage({viewport: {width: w, height: h}});
  await page.goto(URL, {waitUntil: 'networkidle'});
  await page.waitForFunction(() => window.__atlasGlobe, null, {timeout: 15000});
  await page.waitForTimeout(1200);
  const hero = await page.evaluate(sel => {
    const c = window.__atlasGlobe.layout();
    return {c, boxes: sel.map(s => { const e = document.querySelector(s); if (!e) return null; const b = e.getBoundingClientRect(); return {s, left: b.left, right: b.right, top: b.top, bottom: b.bottom}; }).filter(Boolean),
      hscroll: document.documentElement.scrollWidth - innerWidth};
  }, HERO_BLOCKS);
  const checks = hero.boxes.map(b => ({where: 'hero ' + b.s.replace('.hero ', ''), g: gap(hero.c, b)}));
  const cards = await page.$$eval('.hs', els => els.length);
  for (let i = 0; i < cards; i++) {
    await page.evaluate(i => { const s = document.querySelectorAll('.hs')[i]; scrollTo(0, s.getBoundingClientRect().top + scrollY + s.offsetHeight / 2 - innerHeight / 2); }, i);
    await page.waitForTimeout(900);
    const r = await page.evaluate(i => { const card = document.querySelectorAll('.hs')[i].querySelector('.card'); const b = card.getBoundingClientRect();
      return {c: window.__atlasGlobe.layout(), b: {left: b.left, right: b.right, top: b.top, bottom: b.bottom}, name: card.querySelector('h3').textContent}; }, i);
    checks.push({where: 'hotspot ' + r.name, g: gap(r.c, r.b)});
  }
  checks.push({where: 'horizontal scroll', g: hero.hscroll > 0 ? -hero.hscroll : 99});
  // 4. everything that looks clickable below the globe zone is really clickable (nothing invisible on top of it)
  for (const sec of ['#engine', '#live']) {
    await page.evaluate(sel => { const e = document.querySelector(sel); if (e) scrollTo(0, e.getBoundingClientRect().top + scrollY); }, sec);
    await page.waitForTimeout(900);
    const blocked = await page.evaluate(sel => {
      const root = document.querySelector(sel); if (!root) return [];
      return [...root.querySelectorAll('button, a[href], [data-lib], input')].filter(e => { const b = e.getBoundingClientRect();
        if (!b.width || !b.height || b.bottom < 0 || b.top > innerHeight || b.right < 0 || b.left > innerWidth) return false;
        if (getComputedStyle(e).visibility === 'hidden') return false;
        const x = Math.min(Math.max(b.left + b.width / 2, 1), innerWidth - 1), y = Math.min(Math.max(b.top + b.height / 2, 1), innerHeight - 1);
        const top = document.elementFromPoint(x, y); return top && !e.contains(top) && !top.contains(e) && !(top.closest && top.closest('nav'));
      }).map(e => (e.textContent || e.getAttribute('aria-label') || e.tagName).trim().slice(0, 30))
        .concat((() => { const hits = []; for (let x = .05; x < 1; x += .1) for (let y = .15; y < 1; y += .1) { const t = document.elementFromPoint(x * innerWidth, y * innerHeight); if (t && t.id === 'gl') hits.push('globe canvas on top'); } return hits.slice(0, 1); })());
    }, sec);
    checks.push({where: `clickable in ${sec}` + (blocked.length ? ` (blocked: ${blocked.slice(0, 3).join(' | ')})` : ''), g: blocked.length ? -blocked.length : 99});
  }
  const bad = checks.filter(c => c.g < MIN_GAP);
  if (bad.length) { failed += bad.length; await page.evaluate(() => scrollTo(0, 0)); await page.waitForTimeout(800); await page.screenshot({path: `ui-check-out/fail_${w}x${h}.png`}); }
  rows.push({viewport: `${w}x${h}`, mode: hero.c.mode, globe_r: Math.round(hero.c.r), min_gap: Math.round(Math.min(...checks.map(c => c.g))), worst: checks.sort((a, b) => a.g - b.g)[0].where, result: bad.length ? 'FAIL' : 'ok'});
  await page.close();
}
await browser.close();
console.table(rows);
console.log(failed ? `${failed} layout violation(s); screenshots in ui-check-out/` : `all ${VIEWPORTS.length} viewports pass (min gap ${MIN_GAP}px)`);
process.exit(failed ? 1 : 0);
