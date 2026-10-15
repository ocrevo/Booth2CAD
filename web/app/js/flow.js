// The flow page: image -> reading -> compile -> preview -> edit -> build -> open in Blender, one card per step.
// It only talks to the local studio server (/api). Every card shows what that step did, what went wrong and how long it took.

const $ = (id) => document.getElementById(id);
const STATE = { idle: '未开始', queued: '排队中', running: '运行中', done: '完成', error: '失败', stale: '已过期', skipped: '已跳过' };
const RUNNING = ['running', 'queued'];

function h(tag, attrs = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === false || v === null || v === undefined) continue;
    if (k === 'class') el.className = v;
    else if (k.startsWith('on')) el.addEventListener(k.slice(2).toLowerCase(), v);
    else if (k === 'value') el.value = v;
    else el.setAttribute(k, v === true ? '' : v);
  }
  for (const kid of kids.flat(Infinity)) if (kid !== null && kid !== undefined && kid !== false) el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  return el;
}

const ui = { job: null, current: null, offline: false, health: null, tab: 'scene', consent: false, key: '', hd: false, notes: {}, timer: null, last: '' };
const MAX_IMAGE_MB = 25;

async function call(method, path, { json, raw, type } = {}) {
  const init = { method, headers: {} };
  if (json !== undefined) { init.body = JSON.stringify(json); init.headers['Content-Type'] = 'application/json'; }
  if (raw !== undefined) { init.body = raw; init.headers['Content-Type'] = type || 'application/octet-stream'; }
  let res;
  try {
    res = await fetch(path, init);
  } catch {
    return { ok: false, status: 0, data: { error: '连不上本机服务（服务停了或重启了？）' } };
  }
  let data = null;
  try { data = await res.json(); } catch { /* not JSON */ }
  return { ok: res.ok, status: res.status, data };
}

// ---------------------------------------------------------------- data
async function refreshHealth() {
  const { ok, data } = await call('GET', '/api/health');
  ui.health = ok ? data : null;
  const b = $('chipBlender');
  const o = $('chipOpenai');
  if (!ui.health) { b.textContent = '没有连上本机服务'; b.className = 'chip off'; o.textContent = ''; return; }
  b.textContent = ui.health.blender ? 'Blender 可用' : '没找到 Blender（预览和生成不可用）';
  b.className = `chip ${ui.health.blender ? 'ok' : 'off'}`;
  o.textContent = ui.health.openai.configured ? `OpenAI key 已配置（${ui.health.openai.model}）` : 'OpenAI 没有 key（自动读图不可用）';
  o.className = `chip ${ui.health.openai.configured ? 'ok' : 'off'}`;
}

async function refreshPicker() {
  const { data } = await call('GET', '/api/jobs');
  const picker = $('jobPicker');
  picker.replaceChildren(h('option', { value: '' }, '（选择已有任务）'),
    ...(data?.jobs || []).map((j) => h('option', { value: j.id, selected: ui.job && j.id === ui.job.id }, `${j.id} · ${j.image}`)));
}

async function loadJob(id, { quiet = false } = {}) {
  ui.current = id;
  clearTimeout(ui.timer);
  const { ok, status, data } = await call('GET', `/api/jobs/${encodeURIComponent(id)}`);
  if (ui.current !== id) return;                            // the user moved on to another job while this request was out
  if (status === 0) {                                       // the server is away: say so and keep trying
    ui.offline = true;
    await refreshHealth();
    ui.timer = setTimeout(() => loadJob(id, { quiet: true }), 3000);
    return;
  }
  if (ui.offline) { ui.offline = false; await refreshHealth(); }
  if (!ok) { ui.job = null; ui.notes.job = `找不到任务 ${id}`; render(); return; }
  ui.job = data;
  $('jobLabel').textContent = data.id;
  document.body.dataset.job = data.id;
  const running = Boolean(data.busy) || Object.values(data.steps).some((s) => RUNNING.includes(s.state));
  document.body.dataset.busy = String(running);
  const signature = JSON.stringify(data);
  if (!quiet || signature !== ui.last) { ui.last = signature; render(); }
  if (running) ui.timer = setTimeout(() => loadJob(id, { quiet: true }), 1500);
}

function go(id) {
  ui.consent = false;                          // the consent is for one picture: ask again for the next job
  ui.notes = {};                               // errors belong to the job they happened in
  ui.current = id || null;
  clearTimeout(ui.timer);                      // a poll scheduled for the job we are leaving must not bring it back
  const url = new URL(window.location.href);
  if (id) url.searchParams.set('job', id); else url.searchParams.delete('job');
  window.history.replaceState({}, '', url);
  if (id) loadJob(id); else { ui.job = null; $('jobLabel').textContent = ''; render(); }
  refreshPicker();
}

// ---------------------------------------------------------------- actions
const busy = () => !ui.job || Boolean(ui.job.busy) || Object.values(ui.job.steps).some((s) => RUNNING.includes(s.state));

async function act(card, path, body) {
  ui.notes[card] = null;
  const res = await call('POST', `/api/jobs/${ui.job.id}/${path}`, { json: body || {} });
  if (!res.ok) ui.notes[card] = res.data || { error: `HTTP ${res.status}` };
  else if (card === 'open') ui.notes.opened = '已请求 Blender 打开这个文件（窗口出现可能要几秒）。';
  await loadJob(ui.job.id);
}

async function uploadImage(file) {
  ui.notes.image = null;
  if (file.size > MAX_IMAGE_MB * 1024 * 1024) { ui.notes.image = { error: `图片超过 ${MAX_IMAGE_MB} MB，请先缩小` }; render(); return; }
  const res = await call('POST', `/api/jobs?name=${encodeURIComponent(file.name)}`, { raw: await file.arrayBuffer(), type: file.type || 'image/png' });
  if (!res.ok) { ui.notes.image = res.data; render(); return; }
  go(res.data.id);
}

async function uploadJson(card, path, file) {
  ui.notes[card] = null;
  let body;
  try { body = JSON.parse(await file.text()); } catch (e) { ui.notes[card] = { error: `${file.name} 不是有效的 JSON：${e.message}` }; render(); return; }
  const res = await call('PUT', `/api/jobs/${ui.job.id}/${path}`, { json: body });
  if (!res.ok) ui.notes[card] = res.data;
  await loadJob(ui.job.id);
}

async function saveKey() {
  const res = await call('POST', '/api/config', { json: { openai_api_key: ui.key } });
  ui.key = '';
  if (res.ok) { await refreshHealth(); }
  render();
}

// ---------------------------------------------------------------- pieces
function badge(step) {
  const s = ui.job.steps[step];
  return h('span', { class: `badge s-${s.state}`, 'data-step': step, 'data-state': s.state }, STATE[s.state] || s.state);
}

function summary(step) {
  const s = ui.job.steps[step];
  const text = [s.message, s.seconds != null ? `${s.seconds} 秒` : ''].filter(Boolean).join(' · ');
  return h('span', { class: `msg ${s.state === 'error' ? 'error' : ''}` }, text);
}

function errorBlock(source) {
  if (!source) return null;
  const list = source.errors || source.detail?.errors || [];
  return h('div', { class: 'errors', role: 'alert' },
    source.error || source.message || '',
    list.length ? h('ul', {}, list.slice(0, 12).map((e) => h('li', {}, h('code', {}, `${e.code || ''} ${e.where || e.path || ''}`.trim()), ` ${e.message || ''}`))) : null,
    source.log_tail ? h('details', {}, h('summary', {}, '日志'), h('pre', { class: 'log' }, source.log_tail)) : null);
}

function card(num, title, step, ...body) {
  return h('section', { class: 'card', id: `card-${step || title}` },
    h('header', {}, h('span', { class: 'num' }, num), h('h2', {}, title), step ? badge(step) : null, step ? summary(step) : null),
    h('div', { class: 'body' }, body));
}

const fileUrl = (rel) => `/api/jobs/${ui.job.id}/files/${rel}`;
const image = (rel, alt) => h('img', { class: 'shot', src: `${fileUrl(rel)}?t=${encodeURIComponent(ui.job.steps.compile.updated)}${ui.job.steps.preview.updated}${ui.job.steps.build.updated}`, alt });

function listOf(title, items, render) {
  if (!items || !items.length) return null;
  return h('details', {}, h('summary', {}, `${title}（${items.length}）`), h('ul', {}, items.map((x) => h('li', {}, render(x)))));
}

// ---------------------------------------------------------------- cards
function cardImage() {
  if (!ui.job) {
    return card(1, '上传图片', null,
      h('p', { class: 'hint' }, '选一张展台效果图（PNG 或 JPEG）。图片只保存在本机的任务目录里，除非你在第 2 步选择让 OpenAI 读图并勾选同意。'),
      h('div', { class: 'row' }, h('input', { type: 'file', id: 'imageInput', accept: 'image/png,image/jpeg', onChange: (e) => e.target.files[0] && uploadImage(e.target.files[0]) })),
      errorBlock(ui.notes.image), errorBlock(ui.notes.job ? { error: ui.notes.job } : null));
  }
  const im = ui.job.image;
  return card(1, '图片', null,
    h('div', { class: 'row' }, h('img', { class: 'shot', style: 'max-height:160px', src: fileUrl(im.name), alt: '原图' }),
      h('div', { class: 'metric' }, `${im.original_name}`, h('br'), `${im.width} × ${im.height} px`, h('br'), `sha256 ${im.sha256.slice(0, 12)}…`)));
}

function cardRead() {
  const tabs = [['scene', '上传场景描述'], ['spec', '直接上传 spec'], ['openai', 'OpenAI 自动读图']];
  const o = ui.health?.openai;
  const free = !busy();
  let panel;
  if (ui.tab === 'scene') {
    panel = h('div', { class: 'panel' },
      h('p', { class: 'hint' }, '场景描述是“图上看到什么”的 JSON（像素加普通数字，格式见 references/scene-description.md），可以由人、脚本或 agent 写好再上传。'),
      h('input', { type: 'file', id: 'sceneInput', accept: '.json,application/json', disabled: !free, onChange: (e) => e.target.files[0] && uploadJson('read', 'scene', e.target.files[0]) }));
  } else if (ui.tab === 'spec') {
    panel = h('div', { class: 'panel' },
      h('p', { class: 'hint' }, '已经有这张图对应的 spec.json 时直接上传，会跳过读图和编译。spec 里记录的图片 sha256 必须和本任务的图片一致。'),
      h('input', { type: 'file', id: 'specInput', accept: '.json,application/json', disabled: !free, onChange: (e) => e.target.files[0] && uploadJson('read', 'spec?origin=uploaded', e.target.files[0]) }));
  } else {
    const ready = Boolean(o?.configured) && ui.consent && free;
    panel = h('div', { class: 'panel' },
      h('p', { class: 'hint' }, o?.configured ? `已配置 key（来源：${o.key_source === 'env' ? '环境变量' : '页面，仅在服务内存里'}）；模型 ${o.model}；接口 ${o.base_url}` : '没有 key：设置环境变量 OPENAI_API_KEY 后重启服务，或在下面粘贴（只保存在服务进程的内存里，不写盘）。'),
      h('div', { class: 'row' }, h('input', { type: 'password', id: 'keyInput', placeholder: 'sk-…', autocomplete: 'off', value: ui.key, onInput: (e) => { ui.key = e.target.value; } }),
        h('button', { id: 'btnSaveKey', onClick: saveKey }, '保存 key')),
      h('label', { class: 'row' }, h('input', { type: 'checkbox', id: 'consent', checked: ui.consent, onChange: (e) => { ui.consent = e.target.checked; render(); } }),
        `我同意把这张图片发送给 ${o?.base_url || 'OpenAI'}（用于读出场景描述）`),
      h('div', { class: 'row' },
        h('button', { id: 'btnRead', class: 'primary', disabled: !ready, onClick: () => act('read', 'read', { mode: 'openai', consent: true }) }, '读图'),
        h('button', { id: 'btnReadAuto', disabled: !ready || !ui.health?.blender, onClick: () => act('read', 'auto', { mode: 'openai', consent: true, hd: ui.hd }) }, '读图并一键跑完'),
        !o?.configured ? h('span', { class: 'hint' }, '先配置 key') : !ui.consent ? h('span', { class: 'hint' }, '先勾选同意') : null));
  }
  const scene = ui.job.steps.scene;
  return card(2, '读图（图片 → 场景描述）', 'scene',
    h('div', { class: 'tabs' }, tabs.map(([k, label]) => h('button', { 'aria-pressed': String(ui.tab === k), id: `tab-${k}`, onClick: () => { ui.tab = k; render(); } }, label))),
    panel, errorBlock(ui.notes.read), scene.state === 'error' ? errorBlock({ errors: scene.detail?.errors, error: '' }) : null,
    ['done'].includes(scene.state) ? h('a', { class: 'plain', href: fileUrl('scene.json'), target: '_blank', rel: 'noopener' }, '查看 scene.json') : null);
}

function cardCompile() {
  const s = ui.job.steps.compile;
  const d = s.detail;
  const free = !busy();
  const fit = d?.fit;
  return card(3, '编译（场景描述 → spec）', 'compile',
    h('div', { class: 'row' }, h('button', { id: 'btnCompile', class: 'primary', disabled: !free, onClick: () => {
      if (ui.job.spec.origin === 'edited' && !window.confirm('重新编译会用场景描述重新生成 spec，覆盖你在编辑器里做的修改。继续吗？')) return;
      act('compile', 'compile');
    } }, '编译'),
      h('span', { class: 'hint' }, '拟合相机、把像素反投影成零件、校验。约几秒。')),
    errorBlock(ui.notes.compile), s.state === 'error' ? errorBlock({ errors: d?.errors || d?.detail?.errors }) : null,
    d && fit ? h('div', { class: 'body' },
      h('div', { class: 'metric' }, `拟合 ${fit.status}，残差 ${fit.rms_px} px（最大 ${fit.max_px} px）· ${d.components} 个零件 · 丢弃 ${d.dropped.length} · 调整 ${d.adjustments_total} · 代填假设 ${d.assumed_total}`),
      d.points?.length ? h('table', { class: 'mini' }, h('tr', {}, h('th', {}, '角点'), h('th', {}, '误差 px')),
        d.points.map((p) => h('tr', {}, h('td', {}, p.id), h('td', { class: p.err_px > 6 ? 'bad' : '' }, String(p.err_px))))) : null,
      d.overlay ? h('figure', { style: 'margin:0' }, image(d.overlay, '拟合叠加图'), h('figcaption', { class: 'hint' }, '拟合出的展台外框和 0.5 m 网格叠在原图上；对不上就说明角点读错了')) : null,
      listOf('被丢弃的构件', d.dropped, (x) => `${x.id}：${x.reason}`),
      listOf('调整', d.adjustments, (x) => `${x.id}：${x.what}`),
      listOf('代填的假设', d.assumed, (x) => `${x.id}.${x.what} = ${typeof x.value === 'object' ? JSON.stringify(x.value) : x.value}`),
      listOf('警告', d.warnings, (x) => x),
      listOf('拟合警告', fit.warnings, (x) => x)) : null);
}

function cardPreview() {
  const s = ui.job.steps.preview;
  const d = s.detail;
  const free = !busy() && Boolean(ui.health?.blender);
  return card(4, '预览（spec → Blender 对照图）', 'preview',
    h('div', { class: 'row' }, h('button', { id: 'btnPreview', class: 'primary', disabled: !free, onClick: () => act('preview', 'preview') }, '生成预览'),
      h('span', { class: 'hint' }, ui.health?.blender ? '渲染一张和原图同机位的对照图，约 10–30 秒。' : '没找到 Blender，这一步不可用。')),
    errorBlock(ui.notes.preview), s.state === 'error' ? errorBlock({ log_tail: d?.log_tail, errors: d?.errors }) : null,
    d?.sheet ? h('div', { class: 'body' }, h('div', { class: 'metric' }, `角点误差：中位数 ${d.landmark_median_px} px，最大 ${d.landmark_max_px} px`),
      h('figure', { style: 'margin:0' }, image(d.sheet, '预览对照'), h('figcaption', { class: 'hint' }, '左上原图，右上渲染，左下叠加，右下轮廓与角点')),
      listOf('设计检查提示（建议性）', d.design_findings, (x) => `${x.check}：${x.message}`)) : null);
}

function cardEdit() {
  const spec = ui.job.spec;
  const have = Boolean(spec.origin);
  const origin = { compiled: '由编译得到', uploaded: '直接上传', edited: '已在编辑器里修改' }[spec.origin] || '还没有 spec';
  return card(5, '编辑（在网页编辑器里改 spec）', null,
    h('p', { class: 'hint' }, `当前 spec：${origin}${spec.updated ? `（${spec.updated}）` : ''}。在编辑器里移动、改色、改尺寸、复制，改完点“保存到工作区”，预览和生成会被标为已过期，回来重新运行即可。`),
    h('div', { class: 'row' }, h('a', { id: 'linkEditor', class: have ? '' : 'plain', href: have ? `index.html?job=${ui.job.id}` : null, target: '_blank', rel: 'noopener' },
      h('button', { class: 'primary', disabled: !have }, '在编辑器中打开'))));
}

function cardBuild() {
  const s = ui.job.steps.build;
  const g = ui.job.steps.glb;
  const d = s.detail;
  const free = !busy();
  const canBuild = free && Boolean(ui.health?.blender) && Boolean(ui.job.spec.origin);
  const files = d?.files || {};
  return card(6, '生成（spec → .blend、客户图、GLB）', 'build',
    h('div', { class: 'row' },
      h('button', { id: 'btnBuild', class: 'primary', disabled: !canBuild, onClick: () => act('build', 'build', { hd: ui.hd }) }, '生成 .blend 和客户图'),
      h('label', { class: 'row' }, h('input', { type: 'checkbox', id: 'hd', checked: ui.hd, onChange: (e) => { ui.hd = e.target.checked; } }), '同时渲高清图（更慢）'),
      h('span', { class: 'hint' }, '用 Blender 渲染客户图，约 1–3 分钟（CPU）。')),
    errorBlock(ui.notes.build), s.state === 'error' ? errorBlock({ log_tail: d?.log_tail }) : null,
    d?.files ? h('div', { class: 'thumbs' }, [['client', '客户图'], ['reference', '同机位对照'], ['inspection', '第二视角']].filter(([k]) => files[k]).map(([k, label]) =>
      h('figure', {}, image(files[k], label), h('figcaption', {}, label)))) : null,
    h('div', { class: 'row' },
      h('button', { id: 'btnGlb', disabled: !free || !ui.job.spec.origin, onClick: () => act('glb', 'glb') }, '导出 GLB（不需要 Blender）'),
      badge('glb'), summary('glb')),
    errorBlock(ui.notes.glb), g.state === 'error' ? errorBlock({ error: g.message }) : null,
    g.detail?.skipped_text?.length || g.detail?.pattern_omitted?.length ? h('p', { class: 'hint' }, `GLB 不含：文字 ${g.detail.skipped_text.length} 个、格网纹样 ${g.detail.pattern_omitted.length} 个。`) : null);
}

function cardOpen() {
  const s = ui.job.steps;
  const files = s.build.detail?.files || {};
  const have = Boolean(files.blend) && ['done', 'stale'].includes(s.build.state);
  const links = [];
  if (files.blend) links.push(['.blend', fileUrl(files.blend)]);
  if (files.client) links.push(['客户图 PNG', fileUrl(files.client)]);
  if (files.client_hd) links.push(['高清客户图', fileUrl(files.client_hd)]);
  if (s.glb.detail?.glb) links.push(['.glb', fileUrl(s.glb.detail.glb)]);
  if (ui.job.spec.origin) links.push(['spec.json', fileUrl('spec.json')]);
  return card(7, '打开和下载', null,
    h('div', { class: 'row' }, h('button', { id: 'btnOpen', class: 'primary', disabled: !have, onClick: () => act('open', 'open-blender') }, '用 Blender 打开'),
      s.build.state === 'stale' ? h('span', { class: 'hint' }, '注意：spec 之后改过，这个 .blend 是旧的；先重新生成。') : null),
    errorBlock(ui.notes.open), ui.notes.opened ? h('p', { class: 'hint', id: 'openedNote' }, ui.notes.opened) : null,
    h('div', { class: 'row' }, links.map(([label, href]) => h('a', { class: 'plain', href, download: '' }, label))));
}

function cardAuto() {
  const free = !busy() && Boolean(ui.health?.blender);
  return h('section', { class: 'card', id: 'card-auto' }, h('header', {}, h('h2', {}, '一键'),
    h('span', { class: 'msg' }, '从当前状态往后一次跑完：编译（已完成的不重做，不会覆盖编辑过的 spec）→ 预览 → 生成 → GLB；读图要先做')),
    h('div', { class: 'row', style: 'margin-top:8px' }, h('button', { id: 'btnAuto', disabled: !free || !(ui.job.steps.scene.state === 'done' || ui.job.spec.origin), onClick: () => act('auto', 'auto', { hd: ui.hd }) }, '一键跑完后面的步骤')),
    errorBlock(ui.notes.auto));
}

function render() {
  const cards = $('cards');
  if (!ui.job) { cards.replaceChildren(cardImage()); return; }
  cards.replaceChildren(cardImage(), cardRead(), cardCompile(), cardPreview(), cardEdit(), cardBuild(), cardOpen(), cardAuto());
}

// ---------------------------------------------------------------- start
async function boot() {
  await refreshHealth();
  await refreshPicker();
  $('btnNew').addEventListener('click', () => go(null));
  $('jobPicker').addEventListener('change', (e) => e.target.value && go(e.target.value));
  const id = new URLSearchParams(window.location.search).get('job');
  if (id) await loadJob(id); else render();
  document.body.dataset.ready = 'true';
  window.studioFlow = { ui, loadJob, render };
}

boot();
