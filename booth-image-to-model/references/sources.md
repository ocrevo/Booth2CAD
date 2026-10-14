# 外部接口依据与版本核验

以下是开发时核对的官方接口资料，不代替实际版本测试。

Agent Skills format specification：`https://agentskills.io/specification`
目录包含 SKILL.md、YAML 元数据以及可选 scripts/references/assets；主说明按需加载附属内容。

Blender API world_to_camera_view：`https://docs.blender.org/api/current/bpy_extras.object_utils.html`
将世界坐标投影到指定场景相机。代码会先更新 view layer，再输出左上原点的 uv。

Blender command line arguments：`https://docs.blender.org/manual/en/latest/advanced/command_line/arguments.html`
后台进程、禁用自动执行及 Python 异常退出设置需在本地 Blender 上验证。

本环境的 web 抓取并未成功读取全部 Blender 手册页面。Blender 脚本 API 的最终有效性以实际运行的集成测试为准，不能仅凭这些资料宣布兼容性已验证。

原图与旧版代码/参数来自本次对话上传文件。原始已安装 Skill 源文件未被读取，不作已同步或逐行修改的声明。
