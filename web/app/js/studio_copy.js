// The words of the studio page, in one place. `main` is what a person sees on the main path: plain Chinese, no engineering terms
// (a test scans it for BANNED). `advanced` is the professional drawer and the folded "more ways" area, where the terms belong.

export const COPY = {
  main: {
    appName: '展台工作台',
    stepNames: ['选图', '生成模型', '调整', '出图'],
    drop: '把展台效果图拖到这里，或点击选择',
    dropSmall: 'PNG 或 JPEG，不超过 25 MB、500 万像素',
    recent: '最近的任务',
    newJob: '换一张图',
    emptyTitle: '先选一张展台效果图',
    emptyBody: '选好图后，大模型会看图，搭出一个可以修改的三维模型。',
    tryDemo: '试用示例展台（合成数据，不需要 key）',
    tryDemoHint: '载入一张合成的展台图和它的模型，可以直接调整、对照和出图。',
    imageInfo: '{w} × {h} 像素',

    consent: '同意把这张图发送给已配置的大模型服务（{model}）',
    needKey: '还没有配置大模型的 key。粘贴后只保存在这台电脑的内存里，不会写进任何文件。',
    keyPlaceholder: '粘贴 API key',
    saveKey: '保存 key',
    generate: '生成模型',
    generateAll: '生成并直接出图',
    generateHint: '大模型看图并搭出模型，通常 1–2 分钟。',
    retry: '再试一次',

    reading: '正在看图…',
    building: '正在搭模型…',
    checking: '正在快速校对…',
    rendering: '正在出图…',
    exporting: '正在导出模型文件…',
    waitingBlender: '排队中，另一个任务正在使用 Blender',
    progress: '已用 {elapsed}，通常{expected}',
    slow: '比平时久一些，仍在运行',
    secondsFew: '几秒',
    secondsAbout: '约 {n} 秒',
    minutesAbout: '约 {n} 分钟',
    minutesRange: '约 {lo}–{hi} 分钟',

    fitGood: '模型已生成，共 {n} 个部件',
    fitDone: '模型已生成，共 {n} 个部件，建议对照原图看一看',
    fitOff: '模型和照片可能没对齐（最差处偏 {px} 像素）· 看看哪里不对',
    sizeUnknown: '有些尺寸无法从图上确定，请核对 · 查看',
    dropped: '有 {n} 个部件没能放进模型 · 查看原因',
    assumed: '有 {n} 个尺寸是估算的 · 查看',
    modelReady: '现在可以直接在画面里点选、拖动、改颜色。',
    nextRender: '满意了就出图',

    render: '出图（1–3 分钟）',
    renderAgain: '重新出图',
    quickCheck: '先快速校对（约 15 秒）',
    hd: '高清（更慢）',
    stale: '模型改动后还没有重新出图',
    noBlender: '这台电脑没找到 Blender：可以导出模型文件（.glb），但不能出图。',
    exportGlb: '导出模型文件（.glb）',

    downloads: '下载',
    dlClient: '客户图（PNG）',
    dlClientHd: '客户图（高清）',
    dlOther: '另一个角度',
    dlGlb: '模型文件（.glb）',
    dlBlend: 'Blender 文件（.blend）',
    openBlender: '在 Blender 中打开',
    openedBlender: '已请求 Blender 打开这个文件，窗口出现可能要几秒。',

    compareName: ['原图', '对照', '叠加', '模型'],
    afterName: ['即时模型', '快速校对', '成品图'],
    liveNote: '即时视图：材质为示意，光影以成品图为准',
    renderNote: '正在看渲染图：回到「即时模型」才能继续修改',
    holdSpace: '按住空格临时看原图',
    toLive: '回到即时模型',

    savedChip: '已保存 ✓',
    savingChip: '保存中…',
    waitChip: '出图结束后再保存',
    failChip: '没保存上',
    saveFailed: '这次修改没通过检查：{msg}',
    undoStep: '撤销这一步',

    offline: '没有连上本机服务。运行 python web/server/run.py 后这里会自动恢复。',
    pro: '专业视图',
    tools: { move: '移动', rotate: '旋转', snap: '吸附', dup: '复制', del: '删除', undo: '撤销', redo: '重做' },
    parts: '构件',
    filter: '搜索',

    errReadTitle: '大模型没有读出这张图',
    errBuildModelTitle: '没能搭出模型',
    errCheckTitle: '快速校对没有完成',
    errRenderTitle: '出图没有完成',
    errExportTitle: '导出模型文件没有完成',
    useUpload: '改用上传文件',
    changeKeyOrUpload: '换一个 key，或改用上传文件',
    seeLog: '看详细记录',
    rawLog: '详细记录',
    errKey: '大模型服务不接受这个 key。换一个 key 再试，或者改用上传文件。',
    errBusy: '大模型服务现在太忙，或者额度用完了。稍等一会儿再试。',
    errSlow: '大模型太久没有回答，没有自动重试（重试会重复计费）。可以再试一次。',
    errCut: '大模型的回答没有写完。可以再试一次，或换一个输出更长的模型。',
    errRefused: '大模型拒绝了这个请求。可以再试一次，或改用上传文件。',
    errUnusable: '大模型改了两次，结果仍然不能用。可以再试一次，或改用上传文件。',
    errNet: '连不上大模型服务。检查网络或服务地址后再试。',
    errReadWhy: '大模型没有给出可用的结果。可以再试一次，或改用上传文件。',
    errBuildWhy: '图里读出的内容放不进一个合理的模型。可以再试一次，或改用上传文件。',
    errCheckWhy: '快速校对的渲染没有成功。可以再试一次。',
    errRenderWhy: '出图的渲染没有成功。可以再试一次；详细记录里有原因。',
    errExportWhy: '模型文件没有导出成功。可以再试一次。',
    discardEdits: '有改动还没保存上，现在离开会丢掉它们。仍要离开吗？',
    offlineChip: '连不上服务，恢复后自动保存',
    needConsent: '先勾选同意，才能再试一次',
    modelLoaded: '模型已载入，共 {n} 个部件',
  },
  advanced: {
    moreWays: '更多方式',
    changeKey: '更换大模型的 key（只保存在这台电脑的内存里）',
    uploadScene: '上传场景描述（scene.json）',
    uploadSpec: '上传已有的模型文件（spec.json，必须是这张图生成的）',
    uploaded: '已载入 {name}（{n} 个构件）',
    uploadedSpec: '已载入 {name}（{n} 个构件）；已跳过读图和编译',
    uploadRefused: '没有载入 {name}：{msg}',
    proTabs: ['对齐', '数据与日志'],
    overlayTitle: '拟合出的展台外框叠在原图上（0.5 m 网格）',
    fitLine: '拟合 {status}，残差 {rms} px（最大 {max} px），{n} 个零件',
    pointsTitle: '角点误差（px）',
    droppedTitle: '没能放进模型的构件',
    assumedTitle: '估算的值',
    adjustTitle: '自动调整',
    warnTitle: '警告',
    designTitle: '设计检查提示（建议性）',
    logTitle: '各步记录',
    sheetTitle: '四格检查图（原图 / 渲染 / 叠加 / 轮廓与角点）',
    files: '文件',
    noDetail: '还没有数据',
  },
};

/** Words that must not appear on the main path. */
export const BANNED = ['编译', '残差', 'rms', 'RMS', 'spec', 'Workbench', 'Cycles', '反投影', '拟合', 'scene', '场景描述', 'JSON', 'json', 'sha256'];

export function fill(text, params = {}) {
  return String(text).replace(/\{(\w+)\}/g, (_, name) => (name in params ? params[name] : `{${name}}`));
}

/** Every string under `main`, for the banned-word test. */
export function* mainStrings(node = COPY.main) {
  if (typeof node === 'string') yield node;
  else if (Array.isArray(node)) for (const v of node) yield* mainStrings(v);
  else if (node && typeof node === 'object') for (const v of Object.values(node)) yield* mainStrings(v);
}
