# NX12.0 v0.2

面向 Siemens NX 12 的建模与工程图重建 skill，包含 Python / C# Journal 模板、API 证据检查、静态检查、C# 编译检查及几何验收规则。

当前发布修订为 **v0.2-r2（2026-10-03）**。本次根据多轮建模返回记录，补齐带正负方向的视图对应、剖切材料与投影边线的区分、实际构面导向、错误样例反证和测量完成量核对。

skill 元数据保留 `version: "0.2"` 和来源修订标识 `revision: "r2-local-20261003"`；后者标识本次本地形成的修订，不代表尚未发布。

## 使用入口

- [SKILL.md](nx12-modeling/SKILL.md)：主流程与适用范围。
- [强制交叉读图](nx12-modeling/references/cross-reading.md)：视图注册、材料关系、尺寸归属与放行依据。
- [图纸重建](nx12-modeling/references/drawing-reconstruction.md)：特征台账、矢量证据、截面/导向/修剪与构建来源。
- [几何验收](nx12-modeling/references/geometry-acceptance.md)：有辨别力的检查、实际覆盖量与结论范围。
- [NX12 运行观察](nx12-modeling/references/runtime-observations.md)：符号螺纹、整体包围盒和局部面边界的特定环境记录。
- [版本说明](VERSION-NOTES.md)：本轮修改文件、问题来源、实际验证与待验证事项。
- [文件清单](MANIFEST.json)：27 个 skill 文件的大小与 SHA-256。

下载仓库后使用完整的 `nx12-modeling/` 目录。入口名称仍为 `nx12-modeling`；将该目录交给支持本地 skill 的执行环境，或明确要求执行者读取其 `SKILL.md`。保留相对目录结构，以便加载参考文件、脚本和模板。

## 目录

```text
nx12-modeling/
  SKILL.md
  agents/             界面元数据
  references/         NX12、交叉读图、建模与验收参考
  assets/templates/   Journal、图纸台账与验收报告模板
  scripts/            环境探测、静态/API 证据及编译检查
  tests/              既有118项回归测试
```

## 验证与边界

2026-10-03 本地实际执行 118 项既有回归测试，全部通过，0 失败、0 错误、0 跳过。默认 Python 3.14.7 已有 PyYAML 6.0.3，官方 `quick_validate.py` 返回 `Skill is valid!`；本轮未安装依赖，也没有重新判断其他 Python 环境的依赖状态。

在 skill 目录运行既有回归测试：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONIOENCODING='utf-8'
python -X utf8 -B tests/test_nx12_skill.py
```

部分测试依赖 PowerShell、目标 NX 安装或 C# 编译器；其他环境可能跳过相应检查，应以实际日志为准。C# 检查只编译，不执行建模程序集。8 个脚本、1 个测试文件、2 个 Journal 模板及 agents 配置共12个文件保持原字节；此次只修改文档与记录模板。

**新规则尚待前向行为验证。** 本轮审计既有报告和测量记录，没有启动 NX 或重新测量模型。来源任务的最新候选仍存在叶轮检查失败；局部纠错和工具测试通过均不等于整件模型合格。后续需用未接触旧模型、旧代码的图纸任务，观察跨视图证据和反证是否先于建模形成。

工程图渲染可在来源可信、标注清晰时用于读图；单视图有充分依据时可放行，不增加固定视图数量或重复确认。已有授权、保存保护、五种单项状态及脚本 JSON 契约保持不变。

本仓库保留完整 skill、公开说明与文件清单。原始任务报告、CAD 文件、本机绝对路径审计和备份保留本地，不附带 Siemens 二进制或专有文档。
