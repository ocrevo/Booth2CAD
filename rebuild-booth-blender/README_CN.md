# rebuild-booth-blender · v2.0.0-rc1

展台效果图 → 分件可编辑 Blender 场景的 Skill 升级候选包。

**本包已在当前工作目录生成并执行测试，但没有写回用户账号中的已安装 Skill。**
本轮未能取得那个远端 Skill 的完整源文件及写入入口；本包基于可读取的旧建模脚本、参数、原图与已确认的改进要求，提供同名替换实现。

## 文件

- `SKILL.md`：Agent 执行入口，包含图像观察、结构/相机优先、原生交付及验收规则。
- `scripts/`：确定性几何、参数/范围校验、相机拟合、图像比较、受控参数修改、Blender 构建和独立复核。
- `schemas/`：v2 参数 JSON Schema。
- `references/`：观察协议、数据约定、算力分工、失败案例、视觉审核模板。
- `examples/legacy-case/`：用户参考、旧失败预览与旧参数、新格式候选及尚待填充的标注模板。
- `tests/`、`validation/`：可运行测试和本次实际结果。

## 本轮有意保留的边界

当前环境没有原生 Blender；安装尝试也未取得可用运行环境。
因此 `blender_build.py` / `blender_verify.py` 已通过语法编译检查，但本环境未实际执行 Blender API；对应集成测试明确 skipped。
没有生成“新版 Legacy case 已准确还原”的结论，也没有将候选 spec 伪装成最终 `.blend`。

示例 `candidate_spec.json` 的相机仍是 unfitted，关键白色带状结构连接及产品/图文仍有 open uncertainties。
这不是遗漏：其用途之一就是证明系统能够拒绝把未完成的结构候选作为完成品。

## 使用

保留整个 `rebuild-booth-blender/` 目录，不要只复制 SKILL.md 而丢掉代码与 schema。
把该目录交给支持这种 Skill 目录格式的 Agent 环境，并通过该环境的实际安装/更新入口操作。
不同平台的目录或安装方式需以其可用功能为准；本包没有自动上传、远端安装或模型账户切换器。

在有命令执行能力的环境，可直接从包根目录开始：

```bash
python -m pip install -r requirements.txt
python tests/run_tests.py
python scripts/boothctl.py doctor --output validation/runtime_probe.json
python scripts/validate_spec.py --spec examples/legacy-case/candidate_spec.json --check-source
```

Python 和 Blender 依赖是分开的。第三方库安装到用于相机/QA 的外部 Python 即可，Blender 构建脚本只用标准库和 bpy。
Blender 的真实生成、复核、对拍命令在 SKILL.md；运行前读清楚输出目录与完成条件。
不要把 examples/legacy-case/candidate_spec.json 直接改个项目名就用于别的展台。

## 版本替换

先保留原 Skill 完整备份，验证新包在实际 Blender 环境可运行，再替换对应版本。
目前没有读取原始已安装 SKILL.md，因此不能证明所有旧版私有功能都向后兼容；旧 spec 不会被静默接受。
保存本次的回归失败样本，以后每次升级都运行 tests/run_tests.py，真实原生 Blender 集成测试不能长期以 skipped 当作正式发布依据。

## 重点变化

连续圆角轮廓是真正的几何，不是给四个盒子分别倒角。
尺寸、归属、画幅、文件哈希、原生重新打开和视觉判断分别核验，不能只检查“模型文件能生成”。
程序执行可复用，视觉判断按需升级；现有版本不含自动图像分割、自动 2D 锚点提取、全自动几何误差优化、构件级增量 Blender 更新或多模型收费路由。
