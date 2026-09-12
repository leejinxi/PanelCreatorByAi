# AI Ship CAD Copilot 板架智能评审 Demo 增强开发方案 v1.0

日期：2026-09-12  
状态：已按最小增强范围实施并完成 Demo 验收<br>
定位：在现有板架创建 Agent 上增加可展示的设计评审、计划调整与决策护照  
适用范围：仅限当前 `create_panel` Demo，不代表真实 CAD、CCS 合规或结构强度集成

## 1. 背景

当前系统已经具备以下主链路：

```text
自然语言输入
  -> Qwen 参数解析
  -> PanelRequest 校验
  -> Agent 首次决策
  -> Mock 工程对象查询
  -> Qwen 查询后决策
  -> Safety Gate
  -> Direct Mock / MCP Contract Mock
```

页面已经可以展示两次结构化决策、对象匹配结果、安全门禁和 CAD Provider 调用结果。当前不足不是“没有 Agent”，而是 Agent 获得工程观察后主要只判断能否创建，缺少设计人员和管理者容易理解的以下能力：

1. 创建前是否进行过工程化检查。
2. 是否对比过已有相邻设计。
3. 是否发现风险、提醒和未覆盖能力。
4. 获得新信息后是否调整过原计划。
5. 最终对象为什么被允许创建，后续能否审计。

本方案增加一个小范围、确定性、可回归的“板架智能评审层”。它不依赖 RAG，不声称完成规范或强度校核，重点提升 Demo 的决策表现力。

## 2. 产品目标

演示结束后，观众应能明确看到：

```text
Agent理解了什么
  -> Agent查询了哪些Mock工程事实
  -> Agent执行了哪些设计检查
  -> 哪些检查通过、提醒、阻断或尚未验证
  -> Agent是否因此调整计划
  -> 为什么允许或拒绝模拟创建
  -> 本次决策留下了什么审计记录
```

目标不是增加更多装饰性流程卡片，而是让每一个结论都有结构化数据来源，并能影响最终动作。

## 3. 范围与非目标

### 3.1 本期包含

- 一份版本化的 Demo 板架评审规则包。
- Mock 工程目录中的少量既有板架快照和显式邻近关系。
- `DesignReviewReport` 及相关强类型 Schema。
- 一个确定性的 `review_panel_design` 只读工具。
- Graph 中独立的 `design_review` 节点。
- Agent 查询后决策使用评审结果，并展示计划是否发生变化。
- Web 端“创建前智能评审”和“决策护照”。
- 正常提醒、规则阻断、对象歧义三个稳定演示场景。
- 离线自动化测试；默认不依赖 Ollama 或真实 CAD。

### 3.2 本期不包含

- 向量数据库、Embedding、RAG 检索和文档切分平台。
- CCS 规范合规结论。
- 结构强度、屈曲、疲劳或有限元计算。
- 真实几何邻接、碰撞、封闭性和可制造性计算。
- 根据经验自动修改用户明确指定的板厚或材料。
- 将 Mock 相邻板架数据描述为真实工程事实。
- 通用多方案优化、长期记忆或跨项目经验学习。
- 新增 stiffener、bracket 或其他结构创建能力。

## 4. 核心演示故事

### 4.1 场景 A：参数有效，发现差异后仍安全执行

输入：

```text
在 FR100 创建14mm厚AH36板架，边界 >SL10
```

Mock 工程背景：

- FR100 和 SL10 均唯一可用。
- Mock 数据明确声明 FR99 上有一块 12mm / AH36 既有板架。
- Mock 数据明确声明 FR101 上有一块 14mm / AH36 既有板架。

页面展示：

```text
参数完整性       通过
工程对象唯一性   通过
边界角色合法性   通过
相邻板厚一致性   提醒：邻近样本包含12mm和14mm
材料一致性       通过：均为AH36
结构强度         未验证
CCS规范符合性    未验证
真实几何碰撞     未验证

Agent计划调整：
原计划：对象匹配后直接准备创建
新计划：保留用户明确指定的14mm，附加厚度差异提醒后准备创建
```

最终结果：Safety Gate 允许进入 Direct Mock 或 MCP Contract Mock；结果只能描述为模拟创建。

### 4.2 场景 B：定位面与边界引用同一对象，规则阻断

输入：

```text
在 FR100 创建14mm厚AH36板架，边界 >FR100
```

即使 FR100 同时具备定位面和边界角色，Demo 规则仍将“定位面与边界解析到同一对象”标记为阻断项：

```text
对象查询：全部唯一匹配
设计评审：阻断
命中规则：PANEL-DEMO-003
Agent计划调整：prepare_creation -> stop
Safety Gate：拒绝
CAD Provider：未调用
```

该规则仅作为 Demo 安全规则，不声称是正式 CAD 几何规则或 CCS 条款。

### 4.3 场景 C：定位面歧义，保持现有澄清能力

输入：

```text
在主甲板创建14mm厚AH36板架，边界 >SL10
```

Agent 展示两个 Mock 候选对象并请求用户选择。由于工程对象尚未唯一确定，不执行设计评审中的邻近对比，也不进入 CAD。

## 5. 目标架构

```text
START
  -> parse
  -> validate
  -> decide_before_inspection
       |-- clarify / stop ------------------------------> END
       `-- inspect_project_context
              |-- query failed -------------------------> decide_after_inspection
              `-- objects returned
                     -> design_review
                     -> decide_after_inspection
                          |-- clarify / stop ------------> END
                          `-- prepare_creation
                                 -> safety_gate
                                      |-- rejected -----> END
                                      `-- cad ----------> END
```

职责边界：

| 组件 | 负责内容 | 不负责内容 |
|---|---|---|
| Qwen 参数解析 | 从自然语言提取动作和候选参数 | 确认工程对象存在 |
| Mock Project Context | 返回对象和既有板架快照 | 代表实时 CAD 工程 |
| Design Review | 执行固定 Demo 规则 | 强度、规范和真实几何计算 |
| 查询后 Qwen 决策 | 将结构化观察组织成用户可读决策 | 推翻阻断规则 |
| Safety Gate | 对对象、评审和最终动作确定性授权 | 根据语言说服放宽限制 |
| CAD Backend | 接收通过校验的稳定请求 | 替代正式 C++ CAD 建模 |

## 6. Demo 数据设计

### 6.1 既有工程对象保持不变

继续使用 `mock_data/demo_project.json` 保存定位面和边界对象。为避免将不同职责混在同一对象列表中，建议新增独立文件：

```text
mock_data/demo_panel_context.json
```

建议内容：

```json
{
  "project_id": "demo-ship-001",
  "revision": "mock-panel-context-r1",
  "data_source": "mock",
  "reference_contexts": [
    {
      "reference_name": "FR100",
      "nearby_panels": [
        {
          "panel_id": "existing-panel-fr99",
          "name": "PANEL_FR99",
          "reference_name": "FR99",
          "thickness_mm": 12.0,
          "material": "AH36",
          "approval_state": "demo_approved_sample"
        },
        {
          "panel_id": "existing-panel-fr101",
          "name": "PANEL_FR101",
          "reference_name": "FR101",
          "thickness_mm": 14.0,
          "material": "AH36",
          "approval_state": "demo_approved_sample"
        }
      ]
    }
  ]
}
```

“邻近”关系必须由 Mock 文件显式提供，不允许通过 FR 编号自行推断真实几何邻接。

### 6.2 规则包

新增：

```text
mock_data/demo_panel_review_rules.json
Doc/Knowledge/Demo板架评审规则说明.md
```

JSON 是运行时事实，Markdown 是人可读说明。首版固定以下规则：

| 规则ID | 检查 | 结果策略 |
|---|---|---|
| `PANEL-DEMO-001` | 请求字段和边界格式已通过 `PanelRequest` | 通过，否则不进入评审 |
| `PANEL-DEMO-002` | 定位面及全部边界唯一、可用且角色合法 | 通过，否则沿用对象查询决策 |
| `PANEL-DEMO-003` | 定位面与任一边界是否解析为同一对象ID | 阻断 |
| `PANEL-DEMO-004` | 用户板厚与显式邻近样本是否存在差异 | 提醒，不修改参数 |
| `PANEL-DEMO-005` | 用户材料与显式邻近样本是否存在差异 | 提醒，不修改参数 |
| `PANEL-DEMO-006` | CCS规范符合性 | 未验证 |
| `PANEL-DEMO-007` | 结构强度 | 未验证 |
| `PANEL-DEMO-008` | 真实CAD几何与碰撞 | 未验证 |

规则文件只包含规则元数据、严重级别和展示文案。规则条件由 Python 确定性代码实现，避免把字符串表达式当代码执行。

## 7. Schema 设计

新增 `schemas/design_review_schema.py`。

```python
ReviewStatus = Literal["passed", "warning", "blocked", "not_checked"]
ReviewOutcome = Literal["passed", "passed_with_warnings", "blocked"]
PlanDisposition = Literal["unchanged", "proceed_with_notice", "stopped"]


class NearbyPanelSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    panel_id: str
    name: str
    reference_name: str
    thickness_mm: float = Field(gt=0)
    material: str
    approval_state: Literal["demo_approved_sample"]


class DesignReviewItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str
    title: str
    status: ReviewStatus
    summary: str
    evidence: list[str] = Field(default_factory=list, max_length=4)
    data_source: Literal[
        "validated_request",
        "mock_project_context",
        "demo_rule",
        "capability_boundary",
    ]


class PlanRevision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    changed: bool
    disposition: PlanDisposition
    original_plan: list[str] = Field(min_length=1, max_length=4)
    revised_plan: list[str] = Field(min_length=1, max_length=5)
    trigger_rule_ids: list[str] = Field(default_factory=list)
    summary: str


class DesignReviewReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ruleset_version: str
    project_revision: str
    data_source: Literal["mock"] = "mock"
    outcome: ReviewOutcome
    items: list[DesignReviewItem] = Field(min_length=1)
    nearby_panels: list[NearbyPanelSnapshot] = Field(default_factory=list)
    plan_revision: PlanRevision

    def has_blocker(self) -> bool:
        return any(item.status == "blocked" for item in self.items)
```

约束：

- 所有模型默认 `extra="forbid"`。
- 证据条目数量受限，不保存隐藏思维链。
- `not_checked` 必须作为正式状态，不能与 `passed` 混淆。
- `warning` 不得直接修改 `PanelRequest`。
- `blocked` 必须阻止 Safety Gate 授权。

## 8. 评审工具设计

新增：

```text
tools/design_review_tools.py
```

稳定接口：

```python
def review_panel_design(
    request: PanelRequest,
    inspection: ProjectInspectionResult,
    *,
    context_path: Path | None = None,
    rules_path: Path | None = None,
) -> DesignReviewReport:
    ...
```

执行顺序：

1. 检查 `PanelRequest` 已存在。
2. 检查 `ProjectInspectionResult.all_resolved()`。
3. 对比定位面与边界的 `resolved_object_id`。
4. 按已解析定位面名称加载显式 `reference_context`。
5. 对比板厚和材料，只生成通过或提醒。
6. 固定生成 CCS、强度、真实几何三项 `not_checked`。
7. 聚合总体结果和计划调整摘要。

异常策略：

- Mock 评审文件不存在、损坏或版本不合法：返回受控错误并停止创建。
- 找不到定位面的相邻上下文：不视为异常，返回“无可用邻近样本”。
- 不允许因相邻样本缺失而猜测设计建议。

## 9. Agent 决策与安全策略

### 9.1 AgentDecision 扩展

保持现有动作集合不变，避免扩大路由复杂度。新增两个原因码：

```python
"DESIGN_REVIEW_WARNING"
"DESIGN_REVIEW_BLOCKED"
```

查询后确定性安全决策规则调整为：

```text
对象未全部解析
  -> ask_clarification / stop

对象全部解析，但 review.has_blocker()
  -> stop + DESIGN_REVIEW_BLOCKED

对象全部解析，评审只有 warning
  -> prepare_creation + DESIGN_REVIEW_WARNING

对象全部解析，评审全部通过或未检查项之外无风险
  -> prepare_creation + ALL_PRECONDITIONS_SATISFIED
```

Qwen 可以将评审摘要转成简洁观察和依据，但不能：

- 把 `blocked` 改为 `prepare_creation`。
- 把 `not_checked` 描述为已经通过。
- 根据邻近样本改变请求厚度或材料。
- 宣称符合 CCS、强度要求或真实几何要求。

若 Qwen 动作与确定性安全决策不一致，继续使用现有 `safety_override`。

### 9.2 Safety Gate 扩展

现有条件之外增加：

```python
review is not None
and not review.has_blocker()
and review.project_revision == inspection.revision
```

Safety Gate 授权理由区分：

- `ALL_SAFETY_CHECKS_PASSED`
- `SAFETY_CHECKS_PASSED_WITH_REVIEW_WARNING`
- `DESIGN_REVIEW_BLOCKED`
- `DESIGN_REVIEW_MISSING`
- `DESIGN_REVIEW_REVISION_MISMATCH`

首版 warning 允许继续模拟创建，但页面必须保留提醒。后续如增加人工确认，可再引入 `await_confirmation`，本期不增加第三轮交互。

## 10. Web DTO 与页面设计

### 10.1 新增白名单 DTO

在 `webapp/schemas.py` 增加：

```python
class DesignReviewItemView(BaseModel):
    rule_id: str
    title: str
    status: Literal["passed", "warning", "blocked", "not_checked"]
    summary: str
    evidence: list[str]


class PlanRevisionView(BaseModel):
    changed: bool
    disposition: Literal["unchanged", "proceed_with_notice", "stopped"]
    original_plan: list[str]
    revised_plan: list[str]
    summary: str


class DesignReviewView(BaseModel):
    ruleset_version: str
    project_revision: str
    data_source_label: Literal["Demo Review Rules + Mock Project Context"]
    outcome: Literal["passed", "passed_with_warnings", "blocked"]
    items: list[DesignReviewItemView]
    nearby_panels: list[NearbyPanelView]
    plan_revision: PlanRevisionView
```

`ExecutionTraceView` 增加 `design_review`，Trace 节点增加：

```text
Qwen 参数解析
  -> Agent 首次决策
  -> Mock 工程查询
  -> 板架智能评审
  -> Qwen 结果评估
  -> Safety Gate
  -> CAD Provider
```

### 10.2 页面区域

在当前工程查询和 Agent 评估之间增加“创建前智能评审”区域：

```text
┌ AI 创建前评审 ─────────────────────────┐
│ 总体：带提醒通过                         │
│ ✓ 参数完整性                            │
│ ✓ 对象唯一性                            │
│ ! 邻近板架厚度存在差异                  │
│ — CCS规范符合性未验证                   │
│ — 结构强度未验证                        │
│ — 真实几何碰撞未验证                    │
└─────────────────────────────────────────┘

┌ Agent 计划调整 ─────────────────────────┐
│ 原计划：对象匹配后准备创建              │
│ 新计划：保留14mm并携带差异提醒后创建    │
└─────────────────────────────────────────┘
```

结果区域增加“决策护照”：

```text
请求ID / Mock对象ID
用户明确参数
解析到的工程对象
评审规则版本与工程Mock版本
最终Agent动作和理由码
Safety Gate结果
Provider模式
已验证能力
尚未验证能力
```

颜色语义统一：

- 绿色：通过。
- 黄色：提醒，但没有修改用户参数。
- 红色：阻断，CAD未调用。
- 灰色：本Demo未检查，绝不能显示为通过。

## 11. 状态与 Trace

`AgentState` 新增：

```python
design_review: NotRequired[DesignReviewReport | None]
```

Trace 增加 `design_review` 节点，但不记录：

- Qwen Prompt。
- 模型完整原始输出。
- 隐藏推理过程。
- 未经白名单过滤的内部异常。

Trace 摘要示例：

```json
{
  "name": "design_review",
  "label": "板架智能评审",
  "status": "warning",
  "summary": "5项通过，1项提醒，3项未验证",
  "details": {
    "rulesetVersion": "demo-panel-review-1.0",
    "outcome": "passed_with_warnings"
  }
}
```

若当前 `StepStatus` 不支持 `warning`，首版有两种选择：

1. 推荐：扩展为 `success | warning | error | skipped`，并补齐 CSS 和 Schema 测试。
2. 最小改动：节点状态保持 `success`，通过 `details.outcome` 和评审卡黄色样式表达提醒。

为保证状态语义准确，本方案推荐第一种。

## 12. 文件改动清单

| 文件 | 改动 |
|---|---|
| `schemas/design_review_schema.py` | 新增评审、邻近样本和计划调整模型 |
| `schemas/agent_decision_schema.py` | 增加评审相关原因码 |
| `schemas/project_context_schema.py` | 如有必要增加显式上下文引用，不混入运行时CAD对象事实 |
| `agent/state.py` | 增加 `design_review` |
| `agent/graph.py` | 增加评审节点、路由、Prompt输入和Safety Gate条件 |
| `tools/design_review_tools.py` | 确定性规则执行器 |
| `mock_data/demo_panel_context.json` | 精选既有板架和显式邻近上下文 |
| `mock_data/demo_panel_review_rules.json` | 版本化Demo规则元数据 |
| `Doc/Knowledge/Demo板架评审规则说明.md` | 人可读规则与能力边界 |
| `webapp/schemas.py` | 增加评审和决策护照DTO |
| `webapp/response_mapper.py` | 白名单映射与新Trace节点 |
| `webapp/static/index.html` | 增加评审、计划调整和护照区域 |
| `webapp/static/app.js` | 渲染通过、提醒、阻断和未验证状态 |
| `webapp/static/styles.css` | 新增评审卡和warning样式 |
| `tests/test_design_review_schema.py` | Schema约束测试 |
| `tests/test_design_review_tools.py` | 规则和数据加载测试 |
| `tests/test_agent_decision_graph.py` | 评审对Agent动作和Safety Gate的影响 |
| `tests/test_web_response_mapper.py` | DTO白名单、状态和Trace映射 |
| `tests/test_web_agent_decision_flow.py` | 三个完整Demo场景 |

## 13. 实施阶段

### Step 1：Schema、Mock数据和规则执行器

交付：

- `DesignReviewReport` 强类型模型。
- 两份版本化 Mock JSON。
- `review_panel_design()`。
- 通过、提醒、阻断、未检查和损坏数据测试。

验收：

- FR100 / 14mm / AH36 能产生板厚差异提醒。
- FR100 + 边界 FR100 能产生阻断。
- 未配置相邻样本时不猜测、不报错。
- CCS、强度和真实几何始终为 `not_checked`。

### Step 2：Graph、AgentDecision 和 Safety Gate

交付：

- `design_review` 节点接入主Graph。
- 查询后Qwen Prompt包含结构化评审摘要。
- warning继续执行，blocked停止。
- 缺失报告和版本不一致均安全阻断。

验收：

- 阻断规则命中后 `create_panel()` 调用次数为0。
- warning场景保持用户输入14mm，不被改成12mm。
- Qwen输出与安全规则冲突时触发 `safety_override`。
- Qwen异常时确定性fallback仍能完成安全决策。

### Step 3：Web智能评审与决策护照

交付：

- 七段Agent行为Trace。
- 创建前智能评审卡。
- 原计划/调整后计划对照。
- 创建成功或阻断后的决策护照。
- 静态资源版本升级，避免旧页面缓存。

验收：

- 页面可同时区分“通过、提醒、阻断、未验证”。
- Direct Mock 不出现 MCP tools/call。
- 阻断场景明确显示 Provider 未调用。
- 页面始终显示 `Mock Project Context`、`Demo Review Rules` 和模拟执行标识。

### Step 4：回归与演示固化

交付：

- 完整离线测试。
- 三个固定示例按钮。
- Demo操作说明和预期页面结果。
- 更新 `Doc/current_status.md`、`Doc/TODO.md`、README相关说明。

验收：

- `python -B -X utf8 run_tests.py` 通过，真实Ollama E2E可按设计跳过。
- 使用真实Qwen分别人工验证正常提醒、规则阻断和对象歧义。
- 不出现“符合CCS”“强度通过”“真实CAD创建成功”等越界表述。

## 14. 测试矩阵

| 场景 | 预期评审 | Agent动作 | CAD调用 |
|---|---|---|---|
| FR100 / 14mm / AH36 / >SL10 | 带提醒通过 | prepare_creation | 1次Mock |
| FR100 / 12mm / AH36 / >SL10 | 通过或较少提醒 | prepare_creation | 1次Mock |
| FR100 / 14mm / DH36 / >SL10 | 材料差异提醒 | prepare_creation | 1次Mock |
| FR100 / 14mm / AH36 / >FR100 | 阻断 | stop | 0次 |
| 主甲板 / 14mm / AH36 / >SL10 | 不进入完整评审 | ask_clarification | 0次 |
| FR999 / 14mm / AH36 / >SL10 | 不进入完整评审 | ask_clarification | 0次 |
| 评审数据文件损坏 | 受控错误 | stop | 0次 |
| 评审版本与工程版本不一致 | Safety Gate阻断 | stop | 0次 |
| Qwen建议忽略blocker | safety_override | stop | 0次 |
| Qwen建议把14mm改成12mm | 保持原请求 | prepare_creation或stop | 不得带修改值调用 |

## 15. 验收标准

本方案完成必须同时满足：

1. Agent 在对象查询后执行独立、确定性的设计评审。
2. 至少一个成功场景能展示“发现提醒但尊重用户明确参数”。
3. 至少一个场景能展示“对象都存在，但评审规则仍阻止创建”。
4. 页面能直观看到原计划、触发信息和调整后计划。
5. 创建或阻断后生成结构化决策护照。
6. 每条评审结论具有规则ID、状态、摘要和数据来源。
7. `not_checked` 不得被映射为通过。
8. warning不得擅自修改 `PanelRequest`。
9. blocker、评审缺失或版本不一致不得调用CAD Backend。
10. 所有Mock和未验证边界在页面及文档中清晰可见。

## 16. 后续扩展接口

本期完成后，未来可以在不改写主Graph语义的前提下替换数据来源：

```text
Demo Review Rules
  -> 企业设计规则服务

Mock Nearby Panels
  -> 真实CAD / PLM工程上下文Provider

not_checked: CCS
  -> 规范RAG + 确定性条款适用性规则

not_checked: Strength
  -> 专业强度计算工具

Decision Passport
  -> 企业审计、审批和设计知识沉淀
```

RAG未来只为Agent提供带出处的知识依据，不代替当前工程对象查询、确定性安全规则或正式计算程序。

## 17. 最终建议

按 `Step 1 -> Step 2 -> Step 3 -> Step 4` 顺序实施。首轮不要增加人工确认新状态、多方案自动切换或规范文档检索，先用以下三项形成完整展示闭环：

```text
相邻设计对比
  + 确定性创建前评审
  + 可追踪的计划调整与决策护照
```

这能在维持当前安全边界和稳定CAD契约的情况下，最快把Demo从“会执行固定链路”提升为“会观察工程上下文、发现问题、调整计划并解释责任边界”的板架设计Agent。
