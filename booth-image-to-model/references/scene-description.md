# 场景描述（scene-description.v1）

把“一张展台图里看到了什么”写成一份只有像素和普通数字的 JSON，由 `scripts/draft_compile.py` 编译成 booth-spec-v2 的 spec。它取代手写 `build_spec.py` 的重复部分：反投影、钳位、去重、分组、证据标记、校验。谁来写这份 JSON 都行：agent、脚本、人，或某个看图的模型；编译器不调用任何模型，也不信任 JSON 里的几何。

## 流程

1. 看图：读出图上标注的尺寸、6–10 个外角、每个构件落地（或贴墙）的像素。
2. 写 `scene.json`，格式见 [`schemas/scene-description.v1.json`](../schemas/scene-description.v1.json)。所有键都必填，不适用的写 `null`；schema 只用各家结构化输出都支持的关键字。
3. `python booth-image-to-model/scripts/boothctl.py compile --scene scene.json --image <原图> --out <目录> [--fit box_fit.json]`。不给 `--fit` 就用 `corner_points` 现场拟合（同时运行 `scale_checks`）。
4. 看 `<目录>/compile_report.json` 和命令输出的摘要：
   - `status`：ok / partial（有构件被丢弃）/ invalid（spec 没通过校验，退出码 2）。
   - `fit`：拟合状态和残差。`high_residual` 不阻止编译，但 `fit_warnings` 要看；SKILL.md 第 3 步要求 `fitted`。
   - `dropped`（没建出来的构件及原因）、`adjustments`（被移动、去重、修剪、拉开 2 mm 的东西）、`assumed`（编译器代填的值）、`warnings`（含校验器的警告和“字段未被使用”的提醒）。
5. `boothctl.py preview --spec <目录>/spec.json ...` 对照原图，需要时改 `scene.json` 再编译；从输出目录再编译也可以（`--image <目录>/source.png`）。

输出：`spec.json`（原图复制为同目录的 `source.*`，路径是相对的）、`box_fit.json`、`compile_report.json`。**编译跑完才写文件**：场景描述被拒绝、拟合失败、读不了图时，输出目录保持原样，不会出现新旧混杂。拒绝场景（`scene_invalid`）、输入文件问题（`input_error`）、缺依赖（`missing_dependency`）、spec 校验失败（`invalid`）退出码均为 2；摘要都打印到标准输出。

依赖：numpy、scipy、Pillow、jsonschema（见 `requirements.txt`）。

## 约定

- 像素是原图像素，原点在左上。`base_px` 是构件和地面接触处的中心像素；`wall_rect_px` 是贴墙平面构件的 `[左上 u, v, 右下 u, v]`，会被反投影到墙面平面上，所以要框的是构件贴着墙的轮廓（电视的边框外缘、LED 墙的外缘）。
- `plane` 是展台的哪条边：`back`（+Y）、`front`（−Y）、`left`（−X）、`right`（+X）。
- `inset_m` 因类型而异：`wall` 是墙**外面**离边缘多远（默认 0）；`tv`、`led_wall`、`wall_panel` 是构件所贴的**墙面**离边缘多远（默认 0.1，即贴在 0.1 m 厚墙的内面）；`roof_frame` 是外框向内缩多少（默认 0）。墙的厚度或位置不是默认值时，贴墙构件的 `inset_m` 要写成同一个墙面位置，否则会埋进墙里。
- 尺寸一律米；`size_m = [宽(X), 深(Y), 高]`，写 `null` 的项在有设计先验时用先验。**每一个由先验或默认值补上的数都会记入 `assumed`**（厚度、台面深度和高度、桌的半径和高度、椅座高、聚光灯体、LED 模组和深度、电视边框等），并汇总成 spec 里的 `compile_assumed_values` 不确定项。
- `z_range_m` 是离 z=0 的高度（不是离地面）。
- `evidence: observed` 必须给 `roi_px`（要和图像有交集）；隐藏或假设的部分写 `inferred`。
- 颜色写 `#rrggbb`（从图上读的 sRGB）；`null` 用类型默认色。
- 宏类型（counter、round_table、shell_chair、planter、louvre_wall、tv、led_wall、spotlights）生成多个零件，`id` 就是前缀，同时是分组名；别的 `id` 不能以“前缀_”开头。`box`、`cylinder`、`wall`、`wall_panel`、`roof_frame` 单件，可用 `group` 指定分组。
- 地面不是场景构件：由占地尺寸自动生成，属于范围 `booth_floor`（没定义时自动创建；定义了就必须是 include、owner=booth）。

## 构件类型

| type | 必填 | 其他输入 / 默认 |
|---|---|---|
| `counter` | `base_px`、`size_m[0]` 宽 | 深默认设计先验；高取 `size_m[2]` 或 `height_m`，默认先验；`yaw_deg` 只认 90 的倍数（其他角度警告并忽略）；`accent_hex` 台面色 |
| `round_table` | `base_px` | `radius_m`、`height_m` 默认设计先验；`accent_hex` 桌柱色 |
| `shell_chair` | `base_px` | `yaw_deg`（0 朝 −Y）；`accent_hex` 椅腿色 |
| `planter` | `base_px` | `size_m` 宽深默认 0.4；高取 `size_m[2]` 或 `height_m`，默认 0.45 |
| `box` | `base_px`、`size_m` 宽深、高（`size_m[2]` / `height_m` / `z_range_m`） | `yaw_deg`、`bevel_m`+`bevel_mode`、`role`、`critical`、`note` |
| `cylinder` | `base_px`、`radius_m`、高（同上） | `role`、`critical`、`note`；没有 yaw 和倒角 |
| `louvre_wall` | `base_px`、`base_px_2`（排的两端）、`count`、`width_m`（片宽）、高 | `thickness_m` 默认 0.06。排向取最接近的 X 或 Y 轴（偏离超过 15° 警告）；超出展台的部分修剪并记录；`count` 片排不下时丢弃；`count=1` 居中 |
| `wall` | `plane`、高 | `base_px`+`base_px_2` 成对给出才限定长度（默认整条边）；`thickness_m` 默认 0.1；默认 critical |
| `wall_panel` | `plane`、`wall_rect_px` | `thickness_m` 默认 0.05；超出边缘的部分修剪 |
| `tv` | `plane`、`wall_rect_px`（含边框）、`inch`（43/50/55/60/65/75/85） | `bezel_m` 默认 0.02，`depth_m` 默认 0.05；按档位尺寸建，矩形差 25% 以上警告；部分超出墙边时沿墙滑回，完全在墙外则丢弃；`accent_hex` 是屏幕色 |
| `led_wall` | `plane`（只支持 back）、`wall_rect_px`、`count`（列）、`rows` | `module_m` 默认 0.5，`depth_m` 默认 0.1；整块模组，和矩形不符时警告；超出墙边时沿墙滑回 |
| `spotlights` | `points_px`、`height_m`（挂点高度） | 点按 z=`height_m` 平面反投影；灯体半径 0.04、长 0.12 记入 `assumed` |
| `roof_frame` | 高（`height_m` / `z_range_m` / `size_m[2]`） | `width_m` 框带宽默认 0.6，`radius_m` 角半径默认 0.8；外形取占地，`inset_m` 向内缩；内圆角自动收到开口短边的一半以内 |

尚不支持：`header_band`、`slats`、`shelves`、`wall_screens` 等其他宏和 `swept_strip` / `profile_extrusion` / `arc_panel`。遇到这些造型，先用 `box` / `cylinder` 近似并在 `uncertainties` 里写明，或在编译后的 spec 上继续用 SpecBuilder 或网页编辑器补。

每个类型只读上表列出的字段。场景里填了而该类型不读的字段（例如宏上的 `critical`、`cylinder` 上的 `bevel_m`）不会被悄悄吞掉：报告 `warnings` 里会写 “X 不被类型 T 使用，已忽略”。

## 编译器的规则

- 相机：`box_fit` 现场拟合，或使用给定的 `box_fit.json`。给定的 fit 必须完整并与场景一致：图像尺寸、`known` 的 W/D/H、`floor_z`、相机都要对得上，否则拒绝（`FIT_MISMATCH`）；高度既没给也没有角点确定时拒绝（`H is unknown`）。给定 fit 时 `scale_checks` 不会运行，报告里会这样提醒。拟合状态、残差、拟合警告和歧义提示都写进 `scale.notes`、报告和摘要。
- 地面：由占地尺寸自动生成（critical，下表面在 `floor_z − 0.05`），地面四角里对应 `corner_points` 的点自动成为 landmark，供预览对照；x、y 各自按自己的记号（W/2 或 D/2）取值。
- 位置：落地构件钳进占地范围（旋转后的盒子按旋转后的外形，台面按含 2 cm 出挑的外形）；超出的移回并写进 `adjustments`；比展台还大的构件另给警告。聚光灯 0.25 m 内的重复位置只留一个。
- 共面：同向共面的外露面会渲出黑面；后加的盒子（否则前一个）被拉进 2 mm，**地面从不被移动**，拉不开的列在 `coplanar_unresolved`。
- 范围检查：构件包围盒超出占地 2 cm 以上的，报告里给警告（屋顶框和地面除外）。
- 失败：单个构件建不出来（矩形落到展台外、几何参数被构建器拒绝、排不下等）时整件跳过并写进 `dropped`，它的假设、调整和警告一并撤销，其余照常编译，状态为 `partial`；没有构件的范围会被移除。
- 数值上限：构件 ≤ 500，`count` ≤ 200，`rows` ≤ 100，聚光灯点 ≤ 200，尺寸 ≤ 100 m；`radius_m`、`height_m`、`width_m`、`thickness_m`、`depth_m`、`module_m`、`bezel_m` 必须大于 0；整数字段接受 5.0 这样的整数浮点，不接受 2.5。
- 不做：不猜品牌和文字，不确定的结构不自行补全，不给出合规结论。

## 最小例子

```json
{"id": "counter", "type": "counter", "scope": "furniture", "group": null, "role": null, "evidence": "observed",
 "roi_px": [500, 330, 640, 420], "color_hex": "#F2F0ED", "accent_hex": "#B8D6E0", "base_px": [560, 410], "base_px_2": null,
 "plane": null, "wall_rect_px": null, "points_px": null, "size_m": [1.4, null, null], "radius_m": null, "height_m": null,
 "width_m": null, "thickness_m": null, "depth_m": null, "z_range_m": null, "yaw_deg": null, "count": null, "rows": null,
 "module_m": null, "inch": null, "bezel_m": null, "bevel_m": null, "bevel_mode": null, "inset_m": null, "critical": null, "note": null}
```
