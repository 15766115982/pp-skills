# dv-query 深读报告：可复用知识提取

来源：`research/repos/Dataverse-skills/.github/plugins/dataverse/skills/`（微软官方 Dataverse skills 插件本地克隆）
范围：dv-query（SKILL.md + 4 个 references）、dv-overview、dv-connect（含 tools-setup.md）、dv-data/dv-metadata（边界确认）、scripts/auth.py。

---

## 1. 查询形态 → 工具选择路由表

### 1a. dv-query SKILL.md 的 "How to Answer Data Questions" 路由表（原文照抄）

| User asks... | Approach | Why |
|---|---|---|
| "show me open tickets" / simple filter | **MCP** `read_query` (if available) or `client.records.list(table, filter=...)` | Small result, no aggregation |
| "how many X" / simple count | **MCP** `read_query`, or `client.query.sql("SELECT COUNT(*) AS n FROM <table> WHERE ...")` | Server-side count (no row download) |
| Single-table aggregation (most/sum/avg/top-N) | **`$apply`** (raw) or **`client.query.sql()`** GROUP BY | Both run server-side, return only grouped results |
| Cross-table aggregation | **`client.query.sql("...INNER JOIN...GROUP BY...")`** or **`client.query.fetchxml(...)`** (server-side); else builder→DataFrame + `pd.merge()` | `sql()` supports INNER/LEFT JOIN + GROUP BY; pandas merge for shapes SQL can't express |
| "show me X with related Y" / resolve lookups | `client.records.list(table, expand=...)` or **QueryBuilder** | Lookup resolution |
| "export this data" / bulk extract | **`client.query.builder(t).select(...).execute().to_dataframe()`** | Direct to DataFrame → CSV |
| "load into notebook" / interactive analysis | 同上 | pandas native |
| "find duplicates" / complex filter | `client.records.list(table, filter=...)` or **QueryBuilder** | SDK handles pagination |
| Simple filtered read (<5K rows) | **`client.query.sql()`** | Lightweight SQL SELECT with WHERE, ORDER BY, TOP |

**关键理由翻译**：核心原则是 "Let the server do the work"（让服务端干活）。单表聚合用 `$apply` 或 SQL GROUP BY（服务端只回传分组结果，不下载行）；跨表优先服务端 SQL JOIN 或 FetchXML link-entity；SQL 表达不了的形态才拉到本地 pandas merge——merge 本身是亚秒级，瓶颈在网络传输，`select` 只取所需列可以把传输量降到 1/10–1/20。

### 1b. 表面层（surface）路由原则（dv-overview Hard Rule 2 + Tool Capabilities）

- MCP / Dataverse CLI / Python SDK / PAC CLI / Raw Web API 是**平级的能力面**，没有强制顺序，按形状选：
  - **MCP**：≤25 条/次的小读写、简单查询；不支持 forms/views/全局 OptionSet/N:N/备用键；SQL 子集更窄（不支持 DISTINCT/OFFSET/CTE）。
  - **Dataverse CLI**：无 Python 脚本的 headless 数据面 CRUD、`data associate`/`disassociate`（N:N `$ref`）、`data upload`、`api request`/`invoke`（托管逃生舱）。
  - **Python SDK**：批量、分页、分析、DataFrame。
  - **Raw Web API（urllib）**：**最后手段**，唯一合法理由 = "one attributed HTTP session across many rows inside a single Python process"（单进程内对成千上万行做带遥测标记的 HTTP 循环）。
- 体量指引：MCP ≤ ~25 条；SDK `CreateMultiple`（≥1000 起分块）；`$apply` 走 Web API。

---

## 2. T-SQL `?sql=` 参数能力边界

`client.query.sql()` 底层 = Web API 的 `?sql=` 查询参数，T-SQL 子集。

**支持**：`SELECT` / `SELECT DISTINCT` / `SELECT TOP N`（N 0–5000）、`INNER JOIN` / `LEFT JOIN`、`WHERE`、`GROUP BY`、`ORDER BY`、`OFFSET`/`FETCH`、`COUNT/SUM/AVG/MIN/MAX`。

**不支持**：`SELECT *`、子查询、CTE、`HAVING`、`UNION`、`RIGHT`/`FULL`/`CROSS JOIN`、`CASE`、字符串/日期/数学函数。

**行数上限**：结果**硬性截断在 ~5,000 行**（silently truncated——静默截断，不报错，大表上用它会得到不完整数据）。超过 5K 行必须改用分页迭代或 `$apply`。

**性能数字**：<5K 行的表上 ~2–6 秒返回，因单次 HTTP 调用，远快于分页迭代或 DataFrame 全拉。

**对比 MCP `read_query`**（更窄）：不支持 DISTINCT、HAVING、子查询、OFFSET、UNION、CASE/IF、CAST/CONVERT、CTE、日期函数；但允许 JOIN + GROUP BY。

配套：`client.query.sql_columns(table)` 列出 SQL 端点真实可查的列（排除虚拟/计算/lookup 显示列），每项含 `name/type/is_pk/is_name/label`。

---

## 3. OData 层关键知识

### 3a. `$apply` 聚合写法（SDK 不支持，只能 raw Web API 或 FetchXML 替代）

```
GET /api/data/v9.2/{entitySet}?$apply={expression}
```

常见模式（原文表）：

| User question | $apply expression |
|---|---|
| "total sales by status" | `groupby((statuscode),aggregate(amount with sum as total))` |
| "which account has the most revenue" | `groupby((_parentaccountid_value),aggregate(estimatedvalue with sum as total))` 然后客户端排序 |
| "how many records per category" | `groupby((category),aggregate($count as count))` |
| "average deal size by region" | `groupby((region),aggregate(amount with average as avg))` |

复合聚合示例：`groupby((statuscode),aggregate($count as count,estimatedvalue with sum as total_value))`

**限制**：源记录 50,000 条/次聚合上限；**只在单实体集内有效**（不能跨表）。跨表聚合 → SQL JOIN / FetchXML link-entity / 本地 pandas merge。

### 3b. N:N `$expand`

```
GET /<entitySet>?$expand=<n:n_nav>($select=...)
```

例：`$expand=new_ticket_kbarticle($select=new_title)`。单页限制 ~5,000 条；超过要跟 `@odata.nextLink`。N:N 写入走 `POST .../<nav-property>/$ref`（CLI: `dataverse data associate`）。

### 3c. 分页

- 服务端页大小默认/最大 5,000 行/页；翻页靠响应里的 `@odata.nextLink` 循环。
- SDK 侧抽象：`records.list()`（全收，flat）、`records.list_pages(page_size=N)`（流式逐页）、`query.execute_pages()`（FetchXML/builder 懒分页）。
- 429 限流：SDK 自动重试；手写时要减 page_size、加页间延迟。

### 3d. lookup 展开（$expand + $select 嵌套）

```
GET /opportunities?$select=name,estimatedvalue&$expand=parentaccountid($select=name)
```

- `$expand` 内**必须嵌套 `$select`**，否则回传关联实体的全部列，浪费带宽。
- **大小写铁律（错了就是 400）**：
  - `$select`/`$filter`/`$orderby` 用**全小写 LogicalName**（`new_name`）。
  - `$expand` 用 **Navigation Property Name，大小写敏感，必须与 `$metadata` 的 SchemaName 一致**（`new_AccountId`）；系统表导航属性（`parentaccountid`、`ownerid`）是小写，自定义 lookup 通常混合大小写。
  - 验证方法：查 `EntityDefinitions(LogicalName='...')/Attributes` 或 `$metadata`。
- **GUID-free 显示**：请求头 `Prefer: odata.include-annotations="OData.Community.Display.V1.FormattedValue"`（或 `"*"`），响应里 lookup/choice/status/owner 字段会带 `_field@OData.Community.Display.V1.FormattedValue` 注解（显示名而非 GUID）。**不发这个头响应里就没有**。

---

## 4. web-api-advanced.md 的 hand-rolled urllib/get_token 完整模式（最重要）

这是整个插件中 raw HTTP 的**唯一合法家园**（CLAUDE.md 明确：其他 skill 新增 urllib 示例会被 review 打回）。

**合法使用判据（原文）**："Reach for the raw `urllib` examples below **only** when the call is one step inside a larger **in-process Python loop** — paging thousands of rows via `@odata.nextLink`, or `$apply` results you post-process client-side — where per-call process spawn or subprocess plumbing would be clumsy. This is the sole legitimate reason to hand-roll HTTP."

**完整骨架（N:N $expand 示例，原文）**：

```python
import os, sys, json, urllib.request
sys.path.insert(0, os.path.join(os.getcwd(), "scripts"))
from auth import get_token, get_plugin_headers, load_env

load_env()
env = os.environ["DATAVERSE_URL"].rstrip("/")
token = get_token()

url = (f"{env}/api/data/v9.2/new_tickets"
       f"?$select=new_name"
       f"&$expand=new_ticket_kbarticle($select=new_title)")
headers = get_plugin_headers("dv-query", token)
headers.update({"OData-MaxVersion": "4.0", "OData-Version": "4.0", "Accept": "application/json"})
req = urllib.request.Request(url, headers=headers)
with urllib.request.urlopen(req, timeout=150) as resp:
    data = json.loads(resp.read())
    for ticket in data["value"]:
        ...
```

**可提炼的原生 HTTP 要点**：

1. **基础 URL**：`{env}/api/data/v9.2/{EntitySetName}?...`（用 EntitySetName，复数）。
2. **必带头**：`Authorization: Bearer <token>`、`Accept: application/json`、`OData-MaxVersion: 4.0`、`OData-Version: 4.0`。User-Agent 带遥测上下文是微软自己的需求，我们可换成自己的标识。
3. **超时**：`urlopen(req, timeout=150)`——聚合/大页查询用 150s。
4. **分页**：示例只取单页；>~5000 行要循环 `data.get("@odata.nextLink")`，把 nextLink 原样作为下一次 GET 的 URL（它已含完整查询串），直到 nextLink 消失。
5. **Prefer 头**：`Prefer: odata.include-annotations="OData.Community.Display.V1.FormattedValue"` 拿格式化显示值；写操作返回偏好 `Prefer: return=representation`（插件未展开，属通用 OData 知识）。
6. **创建响应**：raw POST create 返回 **HTTP 204，无 body**，新记录 id 在 **`OData-EntityId` 响应头**（`.../accounts(<guid>)`）——要解析 header，不要等 JSON body。
7. **错误处理**（dv-data 的 HttpError 语义可直接映射到 urllib 的 HTTPError）：400 = 字段名错/`@odata.bind` 格式错/缺必填列（错误消息会点名缺失字段）；403 = 安全角色；404 = 表或记录不存在（注意：也可能是复数化错误，见 §6）；429 = 限流，自动重试 + 减小页/批量。
8. **遥测头模式（他们自家的，可参考其工程做法）**：`User-Agent: Python-urllib (app=dataverse-skills/<ver>;skill=<skill>;agent=<agent>)`，封闭 schema + 正则校验 `^[a-zA-Z0-9_-]+=[a-zA-Z0-9_./-]+(;...)*$`，禁 PII。

**$apply 封装函数（原文，可直接搬）**：

```python
def apply_query(entity_set, apply_expr):
    url = f"{env}/api/data/v9.2/{entity_set}?$apply={apply_expr}"
    req = urllib.request.Request(url, headers=_base_headers.copy())
    with urllib.request.urlopen(req, timeout=150) as resp:
        return json.loads(resp.read()).get("value", [])
```

---

## 5. QueryBuilder 的 DataFrame 导出模式

```python
df = client.query.builder("opportunity") \
    .select("name", "estimatedvalue", "statuscode") \
    .where(eq("statuscode", 1)) \
    .execute() \
    .to_dataframe()
```

- 过滤器可组合：`(eq("statecode",0) | eq("statecode",1)) & gt("estimatedvalue",10000)`。
- 任务→方式路由表（原文）：聚合/透视、导出 CSV/Excel、小表 lookup map → builder→DataFrame；大表流式落盘、导入后比对行数、100K+ 行 lookup map → `list_pages()` 流式；跨表 → 服务端 SQL/FetchXML，否则两表各拉 DataFrame + `pd.merge()`。
- **始终传 `select=`**：100K 行 20 列全取会多传 10–20 倍数据，把 15 秒查询拖成 90 秒。
- pandas merge+groupby 在 100K–300K 行只要几秒，瓶颈是网络不是 Python。

---

## 6. CLI 陷阱清单

1. **自定义表 SQL 复数化 404**：`dataverse data query` SQL 模式自动把表名变复数，不规则复数会错——`FROM im_category` 查 `im_categorys` → 404，看起来像"表不存在"但**不是**。解法：改 OData 模式显式给 EntitySetName（`--table im_categories`）；不确定就从 `EntityDefinitions` 查真实 `EntitySetName`。**永远不要仅凭这个 404 断定表不存在。**
2. **Windows shell 引号**：`--path` 整体用双引号包住，否则 cmd/PowerShell 把 `&` 当命令分隔符。`&` 必须**字面保留**（它是 OData 查询选项分隔符）；编码成 `%26` 会把选项合并毁掉查询。只把 `$` 编码成 `%24`（PowerShell 里裸 `$select` 会被当变量）。未引号的 `&` 拆断命令时，wrapper 可能非零退出**即使 API 返回了合法 JSON**。
3. **`.env`/Windows 脚本**：`.py` 文件只用 ASCII（花引号/破折号 → SyntaxError）；多行代码不要 `python -c`，写 `.py`；GUID 用 `str(uuid.uuid4())` 别用 shell 反引号；后台任务输出可能静默为空——`python -u` + `print(..., flush=True)`。
4. **PAC CLI on Git Bash**：`pac` 是 .cmd wrapper，Git Bash 下可能挂——用 `powershell -Command "& pac.cmd ..."`；Python subprocess 里可能解析到旧版 `pac.exe`，要 `cmd.exe /c pac ...` 或 `shutil.which('pac.cmd')`。
5. **`pac --version` 不是有效命令**（非零退出），检测用裸 `pac` 看 banner。
6. **`--context` 不要自己加括号**（CLI 自动包 `(…)`，预包会变 `((…))` 静默毁掉遥测分类）。
7. **MCP 建表可能超时但成功**——重试前先 `describe` 确认。
8. **MCP 查询要串行**（并行调用会超时）；列名含空格会归一化成下划线。

---

## 7. SDK client 构造与 API 映射（scripts/auth.py 实证）

### 7a. client 构造（auth.py `get_client`）

```python
DataverseClient(
    base_url=os.environ["DATAVERSE_URL"],
    credential=_get_credential(),          # azure-identity TokenCredential
    context=OperationContext(user_agent_context="app=...;skill=...;agent=..."),
)
```

**认证三级回退（`_get_credential`）**：
1. `.env` 里有 `CLIENT_ID`+`CLIENT_SECRET` → `ClientSecretCredential(tenant_id, client_id, client_secret)`（**SPN 非交互，CI 首选**——这正是我们的路线）。
2. 共享 DataverseCLI MSAL 缓存（`msal_extensions.PersistedTokenCache`，Windows 上是 `%LocalAppData%\Microsoft\DataverseCli\tokencache_msalv3.dat` DPAPI 加密）→ 自写 `_MsalSharedCacheCredential` 适配器实现 `get_token(*scopes)` 协议。
3. DeviceCodeCredential 兜底（持久化 AuthenticationRecord）。

**配置来源**：`load_env()` 从 repo 根或 cwd 的 `.env` 读 `DATAVERSE_URL`（必需）、`TENANT_ID`（必需）、`CLIENT_ID/CLIENT_SECRET`（可选）。scope 默认 `{DATAVERSE_URL}/.default`。

### 7b. SDK 方法 → Web API 调用映射

| SDK 方法 | 底层 Web API |
|---|---|
| `client.records.list(select/filter/orderby/top/expand)` | `GET /api/data/v9.2/<set>?$select=...&$filter=...&$expand=...`，自动跟 `@odata.nextLink` 收全页 |
| `client.records.list_pages()` | 同上但逐页 yield |
| `client.records.retrieve(table, guid)` | `GET /<set>(<guid>)?$select=...`（404 返回 None） |
| `client.records.create/update/delete` | `POST/PATCH/DELETE /<set>[(<guid>)]`（批量传 list → CreateMultiple 等） |
| `client.records.upsert()` | `PATCH /<set>(<alt-key>)` + `MSCRM.SuppressDuplicateDetection` 等头 |
| `client.query.sql("SELECT ...")` | `GET /<set>?sql=<T-SQL 子集>` |
| `client.query.fetchxml(xml)` | `GET /<set>?fetchXml=<urlencoded XML>`（`.execute()` 全页 / `.execute_pages()` 逐页） |
| `client.query.builder(t).select().where().execute()` | 拼装成普通 OData GET（与 records.list 同路径） |
| `client.query.sql_columns(t)` | 元数据查询（EntityDefinitions/Attributes 系） |
| `client.dataframe.create/update()` | 同 records 的批量写 |
| `client.files.upload()` | 文件列分块上传 API |

**结论：SDK 每个方法都是一层薄包装，全部对应公开 Web API OData 端点，没有私有协议。** 唯一例外是批量操作用 `CreateMultiple` 等特殊 action 端点。

---

## 8. dv-connect 认证双通道

装两套、登两套，因为背后是**两个不同的 AAD 应用注册、两份独立 token 缓存**：

1. **Dataverse CLI**（`npm i -g @microsoft/dataverse`，自带运行时，Node 驱动）：
   - `dataverse auth create --environment <url>`（Windows 走 WAM broker 不开浏览器；headless 加 `--deviceCode`）。
   - 一次登录覆盖：CLI 本体 + `@microsoft/dataverse` MCP stdio 代理 + 所有 Python 脚本（auth.py 通过 msal-extensions 静默复用同一 MSAL v3 缓存）。
   - 管：connect / data / query / metadata / MCP。
2. **PAC CLI**（`winget install Microsoft.PowerAppsCLI`，需 .NET SDK）：
   - `pac auth create --name <profile> --environment <url>`（交互），或 SPN 非交互：`pac auth create --applicationId <ID> --clientSecret <SECRET> --tenant <TENANT>`。
   - 管：`dv-solution`（solution export/import/pack/unpack）+ `dv-admin`。
   - `pac auth list` / `pac org who` 验证；profile 按环境命名（dev/staging/prod）。

验证三件套：`dataverse auth who` + `pac org who` + `python scripts/auth.py` 必须解析到同一用户/环境。tenant ID 兜底发现法：`curl -sI https://<org>.crm.dynamics.com/api/data/v9.2/ | grep WWW-Authenticate`（响应头里有 login.microsoftonline.com/<tenant>/）。

权限预检（可借鉴）：`GET /api/data/v9.2/WhoAmI` 拿 UserId → `GET systemusers(<id>)/Microsoft.Dynamics.CRM.RetrieveUserSetOfPrivilegesByNames(PrivilegeNames=@p)?@p=["prvCreateEntity"]` 查**含团队继承的**有效权限；最低权限用 System Customizer，别动不动 System Administrator。

---

## 9. dv-query 边界确认（dv-data / dv-metadata 分工）

- **dv-data**（`Record-level CRUD and bulk operations`）：create/update/delete/upsert、`CreateMultiple` 批量、CSV 导入、多表 FK 顺序导入、AI 造样例数据、文件列上传。读只在做写工作流内做（如 lookup 解析）；独立查询归 dv-query。
- **dv-metadata**（`schema authoring and inspection`）：建表/列/关系/forms/views、列与关系检视（`client.tables.list_columns/list_table_relationships`）、备用键。Environment-first：绝不手写 solution XML；元数据变更必须先确认 solution + publisher prefix（永久不可改），SDK 调用传 `solution=` 或头 `MSCRM.SolutionName`。
- **dv-query** 只管：读、分页、聚合、DataFrame、notebook。ERP 读写都不走 DataverseClient（ERP 是另一套 OData：PascalCase 实体集、复合键 `dataAreaId='usmf',Key='10'`、无 $apply/无 FetchXML，走 `--target erp` 或 ERP MCP）。

---

## 10. 剥离 SDK/CLI/MCP 后的可移植知识清单（按三档分类）

### A. 直接可用（知识/端点层，与工具链无关）

1. **完整 HTTP 骨架**：`{env}/api/data/v9.2/{EntitySet}?...` + 头组合（`Authorization/Accept/OData-Version/OData-MaxVersion`）+ 150s 超时——web-api-advanced.md 原文就是 urllib，零改写。
2. **`$apply` 聚合全部写法**（groupby/aggregate/$count/sum/average 模式表）+ 50K 源记录上限 + 单实体集限制。
3. **`?sql=` T-SQL 子集支持/不支持清单 + 5,000 行静默截断红线**——我们直接用 `GET /<set>?sql=...` 即可调用同一端点。
4. **大小写铁律**：$select/$filter 小写 LogicalName、$expand 用大小写敏感的 Navigation Property Name；验证靠 `EntityDefinitions(LogicalName='...')/Attributes`。
5. **`Prefer: odata.include-annotations="OData.Community.Display.V1.FormattedValue"`** 拿显示名（GUID-free 展示）。
6. **分页协议**：跟 `@odata.nextLink` 原样 URL 循环；每页 ≤5000。
7. **创建响应 204 + `OData-EntityId` 头**取新 id。
8. **错误语义表**：400（字段大小写/@odata.bind/缺必填）/403/404（警惕复数化假 404）/429（退避重试）。
9. **查询形态路由思想**："让服务端干活"——聚合下推、select 裁剪列（10–20 倍传输差）、跨表优先服务端 JOIN。
10. **N:N**：读 `$expand=<n:n_nav>($select=...)`，写 `POST .../<nav>/$ref`。
11. **EntitySetName 发现**：从 `EntityDefinitions` 查，不要相信自动复数化。
12. **SPN 认证**：`ClientSecretCredential` 等价的原生 HTTP 就是 POST `https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token`，`client_credentials` grant，scope `{env}/.default`——auth.py 的 Path 1 证明这就是 SDK 的底层。
13. **权限预检**：`WhoAmI` + `RetrieveUserSetOfPrivilegesByNames` 模式。
14. **tenant 发现**：WWW-Authenticate 头解析法。

### B. 需改写（思路可搬，实现要换）

1. **QueryBuilder/records.list 的封装形态** → 我们写成自己的 `query(table, select, filter, expand, orderby, top)` 函数，内部拼 OData URL + nextLink 循环（工作量小）。
2. **DataFrame 交接**：`execute().to_dataframe()` → 我们自己 `pd.DataFrame(records)`；跨表 pandas merge 模式原文已给。
3. **FetchXML**：`?fetchXml=` URL 编码参数我们可自己拼；xml 模板（link-entity、aggregate）直接复用。
4. **遥测/attribution 体系**（`User-Agent: (app=...;skill=...;agent=...)` 封闭 schema + 正则校验）——工程思路值得抄，内容换成我们自己的标识。
5. **CLI 陷阱清单**：复数化/引号问题在我们 urllib 架构下**自然消失**（没有 shell 层），但 "EntitySetName 必须显式" 的教训保留。
6. **dv-connect 的双通道**：我们不需要 pac/dataverse CLI；只需 SPN（CLIENT_ID/SECRET/TENANT_ID/DATAVERSE_URL 四元组）。`RetrieveUserSetOfPrivilegesByNames` 预检可保留为 urllib 调用。
7. **Windows 脚本规则**（ASCII-only、`python -u`、flush）与我们环境直接相关，照单收下。

### C. 不可用 / 不需要

1. MCP 全家（read_query/describe/25 条上限/串行限制）——我们没有 MCP 层。
2. `dataverse` CLI 与 `@microsoft/dataverse` npm 包、`dataverse auth create` 共享 MSAL 缓存路径——我们用 SPN，不碰用户态缓存。
3. PAC CLI 认证与 solution ALM 命令——超出查询范围。
4. 共享缓存实现（msal-extensions、DPAPI/keychain/libsecret 适配）——SPN 无状态拿 token，全部跳过。
5. ERP 专用路径（`--target erp`、复合键、cross-company）——除非目标环境挂了 F&O。
6. 插件遥测合规约束（`_ALLOWED_SKILLS/_ALLOWED_AGENTS` 白名单、`--context` 括号陷阱）——微软自家流量归因需求。

### 依赖剥离可行性结论

**完全可行。** SDK 的每个方法都是公开 Web API 端点的薄封装；web-api-advanced.md 本身就提供了官方背书的 urllib 模式。我们的 urllib+SPN 架构只需要：`client_credentials` 换 token（一个 POST）、OData URL 拼装、nextLink 循环、错误映射，即可覆盖 dv-query 100% 的查询能力（含 `$apply`、`?sql=`、FetchXML、N:N expand），且天然规避了 CLI 复数化/Windows 引号两类陷阱。
