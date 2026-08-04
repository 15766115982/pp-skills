# PowerDocu 及社区仓库事实核实报告

核实日期：2026-08-03
方式：受限网络下通过 `git clone` / `git ls-remote` 直连 github.com 核实。

---

## 1. modery/PowerDocu 核实

仓库已浅克隆至 `D:/claude/power-platform/research/repos/PowerDocu`（含子模块 `modules/PowerDocu.Common`，来源 https://github.com/modery/PowerDocu.Common）。

### a. 功能范围 — 属实

README 原文："allows the automatic generation of technical documentation for **Cloud Flows**, **Canvas Apps**, **Model-Driven Apps**, **Copilot Studio Agents**, **AI Models**, and **Solutions** (including all contained components). The documentation can be generated as a Word document, as HTML, or in Markdown format"。

- 输入：Flow 导出 `.zip`、Canvas App `.msapp`、Solution `.zip`（GUI 文件过滤器 `*.zip;*.msapp`，见 `PowerDocu.GUI/PowerDocuForm.Designer.cs:632-633`）。
- 输出：Word / Markdown / HTML，另有 Graphviz 生成的 PNG+SVG 流程图、屏幕导航图。
- Dataverse 表：Solution 解析覆盖（`SolutionParser`、`CustomizationsParser`、`TableEntity`），README 的 Solution 文档章节列出 tables。
- 项目结构为多个 documenter：`PowerDocu.FlowDocumenter`、`PowerDocu.AppDocumenter`、`PowerDocu.SolutionDocumenter`、`PowerDocu.AppModuleDocumenter`（模型驱动应用）、`PowerDocu.AgentDocumenter`、`PowerDocu.BPFDocumenter`、`PowerDocu.DesktopFlowDocumenter`、`PowerDocu.AIModelDocumenter`，加 WinForms `PowerDocu.GUI`。

### b. 技术栈与 LICENSE — 属实

- C# / .NET：各 csproj `<TargetFramework>net10.0</TargetFramework>`（GUI 为 `net10.0-windows`），README badge 也标注 .NET 10。
- LICENSE 头两行："MIT License / Copyright (c) 2021 Rene Modery" — MIT。
- 关键依赖（`modules/PowerDocu.Common/PowerDocu.Common/PowerDocu.Common.csproj`）：Newtonsoft.Json 13.0.4、DocumentFormat.OpenXml 3.5.1、Grynwald.MarkdownGenerator 3.0.106、Rubjerg.Graphviz 3.0.4、Svg 3.4.7、**Microsoft.PowerFx.Core 1.8.1**、YamlDotNet 16.3.0、HtmlAgilityPack。

### c. Flow definition JSON 解析思路（可借鉴点）

解析器位于子模块 `PowerDocu.Common/PowerDocu.Common/FlowParser.cs`（440 行）：

- `FlowParser(string filename)`：zip 内用 `ZipHelper.getWorkflowFilesFromZip` 找 workflow JSON；依 `.msapp` 存在与否区分 `PackageType.FlowPackage / SolutionPackage`。
- `parseFlow(string flowJSON)`：Newtonsoft `JsonConvert.DeserializeObject<JObject>`（MaxDepth=128）后，依次 `checkFlowType`（按 `schemaVersion=="1.0.0.0"` 或 `type=="Microsoft.Flow/flows"` 判 CloudFlow，`schemaversion` 含 "ROBIN" 判 DesktopFlow）、`parseMetadata`（name/displayName/description）、`parseTrigger`、`parseActions`、`updateOrderNumbers`、`parseConnectionReferences`。
- `parseTrigger`（行 124）：`((JObject)flowDefinition.properties.definition.triggers).First` 取第一个 trigger，按 `description/type/recurrence/inputs` switch 填充 `flow.trigger`（`Trigger.cs`）。
- `parseActions(FlowEntity, JEnumerable<JToken>, ActionNode parentAction, bool isElseActions, string switchValue)`（行 243）递归遍历 `properties.definition.actions`：
  - `case "actions":` 递归进入嵌套/ switch-case 分支；
  - **`case "runAfter":`（行 293）：为空则 `flow.actions.addRootNode(aNode)`；否则对每个 `JProperty raNode` 调 `flow.actions.FindOrCreate(raNode.Name)` 并 `flow.actions.AddEdge(runAfterNode, aNode, raConditionsArray)`** — 即把 runAfter 转为有向图边，条件（Succeeded/Failed 等）作为边标签；
  - else 分支（`elseActions`）单独递归并标记 isElseActions。
- 图结构：`ActionGraph.cs`（196 行）的 `ActionGraph` / `ActionNode`（含 Subactions、Elseactions、root nodes、`FindOrCreate`、`AddEdge`）。`updateOrderNumbers` 做拓扑排序编号。
- 表达式解析：`Expression.cs` `Expression.parseExpressions(prop)` 把 `"@{...}"` 之类的值解析为表达式树。
- 图示生成：`PowerDocu.FlowDocumenter/GraphBuilder.cs`（655 行，含 runAfter）用 Rubjerg.Graphviz 输出 PNG/SVG。

### d. Canvas App 解析深度 — 关键结论：停留在 .msapp 内部 JSON 时代，不支持 .pa.yaml

`PowerDocu.Common/PowerDocu.Common/AppParser.cs`（410 行）证据：

- `parseAppProperties` 解析 zip 内 `"Resources\\PublishInfo.json", "Header.json", "Properties.json"`；
- `parseAppControls`：`ZipHelper.getFilesInPathFromZip(appArchive, "Controls", ".json")` — 读取旧版 .msapp 解包后的 `Controls\*.json`；
- `parseAppDataSources` / `parseAppResources` 读 `References\\DataSources.json`、`References\\Resources.json`；
- 全库 grep 无任何 `pa.yaml` / `Src/*.yaml` / Canvas YAML 源码格式的处理；YamlDotNet 仅用于 Agent（Copilot Studio）定义（`PowerDocu.AgentDocumenter/GraphBuilder.cs`）。
- 但公式层面不弱：`AppParser.CheckForVariables` 用 **Microsoft.PowerFx.Core** 的 `engine.Parse(input)` 构建 AST，内部类 `FormulaVisitor : IdentityTexlVisitor` 重写 `PostVisit(CallNode)` 提取 `Set/UpdateContext/Navigate/Collect/ClearCollect` 调用，识别全局变量、上下文变量、集合与屏幕导航目标。

结论：PowerDocu 解析的是 .msapp zip 包内的 JSON（PAC 工具 unpack 前的原始格式），**没有支持 Power Apps Source Code（.pa.yaml）新格式**——社区在 pa.yaml 解析上确为空白，这与方案假设一致。

### e. 活跃度

- 主仓库最后一次提交：2026-06-14（"Merge branch 'main'..."）；子模块 PowerDocu.Common 最后提交同为 2026-06-14（"Safer way of downloading connector icons"）。
- 版本：`PowerDocu.GUI.csproj` `<Version>3.0.1</Version>`；git tags 最新为 `v-3.0.1`（tag 序列从 v-0.5.0 延续至今），有 Releases 发布。
- 结论：活跃维护中（最近提交距今约 7 周）。

## 2. 社区仓库存在性（git ls-remote --symref HEAD）

| 仓库 | 存在 | 默认分支 |
|---|---|---|
| ryanmichaeljames/dataverse-mcp | 是 | main |
| jukkan/xrm-mcp | 是 | main |
| Cliveo/Power-Platform-MCP | 是 | main |
| callumalpass/power-platform-devkit | 是 | main |
| DanielKerridge/claude-code-power-platform-skills | 是 | master |
| microsoft/Power-Fx | 是 | main |

## 3. microsoft/Power-Fx

浅克隆（sparse）至 `research/repos/Power-Fx`：

- `LICENSE` 首行 "MIT License / Copyright (c) Microsoft Corporation." — MIT 确认。
- `src/libraries/` 含 `Microsoft.PowerFx.Core`（含解析器/AST：`ParseResult.Root.Accept(visitor)`、`IdentityTexlVisitor`、`CallNode` 等，PowerDocu 正是依赖此包 1.8.1 做公式 AST 分析）、`Microsoft.PowerFx.Interpreter`、`Microsoft.PowerFx.Connectors`、`Microsoft.PowerFx.LanguageServerProtocol`、`Microsoft.PowerFx.Repl`、`Microsoft.PowerFx.Json` 等。
- 结论：MIT、提供官方 Power Fx 公式解析（AST）能力，且已有社区项目（PowerDocu）引用 `Microsoft.PowerFx.Core` NuGet 包作为先例。
