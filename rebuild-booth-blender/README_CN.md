# rebuild-booth-blender · v2.1.0-rc1

从展台照片或效果图制作纯展台客户图和分件可编辑 Blender 场景。默认清除展厅、邻展、Logo、人物、广告、水印和尺寸箭头，保留建筑、开口、柜台及自有灯具；屏框保留，内容中性化。

## 使用

保留完整包，按 [SKILL.md](SKILL.md) 执行：实际观察与范围裁定 → 参数化建模/AI 对照 → 复核与客户候选交付。命令从项目根目录 `<repo>` 执行，结果使用新的 `test/runs/` 子目录。

```powershell
python -m pip install -r rebuild-booth-blender/requirements.txt
python rebuild-booth-blender/scripts/boothctl.py doctor --output test/runs/new-booth/runtime_probe.json
python rebuild-booth-blender/scripts/validate_spec.py --spec test/runs/new-booth/spec.json --check-source --report test/runs/new-booth/spec_check.json
```

外部 Python 用于参数、相机和 QA；原生构建/重开脚本使用 Blender 内置 Python。`doctor --blender` 可传已确认的可执行路径。
普通客户展示应检查原图机位与第二视角，并以独立进程重新打开 `.blend`；不必先完成像素分割。未做严格量化 QA 的客户候选保留 `review_required`，不声称已严格验证或还原百分比。
图上尺寸可作为来源证据，客户图仍删除箭头；估计尺寸与隐藏连接不能直接作为施工 BOM。

## 按需参考

- [观察协议](references/observation-protocol.md)：ROI、范围、遮挡、负空间与证据。
- [数据契约](references/data-contract.md) 和 [schema](schemas/booth-spec-v2.schema.json)：坐标、参数与状态。
- [构件 recipes](references/component-recipes.md)：语义组合，不是新增 primitive API。
- [重建 QA](references/reconstruction-qa.md)：量化复原时用 camera-fit、masks、compare、assess。
- [benchmark 工作流](references/benchmark-workflow.md)：原图、基线、优化及 AI 对照。

## 新图实验

```powershell
python rebuild-booth-blender/scripts/benchmark.py prepare --image test/new-image.jpg --out test/runs/new-benchmark
python rebuild-booth-blender/scripts/benchmark.py report --manifest test/runs/new-benchmark/cases.json --out test/runs/new-benchmark/comparison.html
```

批量登记用 `--input-dir test` 替代 `--image`，两者互斥。prepare 不调用模型；report 需要四条真实图片路径，可额外附 client 与 inspection 链接。原图、观察、spec、代码快照、prompt 和输出都留在测试目录，不把客户样本写入通用库。

## 维护与边界

```powershell
python rebuild-booth-blender/tests/run_tests.py
```

`validation/` 是实际测试/环境记录，应按自身 provenance 解读；当前机器 doctor 和本次原生渲染仍需执行。单元测试通过不证明某张图视觉复原通过。
旧 `examples/legacy-case/candidate_spec.json` 保留相机和结构疑点，用于回归，不是新展台模板。
支持真实圆角、连续 Bezier 条带、sRGB 转换、按包围盒调整第二视角/灯光、中性客户图和透明匹配图。没有内置自动分割、自动找对应点、对象级增量更新、自动模型调用或账户切换。
更新代码后保留旧快照并重新验证；只有在实际安装入口更新并读回后才声称远端 Skill 已更新。此包保留本地候选版状态。
