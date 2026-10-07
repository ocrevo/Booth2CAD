# Booth2CAD

从展台图片生成去除展厅、品牌和人物的客户渲染，以及分件可编辑的 Blender 场景。图片中的真实尺寸和隐藏结构无法仅凭单图确定，模型保留观察与估计的区分。

- `rebuild-booth-blender/`：skill 源码、参数契约、通用几何、渲染和验证脚本、合成回归测试。
- `input/`：原始输入图片，不进入 Git。
- `output/`：按任务保存输入快照、观察、spec、代码快照、`.blend`、渲染、AI 对照及验证证据，不进入 Git。
- `test/`：历史兼容目录。旧原图与旧输出访问路径继续可用；新任务使用 input/output。

从项目根目录执行，具体流程见 [SKILL.md](rebuild-booth-blender/SKILL.md)：

```powershell
python rebuild-booth-blender/scripts/benchmark.py prepare --image input/booth.png --out output/new-booth/benchmark
python rebuild-booth-blender/scripts/boothctl.py doctor --blender '实际 Blender 可执行文件路径' --output output/new-booth/runtime_probe.json
```

AI 负责观察、结构拆分和视觉复核，代码负责生成和验证几何。prepare 只登记并保存原始输入快照；它不会自动调用图像模型，也不会自动判断相似度。

升级时使用显式原生环境运行回归测试，结果保存到新的目录：

```powershell
python rebuild-booth-blender/tests/run_tests.py --blender '实际 Blender 可执行文件路径' --require-native --output output/_validation/release-check
```

`--require-native` 在缺少 Blender 时明确阻止原生验证。测试通过不代表某张图片已精确还原；查看每次重建自己的原图对拍、第二视角、尺寸假设和复核记录。

完整回归通过后，使用项目维护工具核对当前代码、schema、测试来源和日志，再归档旧证据并更新发布清单：

```powershell
python tools/package_skill.py --test-run output/_validation/release-check
```

审计结论及验证边界保存在 [audit_report.json](rebuild-booth-blender/validation/audit_report.json)，原始审计实验留在本地 `output/`。本仓库的 `rebuild-booth-blender/` 就是 skill 源码。
