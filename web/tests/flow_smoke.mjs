// End-to-end smoke test of the studio: starts the local server (web/server/run.py) with a stand-in for the OpenAI API, then drives
// the real flow page and the editor in headless Chrome/Edge through the DevTools protocol:
//   upload image -> (broken, then good) scene -> compile -> GLB -> preview -> editor edit + "save to workspace" -> stale marks ->
//   build -> downloads;  paste a key -> consent -> read with the stand-in -> compile;  read + run everything in one click;
//   upload a ready-made spec (wrong image refused).
// The Blender steps run when the server finds Blender (skip with --skip-blender). Needs Chrome or Edge and Python; not part of `npm test`.
//
//   node tests/flow_smoke.mjs [--shots <dir>] [--chrome <path>] [--skip-blender] [--image <png> --scene <json>]     (npm run smoke:flow)

import { spawn, spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import net from 'node:net';
import assert from 'node:assert/strict';

const here = fileURLToPath(new URL('.', import.meta.url));
const webDir = resolve(here, '..');
const repo = resolve(webDir, '..');
const arg = (name, fallback) => { const i = process.argv.indexOf(name); return i > 0 ? process.argv[i + 1] : fallback; };
const flag = (name) => process.argv.includes(name);
const shots = resolve(arg('--shots', join(repo, 'output', '_web_flow_smoke')));
mkdirSync(shots, { recursive: true });

const CHROMES = [arg('--chrome'), process.env.CHROME,
  'C:/Program Files/Google/Chrome/Application/chrome.exe', 'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser',
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'].filter(Boolean);
const chrome = CHROMES.find((p) => existsSync(p));
if (!chrome) { console.error('No Chrome/Edge found; pass --chrome <path>'); process.exit(2); }

const freePort = () => new Promise((res, rej) => {
  const srv = net.createServer();
  srv.on('error', rej);
  srv.listen(0, '127.0.0.1', () => { const { port } = srv.address(); srv.close(() => res(port)); });
});
const APP_PORT = await freePort();
const DEBUG_PORT = await freePort();
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const children = [];
const profile = mkdtempSync(join(tmpdir(), 'booth-flow-profile-'));
const work = mkdtempSync(join(tmpdir(), 'booth-flow-work-'));
const jobsDir = join(work, 'jobs');
const custom = Boolean(arg('--image'));                                  // a real picture: the fit need not be perfect, only reported
const FIT = custom ? /拟合 \w+，残差 [\d.]+ px/ : /拟合 fitted/;
const KEY = 'sk-smoke-secret-0123456789';
const BASE = `http://127.0.0.1:${APP_PORT}`;

async function waitFor(fn, what, ms = 15000) {
  const end = Date.now() + ms;
  for (;;) {
    try { const v = await fn(); if (v) return v; } catch { /* retry */ }
    if (Date.now() > end) throw new Error(`timed out waiting for ${what}`);
    await sleep(150);
  }
}

function cleanup() {
  for (const c of children) {
    try {
      if (process.platform === 'win32') spawnSync('taskkill', ['/PID', String(c.pid), '/T', '/F'], { stdio: 'ignore' });
      else c.kill();
    } catch { /* already gone */ }
  }
  try { rmSync(profile, { recursive: true, force: true }); } catch { /* chrome may still hold files */ }
  if (!flag('--keep')) { try { rmSync(work, { recursive: true, force: true }); } catch { /* ignore */ } }
}

async function connect(url) {
  const ws = new WebSocket(url);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error('devtools socket failed')); });
  let id = 0;
  const pending = new Map();
  const listeners = [];
  ws.onmessage = (m) => {
    const msg = JSON.parse(m.data);
    if (msg.id && pending.has(msg.id)) { const { res, rej } = pending.get(msg.id); pending.delete(msg.id); if (msg.error) rej(new Error(msg.error.message)); else res(msg.result); }
    else listeners.forEach((l) => l(msg));
  };
  return {
    send: (method, params = {}) => new Promise((res, rej) => { const i = ++id; pending.set(i, { res, rej }); ws.send(JSON.stringify({ id: i, method, params })); }),
    on: (l) => listeners.push(l),
    close: () => ws.close(),
  };
}

const failures = [];
const log = (ok, name, extra = '') => { console.log(`${ok ? 'ok  ' : 'FAIL'} ${name}${extra ? ` — ${extra}` : ''}`); if (!ok) failures.push(name); };
let diagnose = async () => '';
async function step(name, fn) {
  const started = Date.now();
  try { await fn(); log(true, name, `${Math.round((Date.now() - started) / 1000)} s`); } catch (e) {
    log(false, name, String(e.message).split('\n').slice(0, 8).join(' | '));
    console.log(`     page: ${await diagnose().catch(() => '?')}`);
  }
}

function files(dir) {
  const out = [];
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) out.push(...files(p)); else out.push(p);
  }
  return out;
}

async function main() {
  // ---- inputs: the synthetic picture and scene, or the ones given on the command line
  const fixtures = join(work, 'fixtures');
  const made = spawnSync('python', [join(here, 'make_flow_fixtures.py'), fixtures], { encoding: 'utf8' });
  assert.equal(made.status, 0, made.stderr);
  const imageFile = resolve(arg('--image', join(fixtures, 'booth.png')));
  const sceneFile = resolve(arg('--scene', join(fixtures, 'scene.json')));
  const badSceneFile = join(fixtures, 'bad_scene.json');

  // ---- the stand-in for OpenAI, then the studio server without a key
  const mock = spawn('python', [join(here, 'mock_openai.py'), '--scene', sceneFile], { stdio: ['ignore', 'pipe', 'inherit'] });
  children.push(mock);
  const base = await new Promise((res, rej) => {
    let text = '';
    mock.stdout.on('data', (d) => { text += d; const m = text.match(/at (http:\S+)/); if (m) res(m[1]); });
    mock.on('exit', () => rej(new Error('the OpenAI stand-in did not start')));
  });
  const env = { ...process.env }; delete env.OPENAI_API_KEY;
  children.push(spawn('python', [join(webDir, 'server', 'run.py'), '--port', String(APP_PORT), '--no-browser', '--jobs-dir', jobsDir,
    '--openai-base-url', base, '--openai-model', 'test-model'], { stdio: 'ignore', env }));
  const health = await waitFor(async () => (await fetch(`${BASE}/api/health`)).json(), 'the studio server');
  const withBlender = Boolean(health.blender) && !flag('--skip-blender');
  console.log(`studio ${BASE}, OpenAI stand-in ${base}, Blender ${withBlender ? health.blender : 'skipped'}`);

  children.push(spawn(chrome, ['--headless=new', `--remote-debugging-port=${DEBUG_PORT}`, '--remote-allow-origins=*', `--user-data-dir=${profile}`,
    '--no-first-run', '--no-default-browser-check', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist',
    '--disable-gpu-sandbox', '--hide-scrollbars', '--window-size=1400,1000', 'about:blank'], { stdio: 'ignore' }));
  const target = await waitFor(async () => (await (await fetch(`http://127.0.0.1:${DEBUG_PORT}/json/list`)).json()).find((t) => t.type === 'page'), 'the browser');
  const cdp = await connect(target.webSocketDebuggerUrl);
  const consoleErrors = [];
  cdp.on((m) => {
    if (m.method === 'Runtime.exceptionThrown') consoleErrors.push(m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text);
    if (m.method === 'Log.entryAdded' && m.params.entry.level === 'error' && !/status of 4(09|22)/.test(m.params.entry.text)) consoleErrors.push(`${m.params.entry.text} ${m.params.entry.url || ''}`);
    if (m.method === 'Runtime.consoleAPICalled' && m.params.type === 'error') consoleErrors.push(m.params.args.map((a) => a.value ?? a.description).join(' '));
  });
  await cdp.send('Runtime.enable');
  await cdp.send('Log.enable');
  await cdp.send('Page.enable');
  await cdp.send('DOM.enable');
  await cdp.send('Emulation.setDeviceMetricsOverride', { width: 1400, height: 1000, deviceScaleFactor: 1, mobile: false });

  const ev = async (expression) => {
    const r = await cdp.send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text);
    return r.result.value;
  };
  const shot = async (name) => {
    await sleep(300);
    const { data } = await cdp.send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true });
    writeFileSync(join(shots, name), Buffer.from(data, 'base64'));
  };
  const api = async (path) => (await fetch(`${BASE}${path}`)).json();
  const goto = async (path) => { await cdp.send('Page.navigate', { url: `${BASE}${path}` }); await waitFor(() => ev('document.body.dataset.ready'), `${path} ready`, 60000); };
  const upload = async (selector, file) => {
    const { root } = await cdp.send('DOM.getDocument', { depth: 0 });
    const { nodeId } = await cdp.send('DOM.querySelector', { nodeId: root.nodeId, selector });
    assert.ok(nodeId, `no element ${selector}`);
    await cdp.send('DOM.setFileInputFiles', { files: [file], nodeId });
  };
  const click = (id) => ev(`document.getElementById('${id}').click()`);
  const state = (stepName) => ev(`document.querySelector('.badge[data-step="${stepName}"]')?.dataset.state || ''`);
  const waitState = (stepName, wanted, ms = 120000) => waitFor(async () => {
    const s = await state(stepName);
    if (s === 'error' && wanted !== 'error') throw new Error(`${stepName} failed: ${await ev(`document.querySelector('#card-${stepName} .msg')?.textContent || document.querySelector('#cards .errors')?.innerText || ''`)}`);
    return s === wanted;
  }, `${stepName} to be ${wanted}`, ms);
  const text = (selector) => ev(`document.querySelector('${selector}')?.innerText || ''`);
  const imageLoaded = (selector) => ev(`(() => { const i = document.querySelector('${selector}'); return Boolean(i && i.complete && i.naturalWidth > 0); })()`);
  const jobId = () => ev('document.body.dataset.job');
  const newJob = async () => {
    await click('btnNew');
    await waitFor(() => ev("Boolean(document.getElementById('imageInput'))"), 'the upload card');
    const before = await jobId();
    await upload('#imageInput', imageFile);
    await waitFor(async () => { const id = await jobId(); return id && id !== before; }, 'the new job');
    return jobId();
  };
  diagnose = () => ev(`JSON.stringify({ url: location.pathname + location.search, job: document.body.dataset.job, badges: [...document.querySelectorAll('.badge')].map((b) => b.dataset.step + ':' + b.dataset.state).join(' '), alerts: [...document.querySelectorAll('[role=alert]')].map((a) => a.innerText.slice(0, 200)) })`);

  // ------------------------------------------------------------ the manual route
  await cdp.send('Page.navigate', { url: `${BASE}/` });
  await step('the flow page loads and reports the machine honestly', async () => {
    await waitFor(() => ev('document.body.dataset.ready'), 'the flow page', 30000);
    assert.match(await text('#chipOpenai'), /没有 key/);
    assert.match(await text('#chipBlender'), withBlender ? /Blender 可用/ : /./);
    assert.ok(await ev("Boolean(document.getElementById('imageInput'))"));
    await shot('01_start.png');
  });

  let jobA;
  await step('uploading a picture creates a job and shows its size', async () => {
    await upload('#imageInput', imageFile);
    jobA = await waitFor(() => jobId(), 'the job');
    await waitFor(() => text('#card-图片').then((t) => /\d+ × \d+ px/.test(t)), 'the picture card');
    assert.match(await text('#card-图片'), custom ? /\d+ × \d+ px/ : /960 × 600 px/);
  });

  await step('a broken scene description is refused with the reason; a good one is accepted', async () => {
    await upload('#sceneInput', badSceneFile);
    await waitFor(() => text('#card-scene [role=alert]').then((t) => /SCOPE/.test(t)), 'the refusal');
    assert.equal(await state('scene'), 'idle');
    await shot('02_scene_refused.png');
    await upload('#sceneInput', sceneFile);
    await waitState('scene', 'done');
    assert.equal(await ev("document.querySelectorAll('#card-scene [role=alert]').length"), 0);
  });

  await step('compile fits the camera, builds a spec and draws the overlay', async () => {
    await click('btnCompile');
    await waitState('compile', 'done');
    assert.match(await text('#card-compile .metric'), FIT);
    await waitFor(() => imageLoaded('#card-compile img.shot'), 'the overlay image');
    assert.ok((await ev("document.querySelectorAll('#card-compile table.mini tr').length")) > 4);
    await shot('03_compiled.png');
  });

  await step('GLB export works without Blender', async () => {
    await click('btnGlb');
    await waitState('glb', 'done');
    const st = await api(`/api/jobs/${jobA}`);
    assert.ok(st.steps.glb.detail.exported > 50);
  });

  if (withBlender) {
    await step('preview renders the comparison sheet', async () => {
      await click('btnPreview');
      await waitState('preview', 'done', 600000);
      await waitFor(() => imageLoaded('#card-preview img.shot'), 'the sheet');
      await shot('04_preview.png');
    });
  }

  let edited;
  await step('the editor opens the job, an edit is saved to the workspace and the later steps go stale', async () => {
    await goto(`/index.html?job=${jobA}`);
    assert.equal(await ev('window.boothEditor.state.job'), jobA);
    const total = (await api(`/api/jobs/${jobA}`)).steps.compile.detail.components;
    await waitFor(async () => (await ev('window.boothEditor.state.spec?.components.length')) === total, 'the spec in the editor', 60000);
    assert.equal(await ev("document.getElementById('btnWorkspace').hidden"), false);
    assert.equal(await ev("document.getElementById('linkFlow').hidden"), false);
    const id = await ev('window.boothEditor.state.spec.components[3].id');
    const x0 = await ev('window.boothEditor.state.spec.components[3].location[0]');
    await ev(`window.boothEditor.select(['${id}'])`);
    for (const type of ['rawKeyDown', 'keyUp']) await cdp.send('Input.dispatchKeyEvent', { type, key: 'ArrowRight', code: 'ArrowRight', windowsVirtualKeyCode: 39 });
    await sleep(200);
    edited = x0 + 0.05;
    assert.ok(Math.abs(await ev('window.boothEditor.state.spec.components[3].location[0]') - edited) < 1e-9);
    await shot('05_editor.png');
    await click('btnWorkspace');
    await waitFor(async () => (await api(`/api/jobs/${jobA}`)).spec.origin === 'edited', 'the saved spec');
    const saved = await api(`/api/jobs/${jobA}/spec`);
    assert.ok(Math.abs(saved.components[3].location[0] - edited) < 1e-9);
    await goto(`/?job=${jobA}`);
    assert.equal(await state('glb'), 'stale');
    if (withBlender) assert.equal(await state('preview'), 'stale');
    await shot('06_stale.png');
  });

  if (withBlender) {
    await step('build makes the .blend and the client picture', async () => {
      await click('btnBuild');
      await waitState('build', 'done', 1500000);
      await waitFor(() => imageLoaded('#card-build .thumbs img.shot'), 'the client picture');
      await shot('07_built.png');
    });
  }

  await step('GLB again, then every download link serves a real file', async () => {
    await click('btnGlb');
    await waitState('glb', 'done');
    const got = await ev(`(async () => { const out = []; for (const a of document.querySelectorAll('a[download]')) {
      const r = await fetch(a.href); const b = new Uint8Array(await r.arrayBuffer());
      out.push({ label: a.textContent, status: r.status, size: b.length, head: String.fromCharCode(...b.slice(0, 4)) }); } return out; })()`);
    const by = Object.fromEntries(got.map((g) => [g.label, g]));
    for (const g of got) assert.ok(g.status === 200 && g.size > 100, JSON.stringify(g));
    assert.equal(by['.glb'].head, 'glTF');
    assert.equal(by['spec.json'].head.slice(0, 1), '{');
    if (withBlender) {
      assert.equal(by['客户图 PNG'].head.slice(1, 4), 'PNG');
      assert.ok(by['.blend'].size > 10000);
      assert.equal(await ev("document.getElementById('btnOpen').disabled"), false);
    }
    await shot('08_downloads.png');
  });

  // ------------------------------------------------------------ states the review found fragile
  await step('compile asks before it overwrites an edited spec; saying no changes nothing', async () => {
    await goto(`/?job=${jobA}`);
    const before = await api(`/api/jobs/${jobA}`);
    assert.equal(before.spec.origin, 'edited');
    await ev('window.__asked = 0; window.confirm = () => { window.__asked += 1; return false; }');
    await click('btnCompile');
    await sleep(600);
    assert.equal(await ev('window.__asked'), 1);
    const after = await api(`/api/jobs/${jobA}`);
    assert.equal(after.spec.origin, 'edited');
    assert.equal(after.steps.compile.updated, before.steps.compile.updated);
  });

  if (withBlender) {
    await step('one click builds from the edited spec and does not recompile over it', async () => {
      const before = await api(`/api/jobs/${jobA}`);
      const spec = await api(`/api/jobs/${jobA}/spec`);
      await click('btnAuto');
      for (const name of ['preview', 'build', 'glb']) await waitState(name, 'done', 1500000);
      const after = await api(`/api/jobs/${jobA}`);
      assert.equal(after.spec.origin, 'edited');
      assert.equal(after.steps.compile.updated, before.steps.compile.updated);                 // compile was not run again
      assert.deepEqual(await api(`/api/jobs/${jobA}/spec`), spec);
    });
  }

  await step('leaving a job while its poll is still in flight does not bring the job back', async () => {
    await goto(`/?job=${jobA}`);
    await ev(`(() => { const real = window.fetch; let release;
      window.fetch = (u, i) => (String(u).split('?')[0].split('/').length === 4 && String(u).includes('/api/jobs/') && (!i || !i.method || i.method === 'GET')) ? new Promise((res) => { release = () => res(real(u, i)); }) : real(u, i);
      window.__release = () => { window.fetch = real; release(); };
      window.studioFlow.loadJob('${jobA}', { quiet: true }); })()`);
    await click('btnNew');
    await waitFor(() => ev("Boolean(document.getElementById('imageInput'))"), 'the upload card');
    await ev('window.__release()');
    await sleep(800);
    assert.equal(await ev('window.studioFlow.ui.job'), null);
    assert.equal(await ev("Boolean(document.getElementById('imageInput'))"), true);
  });

  await step('the page says when the server is away and recovers by itself', async () => {
    await goto(`/?job=${jobA}`);
    await ev("window.__real = window.fetch; window.fetch = () => Promise.reject(new TypeError('Failed to fetch'))");
    await ev(`window.studioFlow.loadJob('${jobA}', { quiet: true })`);
    assert.match(await text('#chipBlender'), /没有连上本机服务/);
    await ev('window.fetch = window.__real');
    await waitFor(() => text('#chipBlender').then((t) => t !== '' && !/没有连上/.test(t)), 'the page to reconnect', 15000);
  });

  // ------------------------------------------------------------ the OpenAI route (against the stand-in)
  await step('without a key the automatic reading is off; pasting a key and consent turn it on', async () => {
    const jobB = await newJob();
    assert.notEqual(jobB, jobA);
    await click('tab-openai');
    assert.equal(await ev("document.getElementById('btnRead').disabled"), true);
    await ev(`(() => { const el = document.getElementById('keyInput'); el.value = '${KEY}'; el.dispatchEvent(new Event('input', { bubbles: true })); })()`);
    await click('btnSaveKey');
    await waitFor(() => text('#chipOpenai').then((t) => /key 已配置/.test(t)), 'the key chip');
    assert.equal(await ev("document.getElementById('keyInput').value"), '');          // the page does not keep the key
    assert.equal(await ev("document.getElementById('btnRead').disabled"), true);       // no consent yet
    await click('consent');
    assert.equal(await ev("document.getElementById('btnRead').disabled"), false);
    await shot('09_openai_ready.png');
    await click('btnRead');
    await waitState('scene', 'done');
    assert.match(await text('#card-scene .msg'), /test-model/);
    await click('btnCompile');
    await waitState('compile', 'done');
    assert.match(await text('#card-compile .metric'), FIT);
    await shot('10_openai_compiled.png');
  });

  if (withBlender) {
    await step('read with OpenAI and run everything in one click', async () => {
      await newJob();
      await click('tab-openai');
      await click('consent');
      await click('btnReadAuto');
      await waitState('scene', 'done');
      for (const s of ['compile', 'preview', 'build', 'glb']) await waitState(s, 'done', 1500000);
      await waitFor(() => imageLoaded('#card-build .thumbs img.shot'), 'the client picture');
      await shot('11_one_click.png');
    });
  }

  // ------------------------------------------------------------ the spec route
  await step('a ready-made spec for this picture skips reading and compiling; one for another picture is refused', async () => {
    const spec = await api(`/api/jobs/${jobA}/spec`);
    const good = join(work, 'good.spec.json');
    const wrong = join(work, 'wrong.spec.json');
    writeFileSync(good, JSON.stringify(spec));
    writeFileSync(wrong, JSON.stringify({ ...spec, source: { ...spec.source, sha256: '0'.repeat(64) } }));
    await newJob();
    await click('tab-spec');
    await upload('#specInput', wrong);
    await waitFor(() => text('#card-scene [role=alert]').then((t) => /sha256/.test(t)), 'the refusal');
    await upload('#specInput', good);
    await waitState('scene', 'skipped');
    await waitState('compile', 'skipped');
    assert.equal(await ev("document.getElementById('linkEditor').getAttribute('href').startsWith('index.html?job=')"), true);
    await click('btnGlb');
    await waitState('glb', 'done');
    await shot('12_spec_upload.png');
  });

  await step('no key or picture bytes were written into any job file', async () => {
    const bad = files(jobsDir).filter((p) => /\.(json|txt|md|log)$/.test(p) && readFileSync(p, 'utf8').includes(KEY));
    assert.deepEqual(bad, []);
    const requests = files(jobsDir).filter((p) => p.endsWith('request.json'));
    assert.ok(requests.length >= 1);
    for (const r of requests) assert.ok(!readFileSync(r, 'utf8').includes('base64,'), r);
  });

  log(consoleErrors.length === 0, 'no console errors or exceptions', consoleErrors.slice(0, 3).join(' | '));
  cdp.close();
}

for (const sig of ['SIGINT', 'SIGTERM']) process.on(sig, () => { cleanup(); process.exit(130); });
try {
  await main();
} catch (e) {
  log(false, 'flow smoke run', e.message);
} finally {
  cleanup();
}
console.log(failures.length ? `\n${failures.length} FAILED` : `\nall flow steps passed; screenshots in ${shots}`);
process.exit(failures.length ? 1 : 0);
