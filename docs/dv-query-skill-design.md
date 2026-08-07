# dv-query Skill 设计方案（v1.0）

> 基于两份深读报告：`research/dv-query-deepdive.md`（Dataverse-skills 官方）、`research/webapi-query-deepdive.md`（power-cat-skills CAT）。日期：2026-08-04

## 1. 定位与差异化

自研轻量 Dataverse 查询 skill，与 pp-kb-builder 同栈（urllib + SPN + 代理 + 本地 kb）。

**与两个官方候选的差异**：

| 维度 | Dataverse-skills dv-query | power-cat webapi-query | 本设计 |
|---|---|---|---|
| 执行层 | SDK + 双 CLI + 可选 MCP | 不执行（用户自己跑） | pp_common（token/代理/api_get，已测试） |
| schema 解析 | MCP → EntityDefinitions 实时查 | MCP → EntityDefinitions → 问用户 | **本地 kb/dataverse/tables/*.md 优先** → 实时 API → 问用户 |
| 依赖 | SDK + dataverse CLI + pac CLI | 零（也不执行） | **零新增**（沿用仅 PyYAML） |
| 无人值守 | CLI 交互认证受限 | 不执行 | SPN client_secret，天然支持 |
| FetchXML 映射 | fetchxml() 黑盒 | 引用文件缺失（8/8 确认缺失） | 自研补齐（最大空洞） |

深读结论：SDK 各方法一一对应公开 OData 端点，剥离 SDK/CLI/MCP 后能力零损失，且天然规避 CLI 复数化假 404 与 Windows `&`/`$` 引号两类 shell 层陷阱。

## 2. 结构

```
.claude/skills/dv-query/
├── SKILL.md                     # 路由表 + schema 解析顺序 + OData 铁律 + 错误诊断 + token 纪律
├── scripts/
│   └── dv_query.py              # GET-only 执行器（OData / ?sql= / ?fetchXml= / $apply），输出 table/CSV/JSON
├── references/
│   ├── odata-rules.md           # 8 条铁律 + 大小写规则 + 请求头（提取自两个候选，MIT，注明出处）
│   ├── tsql-subset.md           # ?sql= 能力边界（支持/不支持清单、5000 行静默截断警告）
│   ├── fetchxml-mapping.md      # FetchXML→Web API 映射（自研补齐：正文 5 条 + 聚合/link-entity/late-bound）
│   └── error-diagnosis.md       # 400/401/403/404 诊断决策树
└── tests/                       # URL 构造、分页循环、格式化输出的单测（不触网）
```

## 3. 核心行为（SKILL.md 内容骨架）

**schema 解析顺序（防猜名，"Never invent a logical name"）**：
1. 读本地 `kb/dataverse/tables/<name>.md`（列名/类型/选项值/Lookup 目标/关系全在）——零网络
2. 本地没有 → 实时 `EntityDefinitions(LogicalName='...')` 查一次并提示"该表不在 kb，可考虑刷新知识库"
3. 仍不确定 → 问用户，绝不编造

**查询形态路由**（吸收官方路由表，去掉 SDK 项）：

| 用户意图 | 执行方式 |
|---|---|
| 简单过滤/列表 | OData `$filter/$select/$orderby/$top` |
| 计数 | `?sql=SELECT COUNT(*)`（服务端，不下载行） |
| 单表聚合 | `$apply=groupby(...)`（≤50K 源记录）或 SQL GROUP BY |
| 跨表查询/聚合 | `?sql=` INNER/LEFT JOIN；或 `?fetchXml=` link-entity |
| 大结果集 | 分页循环跟 `@odata.nextLink`（timeout=150） |
| <5K 行快速读 | `?sql=` 单请求（2-6s） |

**OData 铁律**（references/odata-rules.md，提取自 CAT skill + 官方深读）：entity set 复数小写、`_lookup_value` 读 GUID vs 导航属性仅进 `$expand`（大小写敏感，错则 400）、FormattedValue 需 `Prefer: odata.include-annotations="OData.Community.Display.V1.FormattedValue"`、GUID 不加引号、字符串单引号双写、ISO 日期、T-SQL 5000 行静默截断警告。

**错误诊断**（references/error-diagnosis.md）：400（语法/大小写/expand 名错）→ 401（token 失效/权限）→ 403（安全角色/表级权限）→ 404（entity set 名错，**先查本地 kb 的 EntitySetName 再下结论**）。

**token 纪律**：SPN 走环境变量（与 pp-kb-builder 共用）；用户交互式查询时不接触用户 token，沿用 CAT 的引导路径（az cli/Postman/连接器）。

## 4. dv_query.py 设计

```bash
python dv_query.py --table contoso_salesorder --select contoso_name,contoso_totalamount \
                   --filter "contoso_status eq 100000002" --top 50
python dv_query.py --sql "SELECT contoso_status, COUNT(*) AS n FROM contoso_salesorder GROUP BY contoso_status"
python dv_query.py --fetchxml-file q.xml --format csv -o out.csv
```

- 基于 pp_common：load_config（含 pythonPath）→ get_token → api_get 循环
- 分页：`@odata.nextLink` 跟随，`--max-pages` 防护
- 输出：`--format table|csv|json`（默认 table 打印控制台；csv/json 落盘）
- **只读**：仅 GET；`?sql=`/`?fetchXml=` 都是 GET 参数化
- entity set 解析：`--table` 给 logical name 时先查本地 kb 的 EntitySetName，查不到再实时查

## 5. 与 pp-kb-builder 的关系

- 独立 skill（查询是运行期行为，kb 是构建期产物），但**复用 pp_common.py**（拷贝或 sys.path 引用，倾向拷贝保持 skill 自包含）
- kb 存在时体验显著更好（schema 零网络）；kb 不存在时降级为实时 EntityDefinitions，功能不缺失
- SETUP.md 式引导沿用：pythonPath 询问、凭据 SET/MISSING 检查

## 6. 测试方案

- 单测（不触网）：URL 构造（select/filter/expand/top 组合）、OData 转义、nextLink 分页循环（mock 响应）、SQL/FetchXML 参数化、CSV/table 格式化、entity set 本地解析（用 pp-kb-builder 的 golden kb 做夹具）
- 集成：内网冒烟时与 pp-kb-builder 同一 SPN 一并验证

## 7. 开放问题

1. pp_common 复用方式：拷贝（自包含，推荐）还是跨 skill sys.path 引用？
2. 是否需要写操作（create/update）？——当前设计只读；写操作涉及 `OData-EntityId` 头解析等，建议另立 dv-data skill 或明确排除
3. FetchXML 映射补齐的深度：基础 5 条够用，还是连聚合/多层 link-entity 也映射？
