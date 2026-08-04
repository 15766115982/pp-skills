# Dataverse Web API 与 workflow 表：官方文档核实记录

核实日期：2026-08-03。所有来源均为 learn.microsoft.com 官方文档（经官方搜索 API 定位 + curl 抓取正文核实）。

---

## 1. 元数据端点（EntityDefinitions / RelationshipDefinitions / GlobalOptionSetDefinitions）

**结论：三个都是标准 OData v4.0 entity set，用普通 GET + OData 查询选项访问；$expand=Attributes 取派生类型专有属性时必须 cast，写法是把 `/Microsoft.Dynamics.CRM.<派生类型>` 追加到 URL 段。**

来源：https://learn.microsoft.com/en-us/power-apps/developer/data-platform/webapi/query-metadata-web-api （页面最后更新 2026-03-10）

关键摘录：
- "Use the EntityDefinitions entity set path to retrieve information about the EntityMetadata EntityType."
- 请求头标准 OData v4：`OData-MaxVersion: 4.0` / `OData-Version: 4.0`，响应 `OData-Version: 4.0`。
- "There are no limits on the number of metadata entities that a query returns. There's no paging."
- cast 写法（属性级）：
  `GET [Organization URI]/api/data/v9.2/EntityDefinitions(LogicalName='account')/Attributes/Microsoft.Dynamics.CRM.PicklistAttributeMetadata?$select=LogicalName&$expand=OptionSet,GlobalOptionSet`
- 单个属性 cast：
  `.../Attributes(5967e7cc-...)/Microsoft.Dynamics.CRM.PicklistAttributeMetadata?$select=LogicalName&$expand=OptionSet`
- 限制："you can't cast the attributes to [EnumAttributeMetadata]. This limitation means you must perform separate queries to filter for other types that inherit these properties."（即必须按具体派生类型逐一 cast，不能用中间基类）
- 关系元数据 cast：
  `GET .../RelationshipDefinitions/Microsoft.Dynamics.CRM.OneToManyRelationshipMetadata?$select=SchemaName&$filter=ReferencedEntity eq 'account'`
- GlobalOptionSetDefinitions 限制："this path doesn't support the use of the $filter system query option. So, you can only retrieve a single global option set by either the MetadataId or the unique name." 例如 `GlobalOptionSetDefinitions(Name='incident_caseorigincode')`。
- LabelLanguages：EntityDefinitions 查询可加 `&LabelLanguages=1033` 限制返回的标签语言（LCID）。

需要 cast 的属性派生类型全集（AttributeMetadata 直接派生，来源 https://learn.microsoft.com/en-us/power-apps/developer/data-platform/webapi/reference/attributemetadata?view=dataverse-latest 页面 Derived Types 链接列表）：
BigInt、Boolean、DateTime、Decimal、Double、EntityName、Enum(基类)、File、Image、Integer、Lookup、ManagedProperty、Memo、Money、String、Uniqueidentifier。
EnumAttributeMetadata 的派生类型（https://learn.microsoft.com/en-us/power-apps/developer/data-platform/webapi/reference/enumattributemetadata?view=dataverse-latest ）：
EntityNameAttributeMetadata、MultiSelectPicklistAttributeMetadata、PicklistAttributeMetadata、StateAttributeMetadata、StatusAttributeMetadata。
文档中明确示例的 cast 目标：`Microsoft.Dynamics.CRM.PicklistAttributeMetadata`、`Microsoft.Dynamics.CRM.MoneyAttributeMetadata`、`Microsoft.Dynamics.CRM.OneToManyRelationshipMetadata`（以及 ManyToManyRelationshipMetadata）。注意：一次 $expand=Attributes 查询只能 cast 到单一派生类型，取多种类型的专有属性需多次请求（query-schema-definitions 文档的限制说明）。

## 2. RetrieveMetadataChanges

**结论：它是 Web API 的 Function（不是 Action），官方示例用 GET 调用，Query 参数以 URL 别名的方式传 URL 编码的 JSON；不是 POST + 请求体的形式。增量机制 = 上一次响应的 ServerVersionStamp 作为下次请求的 ClientVersionStamp。**

来源 A（函数签名）：https://learn.microsoft.com/en-us/power-apps/developer/data-platform/webapi/reference/retrievemetadatachanges?view=dataverse-latest
- "RetrieveMetadataChanges Function (Microsoft.Dynamics.CRM)"
- 参数表：Query (EntityQueryExpression)、DeletedMetadataFilters (DeletedMetadataFilters 枚举)、ClientVersionStamp (Edm.String, "Timestamp value representing when the last request was made")、AppModuleId (Edm.Guid)、RetrieveAllSettings（内部用）。返回 RetrieveMetadataChangesResponse。

来源 B（完整请求示例）：https://learn.microsoft.com/en-us/power-apps/developer/data-platform/query-schema-definitions?tabs=webapi
- "The RetrieveMetadataChanges function Query parameter requires a URL encoded string representing the JSON value of the query, which is an EntityQueryExpression complex type."
- 官方请求示例（GET）：
  `GET [Organization URI]/api/data/v9.2/RetrieveMetadataChanges(Query=@p1)?@p1=%7B%22AttributeQuery%22...%7D HTTP/1.1`（带 `OData-MaxVersion: 4.0` / `OData-Version: 4.0` / `Accept: application/json` / `If-None-Match: null`）
- Query JSON 结构（EntityQueryExpression）：Properties `{AllProperties:false, PropertyNames:[...]}`、Criteria `{FilterOperator:"Or", Conditions:[{ConditionOperator:"Equals", PropertyName:"LogicalName", Value:{Type:"System.String", Value:"account"}}]}`、AttributeQuery、RelationshipQuery、KeyQuery、LabelQuery `{FilterLanguages:[1033], MissingLabelBehavior:0}`。
  - 注意：限制语言在 RetrieveMetadataChanges 里用 LabelQuery.FilterLanguages（LCID 数组），而 EntityDefinitions 查询用 URL 参数 LabelLanguages=1033。
  - 约束：用 AttributeQuery 时 EntityQueryExpression.Properties 必须含 "Attributes"；RelationshipQuery/KeyQuery 同理须含对应导航属性。
  - MetadataConditionExpression.Value 是 Object ComplexType：`{Type, Value}`，Type 须匹配 .NET 类型（"System.String"、"System.Boolean"、"System.Int32"、"System.Guid"、"Microsoft.Xrm.Sdk.Metadata.AttributeTypeCode" 等）。
  - MetadataConditionOperator：Equals / NotEquals / In / NotIn / GreaterThan / LessThan。
  - "The Query parameter is optional... but this is equivalent to using RetrieveAllEntities, a very expensive operation."
- 响应：`RetrieveMetadataChangesResponse` 含 EntityMetadata（ComplexEntityMetadata 集合，注意与 EntityDefinitions 用的 EntityMetadata entity type 不同）、ServerVersionStamp（如 `"74812162!10/09/2022 22:10:22"`）、DeletedMetadata（仅当同时传 ClientVersionStamp + DeletedMetadataFilters 才有数据）。

来源 C（增量缓存机制）：https://learn.microsoft.com/en-us/power-apps/developer/data-platform/cache-schema-data?tabs=webapi （最后更新 2026-02-12）
- "Take the ServerVersionStamp value from the previous response and use it as the value for the RetrieveMetadataChangesRequest.ClientVersionStamp when you send it again by using the same query."
- "When you include the ClientVersionStamp property in the request, the RetrieveMetadataChangesResponse.EntityMetadata property returned contains only the changed or added schema data since the previous request."
- "Dataverse stores information about changes for 90 days by default. This value is stored in the Organization.ExpireSubscriptionsInDays property. If you send a request with a ClientVersionStamp value that's older than the setting value, Dataverse returns an ExpiredVersionStamp error (0x80044352)." —— 过期必须全量重建缓存。
- HasChanged 层级语义：false = 本身没变但下层有变化；true = 本项变化；OptionMetadata.HasChanged 通常为 null。
- 删除项：DeletedMetadataFilters 参数可选且影响性能（绕过内部缓存直查数据库）；Web API 的 DeletedMetadataFilters 枚举没有 Entity 成员，用 Default；删除选项（option）不会单独报告，只能比对 OptionSet 当前 Options。
- 若请求 EntityMetadata.Privileges，权限总是返回（无论是否变化）。

补充：函数参考页（来源 A）标注为 Function；按 OData 约定 Function 用 GET 调用（官方示例证实）。未发现官方 POST 调用示例。

## 3. workflow 表

来源：https://learn.microsoft.com/en-us/power-apps/developer/data-platform/reference/entities/workflow

**category 取值（官方 Choices/Options 表，GlobalChoiceName = workflow_category）：**
| 值 | 标签 |
|---|---|
| 0 | Workflow |
| 1 | Dialog |
| 2 | Business Rule |
| 3 | Action |
| 4 | Business Process Flow |
| 5 | Modern Flow |
| 6 | Desktop Flow |
| 7 | AI Flow |

即 category=5 官方标签为 "Modern Flow"（云端流程/cloud flow）。表中另有 modernflowtype 列（"Type of the Modern Flow"，Picklist，GlobalChoiceName workflow_modernflowtype）。

**clientdata 字段（官方列定义）：**
- Description: "Business logic converted into client data"
- Type: Memo，Format TextArea，MaxLength 1073741823，IsValidForForm False / IsValidForRead True。
- 相关列 clientdataiscompressed（Boolean，"For Internal Use Only"，True Label "Workflow has compressed client data"）——说明 clientdata 可能压缩存储，采集层须注意。

**connectionReferences（重要修正点）：**
workflow 表有独立的 connectionreferences 列（官方列定义）：Description "Connection References related to this workflow"，Type Memo，MaxLength 100000。另有 ListConnectionReferences 相关条目出现在该表文档中。即连接引用不只存在于 clientdata JSON 内部，官方提供了专用列。

**clientdata 内部 JSON 结构（definition / connectionReferences / $authentication）：**
未找到 Microsoft Learn 官方文档描述 clientdata 列的内部 JSON schema（包括其中 connectionReferences、definition 字段结构、$authentication 是否含敏感信息）。这些属于未正式文档化的实现细节；方案中相关描述应标注"社区观察/未官方文档化"。可佐证的官方旁证：solution 导出文档（见第 5 条）确认 Workflows 文件夹中每个 flow 是一个 JSON 定义文件。

## 4. SPN 认证（client_credentials 调 Dataverse Web API）

来源 A：https://learn.microsoft.com/en-us/power-apps/developer/data-platform/authenticate-oauth （最后更新 2026-07-24）
- "use a \"<environment-url>/user_impersonation\" scope for a public client. For a confidential client, use a scope of \"<environment-url>/.default\"."
- "create a special application user that is bound to a Microsoft Entra ID registered application. Next, use either a key secret configured for the app or upload a X.509 certificate. Another benefit of this approach is that it doesn't consume a paid license."
- 要求："A registered app / A Dataverse user bound to the registered app / Connect by using either the application secret or a certificate thumbprint."
- 注册注意："You don't need to grant the Access Dynamics 365 as organization users permission."（SPN 模式不需要该委托权限）
- 权限模型："First, create a custom security role that defines what access and privileges this account has within the Dataverse organization... After creating an application user, associate the application user with the custom security role you created." —— 权限完全由 Dataverse 安全角色决定，需在 PPAC 创建 application user 并绑定角色。
- 连接串示例：`AuthType=ClientSecret; url=...; Secret=...; ClientId=...` 或 `AuthType=Certificate; thumbprint=...`。

来源 B（token 端点与 scope 写法）：https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-client-creds-grant-flow
- `POST https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token`，参数 `client_id` / `client_secret`（或证书断言）/ `grant_type=client_credentials` / `scope=<resource>/.default`。
- "The value passed for the scope parameter in this request should be the resource identifier (application ID URI) of the resource you want, suffixed with .default."
- 对 Dataverse 即 `scope=https://<org>.crm.dynamics.com/.default`（环境 URL + /.default）。

来源 C（application user 管理）：https://learn.microsoft.com/en-us/power-platform/admin/manage-application-users
- "You can create an unlicensed application user in your environment."
- 在 Power Platform 管理中心创建后需为其分配安全角色（"Select the edit icon to select security roles for the new application user"）。

## 5. solution 导出 Workflows/*.json 多行格式化（2022 年 2 月）

**结论：找到官方来源，属实。**

来源：https://learn.microsoft.com/en-us/power-automate/export-flow-solution
关键摘录：
- "Find the flows in the Workflows folder in the solution zip file."
- "Each exported workflow is represented as a JSON file. Flow definitions were traditionally a compact block of JSON in a single line. In February 2022 the export format was changed to multi-line formatted JSON to make them easier to read and make them friendlier to revision tracking in source control."

---

## 对采集层设计的主要修正点

1. **RetrieveMetadataChanges 用 GET 而非 POST**：Query 是 URL 编码 JSON 通过参数别名（`RetrieveMetadataChanges(Query=@p1)?@p1=...`）传递；客户端需处理 URL 长度（查询复杂时 URL 很长）并保存/比对 ServerVersionStamp；还要处理 90 天 ExpiredVersionStamp (0x80044352) 全量重建逻辑。
2. **connectionreferences 是 workflow 表的独立列**：连接引用应优先从该专用列（及 clientdata 内 connectionReferences 作补充）采集；clientdata 内部 JSON 结构（definition/$authentication）无官方文档，解析逻辑要按未文档化结构做防御性处理，并注意 clientdataiscompressed=true 时内容被压缩。
3. $expand=Attributes 一次查询只能 cast 一种派生属性类型，枚举类属性须按 Picklist/State/Status/MultiSelectPicklist 分别发请求；GlobalOptionSetDefinitions 不支持 $filter，只能按键或 Name 单个取。
