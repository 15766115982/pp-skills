# Dataverse 查询 Skill 调研（2026-08-04）

问题：是否存在现成的"Power Platform Dataverse 查询" skill 可复用？
方法：复用已克隆的一手仓库（Dataverse-skills、power-cat-skills、power-platform-skills、DanielKerridge 仓库存在性已确认）。

## 结论：有，而且有两个官方级候选，但都不能直接搬用

### 候选 1：Dataverse-skills 的 dv-query（微软官方，功能最强）

- 位置：`Dataverse-skills/.github/plugins/dataverse/skills/dv-query/`（SKILL.md + 4 个 references）
- 能力：读取路由表（按查询形态选工具）、T-SQL 子集（`?sql=` 参数，支持 JOIN/GROUP BY，≤5000 行）、$apply 聚合、FetchXML、QueryBuilder→DataFrame 导出、CLI 陷阱（自定义表复数化 404、Windows `&`/`$` 引号）
- **但执行层重**：核心路径依赖
  1. `PowerPlatform-Dataverse-Client` Python SDK（pip 包，v1.10.0）
  2. `dataverse` CLI + `pac` CLI（双认证面：dv-connect 要求 `dataverse auth who` 与 `pac org who` 同时就绪）
  3. 可选 Dataverse MCP server（需 admin consent + 环境 allowlist）
- 判定：**知识可参考，执行链不可搬**——与我们"仅 PyYAML + urllib 零额外依赖、SPN client_secret、走代理"的约束冲突。

### 候选 2：power-cat-skills 的 dataverse-webapi-query（微软 CAT，纯知识型）

- 位置：`plugins/powercat-dataverse/skills/dataverse-webapi-query/dataverse-webapi-query.md`（12.7KB 单文件）
- 能力：自然语言→OData URL、FetchXML→Web API 转换、多宿主形态适配（Xrm.WebApi / 连接器 / curl / Postman）、400/404 诊断、"绝不接触用户 token"纪律
- 优点：**零执行依赖**——只教 agent 怎么构造 URL，请求由用户自己跑（az cli/Postman/浏览器）
- **但**：引用的 8 个 `references/*.md`（webapi-syntax / metadata-discovery / aggregation / fetchxml-mapping / common-errors / authentication / examples / power-apps-contexts）**在该仓库内不存在**，本地两个姊妹仓库也未找到对应文件。直接搬用会缺引用。
- 判定：**最接近我们需求的形态，但材料不完整**；其单文件正文仍有不少可提取的知识（schema 优先解析、lookup `_value` 过滤列、formatted-value 注解等）。

### 候选 3：DanielKerridge/claude-code-power-platform-skills 的 dataverse-web-api

- 存在性已确认（default branch `master`），未克隆细查；定位是教 agent 通过 Web API **管理 schema**（更偏写操作）。

## 我们的增量空间

现有候选都是"通用 Dataverse 查询"，没有一个利用**本地已入库的元数据知识库**。我们的差异化设计：

| 特性 | 现有候选 | 我们可做 |
|---|---|---|
| schema 解析 | 每次现查 EntityDefinitions（或依赖 MCP） | **优先读本地 kb/dataverse/tables/*.md**（列名/类型/选项集/Lookup 目标全在），零网络、零猜名 |
| 执行 | SDK+CLI 全家桶 / 用户自己跑 | 复用 pp_common 的 token+代理+api_get（已测试） |
| 凭据 | az cli / 设备码 / Postman | 复用已配置的 SPN 环境变量，无人值守可用 |
| 只读纪律 | 各自表述 | pp_common 单一入口，天然只读（api_get 仅 GET） |

## 建议：新增 `dv-query` skill（轻量自研，吸收两者知识）

- `skills/dv-query/SKILL.md`：查询路由（按形态选 OData/SQL/FetchXML）、**schema 解析顺序 = 本地 kb → 实时 EntityDefinitions**、错误诊断表（401/403/404/400）
- `scripts/dv_query.py`：基于 pp_common 的查询执行器（GET only），支持 OData URL 段 / `?sql=` T-SQL / `$apply`，结果落 CSV/JSON
- references：从两个候选 skill 的正文提取 OData 语法陷阱、聚合写法、fetchxml 映射要点（MIT，注明出处）
- 依赖增量：**零**（沿用 urllib 方案；T-SQL 走 `?sql=` 参数无需 SDK）
