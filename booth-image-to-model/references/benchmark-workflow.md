# 测试图片：双路线对比与迭代

新图片放在工作目录的 `input/`；输入快照、观察表、spec、旧代码快照、渲染、AI prompt、模型和本地报告按任务保存在同一工作目录的 `output/`。两个目录都不纳入版本库（本仓库里被 Git 忽略）；`test/` 仅保留历史兼容访问。生产 skill 只保留可复用规则、代码和非客户专有的测试，不提交原图或从原图派生的客户场景。

## 同一输入，两条路线

1. 在工作目录运行 `python "<SKILL_DIR>/scripts/benchmark.py" prepare --image input/new-image.jpg --out output/new-benchmark`，复制单张原图为本次输入快照，核对 hash，登记画幅和清洁 prompt。manifest 的 `source` 指向快照，`source_original` 记录原始位置；后续 input 文件改名或移除不会破坏已保存实验。批量时以 `--input-dir input` 替代 `--image`；两者互斥，目录模式只读取直属图片，不把旧渲染当新输入，不覆盖旧实验。
2. 实际看原图，记录建筑、家具、开口、范围排除、关键歧义和尺寸依据。为两条路线固定相同的 Logo/文字/人物/产品处理规则。
3. Skill 路线：冻结本次旧 builder 到该任务输出目录生成基线，修改通用逻辑或本次 spec 后生成新 run。spec 的 source 绑定已登记的输入快照；每次保存 spec、代码和真实文件 hash，独立重新打开 `.blend`。固定尺寸、数量或品牌只能出现在这个样本 spec 中。
4. AI 路线：使用可用的图像生成工具，以原始图片为 edit target，附清洁规则及从原图观察出的结构不变量。保存实际 prompt、工具来源和输出；若工具未提供准确模型名，不猜测。图像只用作视觉对照，不能反向成为测量、遮挡补全或 BOM 证据。
5. 实际看原图/基线/优化/AI及第二视角。先排除归属、拓扑和构图问题，再调圆角、厚度、材质与光照。AI图另检查边缘杂点、透明孔洞、家具数量和曲面是否漂移。
6. 填写 cases.json 的 baseline/blender/ai 路径（相对 manifest 目录）、notes、status，可选 spec/native_verification/blend，以及客户图 client 和第二视角 inspection。运行 `python "<SKILL_DIR>/scripts/benchmark.py" report --manifest output/new-benchmark/cases.json --out output/new-benchmark/comparison.html` 生成四列对比页及证据清单，页面可切换深浅底检查透明边缘。

四列 baseline/blender/ai 使用同机位透明匹配图；客户图 client 为中性背景展示，inspection 为第二视角，分开链接。AI 默认要求透明 alpha；需要客户展示时用一致的中性背景，不把透明图与灰底客户图直接计算像素差。
脚本不自动调用模型，也不自动写视觉 pass。AI 输出尺寸或构图不同会记录到 evidence；缩略图里的 object-fit 仅方便查看。普通客户候选完成实际视觉与原生重开后可交付并保留 review_required；严格量化需求再按 [重建 QA](reconstruction-qa.md) 准备标注。无原图 mask 不报 IoU 或“还原百分比”；有 mask 时明确清洁删除区域的有效比较规则。AI 路线不可独立扭曲各构件来提高指标。

## 复用结构，不复用答案

组合 recipe 的参数与 API 说明见 [component-recipes.md](component-recipes.md)。以下是选择提示，组合不等于新增 primitive kind，也不实例化原图不存在的家具。

| 源图观察 | 可复用组合 | 本次必须确定 |
|---|---|---|
| 连续中空闭合吊楣 | rounded_ring | 外/内尺寸、圆角、厚度、标高及是否真闭环 |
| 两柱连续圆角门架 | rounded_portal | 开口、柱宽、梁高、朝向、接地和连接 |
| 带顶/底/侧开口的异形面板 | profile_extrusion | 连续外轮廓与缺口朝向、厚度；闭合内孔需其他适合的原型 |
| 圆弧墙板/彩色楣板 | arc_panel + 可选 grid 材质 | 半径、角跨度、分色边界；表面格网不能作为实体孔阵 |
| 开放 L 型楣框/装饰弯肋 | swept_strip，重复实例 | Bezier 控制点、带宽、深度、数量和间距 |
| 圆角柜台 | bevel box 主体 + 独立台面/踢脚 | 真实圆角、台面厚度、家具位置，不能任意添加 |
| 屏幕展示墙 | 墙体 + 外框 + 中性显示面 | 附着墙面、屏幕数量/尺寸和凹槽 |
| 自有灯带 | 独立窄构件 + emission 材质 | 路径与归属，不能补建展厅灯 |

box.bevel_radius 真正改变网格，不能只写备注；all 模式必须小于最薄边的一半，vertical 模式仅约束 XY 最薄边并保持上下端平切，适用于宽圆角立柱。swept_strip 的 control_points 是 3n+1 个局部 `[x,z]` 点，width 是路径平面内带宽，depth 沿局部 Y；每三个新点接一段 Bezier，局部几何中心由控制点约定，placement/rotation 决定世界位置。关键曲面不能为了省分析全部降成盒子。

构件数量、视觉观察和 primitive 选择由 Agent 决定；确定的几何、颜色转换、包围盒 framing、重复运行和文件校验由代码执行。改变共享代码后旧文件仍绑定其代码快照；不可用新 code_hash 冒充旧文件已重新构建。
源图分辨率很低时，对拍保留原始画幅；客户图可从相同 `.blend`、相同相机、相同比例另行高清渲染。登记所用模型 hash、输出尺寸与渲染设置；高清只增加展示像素，不增加设计或尺寸证据。实际查看要交付的高清图，低清缩略图可能掩盖墙/楣相交、薄边接缝和纹样杂点。

## 本轮发现（2026-10-06）

三类参考分别暴露：闭环吊楣下的相交门架关系；彩色弯肋和 sRGB/linear 混用；白色科技展台的顶棚解释与相机高度混淆造成屏幕遮挡。原图看见顶棚底面时应先核对机位，再决定是否为完整闭环。修正应用于通用弯肋、真实圆角、颜色转换、范围规则及包围盒展示机位，未把某个展台答案写入库。

Blender 5.2.2 已实测建模和重开；纯 Python 单测不能证明视觉还原通过。本轮仍存在单图隐藏结构和相机比例偏差，准确状态以各 run 的实际 QA 为准。
