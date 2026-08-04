# 事实核实报告：awesome-copilot canvas YAML 指南与 .pa.yaml schema v3.0

核实日期：2026-08-03。核实方式：git clone（github.com 直连）+ curl 抓取 learn.microsoft.com 页面（环境限制：WebSearch/WebFetch 不可用，raw.githubusercontent.com 被封）。

## 1. awesome-copilot 仓库核实

仓库：https://github.com/github/awesome-copilot（main 分支，2026-08-03 克隆）

### a. 文件存在性与全名
- 文件存在：`instructions/power-apps-canvas-yaml.instructions.md`
- 本地副本：`D:/claude/power-platform/research/repos/awesome-copilot/instructions/power-apps-canvas-yaml.instructions.md`
- 已复制到 `D:/claude/power-platform/research/assets/power-apps-canvas-yaml.instructions.md` 备用。
- 同目录还有相关文件：`power-apps-code-apps.instructions.md`、`pcf-canvas-apps.instructions.md`、`power-platform-connector.instructions.md`、`power-platform-mcp-development.instructions.md`、`dataverse-python-pandas-integration.instructions.md`。

### b. 内容核实
- frontmatter：`description: 'Comprehensive guide ... based on Microsoft Power Apps YAML schema v3.0...'`，`applyTo: '**/*.{yaml,yml,md,pa.yaml}'`。
- 篇幅：827 行 / 约 22 KB（22,019 字节）。
- 明确基于 schema v3.0，第 11 行写明官方 schema 源：`https://raw.githubusercontent.com/microsoft/PowerApps-Tooling/refs/heads/master/schemas/pa-yaml/v3.0/pa.schema.yaml`（此 URL 与微软官方文档中给出的链接逐字一致，见第 3 节）。
- 涵盖主题：Power Fx 设计原则；根结构（App/Screens/ComponentDefinitions/DataSources/EditorState 五个顶层节点，与 pa.schema.yaml v3.0 的 properties 完全一致）；控件定义格式（Control/Variant/Group/Children/IsLocked 等）；控件版本 `@` 操作符（如 `Button@2.1.0`）；标准控件清单；容器/画廊/表单控件；自定义组件（DefinitionType: CanvasComponent、CustomProperties、PropertyKind Input/Output/InputFunction 等）；数据源（Type: Table / Actions、ConnectorId）；EditorState（ScreensOrder）；Power Fx 公式语法（`=` 前缀、null 值）；z-index 排序规则；命名规范与验证规则（含控件 ID 正则 `^([A-Z][a-zA-Z0-9]*/)?[A-Z][a-zA-Z0-9]*(@\d+\.\d+\.\d+)?$`）；源码管理（pac canvas download、.msapp 解包、Dataverse Git 集成）；schema 版本演进（fx.yaml 实验格式已停止开发、早期 preview、pa.yaml 当前格式）；大量 Power Fx 函数示例与性能/委托建议。
- 细节抽查与官方 schema 比对一致：顶层五节点、`Control` 属性、EditorState.ScreensOrder、DataSources 映射结构均与 `schemas/pa-yaml/v3.0/pa.schema.yaml`（584 行）吻合。
- 与官方文档一致但需注意的两点：
  - 文件写 `\src\Component\[ComponentName].pa.yaml`，官方 learn 文档写 `\Component` 文件夹（在 `\src` 内）。schema 本身不规定目录，仅规定单文件逻辑结构。
  - 文件明确写明 ".pa.yaml files are read-only and for review purposes only; External editing, merging, and conflict resolution isn't supported"——这与官方旧版文档一致，但官方文档 2025-10 更新后改为"仅 Power Platform Git Integration 支持外部编辑/合并"（见下）。

### c. 能否直接作为 agent 格式说明书
- 可以。它就是为 Copilot instruction 设计的格式规范（applyTo 匹配 *.pa.yaml），结构完整、示例丰富、含验证规则与常见错误。注意事项：(1) 它引用 raw.githubusercontent.com 作为 schema 源，受限网络下应改用本地克隆的 `PowerApps-Tooling/schemas/pa-yaml/v3.0/pa.schema.yaml`；(2) 个别表述滞后于最新官方文档（pa.yaml 可编辑性已随 Git Integration 放开）。

### d. LICENSE
- MIT License（Copyright GitHub, Inc.）。复制/改写进知识库无许可证障碍，建议保留出处声明。

## 2. pa.yaml 源码格式关键事实核实

### e. .pa.yaml 是唯一活跃 schema（v3.0），fx.yaml 与 Code View 格式已退役 —— 属实
官方文档《View source code files for canvas apps》（https://learn.microsoft.com/en-us/power-apps/maker/canvas-apps/power-apps-yaml ，最后更新 2025-10-23）原文：
> "Currently, the only active schema version of Power Apps source code is Source Code (*.pa.yaml)."
表格：Experimental（*.fx.yaml）"Retired...no longer in development"；Early preview（Code view/copy-paste）"Retired...no longer in use"；Source code（*.pa.yaml）"Active. Includes enhancements and version details for source control."

### f. pa.schema.yaml 静态 schema 文件存在与位置 —— 属实
- 官方文档原文："The current static schema for *.pa.yaml files is available here."，href 指向 `https://raw.githubusercontent.com/microsoft/PowerApps-Tooling/refs/heads/master/schemas/pa-yaml/v3.0/pa.schema.yaml`。
- 已克隆 github.com/microsoft/PowerApps-Tooling 核实文件真实存在：`schemas/pa-yaml/v3.0/pa.schema.yaml`（584 行，JSON Schema draft-07，`$id: http://powerapps.com/schemas/pa-yaml/v3.0/pa.schema`，顶层 properties 为 App/Screens/ComponentDefinitions/DataSources/EditorState）。schemas/pa-yaml/ 下只有 v3.0 一个版本目录。
- 本地路径：`D:/claude/power-platform/research/repos/PowerApps-Tooling/schemas/pa-yaml/v3.0/pa.schema.yaml`。

### g. unpack 产物目录结构 —— 部分需修正
官方文档（power-apps-yaml 页）对现代 .msapp 解包后 `\Src` 的描述：
> "App.pa.yaml: Represents the App. [screen Name].pa.yaml: One file for each screen... \Component: A folder containing one file for each component..."
并强调 "Only files located in the \Src directory of the extracted .msapp are intended for use with source control. The JSON files in the .msapp shouldn't be used as source code..."

而 `DataSources/*.json`、`Connections/*.json`、entropy 等目录出自 **pac canvas unpack 旧文档**（https://learn.microsoft.com/en-us/power-platform/developer/cli/reference/canvas ，该页顶部已标注 pack/unpack deprecated）：`\src`（*.fx.yaml + CanvasManifest.json + control json + EditorState）、`\DataSources`、`\Connections`、`\Assets`、`\pkgs`、`\other`（含 entropy.json）。
注意差异：旧 pac 文档写的是 `\other\entropy.json`（不是顶层 `\Entropy\` 目录；PASopa 时代曾有 \Entropy 目录的说法），且这些目录对应的是 **fx.yaml 实验格式** 的 unpack 产物，不是 pa.yaml 时代推荐的源码布局。结论：用户论断中的目录清单基本真实存在，但属于已弃用的 pac canvas unpack 布局；pa.yaml 时代官方只承认 .msapp 内 `\Src` 下的 *.pa.yaml 为源码。

### h. Power Fx 公式在 YAML 中的表达 —— 属实（细节来自官方语法文档）
来源：microsoft/PowerApps-Tooling `docs/YAMLFileFormat.md`：
- 单行公式形式：*Name* `:` `SPACE` `=` *Expression*，"The space between the colon and the equals sign is required to be YAML compliant. The equals sign disrupts YAML's normal interpretation..."。
- 单行公式中不允许出现 `#` 和 `:`（即使在字符串内），否则必须改用多行公式；不支持 YAML 单引号转义和反斜杠转义。
- 多行公式用 YAML 块标量 `|`/`|+`/|-，首行须以 `=` 开头；导入时接受所有多行标量形式（如 `>+`），但工具只产生 `|`/`|+`/|-。
- YAML 的 `#` 注释不保留，公式内注释用 Power Fx 的 `//` 和 `/* */`。
- 区域文化：核实到的来源中没有明确章节讲 locale 序列化；间接证据是 KnownIssues.md 中的 `InvariantScript`（msapp 内部以区域无关格式存储公式脚本）及 pa.schema.yaml 中控件类型为 "invariant identifier"。论断"invariant/en-US 序列化"方向正确但在本次可及来源中无逐字官方表述，建议报告中标为"间接证实"。

### i. pac canvas unpack vs pac solution unpack；--processCanvasApps —— 属实（均已弃用/移除）
- pac canvas 参考页顶部醒目提示："The pack and unpack commands are deprecated. To source control your canvas app, use the Power Platform Git Integration."（pac canvas create 仍 GA；pack/unpack 为 Preview 且 deprecated）。
- pac canvas unpack 的 `--layout` 参数："'Experimental' layout is deprecated...Use 'SourceCode' layout"，即 unpack 支持 Experimental（fx.yaml）与 SourceCode（pa.yaml）两种布局。
- microsoft/PowerApps-Tooling README 顶部公告："This repo contains the legacy PASopa tool to unpack a .msapp and is no longer supported. The `pac solution` command with the `--processCanvasApps` parameter also uses this tool and will be deprecated."
- 2026-08-03 抓取的 pac solution 参考页（https://learn.microsoft.com/en-us/power-platform/developer/cli/reference/solution）全文已无 `--processCanvasApps` 参数，unpack 仅解出 XML 目录结构（canvas apps 以 .msapp 二进制存于 `canvasapps/` 目录）。即该参数已从文档移除，处于"已弃用并下线"状态。
- 差异总结：pac canvas unpack 处理单个 .msapp → 源文件目录；pac solution unpack 处理 solution zip → XML 组件目录（canvas app 保持 .msapp 原样，不再展开）；官方推荐的替代路径是 Power Platform Git Integration。

## 3. 产物清单
- 核实报告：`D:/claude/power-platform/research/verify-awesome-copilot-payaml.md`
- instruction 文件副本：`D:/claude/power-platform/research/assets/power-apps-canvas-yaml.instructions.md`
- 仓库克隆：`D:/claude/power-platform/research/repos/awesome-copilot`（sparse: instructions + LICENSE）、`D:/claude/power-platform/research/repos/PowerApps-Tooling`（sparse: schemas + docs + README）
- 官方文档文本快照：`D:/claude/power-platform/research/tmp/pa-yaml-doc.txt`、`pac-canvas.txt`、`pac-solution.txt`
