# rebuild-booth-blender · v2.4.0-rc4

从展台照片或效果图制作纯展台客户图和分件可编辑 Blender 场景。默认清除展厅、邻展、Logo、人物、广告、水印和尺寸箭头，保留建筑、开口、柜台及自有灯具；屏框保留，内容中性化。

## 使用

保留完整包，按 [SKILL.md](SKILL.md) 执行：实际观察与范围裁定 → 参数化建模/AI 对照 → 复核与客户候选交付。命令从包含本包的项目根目录执行；原始输入放在 `input/`，结果使用新的 `output/` 子目录。

```powershell
python -m pip install -r rebuild-booth-blender/requirements.txt
python rebuild-booth-blender/scripts/boothctl.py doctor --output output/new-booth/runtime_probe.json
python rebuild-booth-blender/scripts/validate_spec.py --spec output/new-booth/spec.json --check-source --report output/new-booth/spec_check.json
```

快速路线（默认）：角点拟合相机与比例 → 模板 + 构件宏写 spec → `boothctl.py preview` 迭代 → 一次终版渲染（含高清）。命令见 [SKILL.md](SKILL.md) 第 0 节，默认尺寸与定尺度方法见 [设计先验](references/design-priors.md)。

外部 Python 用于参数、相机和 QA；原生构建/重开脚本使用 Blender 内置 Python。`doctor --blender` 可传已确认的可执行路径。
普通客户展示应检查原图机位与第二视角，并以独立进程重新打开 `.blend`；不必先完成像素分割。未做严格量化 QA 的客户候选保留 `review_required`，不声称已严格验证或还原百分比。
图上尺寸可作为来源证据，客户图仍删除箭头；估计尺寸与隐藏连接不能直接作为施工 BOM。

## 按需参考

- [观察协议](references/observation-protocol.md)：ROI、范围、遮挡、负空间与证据。
- [数据契约](references/data-contract.md) 和 [schema](schemas/booth-spec-v2.schema.json)：坐标、参数与状态。
- [构件 recipes](references/component-recipes.md)：语义组合与 `components.py` 宏，不是新增 primitive API。
- [设计先验](references/design-priors.md)：常用尺寸、尺度锚点、展位类型与坐标换算；机器可读版本见 `schemas/design-priors.v1.json`，建议性检查见 `scripts/design_check.py`。
- [重建 QA](references/reconstruction-qa.md)：量化复原时用 camera-fit、masks、compare、assess。
- [benchmark 工作流](references/benchmark-workflow.md)：原图、基线、优化及 AI 对照。

## 新图实验

```powershell
python rebuild-booth-blender/scripts/benchmark.py prepare --image input/new-image.jpg --out output/new-benchmark
python rebuild-booth-blender/scripts/benchmark.py report --manifest output/new-benchmark/cases.json --out output/new-benchmark/comparison.html
```

批量登记用 `--input-dir input` 替代 `--image`，两者互斥。prepare 将原图复制为输出目录中的输入快照，登记实际 hash 与画幅，不调用模型；report 需要四条真实图片路径，可额外附 client 与 inspection 链接。原图留在 `input/`，观察、spec、代码快照、prompt 和派生文件留在 `output/`，不把客户样本写入通用库。

## 维护与边界

```powershell
python rebuild-booth-blender/tests/run_tests.py --blender $blenderExe --require-native --output output/_validation/release-check
```

先将 `$blenderExe` 设置为实际可执行路径。runner 将完整日志和结果写入独立目录；缺原生 Blender 时 `--require-native` 明确阻止原生验证。默认测试或针对性 `--pattern` 中的 skipped 不得算通过；`validation/` 只保存经核对后归档的发布证据，不由测试自动覆盖。

在 Booth2CAD 项目中，完整回归通过后运行 `python tools/package_skill.py --test-run output/_validation/release-check`，核对当前代码、实际测试日志、原生环境和零跳过结果，再更新证据和文件清单。独立安装本包时可手动做相同核对和归档，无需项目维护工具。

审计记录见 [audit_report.json](validation/audit_report.json)。测试与独立 AI 审查验证的是可执行行为和维护流程；当前机器 doctor 和每次实际原生渲染仍需执行，不能用它们替某张图片的视觉复原结论。
旧 `examples/legacy-case/candidate_spec.json` 保留相机和结构疑点，用于回归，不是新展台模板。
支持真实圆角、连续 Bezier 条带、带边缘缺口的轮廓挤出、弧形板、米制格网材质、sRGB 转换、按包围盒投影调整第二视角/灯光、中性客户图和透明匹配图；角点拟合相机与比例、像素反投影定位、构件宏、共面重叠检查、Workbench 快速预览和同进程高清出图。没有内置自动分割、自动找对应点、对象级增量更新、自动模型调用或账户切换。
本目录就是 skill 源码；更新代码后保留旧快照并重新验证。仓库提交与安装副本分别记录版本，源码升级不会自动更新已有客户模型。
