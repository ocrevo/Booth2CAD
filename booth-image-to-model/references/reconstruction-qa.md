# 重建 QA：按交付需求选择深度

命令从项目根目录执行。示例 spec 为 `output/new-booth/spec.json`；输出到新目录 `output/new-booth/native-qa/`。`$blenderExe` 是已确认的真实可执行路径。

## 客户展示复核

普通客户候选需要真实渲染、原图与匹配机位对照、第二视角检查及独立进程重开 `.blend`。先归属/拓扑，再投影、关键比例、家具/材质；确认清洁范围与屏幕中性化，记录估计尺寸、隐藏连接及未决结构。
`client_render.png` 使用中性浅灰 World 和可用 PBR Neutral 显示，`--client-exposure` 默认 -1.0 EV（2.4.0-rc3 及更早为 -0.5；全白展台在 -0.5 下高光会被压平）；透明 `reference_render.png` 用于结构对照。客户图背景不能充当 silhouette。
普通客户图无需先制作完整 masks；没有严格量化证据时交付客户候选，保留 `review_required`，不把未调用 assess 当成全项通过。

## 启用严格 QA 的条件

用户要求量化复原、可重复几何指标或正式 `verified_visual_reconstruction` 时使用本流程。关键拓扑有争议时可局部使用 masks/对应点定位，不必一开始制作全套标注。
保存原图 hash、裁切、画幅和尺寸来源；原图与验收渲染采用同画幅/裁切/投影。总览图不能替代匹配图，不能逐件拉伸以提高指标。可见对象有 ROI，hidden 部分标 inferred，关键件进入 requirements。
open critical uncertainty 可进入简模，但阻止严格已验证交付。AI 图不能成为测量或隐藏几何真值。格式见 [data-contract](data-contract.md) 和 schema。

## 对应点与相机

先比较投影、消失方向和上/下表面关系。原图看见楣框底面时先核对机位；过高相机可能让近侧梁遮屏，不应直接据此改成开放 L 框。
固定几何/尺度，至少 8 个可见拟合点与 2 个不参与拟合的检查点，跨多个深度/高度。圆角包围框的虚拟角未必是真实几何点。

```powershell
python booth-image-to-model/scripts/camera_fit.py --spec output/new-booth/spec.json --output output/new-booth/camera_candidate.json
```

脚本只拟合已有 3D–2D 对应点，不自动看图找点或修复错误几何。搜索范围围绕当前相机种子设置，支持合法长焦、大 roll 和陡俯仰；局部优化仍依赖合理初始机位。缺可靠点、共面退化或正交拟合未支持时，使用视觉审核的相机并记录局限，不编造点。检查拟合与保留点误差后再合入 spec，实际复核后才标 `fit_status=reviewed`。

## Mask 与有效区域

严格验收使用审核过的可见整台 silhouette、关键件可见 masks 和 valid mask，尺寸与原图一致。分割不是内置能力，可由视觉 Agent/人工给多边形；不能对照片按亮度阈值就声称完成语义分割。
part mask 保留其他构件遮挡，不能混用 isolate/amodal 与 visible masks。孔洞露出的后方 booth 属于整台 mask，展馆/背景不属于。valid mask 仅剔除不可信边界、外物遮挡和裁切；记录理由与面积比例，不只留下容易匹配区域。删除 Logo/人物后明确有效比较范围。
标注见 [观察协议](observation-protocol.md)、[data-contract](data-contract.md)；`examples/legacy-case/annotations.template.json` 的路径不代表 masks 已存在。

```powershell
& $blenderExe --background --factory-startup --disable-autoexec --python-exit-code 1 --python booth-image-to-model/scripts/blender_build.py -- --spec output/new-booth/spec.json --out output/new-booth/native-qa --render --part-masks
python booth-image-to-model/scripts/compare.py --reference-mask output/new-booth/masks/booth_visible.png --candidate-mask output/new-booth/native-qa/reference_render.png --valid-mask output/new-booth/masks/valid.png --output output/new-booth/native-qa/mask_metrics.json
```

RGBA alpha 是整台候选 mask，part_masks 是可见构件黑白图；脚本不自动缩放/对齐。总 silhouette IoU 不代替拓扑、负空间和局部检查，不生成掩盖问题的综合“95 分”。
默认项目起点：全局 IoU ≥ 0.90、关键件 IoU ≥ 0.85、点误差中位数 ≤ 画面对角线 2.5%、P90 ≤ 5%、平均边界距离 ≤ 1.2%。保留点的中位数和 P90 单独计算，并须通过同样的点误差阈值；不能让大量拟合点稀释少量保留点的失败。旧证据只有总点误差时须重新 assess。这是可配置起点，非行业标准/成功保证。按分辨率、遮挡和标注噪声提前记录适用阈值及原因，不为过检临时放宽。

## 修正与证据失效

共同偏差改相机，局部比例改构件，结构类型错返回拆解，最后调材质。先做约 3 轮低采样对拍，连续两轮无改善时记录停滞并重审关键区域。

```powershell
python booth-image-to-model/scripts/boothctl.py patch --spec output/new-booth/spec.json --component top_ring --field params.outer_radius --value 0.8 --output output/new-booth/spec_r2.json
```

此例只适用于已有 top_ring，值由本图决定。几何修改使相机复核和下游验收失效，颜色修改不使几何指纹失效。builder 仍完整重建，未实现对象级增量更新；旧结果绑定旧 spec/代码快照，不能用新 hash 冒充旧文件已重建。

## 原生重开与严格验收

```powershell
& $blenderExe --background --factory-startup --disable-autoexec --python-exit-code 1 --python booth-image-to-model/scripts/blender_verify.py -- --spec output/new-booth/spec.json --blend output/new-booth/native-qa/booth.blend --report output/new-booth/native-qa/native_verification.json
python booth-image-to-model/scripts/assess.py --spec output/new-booth/spec.json --run output/new-booth/native-qa --annotations output/new-booth/annotations.json --review output/new-booth/native-qa/visual_review.json
```

实际查看原图/匹配渲染/第二视角后填 [visual_review.template.json](visual_review.template.json)，绑定真实图像/spec/代码 hash，禁止自动填所有 pass。
文件、原生重开、指标、mask 正确性和语义复核分别通过才标 `verified_visual_reconstruction`。缺/过期证据、关键疑点未决或无真实渲染保留 `review_required`；native 不可用为 `blocked_native_blender`，仅草稿为 `draft_unverified`，已有文件待核为 `built_not_verified`。
严格已验证也不是实测 CAD、施工 BOM、结构承载认证或原作者建模历史。
