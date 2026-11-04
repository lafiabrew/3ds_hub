/* Browser integration with captured production HTML; no synthetic replacement DOM.
   Run with PLAYWRIGHT_MODULE_PATH, CHROMIUM_EXECUTABLE and PAGES_CAPTURE_DIR.
   --live-url verifies the actual deployed origin separately from local integration. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');
const net = require('node:net');
const { execFileSync } = require('node:child_process');
const { spawn } = require('node:child_process');
const root = path.resolve(__dirname, '../..');
assert(process.env.PLAYWRIGHT_MODULE_PATH && process.env.CHROMIUM_EXECUTABLE,
  'Set PLAYWRIGHT_MODULE_PATH and CHROMIUM_EXECUTABLE to isolated installed tools.');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE_PATH);
const args = process.argv.slice(2);
const liveIndex = args.indexOf('--live-url');
const liveURL = liveIndex >= 0 ? args[liveIndex + 1] : null;
const siteIndex = args.indexOf('--site-dir');
const siteDir = siteIndex >= 0 ? path.resolve(args[siteIndex + 1]) : null;
const capture = process.env.PAGES_CAPTURE_DIR;
const include = fs.readFileSync(path.join(root, '_includes/head-custom.html'), 'utf8');
const vendor = fs.readFileSync(path.join(root, 'assets/vendor/mermaid-11.12.2.min.js'));
const sri = 'sha384-' + crypto.createHash('sha384').update(vendor).digest('base64');
assert(include.includes('data-mermaid-integrity="' + sri + '"'), 'Vendored SRI must match the hook.');
const temp = fs.mkdtempSync(path.join(os.tmpdir(), '3ds-pages-browser-'));
let listener, browserServer, browser, browserPID;
let cleanupPromise;
const state = { test: 'Pages privacy/Mermaid', pid: null, port: null, results: [], cleanup: {} };
const selectors = 'pre > code.language-mermaid, .language-mermaid pre > code';
const policy = JSON.parse(fs.readFileSync(path.join(root, 'site/docs-manifest.json'), 'utf8'));
const sourceOnlyExceptions = new Set(policy.source_only);
const expectedIndex = args.indexOf('--expected-commit');
const expectedCommit = expectedIndex >= 0 ? args[expectedIndex + 1] : null;
if (expectedCommit) assert(/^[0-9a-f]{40}$/.test(expectedCommit), 'Expected commit must be a full lowercase SHA');
function requirePublished(status, item) {
  assert(!sourceOnlyExceptions.has(item.source), 'Source-only file must not be inferred published');
  assert.equal(status, 200, 'Required public route unavailable: ' + item.route);
  return true;
}
const hook = include.replace(/\{\{\s*'([^']+)'\s*\|\s*relative_url\s*\}\}/g, (_m, asset) => '/3ds_hub' + asset);
function alive(pid) { try { process.kill(pid, 0); return true; } catch (e) { if (e.code === 'ESRCH') return false; throw e; } }
async function bounded(promise, ms = 10000) {
  let timer;
  try { return await Promise.race([promise, new Promise((_r, reject) => { timer = setTimeout(() => reject(new Error('cleanup timeout')), ms); })]); }
  finally { clearTimeout(timer); }
}
async function cleanup() {
  if (cleanupPromise) return cleanupPromise;
  cleanupPromise = (async () => {
    if (browserServer) {
      try {
        if (args.includes('--inject-close-failure')) throw new Error('injected graceful-close failure');
        await bounded(browserServer.close());
      } catch (e) {
        state.cleanup.graceful_error = e.message;
        await bounded(browserServer.kill());
        state.cleanup.kill_fallback = true;
      }
      assert(!alive(browserPID), 'Owned browser PID remains alive');
      state.cleanup.browser_absent = true;
      browserServer = null; // Release ownership only after absence is observed.
    }
    if (listener) {
      await bounded(new Promise((resolve, reject) => listener.close(e => e ? reject(e) : resolve())));
      assert(!listener.listening, 'Owned listener remains open');
      state.cleanup.listener_closed = true;
      listener = null;
    }
    fs.rmSync(temp, { recursive: true, force: true });
  })();
  try { return await cleanupPromise; }
  catch (e) {
    // Retain explicit ownership evidence instead of forgetting a failed resource.
    const retained = path.join(os.tmpdir(), '3ds-pages-cleanup-' + process.pid + '.json');
    fs.writeFileSync(retained, JSON.stringify({ ...state, error: e.message, retained_resources: true }));
    console.error('Cleanup failed; ownership record retained at ' + retained);
    throw e;
  }
}
function interrupted(code) {
  cleanup().then(() => {
    if (process.send) process.send({ cleanup: state.cleanup }, () => process.exit(code));
    else process.exit(code);
  }, () => process.exit(1));
}
process.on('SIGTERM', () => interrupted(143));
process.on('SIGINT', () => interrupted(130));

function captured(name) { return fs.readFileSync(path.join(capture, name), 'utf8'); }
function adapt(html, mode = '', inject = true) {
  // Real Jekyll output is served unchanged in nominal --site-dir checks.
  if (inject || mode === 'omitted') {
    html = html.replace(/<script\b[^>]*src="[^"]*\/assets\/js\/mermaid-loader\.js[^\"]*"[^>]*>\s*<\/script>/g, '');
  }
  if (mode === 'bad') {
    html = html.replace(/(<code class="language-mermaid">)[\s\S]*?(<\/code>)/,
      '$1this is deliberately invalid Mermaid !!!$2');
  }
  if (mode === 'xss') {
    const source = '%%{init: {"securityLevel": "loose"}}%%\nflowchart LR\nA["&lt;img src=x onerror=alert(1)&gt;"] --&gt; B';
    html = html.replace('</body>', '<pre><code class="language-mermaid">' + source + '</code></pre></body>');
  }
  return inject ? html.replace('</head>', (mode === 'omitted' ? '' : hook) + '</head>') : html;
}
async function serve() {
  if (siteDir) {
    assert(fs.existsSync(path.join(siteDir, 'index.html')), 'Missing real Jekyll output');
  } else {
    assert(capture, 'PAGES_CAPTURE_DIR must name captured production HTML outside the repository.');
    for (const file of ['index.html', 'docs/ARCHITECTURE.html', 'docs/AGENT_PLAYBOOK.html', 'docs/SOP.html', 'style.css', 'anchor.min.js']) {
      assert(fs.existsSync(path.join(capture, file)), 'Missing capture prerequisite: ' + file);
    }
  }
  const files = { '/': 'index.html', '/docs/ARCHITECTURE.html': 'docs/ARCHITECTURE.html',
    '/docs/AGENT_PLAYBOOK.html': 'docs/AGENT_PLAYBOOK.html', '/docs/SOP.html': 'docs/SOP.html' };
  listener = http.createServer((req, res) => {
    const url = new URL(req.url, 'http://127.0.0.1');
    const local = url.pathname.replace(/^\/3ds_hub/, '') || '/';
    let body, type;
    if (url.searchParams.get('case') === 'missing-status' && local === '/docs/STATUS.html') {
      res.writeHead(404, { 'X-Pages-Test-Injected': 'missing-STATUS' }); res.end(); return;
    }
    if (siteDir) {
      let file = path.resolve(siteDir, '.' + local);
      if (path.relative(siteDir, file).startsWith('..')) { res.writeHead(400); res.end(); return; }
      if (fs.existsSync(file) && fs.statSync(file).isDirectory()) file = path.join(file, 'index.html');
      if (!fs.existsSync(file) || !fs.statSync(file).isFile()) { res.writeHead(404); res.end(); return; }
      body = fs.readFileSync(file);
      const extension = path.extname(file);
      type = extension === '.html' ? 'text/html' : extension === '.css' ? 'text/css' : extension === '.js' ? 'text/javascript' : 'text/plain';
      if (extension === '.html' && url.searchParams.has('case')) body = adapt(body.toString(), url.searchParams.get('case'), false);
    }
    else if (files[local]) { body = adapt(captured(files[local]), url.searchParams.get('case') || ''); type = 'text/html'; }
    else if (local === '/assets/css/style.css') { body = fs.readFileSync(path.join(capture, 'style.css')); type = 'text/css'; }
    else if (local === '/assets/js/mermaid-loader.js' || local === '/assets/vendor/mermaid-11.12.2.min.js') {
      body = fs.readFileSync(path.join(root, local)); type = 'text/javascript';
    } else { res.writeHead(404); res.end(); return; }
    res.writeHead(200, { 'Content-Type': type + '; charset=utf-8' }); res.end(body);
  });
  await new Promise(resolve => listener.listen(0, '127.0.0.1', resolve));
  state.port = listener.address().port;
  return 'http://127.0.0.1:' + state.port + '/3ds_hub/';
}
async function open(url, options = {}) {
  const context = await browser.newContext({ viewport: options.mobile ? { width: 390, height: 844 } : { width: 1100, height: 850 } });
  const page = await context.newPage();
  const errors = [], requests = [], dialogs = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('request', req => requests.push(req.url()));
  page.on('dialog', async dialog => { dialogs.push(dialog.message()); await dialog.dismiss(); });
  if (!liveURL && capture) {
    // Preserve the actual theme dependency bytes, not a stubbed anchors.add().
    await context.route('https://cdnjs.cloudflare.com/ajax/libs/anchor-js/4.1.0/anchor.min.js', route =>
      route.fulfill({ contentType: 'text/javascript', headers: { 'Access-Control-Allow-Origin': '*' }, body: fs.readFileSync(path.join(capture, 'anchor.min.js')) }));
  }
  if (options.missing) await context.route('**/assets/vendor/mermaid-11.12.2.min.js', route => route.abort());
  const response = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
  assert(response && response.status() === 200, 'Unexpected page response');
  return { context, page, errors, requests, dialogs };
}
async function expectSVG(page, count, timeout = 25000) {
  await page.waitForFunction(n => document.querySelectorAll('.pages-mermaid-viewport > svg').length === n,
    count, { timeout });
}
async function normal(base, suffix, mobile = false) {
  const session = await open(base + suffix, { mobile });
  try {
    const count = await session.page.locator(selectors).count();
    assert(count > 0, 'Expected actual production Mermaid blocks');
    await expectSVG(session.page, count);
    assert.equal(await session.page.locator('.pages-mermaid details code').count(), count, 'Original source must survive');
    const geometry = await session.page.locator('.pages-mermaid-viewport').evaluateAll(nodes => nodes.map(n => ({ width: n.clientWidth, scroll: n.scrollWidth, svg: n.querySelector('svg').getBoundingClientRect().height })));
    assert(geometry.every(g => g.width > 0 && g.svg > 0), 'Diagrams must be visible, not empty output');
    if (mobile && !liveURL) assert(geometry.some(g => g.scroll > g.width), 'Wide mobile diagrams must scroll rather than squash');
    assert.equal(session.errors.length, 0, JSON.stringify(session.errors));
    assert.equal(session.dialogs.length, 0, 'No script dialogs from diagram content');
    const foreign = session.requests.filter(u => new URL(u).origin !== new URL(base).origin && !u.includes('/anchor-js/'));
    assert.deepEqual(foreign, [], 'Mermaid must not require third-party requests');
    state.results.push({ page: suffix || '/', diagrams: count, mobile, rendered: true, source_preserved: true });
  } finally { await session.context.close(); }
}
async function main() {
  const base = liveURL || await serve();
  browserServer = await chromium.launchServer({ executablePath: process.env.CHROMIUM_EXECUTABLE, headless: true, host: '127.0.0.1',
    env: { HOME: temp, PATH: process.env.PATH, LANG: 'C.UTF-8', TZ: 'UTC' } });
  browserPID = browserServer.process().pid; state.pid = browserPID;
  browser = await chromium.connect(browserServer.wsEndpoint());
  if (args.includes('--hold-ready')) {
    if (process.send) process.send({ ready: true, browserPID, port: state.port });
    await new Promise(() => {}); // Parent interrupts this exact owned run.
  }
  if (liveURL || siteDir) {
    const sourceAudit = JSON.parse(execFileSync('python3', [path.join(root, 'tests/pages/check_privacy.py')], { cwd: root, encoding: 'utf8' }));
    const context = await browser.newContext();
    try {
      const catResponse = await context.request.get(base + 'catalog.json');
      const docResponse = await context.request.get(base + 'docs/publication.json');
      assert.equal(catResponse.status(), 200); assert.equal(docResponse.status(), 200);
      const cat = await catResponse.json(), published = await docResponse.json();
      assert.equal(published.schema, '3ds-docs-publication-v1');
      assert.equal(published.hub_source_sha, cat.hub_source_sha, 'Mixed catalogue/docs source revisions');
      if (expectedCommit) assert.equal(published.hub_source_sha, expectedCommit, 'Stale or unintended deployment');
      assert.deepEqual(published.pages, policy.pages);
      assert.deepEqual(published.source_only, policy.source_only);
      for (const [file, hash] of Object.entries(published.sha256)) {
        const response = await context.request.get(base + file);
        assert.equal(response.status(), 200, 'Published docs asset/page unavailable: ' + file);
        assert.equal(crypto.createHash('sha256').update(await response.body()).digest('hex'), hash, 'Published bytes differ: ' + file);
      }
      const homepage = await context.newPage();
      await homepage.goto(base, { waitUntil: 'domcontentloaded' });
      assert((await homepage.title()).includes('FBI'), 'Catalogue homepage was overwritten');
      assert.equal(await homepage.locator('script').count(), 0, 'Catalogue must remain script-free');
      assert(await homepage.locator('a[href="' + policy.base_path + 'docs/"]').count(), 'Catalogue docs navigation missing');
      const rootResponse = await context.request.get(base);
      assert.equal(crypto.createHash('sha256').update(await rootResponse.body()).digest('hex'), published.catalogue_sha256['index.html']);
      await homepage.close();
      for (const forbidden of ['AGENTS.html', 'IMPLEMENTATION_PLAN.html', 'serve_3ds.py', 'tests/pages/test_pages.cjs', '_includes/head-custom.html']) {
        assert.equal((await context.request.get(base + forbidden)).status(), 404, 'Unapproved output exposed: ' + forbidden);
      }
      state.results.push({ catalogue_preserved: true, source_sha: published.hub_source_sha, output_allowlist_checked: true });
      for (const item of sourceAudit.inventory) {
        if (item.publication === 'source-only') {
          assert(sourceOnlyExceptions.has(item.source));
          state.results.push({ source: item.source, published: false, source_only: true }); continue;
        }
        const page = await context.newPage();
        try {
          const route = item.route.replace(/^\//, '');
          const response = await page.goto(base + route, { waitUntil: 'domcontentloaded', timeout: 30000 });
          if (!requirePublished(response.status(), item)) {
            state.results.push({ privacy_route: item.route, published: false, source_only: true }); continue;
          }
          const text = await page.locator('body').textContent();
          if (item.source === 'docs/SOP.md') assert(text.includes("--format '{{.Id}}'"), 'Liquid consumed the documented Podman template');
          const tokens = text.match(/(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])/g) || [];
          const hosts = tokens.filter(value => {
            const b = value.split('.').map(Number);
            if (b.some(n => n > 255) || value === '0.0.0.0' || b[0] === 127) return false;
            return !((b[0] === 192 && b[1] === 0 && b[2] === 2) || (b[0] === 198 && b[1] === 51 && b[2] === 100) || (b[0] === 203 && b[1] === 0 && b[2] === 113));
          });
          assert.equal(hosts.length, 0, 'Identifying network literal in live route: ' + item.route);
          state.results.push({ privacy_route: item.route, published: true, identifying_hosts: 0 });
        } finally { await page.close(); }
      }
      if (siteDir) {
        const missing = await context.request.get(base + 'docs/STATUS.html?case=missing-status');
        assert.equal(missing.status(), 404);
        assert.equal(missing.headers()['x-pages-test-injected'], 'missing-STATUS');
        assert.throws(() => requirePublished(missing.status(), { source: 'docs/STATUS.md', route: 'docs/STATUS.html' }), /Required public route unavailable/);
        state.results.push({ control: 'missing-authoritative-STATUS', injection_reached: true, required_route_gate_rejected: true });
      }
    } finally { await context.close(); }
  }
  const assembled = !!(liveURL || siteDir);
  const primary = assembled ? 'docs/ARCHITECTURE.html' : '';
  const diagramRoutes = assembled ? Object.keys(policy.pages).filter(file =>
    /^```mermaid\s*$/m.test(fs.readFileSync(path.join(root, file), 'utf8'))).map(file => policy.pages[file])
    : ['', 'docs/ARCHITECTURE.html', 'docs/AGENT_PLAYBOOK.html'];
  for (const suffix of diagramRoutes) {
    if (suffix.endsWith('AGENT_PLAYBOOK.html')) {
      const p = await open(base + suffix); const n = await p.page.locator(selectors).count(); await p.context.close();
      if (!n) continue;
    }
    await normal(base, suffix);
  }
  await normal(base, primary, true);
  if (!liveURL) {
    const session = await open(base + primary);
    try {
      await expectSVG(session.page, await session.page.locator(selectors).count());
      // Validate every candidate Mermaid fence, not only the older captured diagrams.
      const sources = ['README.md', ...Object.keys(policy.pages)].flatMap(file =>
        Array.from(fs.readFileSync(path.join(root, file), 'utf8').matchAll(/```mermaid\r?\n([\s\S]*?)```/g), m => m[1]));
      const candidate = await session.page.evaluate(async list => {
        const results = [];
        for (const [index, source] of list.entries()) {
          if (!await window.mermaid.parse(source, { suppressErrors: true })) return false;
          const rendered = await window.mermaid.render('candidate-diagram-' + index, source);
          results.push(rendered.svg.includes('<svg'));
        }
        return results.every(Boolean);
      }, sources);
      assert(candidate && sources.length > 0, 'Candidate source diagram must render');
      const count = await session.page.locator('.pages-mermaid').count();
      await session.page.addScriptTag({ url: base + 'assets/js/mermaid-loader.js' });
      await session.page.waitForTimeout(100);
      assert.equal(await session.page.locator('.pages-mermaid').count(), count, 'Repeated enhancement must not duplicate diagrams');
      state.results.push({ candidate_diagrams: sources.length, all_rendered: true, repeated_loader_idempotent: true });
    } finally { await session.context.close(); }
  }
  if (!liveURL) {
    let s = await open(base + primary + '?case=omitted');
    try {
      const n = await s.page.locator(selectors).count(); assert(n > 0);
      await assert.rejects(() => expectSVG(s.page, n, 1200), 'Omitted renderer must fail the SVG gate');
      state.results.push({ control: 'omitted-loader', raw_source_only: true, rejected_by_SVG_gate: true });
    } finally { await s.context.close(); }
    s = await open(base + 'docs/ARCHITECTURE.html?case=bad');
    try {
      const n = await s.page.locator(selectors).count(); await expectSVG(s.page, n - 1);
      assert.equal(await s.page.locator('.pages-mermaid-fallback').count(), 1);
      state.results.push({ control: 'bad-diagram', other_diagrams_rendered: n - 1, source_and_notice_retained: true });
    } finally { await s.context.close(); }
    s = await open(base + primary + '?case=xss');
    try {
      const n = await s.page.locator(selectors).count(); await expectSVG(s.page, n);
      assert.equal(s.dialogs.length, 0); assert.equal(await s.page.locator('.pages-mermaid-viewport img[onerror]').count(), 0);
      state.results.push({ control: 'HTML-like-label', script_dialogs: 0 });
    } finally { await s.context.close(); }
    s = await open(base + primary, { missing: true });
    try {
      const n = await s.page.locator(selectors).count(); await s.page.waitForSelector('.pages-mermaid-fallback');
      assert.equal(await s.page.locator('.pages-mermaid-fallback').count(), n);
      assert.equal(await s.page.locator('.pages-mermaid-viewport > svg').count(), 0);
      assert(await s.page.locator(selectors).first().isVisible());
      state.results.push({ control: 'missing-library', readable_source_retained: true, visible_failure: true });
    } finally { await s.context.close(); }
    s = await open(base + 'docs/SOP.html');
    try { await s.page.waitForTimeout(300); assert(!s.requests.some(u => u.includes('/assets/vendor/'))); state.results.push({ control: 'no-diagram-page', vendor_downloads: 0 }); }
    finally { await s.context.close(); }
  }
}
async function cleanupProbe() {
  for (const failure of [false, true]) {
    const child = spawn(process.execPath, [__filename, '--hold-ready', ...(siteDir ? ['--site-dir', siteDir] : []), ...(failure ? ['--inject-close-failure'] : [])], { env: process.env, stdio: ['ignore', 'pipe', 'pipe', 'ipc'] });
    let owned, closed;
    child.on('message', message => { if (message.cleanup) closed = message.cleanup; });
    try {
      owned = await bounded(new Promise((resolve, reject) => { child.once('message', resolve); child.once('error', reject); }), 30000);
      const exited = new Promise(resolve => child.once('exit', (code, signal) => resolve({ code, signal })));
      child.kill('SIGTERM'); const result = await bounded(exited, 20000);
      assert.equal(result.code, 143); assert(!alive(owned.browserPID), 'Cancelled child leaked browser');
      assert(closed && closed.browser_absent && closed.listener_closed, 'Cleanup acknowledgement missing');
      if (failure) assert(closed.graceful_error && closed.kill_fallback, 'Injected cleanup fallback not observed');
      await new Promise((resolve, reject) => {
        const socket = net.connect({ host: '127.0.0.1', port: owned.port });
        socket.once('connect', () => { socket.destroy(); reject(new Error('Owned listener port still reachable')); });
        socket.once('error', error => error.code === 'ECONNREFUSED' ? resolve() : reject(error));
        socket.setTimeout(3000, () => { socket.destroy(); reject(new Error('Port absence uninspectable')); });
      });
      state.results.push({ cleanup_probe: true, injected_close_failure: failure, observed: closed, browser_absent: true, listener_port_closed: true, child_exit: result.code });
    } finally { if (child.exitCode === null) child.kill('SIGTERM'); }
  }
}
(async () => {
  let failed;
  try { if (args.includes('--cleanup-probe')) await cleanupProbe(); else await main(); }
  catch (e) { failed = e; }
  try { await cleanup(); } catch (e) { failed ||= e; }
  state.pass = !failed;
  if (failed) state.error = failed.message;
  console.log(JSON.stringify(state, null, 2));
  process.exitCode = failed ? 1 : 0;
})();
