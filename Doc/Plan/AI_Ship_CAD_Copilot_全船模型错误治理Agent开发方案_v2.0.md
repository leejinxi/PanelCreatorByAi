# AI Ship CAD Copilot 全船模型错误治理 Agent 开发方案 v2.0

日期：2026-09-13  
状态：方案更新完成，Agent 动态选择待实现  
替代关系：本方案替代 v1.0 作为后续开发依据；v1.0 保留用于追溯初始设计  
定位：在已经完成“原始错误快照 → 确定性归组”的基础上，引入受约束的 Agent 动态选择、Workflow 条件路由、Safety Gate 执行裁决和修复后复核闭环

## 1. 版本更新摘要

v1.0 确立了全船结构模型错误治理的产品方向：CAD 负责发现错误和几何合法性，Agent 负责错误归因、风险分流、修复编排和结果收口。

当前 Demo 已完成以下基础能力：

- `demo_model_errors.json` 只保存原始错误、父子关系、工程变更事件和 CAD 诊断，不再预置问题组与处置路线。
- 确定性代码沿父子关系识别根错误和级联错误，并把 36 个错误归并为 4 个问题组。
- 确定性代码根据错误码和 Provider 诊断生成修复候选与四类处置路线。
- Web 展示 36 个错误、4 个问题组、23 个级联错误，以及 26 个模拟恢复、10 个剩余错误的结果收口。
- 当前全部数据和执行仍为 Mock，不查询或修改真实 CAD 工程。

v2.0 的主要变化是将“根因识别”和“路线选择”进一步解耦：

```text
原始 CAD 事实
  -> 确定性归组
  -> 确定性计算允许路线 allowed_routes
  -> Agent 根据用户治理目标动态选择路线
  -> 确定性校验与安全降级
  -> Workflow 执行条件路由
  -> Safety Gate 最终授权
```

核心原则：

> Agent 决定在安全范围内采用哪一种治理策略；Workflow 负责执行合法控制流；Safety Gate 决定是否允许修改；CAD Provider 负责工程事实、修复候选和几何合法性。

## 2. 当前实现基线

### 2.1 已完成

当前 Mock 快照包含：

- `project_id`、`project_revision` 和 `data_source`。
- `change_events`：边界 Schema 从 `0.1-poc` 升级为 `0.2-poc`。
- `errors`：36 条未分组错误及父对象引用。
- `diagnostics`：Provider 给出的操作类型、候选对象、预校验状态和设计意图影响。

当前 `group_model_errors()` 已负责：

1. 根据 `parent_id` 沿依赖关系寻找主要错误对象。
2. 检测错误关系循环引用。
3. 根据主要错误码生成根因分类。
4. 合并同类根错误和下游级联错误。
5. 聚合根对象的 Provider 诊断。
6. 生成 `RepairCandidate` 和面向用户的证据。

### 2.2 当前局限

当前 `_route_for_group()` 直接返回一个固定路线：

```text
cause + candidate -> route
```

这属于可测试的确定性 Agent 策略，但还不能根据用户的治理指令改变执行方式。例如“只分析”“安全项自动执行”和“所有修改都需确认”目前不能对同一个错误组产生不同计划。

`execute_safe_repairs()` 目前按路线模拟修改结果，不调用真实重算、更新或复核接口。因此现阶段不得表述为真实 CAD 自动修复。

## 3. v2.0 目标与非目标

### 3.1 目标

- 支持用户用自然语言指定本次治理模式和授权偏好。
- 保持错误归组、候选合法性和允许路线计算为确定性逻辑。
- 让 Agent 在 `allowed_routes` 范围内为每个问题组动态选择路线。
- 记录决策来源、观察、证据、选择理由和安全覆盖结果。
- 让 Workflow 根据经过校验的结构化计划进入不同节点。
- LLM 不可用、输出非法或越权时能够安全降级。
- 对自动执行和确认后执行统一经过 Safety Gate。
- 修复后重新读取受影响范围，基于新快照收口结果。
- 在不接入真实 CAD 的前提下，先用 Mock Provider 完成行为和安全回归。

### 3.2 非目标

- 不让 LLM 判断真实几何是否有效。
- 不让 LLM 生成新的边界、定位面、对象 ID 或修复候选。
- 不实现强度计算、CCS 规范校核或设计正确性判断。
- 不把错误数量下降等同于工程设计验收通过。
- 不把当前 Mock 快照、修复候选或模拟结果描述成真实 CAD 事实。
- 不扩展 stiffener、bracket、opening 的通用创建工具。
- 不在本阶段接入 RAG；RAG 不得代替 CAD 工程对象查询。

## 4. 责任边界

| 能力 | CAD / Provider | 确定性策略 | Agent | Workflow / Safety Gate | 人工 |
|---|---|---|---|---|---|
| 标记错误与返回工程版本 | 负责 | 校验 | 读取 | 保存快照上下文 | 查看 |
| 返回对象关系与修复候选 | 负责 | 校验和聚合 | 不构造 | 控制调用顺序 | 必要时选择 |
| 根错误与级联识别 | 提供关系 | 负责 | 读取结果 | 编排节点 | 可复核 |
| 计算允许路线 | 提供候选事实 | 负责 | 不得扩大 | 校验 | — |
| 在允许路线中选择 | — | 提供约束 | 负责 | 验证选择 | 提供偏好与授权 |
| 判断几何是否合法 | 负责 | 不替代 | 不替代 | 根据 Provider 结果阻断 | 复核高风险结果 |
| 执行修改 | 负责 | — | 只提出计划 | Gate 授权并调用 | 审批高风险操作 |
| 修复后验证 | 返回新状态 | 比较前后状态 | 解释结果 | 强制执行复核节点 | 验收关键结果 |

## 5. 决策分层

### 5.1 第一层：确定性事实整理

输入只允许来自 Provider 或版本化规则：

- 工程 ID 和工程版本。
- 错误对象 ID、对象类型、父对象和错误码。
- Provider 修复操作和候选对象 ID。
- Provider 预校验状态。
- 候选数量和是否改变设计意图。
- 工程变更事件。

输出为 `ErrorGroup` 和 `RepairCandidate`，不产生最终执行授权。

### 5.2 第二层：确定性允许路线

将当前 `_route_for_group()` 改为 `derive_allowed_routes()`。它不替用户选择路线，而是给出 Agent 可以选择的安全集合。

建议规则：

| 事实条件 | `allowed_routes` |
|---|---|
| 几何内核异常、Provider 结果不稳定 | `provider_issue` |
| 候选缺失、候选冲突或预校验失败 | `manual` 或 `provider_issue`，由明确错误类型决定 |
| 需要重新选择边界或拓扑 | `manual` |
| 唯一 `recompute`、预校验通过、不改变设计意图 | `auto_execute`、`confirm_then_execute`、`manual` |
| 唯一 `update_panel`、预校验通过、不改变设计意图 | `confirm_then_execute`、`manual` |
| `update_panel` 可能改变设计意图 | `manual` |
| 工程版本或对象状态不可验证 | 不允许执行；重新分析或停止 |

`update_panel` 第一阶段不得进入 `auto_execute`。

### 5.3 第三层：Agent 动态选择

Agent 根据以下内容选择路线：

- 用户本轮是只分析还是允许执行。
- 用户是否允许低风险重算自动执行。
- 用户是否要求所有修改先确认。
- 用户指定的区域、对象类型或批次偏好。
- 每组的结构化观察和 `allowed_routes`。

Agent 输出必须是强类型 `RepairPlan`，不得输出自由形式工具调用。

### 5.4 第四层：确定性复核与安全覆盖

对 Agent 输出逐项检查：

- `group_id` 必须存在且不能重复。
- 每个当前问题组必须恰好有一个决定。
- `route` 必须属于该组的 `allowed_routes`。
- `candidate_id` 必须引用当前 Provider 候选。
- `auto_execute` 不得要求用户确认。
- `confirm_then_execute` 必须进入确认节点。
- 分析模式不得进入任何修改节点。
- Agent 不得增加输入中不存在的对象 ID。

模型越权时不重试执行，而是使用 `safety_override` 替换为确定性安全决策。

### 5.5 第五层：Safety Gate

Agent 决策通过 Schema 和允许路线校验后，仍然只是计划。Safety Gate 必须在修改前再次检查当前工程状态、用户授权和执行契约。

## 6. 治理意图模型

建议新增：

```python
class GovernanceIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["analyze_only", "execute_allowed"]
    low_risk_policy: Literal[
        "allow_auto_execute",
        "require_confirmation",
    ]
    confirmed_group_ids: list[str] = Field(default_factory=list)
    scope_object_ids: list[str] = Field(default_factory=list)
    max_batch_size: int | None = Field(default=None, ge=1)
```

第一阶段只需支持三个稳定演示意图：

1. `只分析，不要修改模型`。
2. `自动处理不改变设计意图的重算，其余让我确认`。
3. `所有修改都必须先确认`。

自然语言解析失败时默认：

```text
mode = analyze_only
low_risk_policy = require_confirmation
```

## 7. Agent 决策 Schema

建议新增 `schemas/repair_decision_schema.py`：

```python
RepairReasonCode = Literal[
    "ANALYSIS_ONLY",
    "LOW_RISK_RECOMPUTE",
    "USER_CONFIRMATION_REQUIRED",
    "UNIQUE_PROVIDER_CANDIDATE",
    "DESIGN_INTENT_MAY_CHANGE",
    "REPAIR_CANDIDATE_AMBIGUOUS",
    "PROVIDER_VALIDATION_FAILED",
    "PROVIDER_INTERNAL_ERROR",
    "SAFETY_POLICY_OVERRIDE",
]


class RepairGroupObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group_id: str
    root_cause_code: str
    root_object_ids: list[str]
    affected_object_ids: list[str]
    candidate: RepairCandidate | None
    allowed_routes: list[RepairRoute]


class RepairRouteDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group_id: str
    route: RepairRoute
    candidate_id: str | None
    reason_code: RepairReasonCode
    observation: str = Field(min_length=1)
    evidence: list[str] = Field(default_factory=list, max_length=5)
    requires_confirmation: bool


class RepairPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    expected_project_revision: str
    intent: GovernanceIntent
    decisions: list[RepairRouteDecision]
```

决策历史继续使用受控来源：

```python
DecisionSource = Literal["policy", "llm", "fallback", "safety_override"]
```

不得保存隐藏思维链、完整 Prompt 或模型原始推理，只保存结构化观察、证据和理由码。

## 8. Agent 输入与提示词约束

### 8.1 输入示例

```json
{
  "intent": {
    "mode": "execute_allowed",
    "low_risk_policy": "allow_auto_execute"
  },
  "project_id": "DEMO-SHIP-001",
  "project_revision": "DEMO-REV-18",
  "groups": [
    {
      "group_id": "GROUP-B",
      "root_cause_code": "PANEL_RECOMPUTE_REQUIRED",
      "root_object_ids": ["PANEL-FR104", "PANEL-FR106"],
      "candidate": {
        "candidate_id": "AGENT-GROUP-B-RECOMPUTE",
        "operation": "recompute",
        "provider_validation": "passed",
        "ambiguity_count": 0,
        "changes_design_intent": false
      },
      "allowed_routes": [
        "auto_execute",
        "confirm_then_execute",
        "manual"
      ]
    }
  ]
}
```

### 8.2 输出示例

```json
{
  "project_id": "DEMO-SHIP-001",
  "expected_project_revision": "DEMO-REV-18",
  "intent": {
    "mode": "execute_allowed",
    "low_risk_policy": "allow_auto_execute",
    "confirmed_group_ids": [],
    "scope_object_ids": [],
    "max_batch_size": null
  },
  "decisions": [
    {
      "group_id": "GROUP-B",
      "route": "auto_execute",
      "candidate_id": "AGENT-GROUP-B-RECOMPUTE",
      "reason_code": "LOW_RISK_RECOMPUTE",
      "observation": "两个父板架具有同类重算错误，Provider 候选唯一且预校验通过。",
      "evidence": [
        "operation=recompute",
        "provider_validation=passed",
        "ambiguity_count=0",
        "changes_design_intent=false"
      ],
      "requires_confirmation": false
    }
  ]
}
```

### 8.3 提示词硬约束

提示词必须明确：

- 只能依据输入中的结构化事实。
- 每组路线必须属于 `allowed_routes`。
- 只能引用输入中已有的 `group_id`、`candidate_id` 和对象 ID。
- 不得生成边界、定位面或几何候选。
- `update_panel` 不得选择 `auto_execute`。
- 多候选、候选失败或设计意图可能改变时不得自动执行。
- 只返回符合 `RepairPlan` Schema 的 JSON。

## 9. Workflow 设计

### 9.1 独立 Graph

错误治理应使用独立于板架创建的 Graph，避免两个业务的状态、决策次数和安全门相互污染。

```text
parse_governance_intent
  -> collect_error_snapshot
  -> validate_snapshot
  -> build_dependency_graph
  -> group_root_causes
  -> query_repair_candidates
  -> derive_allowed_routes
  -> decide_repair_routes
  -> validate_repair_plan
      |-- analyze_only / 无可执行项 --> summarize_remaining_work
      |-- 需要确认 ------------------> request_confirmation
      `-- 存在已授权动作 ------------> repair_safety_gate
                                          |-- rejected --> summarize_remaining_work
                                          `-- allowed ---> execute_parent_first
                                                             -> revalidate_affected_scope
                                                             -> summarize_remaining_work
```

### 9.2 State

```python
class ModelErrorAgentState(TypedDict):
    user_message: str
    intent: GovernanceIntent | None
    snapshot: ModelErrorSnapshot | None
    dependency_graph: ErrorDependencyGraph | None
    groups: list[ErrorGroup]
    observations: list[RepairGroupObservation]
    repair_plan: RepairPlan | None
    decision_history: list[RepairDecisionRecord]
    authorized_group_ids: list[str]
    execution_report: RepairExecutionReport | None
    remaining_work: list[RemainingWorkItem]
    error: str | None
    error_code: str | None
```

### 9.3 路由职责

Agent 只写入结构化 `repair_plan`。Workflow 的条件函数负责读取已校验状态：

```python
def route_after_plan(state):
    if state["intent"].mode == "analyze_only":
        return "report"
    if has_unconfirmed_actions(state):
        return "confirm"
    if has_executable_actions(state):
        return "safety_gate"
    return "report"
```

Agent 不得输出节点名称，也不能指定跳过 Safety Gate。

## 10. 确定性 fallback 与 safety override

### 10.1 触发条件

- Ollama 不可用或超时。
- 返回内容不是合法 JSON。
- `RepairPlan` Schema 校验失败。
- 缺失问题组、重复问题组或引用未知候选。
- 选择的路线不属于 `allowed_routes`。
- Agent 请求自动执行更新板架或其他禁止动作。

### 10.2 安全降级规则

```text
Provider 内部错误
  -> provider_issue

无候选 / 多候选 / 预校验失败 / 改变设计意图
  -> manual

唯一低风险 recompute
  -> confirm_then_execute

唯一 update_panel
  -> confirm_then_execute

其他未知情况
  -> manual
```

fallback 不得默认自动执行。只有 LLM 决策有效、用户明确允许且 Safety Gate 通过时，低风险重算才能进入自动执行。

## 11. Repair Safety Gate

每个计划项分别授权，不允许用一个全局布尔值笼统授权全部对象。

必须检查：

1. 当前 `project_id` 与计划一致。
2. 当前工程版本与 `expected_project_revision` 一致。
3. 目标对象全部存在且类型匹配。
4. 根因组与对象关系没有在决策后变化。
5. `candidate_id` 仍由 Provider 返回且有效。
6. Provider 预校验仍然通过。
7. 不存在未解决歧义。
8. 父对象先于子对象处理。
9. `update_panel` 必须带现有 `panel_id`，不得降级为新建。
10. 每次修改具有幂等键。
11. 用户授权覆盖当前组、动作和批次范围。
12. 分析模式永远不授权修改。

建议输出逐组结果：

```python
class RepairAuthorization(BaseModel):
    group_id: str
    authorized: bool
    reason_code: str
    checked_project_revision: str
    idempotency_key: str | None
```

## 12. 父对象优先与执行策略

执行顺序由依赖图和确定性拓扑排序生成，不由 LLM 直接排列对象列表。

```text
修复根板架
  -> CAD 关联更新
  -> 重新读取板架子树
  -> 删除已自然消失的级联错误
  -> 只对仍然存在的错误继续诊断
```

对象类型优先级只能作为没有直接依赖边时的稳定排序条件：

```text
panel -> stiffener -> bracket / opening
```

不得把当前 26 个可恢复错误简单展开成 26 次独立修改调用。

## 13. 修复后复核与结果收口

真实闭环必须由 Provider 新状态驱动：

```text
snapshot_before
  -> authorized actions
  -> Provider execution result
  -> snapshot_after
  -> compare active error IDs and object revisions
  -> resolved / remaining / newly_created / stale
```

建议执行报告至少包含：

```python
class RepairExecutionReport(BaseModel):
    project_revision_before: str
    project_revision_after: str
    attempted_group_ids: list[str]
    authorized_group_ids: list[str]
    resolved_error_ids: list[str]
    remaining_error_ids: list[str]
    new_error_ids: list[str]
    failed_actions: list[RepairActionFailure]
```

当前 Mock 阶段可以继续模拟 `26/10`，但代码和页面必须显式标记 `simulated=true`，不得把列表过滤结果描述成 Provider 重算验证。

## 14. Web Demo 更新

### 14.1 用户可见的动态选择

错误治理首页增加简洁治理指令输入或三个演示策略：

| 演示策略 | GROUP-B 低风险重算 | GROUP-A 板架更新 |
|---|---|---|
| 只分析 | 仅建议 | 仅建议 |
| 安全项自动处理 | 自动执行 | 等待确认 |
| 所有修改需确认 | 等待确认 | 等待确认 |

GROUP-C 始终人工处理，GROUP-D 始终进入 Provider 问题清单。这样可以同时展示动态决策和安全边界不随用户要求改变。

### 14.2 每组新增信息

- 结构化观察。
- Provider 候选。
- `allowed_routes`。
- Agent 选择。
- 决策来源：`llm`、`fallback` 或 `safety_override`。
- 是否需要用户确认。
- Safety Gate 结果。
- 最终执行或剩余工作状态。

### 14.3 治理轨迹

建议展示七步真实行为轨迹：

```text
解析治理意图
  -> 读取 Mock CAD 错误快照
  -> 确定性根因归组
  -> 生成允许路线
  -> Qwen 动态决策
  -> Repair Safety Gate
  -> Mock Provider 执行与结果收口
```

Trace 记录阶段、状态、耗时和安全结果，不保存 Prompt 或模型原文。

## 15. API 调整

保留现有查询接口并逐步扩展：

```text
POST /api/model-errors/analyze
POST /api/model-errors/repair/{task_id}
GET  /api/model-errors/status/{task_id}
GET  /api/operations/{operation_id}
```

建议 `analyze` 请求新增用户指令：

```json
{
  "message": "自动处理不改变设计意图的重算，其余让我确认"
}
```

返回增加：

```text
intent
decisions
decision_history
allowed_routes
confirmation_required_group_ids
simulated
```

建议后续将“分析”和“确认执行”拆开：

```text
POST /api/model-errors/tasks
POST /api/model-errors/tasks/{task_id}/confirm
POST /api/model-errors/tasks/{task_id}/execute
GET  /api/model-errors/tasks/{task_id}
```

第一阶段可以兼容旧 API，但不得让 `/repair/{task_id}` 自动视为用户确认所有高风险动作。

## 16. Provider / MCP 边界

正式 Provider 至少需要以下只读能力：

```text
list_model_errors(scope, expectedProjectRevision)
get_error_details(errorIds)
get_object_dependencies(objectIds)
get_repair_candidates(groupId, expectedProjectRevision)
get_object_status(objectIds)
```

修改能力：

```text
recompute_objects(objectIds, expectedProjectRevision, idempotencyKey)
refresh_associations(objectIds, expectedProjectRevision, idempotencyKey)
update_panel(panelId, panelRequest, repairCandidateId,
             expectedProjectRevision, idempotencyKey)
```

Provider 必须保证：

- 返回稳定对象 ID 和工程版本。
- 修复候选由 CAD 生成，不由 Agent 构造。
- 批量结果逐项返回成功、失败和错误码。
- 修改具有幂等、事务或明确的部分失败语义。
- 更新失败不得静默变成新建。
- 支持修改后重新查询受影响对象范围。

## 17. 实施步骤

### Step 1：冻结当前确定性归组基线

- 保持原始 `errors + diagnostics + change_events` 快照。
- 冻结 36/4/23 和四组根因结果测试。
- 保持循环引用、未知错误码和冲突诊断返回受控错误。

### Step 2：引入允许路线

- 新增 `RepairGroupObservation`。
- 将 `_route_for_group()` 拆为 `derive_allowed_routes()` 和保守默认路线。
- 为每条安全矩阵规则增加单元测试。

### Step 3：治理意图解析

- 新增 `GovernanceIntent`。
- 支持三个演示策略。
- 解析失败时安全降级为只分析。
- 测试用户指令冲突和不支持范围。

### Step 4：Agent 动态选择

- 新增 `RepairRouteDecision` 和 `RepairPlan`。
- 使用可注入 LLM，测试默认不得依赖 Ollama。
- 限定 Agent 只选择输入中的路线和候选。
- 增加非法 JSON、未知组、未知候选、越权路线回归。

### Step 5：计划验证与安全覆盖

- 实现 `validate_repair_plan()`。
- 实现逐组 fallback。
- 保存 `decision_history` 和决策来源。
- 确保一个组失败不会授权其他非法组。

### Step 6：独立 LangGraph

- 新增错误治理 State 和 Graph。
- 接入分析、确认、执行、复核和收口节点。
- 设置决策和复核次数上限，避免循环。

### Step 7：Web 动态演示

- 增加治理指令输入或三个策略入口。
- 展示允许路线、Agent 选择、来源和 Gate 结果。
- 确认后只执行用户授权的问题组。
- 保留 Mock 和模拟执行标识。

### Step 8：Mock Provider 执行闭环

- 将简单列表过滤替换为 Mock Provider 执行结果。
- 模拟工程版本变化、部分失败和重算后新增错误。
- 通过重新查询接口生成结果收口。

### Step 9：真实 MCP / C++ Provider

- 与 CAD 团队确认正式错误快照、依赖、候选、执行和复核契约。
- 用真实 Provider 替换 Mock，不改变 Graph 上层 Schema。
- 完成超时、断连、版本冲突和部分失败测试后才允许真实修改。

## 18. 测试矩阵

### 18.1 归组测试

- 36 条错误生成 4 个问题组和 23 个级联错误。
- 父子关系循环被拒绝。
- 未知错误码被拒绝或进入明确的未知问题分支。
- 同组冲突操作被拒绝。

### 18.2 决策测试

- 只分析模式不产生可执行授权。
- 低风险自动策略使 GROUP-B 选择 `auto_execute`。
- 全部确认策略使 GROUP-B 降为 `confirm_then_execute`。
- GROUP-A 不得自动执行。
- GROUP-C 始终为 `manual`。
- GROUP-D 始终为 `provider_issue`。
- LLM 选择允许集合之外的路线时触发 `safety_override`。
- LLM 超时、异常和非法 JSON 时使用保守 fallback。

### 18.3 Safety Gate 测试

- 工程版本变化时拒绝执行。
- 对象不存在或类型变化时拒绝执行。
- 候选失效、变多或验证失败时拒绝执行。
- 未确认的 `confirm_then_execute` 不得执行。
- `update_panel` 缺少 `panel_id` 时拒绝执行。
- 更新不得降级成新建。
- 缺少幂等键时拒绝执行。

### 18.4 执行与复核测试

- 父对象先于子对象。
- 父对象修复后已消失的级联错误不再单独执行。
- 部分失败保留已完成和未完成对象的逐项结果。
- 修复后新错误进入 `new_error_ids`。
- Provider 超时和异常映射为受控错误。

### 18.5 Web / API 测试

- 三种治理策略产生不同的结构化计划。
- 页面展示决策来源和 Safety Gate 结果。
- 确认接口只授权选中的问题组。
- Mock 模式始终明确标识为模拟。
- 任务和操作记录不存在时返回受控 404。

## 19. 验收标准

v2.0 的 Agent 动态选择完成必须同时满足：

1. `demo_model_errors.json` 不包含问题组、根对象标记或处置路线。
2. 问题组继续由确定性代码根据原始错误事实生成。
3. 每个问题组都有确定性生成的 `allowed_routes`。
4. 同一快照在不同用户治理指令下能够生成不同 `RepairPlan`。
5. Agent 只能引用现有组、对象和 Provider 候选。
6. 越权输出会被检测并安全降级。
7. Workflow 只根据经过校验的状态路由。
8. 所有修改动作必须经过逐组 Safety Gate。
9. 分析模式、LLM 故障和未知状态均不得触发修改。
10. 页面明确区分 CAD 事实、确定性约束、Agent 选择和 Gate 裁决。
11. 当前 Mock 执行继续明确标记为模拟，不宣称真实 CAD 集成。
12. 全量测试在 Python 3.11 `ai_cad_agent` 环境通过，真实 Ollama 测试保持显式启用。

## 20. 演示话术

推荐表述：

> CAD 提供错误、对象依赖和修复候选。Agent 先把全船分散错误归并为少量根因组，再根据用户本轮治理要求，在确定性安全策略允许的路线中选择自动处理、确认后处理、人工处理或提交 Provider 问题。Workflow 执行这份结构化计划，Safety Gate 在修改前重新检查工程版本、对象、候选和用户授权。Agent 不生成几何候选，也不能越过 CAD 和安全门。

避免表述：

- “AI 自动理解并修复所有 CAD 错误。”
- “Agent 能自行判断几何正确性。”
- “36 个错误恢复 26 个证明设计已经正确。”
- “当前 Demo 已经接入真实 CAD。”

## 21. 后续优先级

近期优先级：

1. 冻结原始快照和确定性归组测试。
2. 实现 `allowed_routes` 和安全矩阵。
3. 实现三种治理意图和强类型 Agent 决策。
4. 接入独立错误治理 Graph、fallback 和 safety override。
5. 更新 Web 展示，使用户能看见动态选择的实际差异。
6. 用 Mock Provider 完成真正的“执行后重新查询”闭环。
7. 等待 CAD 团队确认正式 Provider / MCP 契约后再接入真实工程。

长期原则不变：最终 CAD 模型和几何修复必须由 C++ CAD 软件完成；Python Agent 只负责自然语言理解、流程编排、参数与权限校验以及受控工具调用。
