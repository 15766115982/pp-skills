# 深挖报告：微软 CAT `dataverse-webapi-query` skill — 可复用知识提取

来源文件（本地，已完整通读，全文 124 行 / 12.7KB）：
`D:/claude/power-platform/research/repos/power-cat-skills/plugins/powercat-dataverse/skills/dataverse-webapi-query/dataverse-webapi-query.md`

仓库许可证：**MIT License (Microsoft Corporation)** — 位于 `D:/claude/power-platform/research/repos/power-cat-skills/LICENSE`，可直接提取/改写，需保留版权声明。

重要事实：该 skill 目录下**只有这一个 .md 文件，没有 references/ 子目录**。它正文中引用的 8 个 references 文件在发布仓库中全部缺失（详见 §3）。

---

## 1. 完整工作流骨架（Step 1–6 + Step 3.5）

| 步骤 | 名称 | 核心动作 |
|---|---|---|
| Step 1 | Understand what's being asked | 识别三要素：primary table / operation（retrieve multiple、by ID、count、aggregate、related）/ constraints（列、过滤、排序、expand、分页）。若输入是 FetchXML 则先解析 |
| Step 2 | Resolve schema (do not skip) | 三级 schema 解析（见 §1a），**禁止猜 logical name** |
| Step 3 | Build the query | OData 语法要点（见 §1b），聚合走 FetchXML fallback |
| Step 3.5 | Identify the target hosting context | 五宿主适配（见 §1d），"build the OData query first, then drop it into the host pattern" |
| Step 4 | Pick the output format | 按用户信号匹配输出形态：单行 URL / URL+解释 / 工具内 snippet / 调试对照 / FetchXML 并排对照。"Don't dump every possible snippet language; pick one." |
| Step 5 | Note the headers | 直接调 API 时给出 6 个头（见 §1e 下方）；随口问 URL 则省略 |
| Step 6 | Help the user test it (without touching their token) | 不接触 token 的测试引导（见 §1f） |

外加一节 **Behavioral guardrails**（6 条行为护栏，见 §4 可提取清单）。

### 1a. "schema 优先解析"防猜名的具体做法（Step 2，核心价值点）

原文原则：**"Don't skip schema resolution — guessing names is the single most common reason Web API queries fail."** 以及 **"Never invent a logical name. If you're not sure whether it's `account.name` or `account.accountname`, say so and resolve it before building the query."**

问题定义：用户给的往往是显示名（"Account Name"、"Primary Contact"），Web API 需要全小写 logical name（`name`、`primarycontactid`）。

三级解析顺序（有明确 fallback 链）：

1. **Dataverse MCP server (preferred)** — 先检查可用工具，找 `dataverse-*` / `power-platform-*` / `dynamics-*` 这类暴露 EntityDefinitions 或表列举能力的工具，用它确认：entity logical name + **entity set name（复数，如 `accounts`、`new_projects`）**、属性 logical name 及类型（lookup/choice/datetime）、关系/导航属性名（供 `$expand`）。
2. **EntityDefinitions endpoint** — 无 MCP 时，向用户要 org URL（"What's your Dataverse environment URL? (e.g., https://contoso.crm.dynamics.com)"），构造 EntityDefinitions 调用**让用户自己跑**来确认名字。具体 URL 模板在被引用的 `references/metadata-discovery.md` 中（**该文件缺失**）。
3. **Ask the user directly** — 最后手段。告诉用户去哪查：make.powerapps.com → Tables → 表 → "Properties" 面板同时显示 logical name 和 entity set name。

### 1b. OData 语法知识（Step 3 正文内嵌的 8 条 "Key reminders"）

正文直接给出的（可提取）：

1. **Entity set name 复数全小写**：`/api/data/v9.2/accounts`，不是 `/Account` 或 `/accounts(...)/Account`。
2. **版本默认 v9.2**，除非用户指定。
3. **Lookup 列两种形态**：读 GUID 用 `_primarycontactid_value`（可带 formatted-value 注解）；`primarycontactid` 是导航属性，**只用于 `$expand`，不进 `$select`**。
4. **Choice (OptionSet) 列**：`$select` 只回整数；要 label 需加请求头 `Prefer: odata.include-annotations="OData.Community.Display.V1.FormattedValue"`（或 `"*"`）。
5. **GUID 过滤不加引号**：`$filter=_primarycontactid_value eq 00000000-0000-0000-0000-000000000000`。
6. **字符串单引号，内部引号双写转义**：`name eq 'O''Brien'`。
7. **日期 ISO 8601 不加引号**：`createdon ge 2025-01-01T00:00:00Z`。
8. **纯 OData 无 GroupBy/聚合**：SUM/AVG/COUNT-by-group 回退到 FetchXML，通过实体集上的 `?fetchXml=` 参数传递（细节在缺失的 `references/aggregation.md`）。

正文未展开、留给缺失 references 的：`$expand` 的嵌套写法、`$count`、分页 cookie、lambda 运算符 `any`/`all`（声明在 `references/webapi-syntax.md`）。

大小写纪律（guardrail）：**"Casing matters. Logical names are lowercase; entity set names are lowercase plural. Don't camelCase or PascalCase anything in the URL."**

### 1c. FetchXML → Web API 映射规则

**正文里只有一行**（Step 1 末尾）：

> `<entity name="...">` is the primary table, `<attribute name="...">` are columns for `$select`, `<filter>` becomes `$filter`, `<link-entity>` becomes `$expand`, `<order>` becomes `$orderby`.

加上 guardrail 中的一条警示：

> "When converting FetchXML, flag what doesn't translate. Aggregations, more than one level of nested link-entity, and certain late-bound link types need explicit workarounds — call them out, don't silently drop them."

逐元素翻译表、不可转换案例（聚合、多层 join）的处理方式，全部声明在 `references/fetchxml-mapping.md` —— **该文件缺失**，正文实际只给了 5 条映射 + 3 类不可转换情形的一句话警告。这是我们自研 skill 必须自己补齐的最大空洞。

### 1d. 多宿主形态适配（Step 3.5，正文完整给出，可直接提取）

关键架构观：**"In every code-bearing case, the logical names, `_lookup_value` filter columns, formatted-value annotations, and `@odata.bind` write syntax are identical to the Web API. Only the calling object changes."** —— 先构造 OData 查询，再套宿主壳。

| 宿主 | 调用模式 |
|---|---|
| Model-driven **Generative Page**（单文件 React 17 + TS，Fluent UI v9，`pac model genpage` 上传） | `props.dataApi.queryTable("<logical>", { select, filter, orderBy, pageSize })`；logical name 单数小写；lookup 显示名取自 `_<lookup>_value` 列上的 `@OData.Community.Display.V1.FormattedValue` 注解，**绝不直接 select `…name` 注解列** |
| **Power Apps Code App**（全栈 React/Vue SPA，`@microsoft/power-apps`） | 自动生成的 `<Pluralized>Service.getAll({ select, filter, orderBy, top })`；lookup 解析用逐个 `Service.get()` 调用而**不用 `$expand`**；写操作用 `@odata.bind` |
| Model-driven form / ribbon / web-resource JS | `Xrm.WebApi.retrieveMultipleRecords("<logical>", "?$select=…&$filter=…", maxPageSize)`；**无需 token** |
| Canvas app / Power Automate | **不翻译成 OData URL**；用 Power Fx `Filter()` 或 Dataverse 连接器 "List rows" action，把同样的 `$filter`/`$select`/`$orderby` 字符串填进连接器字段 |
| 其他（curl、Postman、.NET、Node fetch） | 裸 Web API URL + bearer token |

触发词：用户提到 Power Apps、generative page、`.tsx` 文件、Code App、`Xrm.WebApi`、canvas app、Power Automate 时走本步。

### 1e. 错误诊断决策树（正文较薄，依赖缺失文件）

正文明确给出的诊断只有：

- **401** → "your token expired (~60 min lifetime), re-acquire it."（几乎总是这个）
- **403** → security role 问题，不是查询问题。
- **400/404** → 点名两类典型报错文案：`"Could not find a property named..."` 和 `"Resource not found for the segment..."`，但**具体含义表在缺失的 `references/common-errors.md`**。

Step 5 的 6 个请求头（正文完整给出，可提取）：

```
Accept: application/json
OData-MaxVersion: 4.0
OData-Version: 4.0
Prefer: odata.include-annotations="*"            # formatted values / lookup labels
Prefer: odata.maxpagesize=500                    # 大结果集分页
If-None-Match: null                              # retrieve 时绕过 etag 缓存
```

### 1f. "不接触 token" 纪律的具体实现（Step 6）

纪律声明：**"The skill does not accept, store, transmit, or ask for the bearer token itself. The user runs the request on their own machine."**

按用户上下文分流到 5 条获取路径：

1. 有 Azure CLI 的开发环境 → `az account get-access-token` 一行命令（最快）。
2. 想要 UI 反复测试 → Postman + 公共 PowerApps client ID 走 device code flow。
3. 已在浏览器登录 make.powerapps.com → DevTools console 里 `fetch`，用会话 cookie，**无需 token**。
4. 要做进 Power Automate flow → Dataverse 连接器 "List rows"，完全无 token。
5. 生产应用集成 → MSAL + 自己的 app registration。

明确的 ✅/❌ 清单（原文，可直接提取）：

- ✅ 解释多种 token 获取流程；提供 ready-to-run 的 curl / Invoke-RestMethod / fetch / Postman 配置让用户自己执行；帮助解读返回的响应或错误。
- ❌ 让用户把 token 贴进聊天；把 token 存进内存/文件/工具调用；代表用户用其凭据调用其租户。

护栏还规定：若用户已粘贴 token，不回显、不保存，温和重定向到自行执行，并建议吊销/轮换（Entra ID → sign-ins，或等 ~60 分钟自然过期）。

---

## 2. 8 个 references 文件缺失确认

在 `power-cat-skills` 全库（含所有 plugins、shared、Common、docs）和 `power-platform-skills` 全库做了文件名 find + 内容 grep 双重搜索：

| 引用文件 | 状态 | 备注 |
|---|---|---|
| references/webapi-syntax.md | **缺失** | 全库无同名/相似文件 |
| references/metadata-discovery.md | **缺失** | 无替代品 |
| references/aggregation.md | **缺失** | 无替代品 |
| references/fetchxml-mapping.md | **缺失** | 无替代品（本地各库均无 fetchxml 主题文件） |
| references/common-errors.md | **缺失** | 无替代品 |
| references/authentication.md | **缺失** | 相似品：`power-platform-skills/plugins/code-apps/skills/add-dataverse/references/api-authentication-reference.md`（5.5KB，Code App 视角）；`power-pages/skills/setup-auth/references/authentication-reference.md`（Power Pages 视角）；`awesome-copilot/instructions/dataverse-python-authentication-security.instructions.md`（Python 视角）。均非 Web API 测试流程替代品 |
| references/examples.md | **缺失** | 无替代品 |
| references/power-apps-contexts.md | **缺失** | 部分内容散见于 `power-platform-skills` 的 `code-apps/skills/add-dataverse/references/dataverse-reference.md`（13.4KB，覆盖 FormattedValue 注解、`_fieldname_value` 读取、`@odata.bind` 写、`lookuplogicalname`/`associatednavigationproperty` 注解）和 `mobile-apps/skills/add-dataverse/references/dataverse-reference.md` |

结论：**8/8 全部缺失**。`dataverse-webapi-query` 目录下确认只有 `dataverse-webapi-query.md` 一个文件。最接近的替代知识源是 `power-platform-skills/plugins/code-apps/skills/add-dataverse/references/dataverse-reference.md`（FormattedValue、lookup `_value`、`@odata.bind` 部分有实质覆盖），但 OData 完整运算符表、FetchXML 映射表、错误码表、聚合 fallback、token 获取流程这五块在本地两库均无现成替代，需要自研时自行补齐。

## 3. 同仓库其他 Dataverse 相关 skill

- **`powercat-canvas-apps/skills/migrate-to-dataverse/SKILL.md`**（作者 Rui Santos）：方向相反——不是查询 Dataverse，而是把 Canvas App `.pa.yaml` 里的 Power Fx 数据源调用（`Filter`/`Patch`/`LookUp`/`Collect` 等）迁移为 Dataverse 表调用。工作流：`sync_canvas` MCP 同步 → `list_data_sources` + `get_data_source_schema` 拿 schema → 读全部 `.pa.yaml` → 产出列映射表请用户审批 → 替换公式 → `compile_canvas` 验证。与 webapi-query 的关系：**互补的 schema 消费者**——两者都强调"先拿权威 schema 再动手"（它用 `get_data_source_schema`，webapi-query 用 MCP/EntityDefinitions），且它依赖的 `${CLAUDE_PLUGIN_ROOT}/references/TechnicalGuide.md` 同样缺失。它的"映射计划→用户审批→再执行"两段式交互模式值得借鉴。
- 其余 plugin（admin-digest、adoption、governance、overflow、overpage、procode-eval、code-apps/design-guide）与 Dataverse 查询无直接关系。`powercat-dataverse/skills/powercat-storytelling` 是叙事 skill，无关。

## 4. 融入自研 dv-query skill 的建议

### 可直接提取的段落（MIT，注明出处）

1. **Step 2 三级 schema 解析框架**（MCP → EntityDefinitions → 问用户 + "Never invent a logical name"）——把第一级从 "Dataverse MCP server" 改写成 "本地 kb 元数据缓存"。
2. **Step 3 的 8 条 OData Key reminders**（§1b 全表）——事实性 API 知识，原样可用。
3. **Step 3.5 五宿主适配表**（§1d 全表 + "build the OData query first, then drop it into the host pattern"）——正文中唯一完整自包含的 references 级内容。
4. **Step 4 输出格式匹配表**（5 种用户信号 → 5 种输出形态）。
5. **Step 5 的 6 个请求头代码块**。
6. **Step 6 的 token 纪律**（✅/❌ 清单 + 5 条获取路径 + 粘贴 token 后的吊销建议）——安全行为设计直接可用。
7. **Behavioral guardrails 全部 6 条**。

### 需结合"本地 kb 优先"架构改写的部分

- **Step 2 优先级重排**：我们架构是"本地 kb（pp-kb-builder 产出的 metadata/schema 缓存）→ EntityDefinitions 在线查询 → 问用户"。MCP 那级替换为本地 kb 查询，且本地命中时无需 org URL。
- **references 用本地 kb 文件替代**：8 个缺失文件恰好是我们 kb 的内容规划清单——`webapi-syntax`、`fetchxml-mapping`、`common-errors`、`aggregation`、`metadata-discovery` 五个可由我们的 MS Learn API 调研管线本地生成；`authentication`、`examples`、`power-apps-contexts` 三个可部分从 power-platform-skills 的 add-dataverse references 抽取改写。
- **FetchXML 映射表必须自建**：CAT 正文只给 5 条映射 + 一句话警告，详细表缺失；这是我们 kb 的差异化补强项（本地有 Power-Fx、Dataverse-skills 等仓库可交叉取材）。
- **错误决策树需扩写**：CAT 正文只有 401/403 两条结论 + 两个 400/404 报错文案，我们应把 `"Could not find a property named"`（→ logical name 错/大小写错）、`"Resource not found for the segment"`（→ entity set name 错，复数/拼写）与 Step 2 的 schema 解析联动成闭环：报错 → 回查本地 kb → 修正名字。
- **宿主适配的范围裁剪**：CAT 覆盖 5 宿主；我们初期可只做 raw HTTP/curl + Xrm.WebApi + 连接器三种，genpage/code-app 两种待本地 kb 有对应内容再接入。
