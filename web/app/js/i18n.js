// UI strings. Chinese by default (the designers' language), English one click away. Spec field names are never translated.

const STRINGS = {
  zh: {
    title: '展台规格编辑器',
    subtitle: '直接编辑 spec：移动、改色、改尺寸、复制。所有操作都在本机浏览器内完成，不上传任何文件。',
    open: '打开 spec', demo: '载入示例', save: '保存 spec', glb: '导出 GLB', undo: '撤销', redo: '重做',
    move: '移动 (W)', rotate: '旋转 (E)', snap: '吸附', match: '对齐原图视角', frame: '显示全部', dup: '复制 (Ctrl+D)',
    del: '删除 (Del)', guide: '测试指引', lang: 'English', close: '关闭',
    outline: '构件', filter: '搜索 id 或 role', ungrouped: '未分组', parts: '{n} 个零件',
    nothing: '点击模型或左侧列表选择。Shift/Ctrl+点击多选，Alt+点击只选单个零件，空白处点击取消。',
    selected: '已选 {n} 个零件', size3: '总尺寸 {w} × {d} × {h} m',
    id: 'id', kind: '类型', role: '用途', scope: '范围', group: '分组', selectGroup: '选中整组', ungroup: '移出分组',
    evObserved: '原图可见', evInferred: '推断', edited: '已在编辑器中修改',
    location: '位置 (m)', rotation: '旋转 (°)', params: '尺寸与参数', material: '材质', color: '颜色', alpha: '不透明度',
    roughness: '粗糙度', metallic: '金属度', emission: '自发光', optional: '可选',
    groupMove: '平移 (m)', groupYaw: '绕竖轴旋转 (°)', groupScale: '整体缩放 ×', apply: '应用', allColor: '统一颜色', groupName: '分组名',
    jsonParam: '坐标列表 (JSON)',
    issues: '问题', noIssues: '无问题', issueCount: '{n} 个问题',
    loaded: '已载入 {name}：{n} 个零件', demoName: '示例展台（合成数据）',
    saved: '已保存 {name}', exported: '已导出 {name}（{kb} KB）', refused: '已拒绝：{msg}', footprint: '地面尺寸已改，展位尺寸同步为 {w} × {d} m',
    deleted: '已删除 {n} 个零件', deletedExtra: '，同时移除 {r} 条要求、{l} 个地标、{s} 个空范围', duplicated: '已复制 {n} 个零件（偏移 +0.6 m，可直接拖动）',
    confirmCritical: '选中包含关键构件（{ids}）。删除后相关要求也会移除。确定删除吗？',
    nothingToDo: '先选中零件', badFile: '无法读取：{msg}', serveHint: '无法载入示例。请用 python web/tools/serve.py 启动本地服务，不要直接双击打开 html。',
    matchFailed: '无法对齐原图视角：{msg}', matchOn: '已对齐原图视角（拖动视图即退出）', dirty: '有未保存的修改。',
    drop: '把 spec.json 拖到这里', groupInvalid: '分组名只能用小写字母、数字和下划线，并以字母开头',
    guideTitle: '测试指引',
    guideBody: [
      ['先看', '打开页面应自动显示一个合成的示例展台（6 × 5 m，79 个零件）。底部状态栏显示“无问题”。右下角没有红色报错。'],
      ['选择', '点击一把椅子：整套椅子（座面、靠背、四条腿）一起高亮；Alt+点击只选一个零件；点空白处取消。'],
      ['移动', '选中桌子 → 拖动箭头，桌面、桌柱、底盘一起走；勾选“吸附”时每次 5 cm。旋转（E）只绕竖轴。'],
      ['改色', '选中单个零件 → 右侧改颜色，立刻看到变化；多选后可统一改色。'],
      ['改尺寸', '选单个零件改右侧尺寸；选整组后用“整体缩放 ×”，例如 1.2。改地面尺寸时，展位尺寸同步更新。'],
      ['复制/删除', 'Ctrl+D 复制一整组（新分组名自动生成）；Del 删除。删除关键构件（如后墙）会先确认；地面不能删除。'],
      ['撤销', 'Ctrl+Z / Ctrl+Y 逐步撤销、重做，包括拖动、改色、复制、删除。'],
      ['原图视角', '点“对齐原图视角”，镜头按 spec 里的相机摆放，虚线框是原图的画幅。拖动视图即退出。'],
      ['保存', '“保存 spec”下载修改后的 spec.json；被改过的零件会标记为“推断”并写明已在编辑器中修改。'],
      ['检查', '把保存的 spec 交给 validate_spec.py 校验，用 boothctl.py glb 或本页“导出 GLB”得到三维文件。'],
      ['已知限制', '格网纹样（LED 墙接缝）和文字只显示示意；暂无家具库，只能复制已有的家具；不支持正交相机。'],
    ],
  },
  en: {
    title: 'Booth Spec Editor',
    subtitle: 'Edit the spec directly: move, recolour, resize, duplicate. Everything runs in this browser; no file is uploaded.',
    open: 'Open spec', demo: 'Load demo', save: 'Save spec', glb: 'Export GLB', undo: 'Undo', redo: 'Redo',
    move: 'Move (W)', rotate: 'Rotate (E)', snap: 'Snap', match: 'Match source view', frame: 'Frame all', dup: 'Duplicate (Ctrl+D)',
    del: 'Delete (Del)', guide: 'Test guide', lang: '中文', close: 'Close',
    outline: 'Parts', filter: 'Search id or role', ungrouped: 'Ungrouped', parts: '{n} parts',
    nothing: 'Click the model or the list. Shift/Ctrl+click adds, Alt+click picks a single part, empty space clears.',
    selected: '{n} parts selected', size3: 'Overall {w} × {d} × {h} m',
    id: 'id', kind: 'kind', role: 'role', scope: 'scope', group: 'group', selectGroup: 'Select whole group', ungroup: 'Remove from group',
    evObserved: 'observed', evInferred: 'inferred', edited: 'edited in the web editor',
    location: 'Position (m)', rotation: 'Rotation (°)', params: 'Size and parameters', material: 'Material', color: 'Colour', alpha: 'Opacity',
    roughness: 'Roughness', metallic: 'Metallic', emission: 'Emission', optional: 'optional',
    groupMove: 'Move by (m)', groupYaw: 'Turn about vertical (°)', groupScale: 'Scale all ×', apply: 'Apply', allColor: 'Colour for all', groupName: 'Group name',
    jsonParam: 'Coordinate list (JSON)',
    issues: 'Problems', noIssues: 'No problems', issueCount: '{n} problems',
    loaded: 'Loaded {name}: {n} parts', demoName: 'demo booth (synthetic)',
    saved: 'Saved {name}', exported: 'Exported {name} ({kb} KB)', refused: 'Refused: {msg}', footprint: 'Floor size changed; footprint is now {w} × {d} m',
    deleted: 'Deleted {n} parts', deletedExtra: '; also removed {r} requirements, {l} landmarks, {s} empty scopes', duplicated: 'Duplicated {n} parts (offset +0.6 m, drag to place)',
    confirmCritical: 'The selection includes critical parts ({ids}). Their requirements will be removed too. Delete anyway?',
    nothingToDo: 'Select some parts first', badFile: 'Cannot read: {msg}', serveHint: 'Cannot load the demo. Start the local server with python web/tools/serve.py instead of opening the html file directly.',
    matchFailed: 'Cannot match the source view: {msg}', matchOn: 'Matching the source view (drag the view to leave)', dirty: 'There are unsaved changes.',
    drop: 'Drop a spec.json here', groupInvalid: 'Group names use lowercase letters, digits and underscores, starting with a letter',
    guideTitle: 'Test guide',
    guideBody: [
      ['Start', 'The page should open on a synthetic demo booth (6 × 5 m, 79 parts). The status bar says "No problems". No red errors.'],
      ['Select', 'Click a chair: the whole chair (seat, back, four legs) highlights; Alt+click picks one part; click empty space to clear.'],
      ['Move', 'Select a table and drag an arrow: top, stem and base move together; with Snap on it steps 5 cm. Rotate (E) turns about the vertical axis.'],
      ['Recolour', 'Select one part and change its colour on the right; with several selected the colour applies to all.'],
      ['Resize', 'Edit sizes of a single part on the right; with a whole group use "Scale all ×", e.g. 1.2. Resizing the floor updates the footprint.'],
      ['Duplicate / delete', 'Ctrl+D copies a whole group under a new group name; Del deletes. Deleting a critical part (e.g. the back wall) asks first; the floor cannot be deleted.'],
      ['Undo', 'Ctrl+Z / Ctrl+Y step through drags, recolours, copies and deletions.'],
      ['Source view', '"Match source view" places the camera as the spec says; the dashed frame is the source picture. Dragging the view leaves it.'],
      ['Save', '"Save spec" downloads the edited spec.json; edited parts are marked inferred and say they were edited in the web editor.'],
      ['Check', 'Run validate_spec.py on the saved file, and boothctl.py glb (or "Export GLB" here) for a 3D file.'],
      ['Known limits', 'Grid patterns (LED seams) and text are shown schematically; there is no furniture library yet (copy existing pieces); orthographic cameras are not supported.'],
    ],
  },
};

let lang = 'zh';
try {
  const saved = localStorage.getItem('booth-editor-lang');
  if (saved === 'zh' || saved === 'en') lang = saved;
} catch { /* storage may be blocked; the default is fine */ }

export const getLang = () => lang;

/** Use a language for this page only (the studio is Chinese); the choice saved by the standalone editor is left alone. */
export function useLang(next) {
  lang = next;
}

export function setLang(next) {
  lang = next;
  try { localStorage.setItem('booth-editor-lang', next); } catch { /* ignore */ }
}

export function t(key, params = {}) {
  const value = STRINGS[lang][key] ?? STRINGS.en[key] ?? key;
  if (typeof value !== 'string') return value;
  return value.replace(/\{(\w+)\}/g, (_, name) => (name in params ? params[name] : `{${name}}`));
}
