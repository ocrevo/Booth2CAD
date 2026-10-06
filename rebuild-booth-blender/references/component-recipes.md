# 语义构件 recipes：复用组合，不复用答案

这里是可重复 spec 组合，不新增 counter/screen/chair 等 kind，不是固定样本模板。公开 primitives 为 box、cylinder、rounded_ring、rounded_portal、swept_strip、text；精确参数以 [schema](../schemas/booth-spec-v2.schema.json) 为准，坐标/证据见 [data-contract](data-contract.md)。
各子件保留独立 component_id、scope_id、placement、material 和原图依据。组合的尺寸、数量、位置、朝向及是否出现按当前图确定；隐藏连接明确 inferred。

| 语义组合 | primitives/拆分 | 本图必须确定 |
|---|---|---|
| 中空闭合吊楣 | rounded_ring + 可见支撑/灯 | 是否真闭环、内外尺寸、圆角、厚度、标高；不补实心顶板 |
| 连续圆角门架 | rounded_portal；独立面板只按观察添加 | 开口、柱宽、梁高、朝向、接地、连接；底部不封口 |
| 开放楣框/连续弯肋 | swept_strip，重复实例 | Bezier 路径、宽深、根数、间距；不融合成墙或强套闭环 |
| 圆角柜台 | bevel box + 独立台面/踢脚/面板 | 真实圆角、厚度、悬挑、位置；删品牌仍保留面板 |
| 屏幕墙/立式屏 | box 墙/支承 + 框条 + 中性显示面 | 数量、尺寸、朝向、附着面/凹槽；不删外框 |
| 圆桌/柱状展具 | cylinder 主体/台面 + 可见支腿 | 半径、高度、腿数、接地；圆台有上下盖 |
| 自有灯带/下照灯 | 窄 box/swept_strip/薄 cylinder + emission | 路径、数量、朝向、booth 归属；不从光斑补展馆灯 |
| 座椅/植物等装饰 | 可准确表达的 primitive 组合，否则按范围扩展或用允许资产 | 数量与曲面按图，不默认添加家具或以盒子代曲面 |

## 形状 API

- box：`size=[x,y,z]`，可选 bevel_radius、bevel_mode=all/vertical。all 圆角小于最薄边一半；vertical 约束 XY 最薄边且上下端平切。圆角真实驱动顶点。
- cylinder：radius、height，局部轴向 Z；placement/rotation 决定方向。
- rounded_ring：局部 XY；outer_size、inner_size 为二维尺寸，outer_radius、inner_radius 控制轮廓，height 沿 Z。开口有效，内外轮廓不相交。
- rounded_portal：局部 XZ，depth 沿 Y；width、height、side_width、beam_height、outer_radius、inner_radius。原点为整体包围盒中心，是两脚连续带状实体。
- swept_strip：control_points 为 3n+1 个局部 `[x,z]` 点，每三个新点延续一段 Bezier；width 为路径平面内带宽，depth 沿 Y。局部中心由控制点约定，placement/rotation 决定世界位置。
- text：仅在用户明确要求图文时使用；默认清洁图不实例化商业文字，也不把整张源图贴到模型保留广告。

## 组合关系

柜台主体高度扣除台面/踢脚后定位子件，悬挑和圆角按图，避免穿插；隐藏背板最小补全。
屏框和显示面共享朝向，显示面位于框可见表面内侧；墙、柱、弯肋等支承分别建件并保持遮挡，不用整块亮面替代可见边框。
重复肋条共享生成逻辑，不写死数量/间距：逐根记录位置，遮挡段标 inferred。源图没有出现的组合不实例化。

## 扩展范围

复杂产品、孔阵、曲面家具、植物资产只有属于本次交付范围才扩展；当前没有资产导入器、自动 UV 或现成精细家具系统。关键形状不支持时扩展通用 builder/schema/测试；客户专有 mesh、品牌和固定尺寸留在样本目录。
从照片/sRGB 色板估色时用 `color_space=srgb`。贴图只用可用用户素材或内置内容，不随包分发运行环境字体。
