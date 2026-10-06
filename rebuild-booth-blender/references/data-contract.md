# 数据和执行约定

## Spec

`schemas/booth-spec-v2.schema.json` 是机器可读格式；`scripts/validate_spec.py` 同时执行跨字段、scope、尺寸与几何可构造性检查。
必须同时理解 schema 与语义规则，不能以“JSON 合法”代替建模判断。

`source` 锁定原始图片、SHA-256 和画幅。`scale` 声明尺寸依据。`scope` 与 `components` 通过 scope_id 关联。
组件默认位于局部几何中心，placement 是世界坐标。Z 朝上。Euler XYZ 单位为度。
`rounded_portal` 位于 XZ 平面，厚度沿 Y，原点为整体包围盒中心；`rounded_ring` 位于 XY 平面，厚度沿 Z。
环的内外圆角分别驱动轮廓；无孔或者相交的环会被拒绝。门架是一条有两只脚的连续带状实体，不跨底部封口。

当前只支持一个矩形 floor/carpet 对象，尺寸须与 footprint 一致。非矩形展位边界要扩展几何与 schema，不能悄悄近似为矩形并声称完成。
不支持的几何原型会报错；请新增确定性 builder、对应 params schema 和拓扑/回归测试后使用。
复杂产品建议通过独立资产扩展；本版本没有资产导入器、自动 UV 或孔阵生成器。

`requirements` 是最低结构义务，例如 `top_ring.kind=rounded_ring`。它只能检验已写入的义务是否实现，不能证明写入的义务本身识别正确。
`evidence.status=observed/inferred` 分离观察与补全。`uncertainties` 中 open 且 critical 的事项阻止最终交付，不阻止低成本候选测试。

## QA 输入

annotations.json 的 source_sha256 必须对应原图。它引用 booth silhouette、各关键件可见 mask 和有效区域 mask。
模板在 `examples/legacy-case/annotations.template.json`。该模板中的 mask 路径不存在，必须实际制作与审阅后才能评估。
所有 mask 必须和原图具有完全相同的像素宽高。脚本不自动缩放或重对齐。RGBA 的 alpha 被当作 mask；灰度/黑白 PNG 使用像素值。
`part_masks/<component_id>.png` 是匹配相机下、保留其他展台物件遮挡的可见构件图。不是移除所有遮挡之后的孤立模型投影。

投影点格式：`[{id, uv:[u,v], depth}]`。不可见点不评分；缺失可见点不是零误差，而是错误。
`camera_fit.py` 对透视相机拟合位姿、roll、焦距，保持主点和几何固定；正交相机需手工/视觉复核设置。

## 证据与真实文件绑定

build_report 绑定 spec、建模代码和输出文件哈希；native_verification 来自另一个原生 Blender 进程。
assess 重新检查输出字节，计算 mask/landmark 指标，检查审核记录绑定的相同 spec、代码和两张渲染。
visual_review 不是数字签名，也不是独立审计认证；其意义是记录具体审核者实际检查了哪些相同版本的图。
篡改所有 unsigned JSON 仍可能伪造证据，本地校验不是对抗恶意运行者的安全系统。

交付状态：
- `blocked_native_blender`：没有能执行/验证 Blender 的环境。
- `draft_unverified` / `built_not_verified`：已有参数或文件，尚未完成质量验证。
- `review_required`：存在缺失证据、错误或关键疑点。
- `verified_visual_reconstruction`：本项目的全部可执行门槛和实际视觉复核通过；不等于实测 CAD 或施工认证。

## 依赖

标准库：geometry、common、spec validator、boothctl（除了 doctor 探测外不加载第三方库）。
外部 Python：camera_fit/compare/assess 使用 numpy、Pillow、scipy；完整测试另外使用 jsonschema 和 trimesh。
Blender 内置 Python：blender_build / blender_verify，不需要往 Blender Python 里安装上述数据科学库。
已锁定测试实际版本在 validation/dependency_versions.json。requirements.txt 是兼容范围，不是对范围内所有组合的测试声明。
