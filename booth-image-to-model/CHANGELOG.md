# 2.7.0-rc1 — 2026-10-15

- 新增场景描述契约 `schemas/scene-description.v1.json`：图上读到的东西（尺寸标注、角点、构件落点像素、颜色、证据）写成纯数字 JSON。所有键必填、可空用 null，只用 `$schema/title/description/type/enum/properties/required/items/additionalProperties` 这几个各家结构化输出都支持的关键字（测试强制白名单），方便任何看图模型或人填写。
- 新增 `scripts/draft_compile.py` 与 `boothctl.py compile`：场景描述加原图编译成 spec，不调用任何模型。流程：结构校验和语义校验（逐条给出错位置）→ box_fit 拟合相机（给定 fit 时核对图像尺寸、W/D/H、floor_z 和相机）→ 用 camera_math 把像素反投影到地面或展台边 → 用构件宏和 SpecBuilder 建模 → 钳进占地、聚光灯去重、同向共面的盒子拉开 2 mm（地面从不被移动）→ validate → 写 spec.json、box_fit.json、compile_report.json。支持 counter、round_table、shell_chair、planter、box、cylinder、louvre_wall、wall、wall_panel、tv、led_wall、spotlights、roof_frame。
- 编译跑完才写输出目录：被拒绝、拟合失败或读不了图时目录保持原样；同一目录可反复编译，也可用输出目录里的 source.* 作为输入；换扩展名时旧的 source.* 会被清掉。单个构件失败（矩形在墙外、构建器拒绝参数、排不下）整件跳过，连同它的假设、调整和警告一起撤销，状态为 partial。所有代填的先验值（厚度、台面深高、桌半径和高、椅座高、聚光灯体、LED 模组等）都记入 `assumed` 并完整汇总到 spec 的 `compile_assumed_values`。场景里填了而类型不读的字段会在报告里列出，不会悄悄吞掉。拟合警告和歧义提示进入报告与摘要。
- 一轮独立对抗性审查（三个视角，每条发现由另一个 agent 复现）发现并已修复：带关键不确定项的场景会崩溃（KeyError）；box/cylinder 几何被拒绝时整个编译中断；高度未知时抛 KeyError；`size_m` 太短时 IndexError；整数字段接受 2.5 之类；旋转盒子按外接圆钳位被误移数米；共面修复会缩小地面使 spec 失效；louvre 排不下、斜排、单片偏心、超出展台；电视和 LED 墙只修剪位置却照常超出墙边；浅展台的默认屋顶框被丢弃；先验值未记录；丢弃的构件仍留下假设记录；`--fit` 与场景不一致时被静默采用；重新编译时 SameFileError 和旧文件残留；地面角点地标按 W/2 取值而不看记号；两个入口失败输出通道不一致、I/O 错误是栈回溯；jsonschema 被写成仅测试依赖。
- 测试：`tests/test_draft_compile.py`（22 项，含 1 项原生预览）和 `tests/test_draft_compile_rules.py`（34 项，每项对应一个审查发现，另含四个展台边的 wall/wall_panel/tv 位置与朝向、schema 白名单和 schema/处理器/文档一致性）。对编译器副本做了 23 种故障注入的变异检查（翻转各边内向符号、去掉去重、跳过共面修复、忽略证据、允许移动地面、取消回滚等）：22 种首轮即被测试发现，剩下的“编译途中先写文件”补了一条晚期失败测试后也被发现。
- 新增 `references/scene-description.md`，SKILL.md 快速路线第 4 步增加这条路径，兼容性说明加入 jsonschema（GLB 导出需 trimesh）。
- 用橙色测试图实测（只在 output/）：同一份读数写成场景描述后编译，99 个构件、校验通过、无警告，与手写 spec 逐件对比位置中位差 0.4 mm、最大尺寸差 4 mm，分组一致；原生预览角点中位误差 2.14 px。

# 2.6.0-rc2 — 2026-10-14

- 仅文档：SKILL.md 与 README_CN.md 不再说网页编辑器“尚未提供”，改为说明仓库根目录 `web/` 的静态编辑器（不属于本 skill 包）及“编辑 spec”的流程：载入、编辑、保存、再校验、再生成；写明改动只回写 spec，改过的零件标为 inferred，相机标为 unfitted。图纸仍未提供。
- 代码、schema 和测试没有变化，回归证据沿用 2.6.0-rc1 的完整原生回归（210 项，0 失败，0 跳过；输入哈希一致）。

# 2.6.0-rc1 — 2026-10-14

- 为网页编辑器做准备：spec 的构件新增可选字段 `group`（schema 与校验器接受小写标识符，缺省即独立件，旧 spec 不变）。构件宏的所有零件自动带宏前缀作 group；`SpecBuilder.grouped(名)` 和 `add(..., group=)` 可手动分组；Blender 构建把 group 写进对象自定义属性。宏输出除多出 `group` 外与此前逐字节一致（测试去掉 group 后比对原指纹）。
- 新增 `scripts/export_glb.py` 与 `boothctl.py glb`：不用 Blender，把 spec 导出为 GLB。Z 向上换成 Y 向上（纯旋转，三角形绕向不变；测试检查每个网格体积为正），颜色按 sRGB 转线性并以精确浮点写入（trimesh 默认存 8 位，暗色会分层，所以重写材质表），每个构件一个节点并带 extras，同组构件挂在 `group:<名>` 下。文字构件、格网纹样不导出、发光强度大于 1 会截断，均列入报告。校验不通过的 spec 不会写出 GLB。trimesh 现在也是 GLB 导出的可选依赖。
- 测试：新增 `tests/test_group_glb.py`（宏分组、可选性、schema/校验器拒绝坏值、GLB 节点层级、extras、坐标轴与绕向、颜色转换、命令行与 boothctl）。

# 2.5.0-rc1 — 2026-10-14

- 改名：skill 与目录由 `rebuild-booth-blender` 改为 `booth-image-to-model`（从一张展台图片生成参数化三维模型和客户渲染图）。新名字不绑定 Blender，也不暗示 CAD 或图纸：当前不输出图纸，尺寸也不是实测值。
- 同步更新 SKILL.md、README、AGENTS.md、模板中的 skill 查找、打包工具的默认路径、schema `$id` 和 `.gitattributes`；打包工具改为从 SKILL.md 读取 `skill_name` 写入发布状态。
- `validation/` 里已归档的审计、历史证据保持当时的旧名字，不改写。GitHub 仓库名尚未更改。

# 2.4.0-rc4 — 2026-10-14

- 客户图默认曝光由 −0.5 EV 改为 −1.0 EV（按所有者确认）。依据：全白展台在 −0.5 EV 下 6%–12% 的展台像素被压平，−1.0 EV 后降到 2.4% 以下；曝光对照图显示 −1.0 EV 能分开墙、地面和柜台。降低曝光会同时压暗灰色背景。需要旧效果时传 `--client-exposure -0.5`。预览的曝光建议以 −1.0 EV 为基准。

# 2.4.0-rc3 — 2026-10-14

- 依据 orange、legacy-case、wx 三张图的新流程计时（20–27 分钟；工具计算只占 2–7 分钟，其余是读图和写 spec）：
- 预览新增 `--client-look`（`boothctl preview --client-look`、`blender_build --preview-client-look`）：同时渲出终版客户画面，报告高光被压平的像素比例，并给出建议的 `--client-exposure`；`--client-exposure` 可传给预览以验证。实测全白展台在默认 −0.5 EV 下 6%–12% 的像素被压平，建议值 −1.0 EV 后降到 2.4% 以下。默认曝光不变。
- box_fit 新增 `scale_checks`（用图中直立标准件的底、顶像素和期望高度核对尺度假设，不参与拟合），结果带 `assumed` 列表，模板把它写进 `scale.notes`。
- 修复：overlay 在没有任何点用到高度时不再 KeyError（只画地面）；宽、深缺失时给出明确提示。
- design_check 以地台构件自己的矩形为基准判断出界和到开口边的距离，不再假定地台以原点为中心。
- `benchmark.py prepare` 的重复目录报错会说明已有的 case 和该怎么做（仍然拒绝覆盖）。

# 2.4.0-rc2 — 2026-10-14

- 修复：`--hd-scale 3` 在 938×816 的图上（6.9 MP）让 OIDN 降噪器内存不足，Blender 崩溃，高清图损坏且没有 build_report。现在高清帧默认限制在 5 MP（`--hd-max-mp`，4.9 MP 实测可渲出），超出时降低有效倍数，必要时跳过高清；高清阶段前先写一份 `partial` 报告，渲染高清前释放持久数据；build_report 的 `hd` 记录请求倍数、有效倍数和是否被限制。
- box_fit：残差超过 4 px 时状态为 `high_residual`，并点名最差的三个点与警告（此前会报 fitted）。
- design_check：单个挤出的 U 形门头不再按平面范围误报带深（改为 not_checked）；椅子和桌子按 0.6 m 内归为一个座位组，避免椅腿被当成独立家具而产生大量窄间隙提示。
- 依据：orange 图的新流程计时（约 26 分钟，终版因上述崩溃失败）。

# 2.4.0-rc1 — 2026-10-14

- 新增建议性设计检查 `design_check.py` 与 `boothctl design-check`（`preview --context` 同步给出）：部件出界、限高、无建模支撑路径、门头楣带、前台、显示面、LED 整块模组、坡道、画面底边、窄间隙。只用中性措辞；缺少 context 的检查报告为 not_checked，不套默认值；不改 `validate()`。
- 新增 `schemas/design-priors.v1.json`：只收 `design-priors.md` 已有数值，每条带出处且 `reviewed=false`；测试保证宏的默认值、电视档位与它一致，且文档与 JSON 中不出现内部规则编号。
- 新增构件宏 `header_band`（直段/L/U 形，拐角不重叠，落地立柱）、`tv`（16:9 档位，必须给边框与厚度）、`led_wall`（整块模组，对齐板边的接缝）、`spotlights`（自发光灯体，不建光锥）；电视档位表补 60 英寸。已有宏的输出用固定指纹测试保证逐字节不变。
- 新增原生预览测试：含全部新宏的合成展台。

# 2.3.0-rc2 — 2026-10-14

- 依据对一张新图的计时基线（约 27.7 分钟，其中读图与写 spec 约 16 分钟、3 倍高清终版 376 秒）补齐测量与诊断，默认行为不变。
- build_report 新增 `stage_seconds`（校验、建模保存、每张渲染、遮罩、终存）；`boothctl preview` 回报阶段用时和启动开销；`--hd-views client|both` 可只出客户视角高清图（默认仍两张）。
- Workbench 预览崩溃后，同一预览目录的后续预览直接用 Cycles（`.preview_engine.json`）。
- box_fit 结果带画幅和地面高；不确定时点名未被约束的尺寸并给出补点建议（`ambiguous_dims`、`ambiguity_hint`）；文件头示例改为中性数字。
- 新增 `overlay.py` 与 `boothctl overlay`：在原图上画拟合出的展台外框、0.5 m 地面和墙面网格、点击点到拟合点的偏差，建模前检查机位是否贴合。
- camera_math 新增 `on_wall_x`（侧墙反投影）和 `height_above`（由底部与顶部像素估直立物体高度，并报告偏离垂线的距离）。
- 预览对照把 landmark 误差分成参与拟合（循环）与独立检查（fit=false）两类；SKILL 说明高调展台用 Cycles 预览和 `--client-exposure`。
- 项目模板从 box_fit.json 读取画幅，并核对输入快照的真实尺寸，不再含固定画幅和像素坐标；新增运行模板的测试。

# 2.3.0-rc1 — 2026-10-14

- 新增快速路线，按上一次单图重建的耗时复盘设计：先用 6–10 个角点同时拟合相机、焦距与展台比例（box_fit），再建模；尺度来自客户尺寸、标准件或显式标注的假设。
- 新增 camera_math（与 Blender 一致的投影/反投影）和 components 宏库（SpecBuilder、柜台、圆桌、壳椅、百叶、格栅、种植槽、壁挂屏、搁板），项目 spec 改为几十行参数脚本；新增项目模板。
- validate 新增 COPLANAR_OVERLAP 警告：同向共面且重叠的外露面会渲出黑面或闪烁；凸面精确求交，被反向面贴住的情况不报。
- blender_build 新增 `--preview`（Workbench 或低采样 Cycles，只渲源机位）与 `--hd-scale`（同进程高清客户图和第二视角）；Cycles 默认自适应采样、OIDN 和持久数据；材质同步视口颜色；相机近裁剪面按距离设置，修复光栅预览和视口的深度锯齿；同一输出目录加构建锁。
- boothctl 新增 `preview`：新编号目录、单图渲染、四宫格对照与 landmark 像素误差；核显驱动导致 Workbench 失败时自动改用 Cycles。
- 新增设计先验文档：工作室规范尺寸换算为米制、尺度锚点优先级（系统展具 0.99/0.992 m 模块、LED 拼缝、电视档位优先；前台、人、绿植只作核对）、展位类型读图提示，并引用 knowledge/research 中带出处的场馆与尺寸整理稿。
- Cycles 降噪改为 OIDN Fast 预滤波 + Balanced 质量；壳椅默认座高 0.45 m。

# 2.2.0-rc2 — 2026-10-07

- 按 skill-creator 标准进行三路独立 AI 初审，再用合成案例复现并修复；报告区分初审、修复和验证，不冒充外部认证。
- 对齐嵌套 schema 与运行时校验，拒绝未知字段、缺失项、非法类型、文字布尔挤出量和非正数对应点权重；源图 hash 与真实像素画幅同时核对。
- 严格 QA 单独检查保留点的中位数与 P90；原生重开核查文字尺寸、挤出和对齐；透视拟合范围围绕相机种子设置。
- 项目分开 input/ 原始输入与 output/ 任务结果；benchmark 保存不可变输入快照，并支持 Windows 跨盘引用。旧 test/ 链接继续可用。
- 回归 runner 显式配置原生 Blender，结果写入独立目录，保留完整真实日志与代码/schema/测试来源 hash；发布维护工具拒绝跳过、过期或不完整证据。
- 实际回归结果见 validation/test_results.json；包含原生 Blender 构建、重开和失败拒绝。视觉相似性和实测尺寸仍需逐个展台复核。

# 2.2.0-rc1 — 2026-10-07

- 新增通用 profile_extrusion 和 arc_panel：真实凹轮廓、顶部/底部边缘缺口、弧形板及相邻分段；拒绝自交与退化输入。
- 可选米制 procedural grid 材质，弧面按弧长展开并可跨分段连续；明确表面格纹不等于实体穿孔。
- 第二视角与源图水平至少相差 35°，按相机坐标中全部包围盒角点取景，改善横向长展台和正面源图的检查视角。
- 区分平面宣传图和实体屏幕；开口保留真实后方可见结构。样本尺寸、色带数量、布局和照片均留在被忽略的 test/。
- 75 项测试通过且无 skip，包括原生 Blender 5.2.2 LTS 重开、真实负空间与材质图篡改拒绝。视觉对照仍不等于实测复原。

# 2.1.0-rc1 — 2026-10-06

- 默认客户纯展台展示：去展厅、邻展、Logo、文字、人物、水印和尺寸箭头，保留建筑、家具与中性屏幕。
- box 真实全边/竖角圆化，新增连续 Bezier swept_strip；尺寸与布局保存在样本 spec。
- 相机、灯光、裁剪按实际包围盒缩放；透明验收图与中性客户图分别输出，客户曝光可配置。
- sRGB 材质真实转换、JPEG 输入编码为真 PNG、修复独立复开 CLI 并核验 shader 参数。
- 新增输入登记、AI 清洁 prompt、四列对比页及真实文件证据。测试素材和所有派生输出留在 Git 忽略的 test/。
- Blender 5.2.2 LTS 原生运行验证，64 项测试通过且无 skip；三类图片的视觉结果仍保留具体近似和待复核项。

# v2.0.0-rc1

## 可执行代码

- 显式 rounded_ring / rounded_portal 原型；真实内外圆角、连续实体与开口。
- 严格 v2 spec；scope 对照、尺寸/几何可构造性、未知/未使用参数、关键构件义务检查。
- 受控参数修改；禁止借修改尺寸接口改归属、输入来源、关键要求和审核证据。
- 固定几何的有界透视相机拟合，要求可信多深度对应点与保留检查点。
- 可见 masks、边界和关键点误差计算；拒绝画幅不一致或直接把 RGB 照片阈值分割。
- 本地阶段指纹和 complete + 文件哈希校验；不是自动任务服务或构件级场景缓存。
- 原生 Blender 分件构建和独立重新打开验证脚本。
- 真实文件、同版本渲染、语义复核与未解决关键疑点的交付检查。

## 工作流

- 先 scope / 负空间 / 拓扑 / 相机，再比例和细节。
- 背景几何不得混入 booth，也不得伪装成 render_rig。
- 同机位对拍与第二视角分别验收；不把大总览图当参考机位。
- 明确对模型能力、计算预算和质量指标的边界，不写虚构的节省比例和还原分数。
- 主 Skill 精简，细节按需加载，重复创建几何交给固定代码。

## 发布状态

候选版。单元与实际旧输入拒绝测试完成；原生 Blender 集成和完整 Legacy case 对拍尚待验证。
未更新用户账号中的已安装版本。
