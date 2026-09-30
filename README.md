# NX12.0 v0.2

面向 Siemens NX 12 的建模与工程图重建 skill，包含 Python / C# Journal 模板、API证据检查、静态检查、C#编译检查及几何验收规则。

**本版重点：把交叉读图设为图纸驱动建模的必经步骤。** 在确定特征类型、推导依赖尺寸或编写对应建模操作前，联合核对相关视图中的材料关系、尺寸归属、方向与基准，并记录能够排除错误解释的证据。

## 使用入口

- [SKILL.md](nx12-modeling/SKILL.md)：主流程与适用范围。
- [强制交叉读图](nx12-modeling/references/cross-reading.md)：完成门槛、判别方法及异常后的回查。
- [几何验收](nx12-modeling/references/geometry-acceptance.md)：局部尺寸、材料侧、连通性、曲面与证据范围。
- [NX12运行观察](nx12-modeling/references/runtime-observations.md)：符号螺纹及包围盒的特定环境经验。
- [版本说明](VERSION-NOTES.md)：0.2的变化及验证情况。
- [文件清单](MANIFEST.json)：27个skill文件的大小与SHA-256。

下载仓库后，使用完整的 `nx12-modeling/` 目录；入口名称仍为 `nx12-modeling`，版本记录在 `SKILL.md` 的 `metadata.version` 中。将该目录交给支持本地skill的执行环境，或明确要求执行者读取其 `SKILL.md`。保留相对目录结构，以便加载参考文件、脚本和模板。

## 目录

```text
nx12-modeling/
  SKILL.md
  agents/             界面元数据
  references/         NX12、交叉读图、建模与验收参考
  assets/templates/   Journal、图纸台账与验收报告模板
  scripts/            环境探测、静态/API证据及编译检查
  tests/              现有118项回归测试
```

## 验证

在skill目录运行：

```powershell
py -X utf8 -B tests/test_nx12_skill.py
```

2026-09-30的本地验证记录为118项通过、0失败、0错误、0跳过，65处内部链接及锚点检查通过。部分测试依赖PowerShell、目标NX安装或C#编译器；其他环境可能跳过相应检查，应以实际日志为准。

官方 `quick_validate.py` 在本次两个现有Python环境中均因缺少PyYAML而未完成。本版文档做过语义自查，尚未用0.2执行新的NX实机建模试验。此前复杂零件的用户验收是本版规则的实践来源，不作为0.2新规则已经通过实机验证的证据。

本skill不附带Siemens二进制或专有文档。运行证据、API可用性和几何符合性分别报告；模板与检查脚本不会自动认证整件模型。
