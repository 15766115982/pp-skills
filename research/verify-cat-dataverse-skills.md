# 事实核实：microsoft/power-cat-skills 与 microsoft/Dataverse-skills

核实日期：2026-08-03
方法：`git clone --depth 1` 浅克隆两仓库至 `D:/claude/power-platform/research/repos/`，直接阅读 README、AGENTS.md/CLAUDE.md、SKILL.md、LICENSE、marketplace/plugin manifest、docs。

两仓库均克隆成功，均为 microsoft org 下的真实官方仓库。

---

## 一、microsoft/power-cat-skills

仓库定位（README 第 3-5 行）：Power CAT（Customer Advisory Team）维护的 **plugin marketplace**，面向 **Microsoft Scout 和 GitHub Copilot CLI**（注意：不是 Claude Code），包含 9 个 plugin、十余个 skill。

### 论断 a：存在 analyze-canvas-performance skill，本质是"扫描 unpacked canvas app 源码做分析"

**结论：属实（有细微补充）。**

证据：
- 路径：`plugins/powercat-canvas-apps/skills/analyze-canvas-performance/SKILL.md`（67 KB，1014 行，单文件，无脚本）。
- AGENTS.md（plugins/powercat-canvas-apps/AGENTS.md）自述：`SKILL.md ← Do a code review of the p.yaml files based on best pratices for Canvas Apps`。
- SKILL.md 工作流：
  1. "CRITICAL: Sync the Canvas App First — call the `sync_canvas` MCP tool to ensure a local copy of the canvas app YAML is present"（unpack 到本地的 `.pa.yaml` 源码）。
  2. "Read every `.pa.yaml` file and build a structural inventory" —— 逐文件读 unpacked 源码，统计 screen/控件/数据源/变量/collections。
  3. 另有 20 个性能审计小节（OnStart 过载、delegation、N+1、ForAll/Patch、Concurrent、ECS、跨屏引用等）+ 编码规范 + 设计布局 + 错误处理 + 查询耗时估算，全部基于对 `.pa.yaml` 文本的静态分析。
  4. 同时调用 MCP 工具 `get_appchecker_errors`、`get_accessibility_errors` 补充 App Checker / 无障碍结果。
- 补充：产出物是 **HTML 报告**（第 8 节 "Generate HTML Report File"，内嵌完整 HTML 模板，文件名 `Performance & Quality Review.html`），不是 Markdown；且严格只读（"Never write, edit, create, or delete any `.yaml` or `.pa.yaml` file"），最后可选经用户批准后修改源码并 `compile_canvas` 验证。

### 论断 b：存在 dataverse-webapi-query skill（自然语言转 OData 参考）

**结论：属实。**

证据：
- 路径：`plugins/powercat-dataverse/skills/dataverse-webapi-query/dataverse-webapi-query.md`（12.7 KB 单文件；注意文件名不是 SKILL.md）。
- frontmatter description："Generate, translate, optimize, explain, and help test Microsoft Dataverse Web API (OData v4) queries …"。
- 正文列出的用途："Natural language → Web API"、"FetchXML → Web API"、面向 Generative Pages / Code Apps / Xrm.WebApi 的目标形态转换、400/404 错误诊断、指导用户自己获取 bearer token 实测（skill 本身不接触 token）。
- README 描述一致："natural language → OData URL, FetchXML conversion, multi-surface targeting … and error diagnosis"。

### 论断 c：LICENSE 类型

**结论：属实——MIT。**
`LICENSE` 文件首行 "MIT License / Copyright (c) Microsoft Corporation."；README 末尾 "licensed under the MIT license"；marketplace.json 每个 plugin 均标 `"license": "MIT"`。

### 论断 d：两个 skill 的实现方式

**结论：两者均为纯 prompt/instruction 型 skill（无随附脚本），但工具链依赖差别很大。**

- **analyze-canvas-performance**：单文件 SKILL.md（含内嵌 HTML 报告模板，近 500 行模板），skill 目录下无任何脚本。但运行依赖 **Canvas Authoring MCP server**（`sync_canvas`、`get_appchecker_errors`、`get_accessibility_errors`、`compile_canvas` 四个工具），README 前置条件要求 **.NET 10 SDK**（Canvas App skills 需要），且 Canvas Authoring MCP 需要 Power Apps Studio 浏览器标签页保持打开的 coauthoring 会话（AGENTS.md："The Power Apps Studio browser tab must remain open … closing it breaks compile_canvas and sync_canvas"）。载体是 Scout / Copilot CLI。
- **dataverse-webapi-query**：单文件纯知识型 prompt，无脚本、无强制工具链；schema 解析优先用 Dataverse MCP server（如有），否则让用户自己跑 EntityDefinitions URL 确认逻辑名；明确 "The skill never handles or stores the token"。
- **重要缺陷/发现**：两个 skill 都引用了 `references/` 下的文件（analyze-canvas-performance 引用 `${CLAUDE_PLUGIN_ROOT}/references/TechnicalGuide.md`；dataverse-webapi-query 引用 `references/webapi-syntax.md`、`references/metadata-discovery.md`、`references/aggregation.md`、`references/power-apps-contexts.md` 等十余处），但 **整个 power-cat-skills 仓库不存在任何 `references/` 目录**（`find -type d -name references` 无结果）。这些参考文档可能在配套的 `microsoft/power-platform-skills` 基础插件仓库中，或属于尚未提交的内容——直接克隆本仓库使用时这两个 skill 的引用文件会缺失。

---

## 二、microsoft/Dataverse-skills

仓库定位（README 第 5 行）：教 AI coding agent 驱动 Dataverse 的 plugin，8 个 skill：dv-connect / dv-query / dv-data / dv-metadata / dv-solution / dv-admin / dv-security / dv-overview。版本 1.10.0。

### 论断 e：封装了 Dataverse MCP / CLI / Python SDK，支持 Copilot / Claude / Codex / Cursor

**结论：属实（且比论断还多封装了 PAC CLI 和原生 Web API）。**

证据：
- README："teaches AI coding agents to drive the **Dataverse MCP server, Dataverse CLI, Python SDK, and PAC CLI**"。
- 四平台安装方式均在 README 中有独立小节：GitHub Copilot（`/plugin install dataverse@awesome-copilot`）、Claude Code（`/plugin install dataverse@claude-plugins-official`）、Codex（app + CLI，`codex plugin marketplace add microsoft/Dataverse-skills`）、Cursor（`/add-plugin dataverse`，已上架 cursor.com/marketplace）。
- 仓库内存在四套 manifest：`.claude-plugin/`、`.codex-plugin/`、`.cursor-plugin/`、`.github/plugin/`（CLAUDE.md 要求六个版本字段同步）。
- dv-connect 工具面选择规则（CLAUDE.md）：MCP tools（≤25 条简单读写）/ Dataverse CLI（headless CRUD + `dataverse api` 逃生口）/ Python SDK `DataverseClient`（批量、脚本化、分析）/ 原生 Web API urllib（最后手段）。

### 论断 f：环境要求（Managed Environment？管理员开启？Copilot Credits？）

**结论：部分属实——确实需要管理员动作，但仓库全文没有提到 Managed Environment，也没有提到 Copilot Credits。**

证据（`docs/safety-and-guardrails.md` 第 36-44 行）：
- MCP 通路有三层独立授权：
  1. **Developer auth**（开发者本人，首次后缓存）
  2. **Tenant admin consent**（Global Admin，每租户一次性）——"Can MCP clients be used in this tenant?"
  3. **Environment allowlist**（Environment Admin，每环境一次性）——"Can MCP clients be used in this specific environment?"
- 但注意：**仅 MCP 通路需要后两层**；"other tools used by the plugin (Python SDK, Web API, PAC CLI) authenticate directly and are not subject to these MCP-specific controls"。
- 环境本身要求很低（README Prerequisites）："A Microsoft Dataverse environment, available through Power Apps, Dynamics 365, or Power Platform plans, or via the **free Power Apps Developer Plan**"。
- dv-connect SKILL.md：GA 端点是 `{DATAVERSE_URL}/api/mcp`；`/api/mcp_preview` 为每环境 opt-in 的预览端点，403 属预期；dv-admin/references/orgdb-settings.md 提到 OrgDB 设置 `IsMCPPreviewEnabled`（"enable non-Copilot Studio MCP clients"）。
- 全仓库 grep "managed environment|copilot credit|billing|consumption|pay-as-you" 无任何命中 → 没有任何 Managed Environment 或 Copilot Credits/消息容量要求的说法。
- 本机工具链要求：Python 3、Node.js（Dataverse CLI npm 包 `@microsoft/dataverse`，兼作 MCP proxy）、.NET SDK（PAC CLI 需要）、PAC CLI、Azure CLI（环境发现兜底）、pip 包 `PowerPlatform-Dataverse-Client >=1.0.0`、pandas、msal 等。
- 权限模型：least-privilege，插件不能超越登录用户的 Dataverse 安全角色；schema 工作底线是 System Customizer，不引导 System Administrator。

### 论断 g：LICENSE 类型

**结论：属实——MIT。**
`LICENSE` 首行 "MIT License / Copyright (c) Microsoft Corporation."；README badge `[![License: MIT]]`；plugin.json `"license": "MIT"`。

### 论断 h：仓库活跃度

**结论：两仓库都活跃，Dataverse-skills 明显更活跃。**

- `git log -1`：
  - power-cat-skills：`2026-07-17 19:55:10 +0200  Update README.md`（约 2 周前）。
  - Dataverse-skills：`2026-07-29 20:25:59 +0530  feat: add ERP routing to dv-admin, dv-metadata, and dv-connect MCP setup (#91)`（4 天前，PR 编号已到 #91）。
- Dataverse-skills 还有严格工程化迹象：静态 eval 套件（`.github/evals/static_checks.py`）、版本号六字段同步检查、branch protection（2 名 maintainer 审批 + CodeQL + CLA）、语义化版本规则写入 CLAUDE.md。

---

## 三、对本方案（扫描资产 → 生成 Markdown 知识库）有直接复用价值的文件

### power-cat-skills（仓库根：`research/repos/power-cat-skills/`）

| 路径 | 复用价值 |
|---|---|
| `plugins/powercat-canvas-apps/skills/analyze-canvas-performance/SKILL.md` | 最重要资产：从 unpacked `.pa.yaml` 提取结构化清单（screen/控件/数据源/变量/Flow 调用）的 Discovery 流程 + 20 类性能 + 规范 + 设计 + 错误处理检查项，可直接改造为 canvas app 知识库的扫描维度与分类体系 |
| `plugins/powercat-dataverse/skills/dataverse-webapi-query/dataverse-webapi-query.md` | Dataverse Web API/OData 陷阱知识（大小写、lookup 注解、导航属性、formatted value），可作为知识库 Dataverse 章节的内容来源 |
| `plugins/powercat-overflow/skills/powercat-overflow/SKILL.md` | 现成的"解包 solution .zip → 枚举 Workflows/*.json → 逐 flow 评审 → 写 findings.json"流水线，与本方案"扫描资产"环节同构，可直接借用解包/枚举逻辑 |
| `Common/PowerCAT OverFlow/solution.findings.schema.json` | findings JSON 的正式 schema（含示例 `solution.findings.sample.json`、`StressTest100Flows_1_0_0_0.findings.json`），可作为知识库每条资产记录的数据结构参考 |
| `Common/PowerCAT OverFlow/sources.md` | Power Automate 编码规范的权威链接清单（overflow skill 把它当作唯一允许的引用源），可做知识库引用白名单 |
| `plugins/powercat-overpage/skills/powercat-overpage/SKILL.md` | Power Pages 站点六维（Security/Performance/A11y/Maintainability/Architecture/Reliability）评审维度，可扩展知识库到 Power Pages 资产 |
| `shared/skills/report-issue/` 与根 `AGENTS.md` | 跨插件共享 skill 的模板化模式（workflow 单写一次 + 每插件薄壳 SKILL.md），自己写 skill 库时可借鉴 |
| `Common/PowerCAT OverPage/app/src/parserSolution.js` | JS 版 solution 包解析器，可参考其解包逻辑 |

### Dataverse-skills（仓库根：`research/repos/Dataverse-skills/`）

| 路径 | 复用价值 |
|---|---|
| `CLAUDE.md` | 高质量 skill 写作规范：三级 token 预算（frontmatter ≤200 / body ≤5000 / references 不限）、"Wrong/Correct 反幻觉表"（实测 flag 幻觉率 58%→2.5%）、frontmatter description 写法、Skill boundaries 路由段——写自己的知识库生成 skill 时直接套用 |
| `.github/evals/static_checks.py` | skill 文件静态检查套件（代码正确性、auth 模式、路由一致性、版本同步），可改造为知识库/skill 产物的 CI 校验器 |
| `.github/plugins/dataverse/skills/dv-query/`（SKILL.md + references/） | Dataverse 查询知识（OData、分页、聚合、web-api-advanced.md），知识库 Dataverse 查询章节素材 |
| `.github/plugins/dataverse/skills/dv-metadata/`、`dv-solution/` | 元数据/solution 生命周期的权威操作清单，可用来定义"扫描哪些 Dataverse 资产"的范围 |
| `.github/plugins/dataverse/scripts/auth.py` | 带 User-Agent 插件归因的认证封装（get_client/get_plugin_headers），若知识库方案需要在线拉取环境元数据可复用 |
| `docs/safety-and-guardrails.md` | MCP 三层授权与 least-privilege 模型的简明表述，方案文档中"权限与安全"章节可直接引用 |

---

## 四、其他值得记录的事实

1. power-cat-skills 官方载体是 **Microsoft Scout（Frontier preview，需 M365 Copilot + Copilot Business/Enterprise）和 GitHub Copilot CLI**，不是 Claude Code——尽管目录结构是 `.claude-plugin/` 兼容格式。在我们的 Claude Code 环境里使用等于"借用内容"，不是官方支持路径。
2. power-cat-skills 依赖姊妹仓库 `microsoft/power-platform-skills`（foundation 插件，如 `canvas-apps@power-platform-skills`），部分 skill 的 references 很可能在那里——如需补齐 TechnicalGuide.md 等缺失引用，应克隆该仓库核实。
3. power-cat-skills 的 `Common/PowerCAT BVA/` 含有现成的治理方案包（`BusinessValue_1_1_0_1.zip`、PPT、DOCX 用户指南），与知识库方案无直接关系但属可复用资产。
