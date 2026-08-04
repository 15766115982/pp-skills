# 核实报告：microsoft/power-platform-skills 仓库

- 核实日期：2026-08-03
- 方法：`git clone --depth 1 https://github.com/microsoft/power-platform-skills.git`（成功，github.com 直连可 clone）
- 本地路径：`D:/claude/power-platform/research/repos/power-platform-skills`
- 最新 commit：`c8455ac` — 2026-07-30 07:12:20 -0700，"docs: correct stale "Stop hook" wording for skill validators (#334)"

## 仓库概况

官方 Microsoft 出品的 Claude Code / GitHub Copilot CLI 插件市场（plugin marketplace），包含 7 个插件：

| 插件 | 说明 |
|---|---|
| power-pages | Power Pages Code Sites（React/Angular/Vue/Astro SPA） |
| model-apps | Model-driven apps 的 generative pages（React+TS+Fluent，pac CLI 部署） |
| mcp-apps | MCP App widgets 生成器 |
| code-apps | Power Apps code apps（React+Vite+TS，pac CLI 部署） |
| mobile-apps | 移动 code apps（Expo+React Native，Power Apps Wrap） |
| canvas-apps | Canvas Apps 创作（Canvas Authoring MCP） |
| power-automate | Power Automate 云端流（FlowAgent MCP server） |

README 原文：「This repository is a **plugin marketplace** containing Claude Code/GitHub Copilot plugins for Power Platform services.」

---

## 逐条论断核实

### a. 存在 canvas-apps 相关 skill/插件 —— 属实

证据：`plugins/canvas-apps/` 目录存在，含 4 个 skill：
- `skills/canvas-app/SKILL.md`（407 行，统一 skill，自动识别创建/编辑模式）
- `skills/configure-canvas-mcp/SKILL.md`（107 行）
- `skills/add-data-source/SKILL.md`（68 行）
- `skills/report-issue/SKILL.md`

另有 2 个 agent：`agents/canvas-app-planner.md`（206 行）、`agents/canvas-screen-builder.md`（155 行）。
`plugins/canvas-apps/.plugin/plugin.json`：name=canvas-apps, version=2.2.2, license=MIT。

### b. Canvas Authoring MCP 及工具清单 —— 属实（且工具比论断中列的更多）

`plugins/canvas-apps/.mcp.json` 原文：

```json
"canvas-authoring": {
  "command": "dnx",
  "args": ["Microsoft.PowerApps.CanvasAuthoring.McpServer", "--yes", "--prerelease",
           "--source", "https://api.nuget.org/v3/index.json"]
}
```

即 MCP server 本体不在仓库内，是通过 `dnx`（.NET 10 的 dotnet 工具执行器）从 nuget.org 拉取的 NuGet 包 `Microsoft.PowerApps.CanvasAuthoring.McpServer`（prerelease 版）。

`plugins/canvas-apps/AGENTS.md` "MCP Tools" 表列出 9 个工具（论断中的 4 个全部在内）：
- `connect`（必须先调用，连接 coauthoring 会话）
- `compile_canvas`、`describe_api`、`describe_control`、`get_data_source_schema`
- `list_apis`、`list_controls`、`list_data_sources`、`sync_canvas`

### c. references/ 下的 agent 格式文档 —— 属实

`plugins/canvas-apps/references/` 实际有 4 个文档（比论断多一个 PlanTemplates.md）：

| 文件 | 行数 | 字节 |
|---|---|---|
| TechnicalGuide.md | 444 | 15,130 |
| DesignGuide.md | 151 | 10,482 |
| QAChecks.md | 253 | 9,366 |
| PlanTemplates.md | 184 | 6,123 |

AGENTS.md 描述：「TechnicalGuide.md ← YAML syntax, control selection, layout strategies, Power Fx patterns；DesignGuide.md ← Aesthetic guidelines, anti-patterns, design process；QAChecks.md ← Runtime anti-pattern checks for self-QA；PlanTemplates.md ← CREATE and EDIT plan document structures for canvas-app-planner」

### d. 文档内容主题与篇幅 —— 属实

- TechnicalGuide.md（444 行）：标题 "Canvas App YAML Generation Guide"，章节含 File Structure、YAML Syntax Rules（含 YAML 陷阱，如 `Label: something` 被解析为嵌套 mapping）、Control Type Selection、Common Property Patterns、Power Fx Formula Patterns（Set()/If/布尔表达式等）。强制要求「Run `list_controls` FIRST — this is non-optional」。
- DesignGuide.md（151 行）：美学指南，明确以「avoid generic "AI slop" aesthetics」为目标，要求先选定大胆的设计方向（brutally minimal / maximalist / retro-futuristic 等），并给出 ModernCard/Avatar/Badge 等现代控件的设计词汇表。
- QAChecks.md（253 行）：「runtime layout issues that `compile_canvas` does NOT catch」，agent 写 YAML 后必须自检并就地修复（如 scrollable container 永不滚动、透明 overlay 按钮把兄弟控件压成零高度）。
- PlanTemplates.md（184 行）：planner agent 的 CREATE/EDIT 计划文档模板。

### e. LICENSE —— 属实（MIT）

`LICENSE` 首行：「MIT License / Copyright (c) Microsoft Corporation.」README 末尾亦注明 MIT。各 plugin.json 均标 `"license": "MIT"`。

### f. 已知限制（512KB / 组件库 / PCF / PowerBIIntegration）—— 不属实（仓库内无记录）

在仓库全部 markdown 中搜索 `512KB`、`512 KB`、`PCF`、`PowerBIIntegration`、`component library`、`known limitation`、`not supported`：
- canvas-apps 插件内**无任何**关于 compile_canvas 512KB 上限、sync_canvas 遗漏组件库/Components、PCF 控件或 PowerBIIntegration 不支持的记录。
- 仅有的 PCF 命中在 mobile-apps 插件（"Do not use HostingSDK / PCF path"，是另一语境）和 `plugins/mobile-apps/skills/design-system/references/canvas-app-extraction.md:94`（「`.msapp` uses PCF / code components → Skip those screens with notice」，属 mobile 设计系统提取工具的语境，非 canvas-apps MCP 的限制）。
- 仓库内的实际限制表述另有内容（见"意外发现"）。这些论断可能来自 GitHub Issues（受限网络无法访问）或其他来源，**仓库内文档无法证实**。

### g. 外部工具依赖 —— 部分属实（按插件不同而异）

- canvas-apps：**.NET 10 SDK**（必需，`dnx` 运行 NuGet 上的 MCP server；hooks 也用 `dotnet run --file` 执行 `hooks/inject-sync-reminder.cs`）。不需要 pac CLI、不需要 node。还需浏览器中保持 Power Apps Studio coauthoring 标签页打开。
- power-automate：**Node.js 18+ + Azure CLI（`az login`）**，MCP server 为仓库自带的 `server/mcp.mjs`（自包含，无需 npm install）。其 `.mcp.json` 还注册了 `microsoft-learn` HTTP MCP（`https://learn.microsoft.com/api/mcp`）。
- 其他插件（power-pages / model-apps / code-apps / mobile-apps）：依赖 **pac CLI**（安装器会自动安装）+ Node/npm。
- 根 `.claude/settings.json` allowlist 印证：`Bash(pac *)`, `Bash(node *)`, `Bash(dotnet *)`, `Bash(npx *)`, `Bash(powershell *)`。

### h. 活跃度 —— 属实（非常活跃）

`git log -1`：commit c8455ac，**2026-07-30**（核实日前 4 天），PR #334。仓库处于活跃开发中，canvas-apps 插件版本 2.2.2，configure-canvas-mcp skill 版本 2.1.0。

---

## 额外记录：flow / dataverse 可用素材

- **power-automate 插件**（独立于 canvas）：10 个 skill——setup、browse-flows、create-flow、build-flow（从描述自动生成完整流）、debug-flow、diagnose-flow、manage-flows、manage-desktop-flows、route-environments、report-issue。自带 FlowAgent MCP（`server/mcp.mjs`，源自 github.com/matow_microsoft/flow-agent），能力覆盖流的 CRUD/复制/发布/运行历史/循环迭代钻取/取消/重提/诊断/连接管理/桌面流。有 `references/` 目录。
- **code-apps/add-dataverse skill**：为 code app 添加 Dataverse 表（生成 TS models/services，可新建表），含 3 个参考文档：dataverse-reference.md（picklist/虚拟字段/lookup/文件图片列/表单模式）、api-authentication-reference.md、table-management-reference.md。
- code-apps 另有 add-sharepoint/add-office365/add-teams/add-onedrive/add-excel/add-connector 等连接器 skill。
- 仓库还有 `evals/`（评估）、`shared/`（含 telemetry）、`scripts/install.js`（一键安装器）。

## 意外发现（重要）

1. **canvas-apps 不依赖 pac CLI**——只依赖 .NET 10 SDK（`dnx` 拉 NuGet 包）+ 浏览器里开着的 Studio coauthoring 标签页；MCP server 本体是闭源 NuGet 包 `Microsoft.PowerApps.CanvasAuthoring.McpServer`（prerelease），仓库里只有插件壳（skills/agents/references/hooks），**没有 MCP server 源码**。
2. **必须保持 Studio 浏览器标签页打开**：MCP 通过 coauthoring 会话与 Power Apps 通信，关标签页即断会话，`compile_canvas`/`sync_canvas` 都会失效——这是架构性强约束（configure-canvas-mcp/SKILL.md 与 AGENTS.md 多处强调）。
3. **canvas-apps 插件标注为 Preview**（README 引用 Microsoft 预览版法律条款），issue 走 aka.ms/power-skills-canvas-issues 而非标准支持渠道。
4. 论断 f 的三条"已知限制"在仓库文档中**完全不存在**——如果方案需要引用这些限制，必须另找来源（GitHub Issues 或微软官方文档），不能引用该仓库。
