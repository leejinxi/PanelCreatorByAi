# AI Ship CAD Copilot 全船模型错误治理 Agent 开发方案 v1.0

日期：2026-09-12  
状态：方案设计完成，尚未开发  
定位：在保留现有智能创建板架能力的基础上，新增面向全船结构模型的错误归因、批量分流、修复编排与结果收口 Demo  
核心判断：CAD 负责发现错误、几何计算和修复合法性；Agent 负责理解全局错误、组织处置过程并跟踪结果

## 1. 背景与问题定义

当前 CAD 工程能够在关联更新或重新计算失败后，将错误状态标记到模型树节点。板架、骨材、肘板、开孔等结构对象数量很大，错误虽然可见，设计人员仍然需要逐个打开对象、查看原因并选择修复方式。

实际困难不在于“CAD 无法发现错误”，而在于：

1. 全船错误对象数量多，分散在模型树的不同层级。
2. 板架错误可能导致其下骨材、肘板、开孔形成大量级联错误。
3. 表面上的多个错误可能来自同一个上游对象或同一次工程变更。
4. 不同错误需要重算、刷新关联、更新板架、人工重新选择拓扑或提交软件问题等不同处理方式。
5. 固定脚本只适合同一种错误和同一种修复动作，无法安全处理异构错误。
6. 修复后仍需重新查询 CAD 状态，确认根对象和下游子构件是否真正恢复。

本方案的核心命题是：

> CAD 能够发现错误，但缺少面向全船模型的错误归因、批量分流、修复编排和结果收口能力。

Agent 不替代 CAD 几何内核，而是在 CAD 已有错误标记和修复能力之上，提供任务级错误治理。

## 2. 产品定位

现有“AI 智能创建板架”保留为基础能力，新增“全船模型错误治理”作为旗舰展示能力：

```text
AI Ship CAD Copilot
├─ 基础能力：自然语言创建板架
└─ 旗舰能力：全船结构模型错误治理
   ├─ 错误快照
   ├─ 根因归组
   ├─ 级联错误识别
   ├─ 修复分流
   ├─ CAD修复编排
   └─ 修复结果收口
```

错误治理不要求错误来自 Agent 创建。错误可以来自外壳替换、关联更新、历史版本演进、人工操作、模型迁移、CAD 重算或软件缺陷。

对外推荐表述：

> AI Ship CAD Copilot 复用 CAD 的错误检测和几何修复能力，将大量分散错误归并为少量根因组，选择合适的 CAD 处置工具，并将自动恢复、待确认和待人工处理结果统一收口。

## 3. 价值目标

本方案不以“比 CAD 更准确地判断几何”为目标，而以减少人工错误处理成本为目标。

### 3.1 用户价值

- 从逐个查看错误节点，转为按根因组处理。
- 优先修复父对象，避免对子构件级联错误做无效操作。
- 将错误自动分为可重算、确认后更新、人工处理和软件异常。
- 对同类低风险动作进行批量编排，不使用一刀切脚本。
- 修复后自动读取 CAD 状态，形成闭环结果。
- 为设计人员生成可继续执行的剩余工作清单。

### 3.2 Demo 展示价值

- 面向全船规模，而非包装单个创建按钮。
- 能展示 Agent 根据不同观察动态选择工具和路径。
- 能用“错误节点数、根因组数、恢复数、剩余数”量化结果。
- 明确体现 CAD、Agent 与人工三方责任边界。
- 不依赖 RAG、强度计算或 Agent 自行推断几何。

## 4. 责任边界

| 能力 | CAD / Provider | Agent | 人工 |
|---|---|---|---|
| 关联更新与形体重算 | 负责 | 不参与几何计算 | — |
| 标记错误对象 | 负责 | 读取 | 查看结果 |
| 返回错误码、对象关系和工程版本 | 负责 | 校验和整理 | — |
| 判断几何是否有效 | 负责 | 不得替代 | 必要时复核 |
| 识别根错误与级联错误 | 提供依赖数据 | 负责归组 | 可调整分组 |
| 选择处置路径 | 提供候选操作 | 按策略决策 | 审批高风险操作 |
| 执行重算、更新和拓扑修复 | 负责 | 调用工具 | 必要时操作 |
| 修复后验证 | 返回最新状态 | 汇总前后差异 | 验收关键结果 |

以下行为明确禁止：

- LLM 根据错误描述自行计算新定位面或新边界。
- Agent 将父对象错误下的所有子构件逐个强制更新。
- 没有目标对象 ID 时，以“修复”为由调用普通新建。
- 存在多个几何候选时静默选择一个候选。
- 将 Mock 错误、依赖和修复结果描述成真实 CAD 事实。
- 将错误节点减少等同于结构强度、CCS 合规或设计正确性已确认。

## 5. 核心 Demo 故事

### 5.1 用户任务

```text
分析当前工程全部结构错误，优先处理可以安全恢复的对象，
需要选择的集中列给我，其余问题按原因整理。
```

### 5.2 Demo 初始数据

Mock 工程包含 36 个错误节点：

| 对象类型 | 错误数量 |
|---|---:|
| 板架 | 3 |
| 骨材 | 15 |
| 肘板 | 6 |
| 开孔 | 12 |
| 合计 | 36 |

### 5.3 Agent 归因结果

Agent 根据 Provider 返回的父子、依赖和错误码，将 36 个错误节点归并为 4 个根因组：

| 根因组 | Provider 事实 | 影响范围 | 处置路径 |
|---|---|---:|---|
| A | 外壳引用被新版对象替换 | 1 个板架及 14 个子构件 | 唯一修复候选，预览后更新 |
| B | 2 个父板架需要重新计算 | 2 个板架及 9 个子构件 | 低风险批量重算 |
| C | 6 个开孔存在多个拓扑候选 | 6 个开孔 | 集中人工选择 |
| D | 4 个对象出现几何内核异常 | 4 个对象 | 不修改，生成软件问题清单 |

### 5.4 预期演示结果

```text
初始错误节点：36
识别根因组：4
自动或确认后恢复：26
需要人工选择：6
软件异常：4
最终剩余错误节点：10
```

上述数字仅属于固定 Demo 快照，不代表真实工程效率收益。真正的展示重点是将 36 次潜在逐项查看压缩为 4 组可理解、可执行的问题。

## 6. Agent 运行流程

```text
用户错误治理请求
  -> parse_error_governance_intent
  -> collect_cad_error_snapshot
  -> load_error_dependencies
  -> group_root_causes
  -> query_repair_candidates
  -> decide_repair_routes
  -> repair_safety_gate
  -> execute_allowed_repairs
  -> revalidate_affected_scope
  -> summarize_remaining_work
```

### 6.1 动态路由

正常分析模式不修改工程：

```text
collect -> group -> decide -> report
```

用户允许执行且存在低风险动作时：

```text
collect -> group -> decide -> safety_gate
  -> recompute/update -> revalidate -> report
```

存在歧义时：

```text
collect -> group -> query_candidates
  -> multiple_candidates -> request_confirmation
```

### 6.2 父对象优先

如果板架错误导致下游子构件报错，Agent 应先暂停子构件处置：

```text
PANEL-FR108                 root error
├─ STIFFENER-01             cascade error
│  └─ BRACKET-01            cascade error
├─ STIFFENER-02             cascade error
└─ OPENING-01               cascade error
```

处理顺序：

1. 修复或重算 `PANEL-FR108`。
2. 由 CAD 执行关联更新。
3. 重新查询整棵对象子树。
4. 只对仍然存在的子构件错误继续诊断。

## 7. 新建与更新板架契约

公司 CAD 原生 `createPanel` 具备双重语义：

```text
不传板架ID -> createNew
传入当前板架ID -> update
```

当前仓库中的 `create_panel(PanelRequest)` 仍然只表示新建，尚未接入板架 ID 和更新语义。开发时不得把未来 CAD 能力描述为现有 Demo 已实现能力。

### 7.1 Agent 层显式拆分

即使底层共用一个原生接口，Agent 层也应暴露两个强类型工具：

```text
create_panel -> native createPanel(panelId absent)
update_panel -> native createPanel(panelId required)
```

原因：如果 Agent 本来要更新错误板架，却遗漏可选 `panelId`，底层会创建新对象并保留原错误对象。显式拆分可以在 Schema 和 Safety Gate 层拒绝这种危险调用。

### 7.2 建议请求模型

```python
class CreatePanelMutation(BaseModel):
    operation: Literal["create"]
    panel: PanelRequest
    idempotency_key: str


class UpdatePanelMutation(BaseModel):
    operation: Literal["update"]
    panel_id: str
    expected_project_revision: str
    repair_candidate_id: str | None
    panel: PanelRequest
    idempotency_key: str
```

Agent 使用判别联合，拒绝未知字段：

```python
PanelMutation = Annotated[
    CreatePanelMutation | UpdatePanelMutation,
    Field(discriminator="operation"),
]
```

### 7.3 更新修复条件

Agent 可以自主决定调用 `update_panel`，但必须同时满足：

1. Provider 返回明确的现有 `panel_id`。
2. 目标对象当前仍存在且类型为板架。
3. 错误状态和工程版本与决策时一致。
4. 更新参数来自现有对象、用户明确输入或 CAD 修复候选，不来自 LLM 猜测。
5. 不存在未解决的多候选歧义。
6. CAD 预览或能力声明允许执行该更新。
7. 幂等键有效，重复提交不会变成新建。
8. Safety Gate 明确授权 `update`，不得复用新建授权。

## 8. 错误治理 Schema

建议在 `schemas/` 增加以下强类型模型。

### 8.1 ModelErrorSnapshot

```python
class ModelErrorSnapshot(BaseModel):
    project_id: str
    project_revision: str
    captured_at: datetime
    scope: str
    errors: list[ModelErrorRecord]
```

### 8.2 ModelErrorRecord

```python
class ModelErrorRecord(BaseModel):
    error_id: str
    object_id: str
    object_type: Literal["panel", "stiffener", "bracket", "opening"]
    parent_id: str | None
    error_code: str
    provider_message: str
    upstream_object_ids: list[str]
    status: Literal["active", "resolved", "stale"]
```

### 8.3 ErrorRootCauseGroup

```python
class ErrorRootCauseGroup(BaseModel):
    group_id: str
    root_object_ids: list[str]
    root_error_codes: list[str]
    cascade_error_ids: list[str]
    affected_object_ids: list[str]
    evidence: list[str]
```

`evidence` 只允许记录 Provider 错误码、依赖关系和规则依据，不保存隐藏思维链。

### 8.4 RepairCandidate

```python
class RepairCandidate(BaseModel):
    candidate_id: str
    target_object_ids: list[str]
    operation: Literal[
        "recompute",
        "refresh_association",
        "update_panel",
        "manual_topology_selection",
        "report_provider_issue",
    ]
    provider_validation: Literal["passed", "failed", "not_run"]
    ambiguity_count: int
    changes_design_intent: bool
    affected_object_ids: list[str]
```

### 8.5 RepairPlan 与执行报告

```python
class RepairPlanItem(BaseModel):
    group_id: str
    route: Literal[
        "auto_execute",
        "confirm_then_execute",
        "manual",
        "provider_issue",
    ]
    candidate_id: str | None
    reason_code: str


class RepairExecutionReport(BaseModel):
    project_revision_before: str
    project_revision_after: str
    attempted_groups: list[str]
    resolved_error_ids: list[str]
    remaining_error_ids: list[str]
    failed_actions: list[str]
```

## 9. Provider / MCP 工具边界

### 9.1 只读工具

```text
list_model_errors(scope, projectRevision)
get_error_details(errorIds)
get_object_dependencies(objectIds)
get_object_children(objectIds)
get_repair_candidates(groupId)
get_object_status(objectIds)
```

### 9.2 修改工具

```text
recompute_objects(objectIds, expectedProjectRevision, idempotencyKey)
refresh_associations(objectIds, expectedProjectRevision, idempotencyKey)
update_panel(panelId, panelRequest, repairCandidateId, expectedProjectRevision, idempotencyKey)
```

### 9.3 Provider 必须保证

- 所有查询结果带 `project_id` 和 `project_revision`。
- 错误对象使用稳定 `object_id`，不得只返回显示名称。
- 修复候选由 CAD 生成，Agent 不构造几何候选。
- 修改操作具备幂等、事务或明确的部分失败语义。
- 更新失败不得静默降级成新建。
- 批量结果逐项返回成功、失败和错误码。
- 支持重新查询修复后的对象状态。

## 10. 决策与安全策略

### 10.1 四类分流

| 路由 | 条件 | 行为 |
|---|---|---|
| 自动执行 | 低风险重算，CAD 确认不改变设计意图 | Safety Gate 后批量执行 |
| 确认后执行 | 唯一修复候选且 CAD 预览通过，但会改变引用或形体 | 集中请求用户确认 |
| 人工处理 | 多候选、无候选或设计意图可能改变 | 不调用修改工具 |
| Provider 问题 | 内核异常、结果不稳定或无受控错误语义 | 保留现场并生成问题清单 |

### 10.2 Safety Gate 检查

- 当前操作是否属于允许的修复动作。
- 目标对象是否全部存在且类型匹配。
- 工程版本是否仍与快照一致。
- 是否先处理了错误父对象。
- 修复候选是否由 Provider 返回且仍有效。
- 是否存在未解决歧义。
- 是否可能把更新误执行为新建。
- 是否具备幂等键。
- 用户授权范围是否覆盖本次修改。

### 10.3 LLM 使用边界

LLM 可用于：

- 理解用户希望分析还是执行修复。
- 将用户的处理偏好转为结构化策略。
- 对结构化错误组生成面向设计人员的说明。
- 在多个允许工具之间生成候选执行计划。

确定性代码必须负责：

- 依赖图遍历和父子排序。
- 错误码归一化和级联标记。
- 版本、对象 ID、候选数量和授权检查。
- Safety Gate 最终裁决。
- 更新与新建的契约隔离。

## 11. Web Demo 设计

### 11.1 信息架构：错误治理主入口与能力下钻

Web 使用一个服务和一个业务主入口，不再并列展示业务 Tab：

```text
AI Ship CAD Copilot
└─ 全船结构模型错误治理
   ├─ 板架自动更新说明 → 复用板架创建/决策链
   └─ 查看板架决策 → 只读操作记录
```

错误治理是默认页面。原板架创建能力不再占据一级导航，只在观众查看“板架自动更新说明”或单对象决策时进入；错误治理仍不要求错误来自 Agent 创建。

推荐使用 Hash 路由，刷新后仍能定位当前业务页：

```text
http://127.0.0.1:8000/#/model-errors
http://127.0.0.1:8000/#/panel?mode=auto-update&taskId=...&groupId=...
http://127.0.0.1:8000/#/panel?operationId=OP-REPAIR-108-01
```

页头持续显示：

```text
AI SHIP CAD COPILOT

运行模式：MCP Contract Mock
工程版本：DEMO-REV-18
真实CAD：未连接
```

### 11.2 板架自动更新说明与创建能力复用页

板架创建页保留：

- 自然语言输入和固定示例。
- Qwen 提取后的板架参数。
- 边界列表和输入问题。
- Provider 工程对象解析结果。
- `Execution Preflight` 结果。
- CAD 创建或更新结果。
- 精简执行 Trace。
- MCP Call Inspector 和 Mock / 真实 Provider 标识。

默认创建页移除：

- 创建前智能评审卡。
- 邻近板架厚度、材料和邻近样本展示。
- 原计划与调整后计划对照。
- 每次创建重复展示的 CCS、强度和真实几何“未验证”列表。
- 与常规创建无关的设计建议和固定等待节点。
- 与决策时间线、Safety Gate和只读操作记录重复的“板架决策护照”卡片；底层结构化决策数据继续保留。

精简行为链：

```text
需求解析
→ 参数校验
→ 工程对象解析
→ Execution Preflight
→ CAD Provider
→ 执行结果
```

页面只回答五个核心问题：用户要创建什么、参数是否合法、工程对象是否可解析、CAD 是否被调用、最终结果是什么。

板架创建页面不再提供一级 Tab，只由错误治理中的按钮进入，内容标题按模式变化：

```text
普通入口      -> 智能创建板架
历史新建详情  -> 板架创建决策详情
错误治理跳转  -> 板架更新决策详情
```

后续若更新成为稳定能力，Tab 名称统一调整为“板架创建与更新”。

### 11.3 模型错误治理主页面

模型错误治理页作为旗舰 Demo，包含以下区域。

在执行分析前提供“了解 Mock 场景”入口，先向观众交代演示假设：货船详细设计模型经历外壳版本替换和关联重算；全船约8,000个板架、约120,000个板架下子构件，当前36个错误只是从固定 Mock 数据中选择的演示快照。数量级只用于说明人工治理压力，不代表特定真实船型或实时 CAD 工程统计。

#### 11.3.1 任务输入

```text
分析当前工程全部结构错误，优先处理可以安全恢复的对象，
需要确认的集中列出，其余问题按原因整理。
```

#### 11.3.2 全船错误总览

```text
错误节点          36
根因组             4
级联错误          23
可自动恢复        11
确认后可恢复      15
需要人工处理       6
Provider异常        4
```

#### 11.3.3 根因组列表

每个根因组只显示全局处置需要的信息：

- 根对象和 CAD 原始错误码。
- 根错误、级联错误和对象类型分布。
- 影响对象数量。
- Agent 分流策略。
- Safety Gate 状态。
- 是否需要人工确认。
- 当前执行结果。

板架新建或更新操作提供“查看板架决策”入口，不在错误治理页重复堆叠板架参数和 MCP 报文。

#### 11.3.4 根因关系树

展示父板架与骨材、肘板、开孔的错误传播关系。每个节点必须标记：

- 对象类型和对象 ID。
- CAD 原始错误码。
- 根错误或级联错误。
- 数据来源和工程版本。
- 当前处置状态。

#### 11.3.5 Agent 分流看板

每个根因组展示：

- CAD 观察事实。
- 影响对象数量。
- Agent 选择的处置路径。
- 可调用的 CAD 工具。
- Safety Gate 结果。
- 是否需要人工确认。
- 处理结果。

#### 11.3.6 修复计划与结果收口

```text
处理前：36个错误
处理后：10个错误
恢复：26个
剩余工作：2组
```

剩余工作必须转换成可执行清单，而不是只显示错误数量：

1. 确认 6 个开孔的拓扑候选。
2. 将 4 个几何内核异常对象提交给研发排查。

#### 11.3.7 Trace 行为链

```text
CAD错误快照
→ Agent根因归组
→ CAD修复候选查询
→ Agent批量分流
→ Safety Gate
→ CAD修复执行
→ CAD状态复核
```

未发生的步骤显示“按策略未触发”，不得残留“等待请求”。Direct Mock 不得伪装成 MCP 调用。

### 11.4 从错误治理跳转到板架决策详情

当根因组触发 `create_panel` 或 `update_panel` 时，错误治理页提供只读深链：

```text
模型错误治理
→ 根因组A
→ PANEL-FR108
→ [查看板架决策]
→ 板架创建Tab / 板架更新决策详情
```

跳转后不得重新解析用户输入、重新调用 Graph 或再次修改 CAD。板架页通过 `operationId` 加载已完成的不可变操作快照，并显示：

- 来源错误治理任务和根因组。
- 操作类型：新建或更新。
- 目标 `panel_id`。
- CAD 错误与修复候选依据。
- 更新前后参数差异及字段来源。
- Agent 结构化决策。
- Execution / Repair Safety Gate。
- MCP Request / Response 或 Direct Mock 说明。
- CAD 执行结果和修复后对象状态。
- 子构件错误数量变化。

页面顶部显示：

```text
模型错误治理 / 根因组A / PANEL-FR108
本页面展示已有操作记录，不会重新调用CAD。
[返回错误治理]
```

### 11.5 操作关联标识

错误治理任务、根因组、Agent 决策和板架操作必须通过稳定 ID 关联：

```json
{
  "taskId": "ERROR-GOV-001",
  "errorGroupId": "GROUP-A",
  "operationId": "OP-REPAIR-108-01",
  "panelId": "PANEL-FR108",
  "operationType": "update",
  "projectRevision": "REV-18",
  "decisionRecordId": "DECISION-001"
}
```

历史详情以 `operationId` 为主键，展示决策时的工程修订快照。即使当前工程状态已经变化，也不能用最新状态覆盖历史证据。

### 11.6 Web API 划分

建议使用独立业务接口：

```text
POST /api/panel/create
POST /api/model-errors/analyze
POST /api/model-errors/repair
GET  /api/model-errors/status?taskId=ERROR-GOV-001
GET  /api/operations/{operationId}
```

其中 `GET /api/operations/{operationId}` 为只读接口，只返回 Web 白名单字段，不触发任何 CAD 调用。修改接口必须携带幂等键和预期工程版本。

### 11.7 前端状态隔离

前端分别维护：

```text
createPanelState
modelErrorGovernanceState
operationDetailState
```

每个状态独立保存请求 ID、加载状态、Trace、结果和错误。切换 Tab 不清空已完成结果，也不复用另一个 Tab 的加载状态。请求执行期间切换 Tab 不代表取消服务端任务，页面必须准确显示后台任务状态。

### 11.8 可跳转操作范围

| 操作 | 展示位置 |
|---|---|
| `create_panel` | 可跳转板架创建决策详情 |
| `update_panel` | 可跳转板架更新决策详情 |
| `recompute_objects` | 留在错误治理根因组详情 |
| 骨材、肘板、开孔操作 | 第一阶段留在错误治理页，后续按需要扩展详情页 |

通过上述结构，错误治理页回答“全船有哪些问题、Agent 如何整体处理”，板架页回答“某个板架为什么被创建或更新、调用了什么、结果如何”。

## 12. Mock 数据设计

真实 CAD Provider 未接入前，新增独立 Demo 快照，例如：

```text
mock_data/demo_model_errors.json
mock_data/demo_object_dependencies.json
mock_data/demo_repair_candidates.json
```

Mock 数据必须显式给出：

- 工程 ID 和修订版本。
- 错误对象与错误码。
- 父子及依赖关系。
- 根错误和级联错误所需证据。
- CAD 模拟修复候选。
- 修复前后的预期状态。

Agent 不得根据 FR 编号、对象名称或对象类型自行制造依赖关系。Mock 关系必须在数据中显式声明。

## 13. 分阶段开发计划

### 13.1 现有创建前智能评审退场策略

当前主流程中的“板架智能评审”以 Mock 邻近板架为样本，比较厚度、材料并展示通过、提醒、阻断和未验证项。该能力最初用于增强 Agent 决策展示，但不能代表真实结构设计、强度计算或规范校核。全船错误治理成为下一阶段主线后，它不再适合作为每次创建的必经步骤。

必须区分两类能力：

```text
创建前智能设计评审       -> 从默认主流程移除或降级
创建请求结构化安全预检   -> 必须保留
```

#### A. 从默认创建流程移除

- `design_review` Graph 固定节点。
- 基于 `demo_panel_context.json` 的邻近板厚和材料比较。
- 基于 `demo_panel_review_rules.json` 的 Mock 设计评价。
- 正常创建必须存在 `DesignReviewReport` 才能进入 CAD 的 Safety Gate 条件。
- 默认页面中的“创建前智能评审”必经卡片。
- 正常创建 Trace 中固定的“邻近样本查询、设计评审、计划调整”步骤。
- 将“结构强度、CCS、真实几何未验证”作为每次创建的重复评审项。

移除后，不得继续让 Qwen 或确定性规则根据附近板架厚度、材料影响正常创建。用户明确参数仍由 `PanelRequest` 校验后提交 CAD。

#### B. 降级为可选或兼容能力

- `schemas/design_review_schema.py`、`tools/design_review_tools.py` 和对应测试先保留一个迁移周期，标记为非默认、Demo-only。
- `mock_data/demo_panel_context.json` 与 `mock_data/demo_panel_review_rules.json` 不再参与默认创建；如保留旧演示入口，必须显式标记“历史 Mock 智能评审”。
- `DesignReviewReport` 从创建 Safety Gate 的必填输入降级为可选展示数据，不得影响常规创建授权。
- “参考同类型板架”未来仅在用户明确提出参考请求时按需触发，不恢复为所有创建请求的固定查询。
- 旧 Web DTO 字段可暂时返回空值或 `not_triggered`，待前后端版本同步后删除，避免旧页面残留“等待请求”。

#### C. 必须保留并改名为 Execution Preflight

以下检查属于执行安全边界，不属于智能设计评审：

- 用户意图是否明确为板架新建或板架更新。
- `PanelRequest` 必要字段、厚度正数、材料非空和边界至少一条的强类型校验。
- 用户原文边界解析、非法片段拦截和多轮修改规则。
- Provider 对定位面、边界对象的存在性、唯一性、可用性和角色校验。
- 新建与更新工具的权限隔离；更新必须携带现有板架 ID。
- 工程修订版本、候选有效期、对象锁定和幂等校验。
- CAD Backend / MCP 配置和可用性检查。
- Safety Gate 最终授权及受控错误映射。

代码和页面统一使用“创建请求预检”或 `Execution Preflight`，不再使用“智能设计评审”描述这些安全检查。

#### D. 简化后的创建链路

```text
Qwen参数解析
  -> Pydantic结构校验
  -> Provider对象解析
  -> Execution Preflight
  -> create_panel
  -> 创建结果
```

只有发生错误治理或用户明确请求可选参考能力时，才进入额外查询和决策分支。

#### E. 代码迁移批次

1. 先解除 `agent/graph.py` 中 Safety Gate 对 `DesignReviewReport` 的强制依赖，补齐正常创建、阻断和 Provider 失败回归。
2. 将默认 Graph 从固定 `design_review` 节点改为精简创建链，保留现有参数、边界和对象安全校验。
3. 更新 Web DTO 和 Trace，删除默认智能评审卡及等待状态，确保新旧静态资源不产生节点错配。
4. 将设计评审 Schema、工具、Mock 数据和测试标记为兼容模块；确认没有调用方后再单独删除，不与错误治理首批开发混在一次大改中。
5. 更新 `Doc/current_status.md`、`Doc/TODO.md`、README 和演示手册，明确新旧能力边界。

#### F. 退场回归要求

- 普通、参数完整的创建请求不调用 `design_review_tools`。
- 普通创建不读取邻近板架 Mock 数据。
- 删除评审后，不降低边界、对象唯一性和 Provider 安全拦截能力。
- 没有 `DesignReviewReport` 时，合法创建仍可通过 Safety Gate。
- 用户明确参数不得被历史邻近样本覆盖。
- Web 不再显示未触发评审仍在“等待请求”。
- 旧评审入口若暂时保留，必须与默认创建和全船错误治理入口隔离。
- 全量测试保持通过，新增退场行为专项回归。

### Phase 0：契约确认

1. 确认公司 CAD 错误对象的实际字段和错误码。
2. 确认能否读取父子关系、引用关系和工程版本。
3. 确认 `createPanel(id)` 更新时的字段覆盖、子构件关联和失败回滚语义。
4. 确认已有重算、刷新关联和修复候选能力。
5. 确认对象发布、锁定和并发修改状态。

本阶段可以先依据 Mock 契约开发，但必须标记为本地实验契约。

### Phase 1：L0 错误分析 Demo

- 新增错误快照和依赖 Schema。
- 新增全船错误 Mock 数据。
- 实现确定性的根错误/级联错误归组。
- 实现四类处置分流，但不执行任何修改。
- Web 将模型错误治理设为主入口；自动重算组提供“板架自动更新说明”入口，并在下钻页复用板架创建链。
- 模型错误治理页展示错误总览、依赖树、分流看板和工作清单。
- 错误治理任务与下钻的板架操作记录通过稳定ID关联，返回后恢复原任务。
- 固化 36 个错误归并为 4 个根因组的演示场景。

完成标准：Agent 能把大量错误整理为少量根因组，且不会调用任何修改工具。

### Phase 2：低风险修复编排

- 新增 `recompute_objects` 和状态复核 Mock。
- 对确定性低风险根因组执行批量重算。
- 修复父对象后重新查询子树。
- 展示处理前后错误数量变化。
- 增加版本变化、部分失败和重复提交回归。

完成标准：只对 Safety Gate 放行的重算动作执行，失败项受控保留。

### Phase 3：板架更新闭环

- 新增 Agent 层 `update_panel` 强类型工具。
- 底层映射到 `createPanel(panelId=...)` 更新语义。
- 增加修复候选、更新预览、幂等和版本门禁。
- 唯一候选允许进入确认后更新；多候选始终转人工。
- 更新后重新查询板架及子构件状态。
- 错误治理根因组增加“查看板架决策”入口。
- 板架 Tab 通过 `operationId` 只读展示更新决策，不重新执行 Graph 或 CAD 调用。
- 支持从板架详情返回原错误治理任务和根因组。

完成标准：更新意图不可能因漏传 ID 退化为新建，且修复结果可以复核。

### Phase 4：真实 CAD Provider 联调

- 用公司确认的正式错误查询和更新契约替换 Mock。
- 保持 Graph、Schema、Web DTO 和测试夹具稳定。
- 验证大数据量、部分失败、并发版本变化和事务回滚。
- 使用脱敏工程完成设计人员验收。

## 14. 测试矩阵

### 14.1 归因和依赖

- 单一根错误，无子构件。
- 一个父板架导致多级子构件错误。
- 多个根错误具有相同错误码但不同上游对象。
- 依赖图存在缺失节点或循环。
- 错误快照与依赖数据版本不一致。

### 14.2 分流

- 低风险重算进入自动执行。
- 唯一更新候选进入确认路径。
- 多个候选进入人工路径。
- 无候选进入人工路径。
- 内核异常进入 Provider 问题路径。
- LLM 输出非法动作时由确定性策略覆盖。

### 14.3 修改安全

- `create` 请求携带 `panel_id` 时拒绝。
- `update` 请求缺少 `panel_id` 时拒绝。
- 目标 ID 不存在或类型错误时拒绝。
- 工程版本变化时拒绝。
- 候选已失效时拒绝。
- 重复幂等键不会创建或更新两次。
- 更新失败不得创建新对象。
- 父对象未恢复时不修改级联子对象。

### 14.4 结果收口

- 修复后错误消失。
- 父对象恢复但部分子错误仍存在。
- 批量修复部分失败。
- 复核查询超时或返回非法数据。
- Web 统计与底层错误 ID 集合一致。

### 14.5 Web 主入口与决策深链

- 默认板架创建页不显示已退场的智能评审卡。
- 错误治理作为默认入口，页面不再显示顶部业务 Tab。
- “板架自动更新说明”可进入复用的板架创建/决策链并返回原治理任务。
- Hash 路由刷新后恢复正确的治理任务或下钻视图。
- “查看板架决策”携带正确 `taskId`、`errorGroupId` 和 `operationId`。
- 历史详情使用决策时的工程修订快照，不被当前状态覆盖。
- 打开、刷新或返回历史详情均不会再次调用修改接口。
- 不存在或无权访问的 `operationId` 返回受控错误。
- `recompute_objects` 和非板架操作不错误跳转到板架详情。
- 旧静态页面遇到新 Trace 节点时给出刷新提示，不残留虚假等待状态。

## 15. 验收标准

### 15.1 产品验收

- 观众能够区分“CAD 发现错误”和“Agent 组织处理”。
- 页面能将原始错误节点归并为根因组，并展示依据。
- 级联错误不会被当作独立根因重复处理。
- 每个根因组都有明确分流和下一步动作。
- 修复前后结果可对比，剩余问题可执行。
- 一个网址以模型错误治理为主入口，并可下钻到板架自动更新说明或单对象决策详情。
- 用户可以从根因组跳转查看单个板架创建或更新的决策详情，并返回原任务位置。
- 错误治理页保持全局摘要，板架页承载单对象详细决策，信息不重复堆叠。

### 15.2 安全验收

- Agent 不生成几何结论和拓扑候选。
- 多候选修复不自动执行。
- 更新板架必须携带现有 ID、版本和幂等键。
- 更新失败绝不降级为新建。
- Mock、MCP Contract Mock 和真实 Provider 标识清楚。
- 未接入真实 CAD 前不得声称已经修复真实工程。

### 15.3 技术验收

- 新增跨层结构全部使用 Pydantic，默认拒绝未知字段。
- 离线测试不依赖 Ollama 或真实 CAD。
- Graph 分支、Safety Gate、Provider 超时和部分失败均有回归。
- Web 只返回白名单字段，不暴露内部异常和隐藏思维链。
- 全量测试保持通过。

## 16. 效果评估指标

真实 CAD 联调后应与当前人工流程对照，不提前宣称效率收益。

建议记录：

- 原始错误节点数量。
- 归并后的根因组数量。
- 设计人员需要逐项打开的对象数量。
- 自动恢复、确认后恢复和人工处理数量。
- 从发现错误到形成处置清单的时间。
- 从开始处置到错误收口的时间。
- 无效子构件修复操作数量。
- 重复修改或误创建数量。
- 修复后再次失败的对象数量。

核心价值指标不是“Agent 调用了多少工具”，而是：

```text
减少逐项排查
+ 减少对级联错误的无效处理
+ 提高修复任务的收口率
+ 保持零误创建和零越权修改
```

## 17. 风险与待确认事项

1. 公司 CAD 是否提供完整、稳定的错误码，而不只是树节点红色状态。
2. 是否能查询跨板架、骨材、肘板和开孔的依赖关系。
3. `createPanel(id)` 是原对象原地更新，还是内部替换对象。
4. 更新时未传字段是保留、清空还是使用默认值。
5. 板架更新后子构件是自动重算、保留还是需要独立调用。
6. 更新失败是否具备事务回滚。
7. CAD 是否能返回唯一修复候选及其预览结果。
8. 对象是否存在发布、锁定、签出和多人并发状态。
9. 全船错误查询的性能和最大返回规模。
10. 哪些错误允许自动重算，必须由 CAD 团队和设计团队共同确认白名单。

## 18. 推荐实施结论

下一阶段不再以“附近板架厚度、材质比较”作为主线，也不以偏移复制作为旗舰故事。推荐顺序为：

```text
第一步：创建前 Mock 智能评审退出默认主流程，保留 Execution Preflight
第二步：全船错误读取与根因归组，只分析不修改
第三步：低风险重算与修复后复核
第四步：createPanel(id) 板架更新闭环
第五步：真实 CAD Provider 联调
```

最终演示要传达的不是“Agent 比 CAD 更懂几何”，而是：

> CAD 标记错误，Agent 理解全局；CAD 提供修复能力，Agent 组织分流；CAD 判断修复结果，Agent 负责把任务收口。
