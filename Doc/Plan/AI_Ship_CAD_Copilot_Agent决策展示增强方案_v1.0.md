# AI Ship CAD Copilot Agent 决策展示增强方案 v1.0

日期：2026-09-10
状态：方案草案，待确认后实施
定位：Demo 展示优先的最小增强，不代表已连接真实 CAD
适用范围：仅限当前 `create_panel` 板架创建流程

## 1. 背景与问题

当前系统已经完成自然语言解析、参数校验、边界原文解析、多轮补充、Mock CAD/MCP 调用和安全拦截。现有链路可靠，但从展示效果看仍接近固定 Workflow：

```text
用户输入
  -> LLM 提取参数
  -> 固定规则校验
  -> 条件满足后调用 create_panel
```

用户能够看到 LLM 参与了解析，但不容易看到 Agent 根据环境反馈进行观察、判断和调整。因此本方案增加一个短小、受约束且可视化的决策闭环：

```text
理解需求
  -> 判断下一步
  -> 查询 Mock 工程上下文
  -> 根据查询结果重新判断
  -> 安全门禁
  -> 模拟创建
```

本方案的目标不是实现通用自主 Agent，而是在不破坏现有安全边界的前提下，让 Demo 清晰呈现以下能力：

1. Agent 能说明当前观察到了什么。
2. Agent 能从有限动作中选择下一步。
3. Agent 能主动调用只读工具获取工程信息。
4. 不同查询结果会导致不同决策。
5. Agent 决策不能绕过确定性校验和 CAD 执行门禁。

## 2. Demo 展示目标

演示时应让观众在页面上直接看到：

```text
我识别到了什么
  -> 我还缺少什么证据
  -> 我决定调用什么工具
  -> 工具返回了什么
  -> 我为什么继续、澄清或停止
```

最终页面至少能表达三类故事：

| 场景 | 工具观察 | Agent 决策 | 最终效果 |
|---|---|---|---|
| 正常创建 | 定位面和边界均唯一匹配 | 允许进入创建准备 | Mock 创建成功 |
| 对象歧义 | 一个名称命中多个对象 | 请求用户选择 | 不调用创建工具 |
| 对象不存在 | 定位面或边界没有匹配 | 停止并给出建议 | 明确显示安全阻断 |

“智能感”主要来自同一个 Agent 在获得不同观察后选择不同动作，而不是来自展示长篇模型思维过程。

## 3. 范围和非目标

### 3.1 本次包含

- 一个精简的 `AgentDecision` Schema。
- 一个 `inspect_project_context` 只读 Mock 工具。
- 一份精心设计的 Demo 工程对象目录。
- 最多两次“决策 -> 观察 -> 再决策”。
- LLM 决策失败时的确定性兜底。
- Web 端 Agent 决策时间线。
- 成功、歧义、不存在三组稳定演示场景。

### 3.2 本次不包含

- 真实 CAD 实时对象查询。
- 完整、通用的 Project Provider 平台。
- Surface 几何、拓扑、相交或闭合计算。
- `<`、`>` 的几何方向解释。
- RAG、长期记忆、多 Agent。
- stiffener、bracket 或其他 CAD 对象类型。
- 自动设计、强度计算和工程规范推导。
- 创建失败后的自动重复创建。

## 4. 核心体验设计

### 4.1 成功演示

输入：

```text
在 FR100 创建14mm厚AH36板架，边界 >SL10 和 <LV5
```

页面按顺序展示：

```text
1. 需求理解
   创建对象：Panel
   定位面：FR100
   厚度：14 mm
   材料：AH36
   边界：>SL10、<LV5

2. Agent 决策
   观察：参数完整，但工程对象尚未验证
   动作：查询工程上下文
   依据：PROJECT_CONTEXT_UNVERIFIED

3. 工具观察
   FR100 -> 唯一匹配，可作为定位面
   SL10  -> 唯一匹配，可作为边界
   LV5   -> 唯一匹配，可作为边界

4. Agent 重新评估
   观察：全部对象匹配唯一，参数完整
   动作：准备创建
   依据：ALL_PRECONDITIONS_SATISFIED

5. 安全门禁
   PanelRequest 校验通过

6. CAD 执行
   Mock 创建成功
```

### 4.2 歧义演示

输入：

```text
在主甲板创建14mm厚AH36板架，边界 >SL10
```

Mock 查询返回两个候选：

```text
Main Deck A
Main Deck B
```

Agent 决策：

```text
观察：定位面名称“主甲板”匹配到两个工程对象
动作：请求用户选择
依据：REFERENCE_AMBIGUOUS
结果：CAD 工具未调用
```

### 4.3 不存在演示

输入：

```text
在 FR999 创建14mm厚AH36板架，边界 >SL10
```

Agent 决策：

```text
观察：当前 Mock 工程目录中不存在 FR999
动作：停止创建并建议可选定位面
依据：REFERENCE_NOT_FOUND
结果：CAD 工具未调用
```

这里必须避免把 `FR-10` 至 `FR200` 的语法范围等同于对象存在范围。名称格式合法与当前工程对象存在是两件事。

## 5. 目标 Graph

建议将展示链路调整为：

```text
START
  -> parse
  -> analyze
  -> decide
       |-- ask_clarification ---------------------------> END
       |-- stop ----------------------------------------> END
       |-- inspect_project_context
                 -> decide
                      |-- ask_clarification ------------> END
                      |-- stop --------------------------> END
                      `-- prepare_creation
                              -> safety_gate
                                   |-- rejected --------> END
                                   `-- approved
                                          -> cad
                                          -> END
```

节点职责：

| 节点 | 职责 | 是否允许产生 CAD 副作用 |
|---|---|---|
| `parse` | LLM 提取动作和候选参数 | 否 |
| `analyze` | 原文边界解析、缺参和格式问题整理 | 否 |
| `decide` | 根据候选参数、问题和工具观察选择下一步 | 否 |
| `inspect_project_context` | 查询 Mock 工程对象目录 | 否 |
| `safety_gate` | 确定性构造并验证 `PanelRequest` | 否 |
| `cad` | 调用已有稳定 CAD Tool | 是 |

`decide` 最多执行两次：查询前一次、查询后一次。超过上限必须安全结束，不继续循环。

## 6. AgentDecision 设计

### 6.1 建议 Schema

```python
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AgentDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    next_action: Literal[
        "inspect_project_context",
        "ask_clarification",
        "prepare_creation",
        "stop",
    ]
    reason_code: Literal[
        "MISSING_REQUIRED_FIELD",
        "INVALID_USER_INPUT",
        "PROJECT_CONTEXT_UNVERIFIED",
        "REFERENCE_NOT_FOUND",
        "REFERENCE_AMBIGUOUS",
        "BOUNDARY_NOT_FOUND",
        "BOUNDARY_AMBIGUOUS",
        "OBJECT_NOT_ELIGIBLE",
        "ALL_PRECONDITIONS_SATISFIED",
        "UNSUPPORTED_REQUEST",
        "DECISION_LIMIT_REACHED",
    ]
    observation: str
    evidence: list[str] = Field(default_factory=list)
    user_message: str | None = None
```

字段含义：

- `next_action`：从白名单中选择下一步动作。
- `reason_code`：稳定、可测试、可展示的决策原因。
- `observation`：面向用户的简短状态总结。
- `evidence`：只引用状态和工具返回中的已知事实。
- `user_message`：需要澄清或停止时的用户提示。

首版不建议展示数值置信度。Mock 对象匹配本身具有明确状态，百分比置信度容易让观众误解为工程可靠性指标。

### 6.2 AgentDecision 与现有模型的关系

| 模型 | 回答的问题 |
|---|---|
| `AgentActionPlan` | 用户总体想做什么，候选参数是什么 |
| `AgentDecision` | 根据当前状态，下一步选择做什么 |
| `ProjectInspectionResult` | Mock 工程查询实际观察到了什么 |
| `PanelRequest` | 哪些数据最终通过校验、允许提交 CAD |
| `CadExecutionResult` | CAD 工具执行结果是什么 |

模型输出的 `prepare_creation` 只是决策建议，不能直接调用 CAD。只有 `safety_gate` 成功构造 `PanelRequest` 后才能进入 `cad`。

## 7. Mock 工程查询设计

### 7.1 单一查询工具

为了控制工作量，本次只增加一个只读工具：

```python
def inspect_project_context(
    reference_plane: str | None,
    boundary_targets: list[str],
) -> ProjectInspectionResult:
    ...
```

工具职责：

1. 在固定 Demo 工程目录中匹配定位面。
2. 在同一目录中逐项匹配边界目标。
3. 检查对象是否允许承担对应角色。
4. 返回唯一命中、未找到、歧义或不可用状态。
5. 不解释边界比较符，不进行几何运算。

### 7.2 Mock 数据

建议只增加一份：

```text
mock_data/demo_project.json
```

示例结构：

```json
{
  "project_id": "demo-ship-001",
  "project_name": "Agent Demo Ship",
  "revision": "mock-r1",
  "data_source": "mock",
  "objects": [
    {
      "object_id": "ruler-fr-100",
      "name": "FR100",
      "aliases": ["FR 100", "第100肋位", "100号肋位"],
      "object_type": "ruler_plane",
      "eligible_roles": ["reference_plane", "boundary"],
      "status": "available"
    },
    {
      "object_id": "ruler-sl-10",
      "name": "SL10",
      "aliases": ["SL 10"],
      "object_type": "ruler_plane",
      "eligible_roles": ["boundary"],
      "status": "available"
    },
    {
      "object_id": "ruler-lv-5",
      "name": "LV5",
      "aliases": ["LV 5"],
      "object_type": "ruler_plane",
      "eligible_roles": ["boundary"],
      "status": "available"
    },
    {
      "object_id": "surface-main-deck-a",
      "name": "Main Deck A",
      "aliases": ["主甲板"],
      "object_type": "surface",
      "eligible_roles": ["reference_plane", "boundary"],
      "status": "available"
    },
    {
      "object_id": "surface-main-deck-b",
      "name": "Main Deck B",
      "aliases": ["主甲板"],
      "object_type": "surface",
      "eligible_roles": ["reference_plane", "boundary"],
      "status": "available"
    }
  ]
}
```

该数据集应服务于固定演示故事，而不是追求模拟完整船舶工程。页面必须显示 `Mock Project Context` 或等价标识。

### 7.3 查询结果

建议定义统一状态：

```python
ObjectMatchStatus = Literal[
    "resolved",
    "not_found",
    "ambiguous",
    "unavailable",
    "not_eligible",
]
```

完整结果示例：

```json
{
  "project_id": "demo-ship-001",
  "revision": "mock-r1",
  "data_source": "mock",
  "reference_plane": {
    "query": "FR100",
    "status": "resolved",
    "resolved_object_id": "ruler-fr-100",
    "resolved_name": "FR100",
    "candidates": []
  },
  "boundaries": [
    {
      "query": "SL10",
      "status": "resolved",
      "resolved_object_id": "ruler-sl-10",
      "resolved_name": "SL10",
      "candidates": []
    }
  ]
}
```

## 8. 决策生成与稳定性策略

### 8.1 LLM 负责的内容

- 在白名单中选择 `next_action`。
- 根据现有状态生成简短观察摘要。
- 将已知问题组织成自然的澄清提示。
- 查询结束后根据结构化观察重新选择动作。

### 8.2 确定性代码负责的内容

- 参数和边界格式是否合法。
- 工程对象匹配结果是什么。
- 对象是否允许作为定位面或边界。
- 是否能够构造 `PanelRequest`。
- 是否允许调用 CAD。
- 决策次数是否超限。

### 8.3 决策兜底

为保证现场演示稳定，LLM 返回非法 JSON、超时、未知动作或与安全事实冲突时，采用确定性决策：

```text
存在缺参或输入问题
  -> ask_clarification

尚无工程查询结果
  -> inspect_project_context

查询结果存在未找到、歧义、不可用或角色不允许
  -> ask_clarification 或 stop

对象全部唯一匹配且 PanelRequest 校验通过
  -> prepare_creation

其他情况
  -> stop
```

Trace 中记录决策来源：

```text
llm
fallback
safety_override
```

当模型建议执行但安全门禁拒绝时，页面应展示“安全规则覆盖了 Agent 建议”，这本身也是有价值的可信 Agent 展示。

## 9. 状态设计

建议在 `AgentState` 增加：

```python
decision: NotRequired[AgentDecision | None]
decision_history: NotRequired[list[AgentDecisionRecord]]
decision_count: NotRequired[int]
project_inspection: NotRequired[ProjectInspectionResult | None]
```

展示记录建议额外保留：

```python
class AgentDecisionRecord(BaseModel):
    sequence: int
    source: Literal["llm", "fallback", "safety_override"]
    decision: AgentDecision
```

`decision_history` 只保存白名单展示字段，不保存隐藏思维链、完整 Prompt、内部异常或机器路径。

## 10. Web 展示方案

### 10.1 页面结构

将现有透明执行台扩展为六个阶段，或者在现有节点之间插入两张决策卡：

```text
1. 需求理解
2. Agent 决策
3. 工程查询
4. Agent 评估
5. 安全校验
6. CAD 执行
```

每张 Agent 卡固定展示：

```text
观察到了什么
决定做什么
决策依据是什么
```

示例：

```text
Agent 观察
已识别 FR100、SL10 和 LV5，但尚无工程对象验证结果。

Agent 决策
查询 Mock 工程上下文。

决策依据
PROJECT_CONTEXT_UNVERIFIED
```

### 10.2 视觉状态

| 状态 | 建议颜色 | 含义 |
|---|---|---|
| 理解/查询中 | 蓝色 | 正在获取信息 |
| Agent 决策 | 紫色 | 正在选择下一步 |
| 等待用户 | 黄色 | 需要澄清或选择 |
| 允许执行 | 绿色 | 安全门禁通过 |
| 安全阻断 | 红色 | 未调用 CAD |

### 10.3 必须显示的真实性说明

- 工程目录：`Mock Project Context`。
- 创建后端：`Direct Mock` 或 `MCP Contract Mock`。
- “对象格式有效”与“Mock 目录中对象存在”分别展示。
- Mock 匹配成功不能描述为真实 CAD 工程验证。
- 阻断路径明确显示 `CAD tool not called`。

## 11. Trace 与 Web DTO

Trace 建议增加以下白名单字段：

```json
{
  "agent_decisions": [
    {
      "sequence": 1,
      "source": "llm",
      "next_action": "inspect_project_context",
      "reason_code": "PROJECT_CONTEXT_UNVERIFIED",
      "observation": "参数完整，但工程对象尚未验证。",
      "evidence": ["reference_plane=FR100", "boundary=SL10"]
    },
    {
      "sequence": 2,
      "source": "llm",
      "next_action": "prepare_creation",
      "reason_code": "ALL_PRECONDITIONS_SATISFIED",
      "observation": "定位面和边界均已唯一匹配。",
      "evidence": ["FR100 resolved", "SL10 resolved"]
    }
  ],
  "project_inspection": {
    "data_source": "mock",
    "project_id": "demo-ship-001",
    "revision": "mock-r1"
  }
}
```

不要将模型完整 Prompt、隐藏推理文本、异常堆栈或 Mock 数据文件绝对路径返回页面。

## 12. 文件改动建议

首版预计涉及：

```text
schemas/agent_decision_schema.py          新增 AgentDecision
schemas/project_context_schema.py         新增对象匹配与查询结果 DTO
mock_data/demo_project.json               新增精选 Demo 工程目录
tools/project_context_tools.py            新增确定性只读查询工具
agent/state.py                            增加决策和查询状态
agent/graph.py                            增加 decide/inspect/safety_gate 路由
agent/execution_trace.py                  增加决策与查询 Trace
webapp/schemas.py                         增加展示 DTO
webapp/response_mapper.py                 映射决策时间线
webapp/static/index.html                  增加 Agent 展示区域
webapp/static/app.js                      渲染决策和工具观察
webapp/static/styles.css                  增加决策状态样式
tests/test_agent_decision_schema.py       Schema 测试
tests/test_project_context_tools.py       Mock 查询测试
tests/test_agent_decision_graph.py        决策路由测试
tests/test_web_agent_decision_flow.py     页面 DTO/流程测试
```

如实现时发现现有边界对象匹配正在修改相同模块，应复用其 DTO 和匹配函数，避免并行维护两套 Mock 事实来源。

## 13. 分步实施计划

### Step 1：先做可展示的 Mock 观察

1. 定义最小工程对象和查询结果 Schema。
2. 新增 `mock_data/demo_project.json`。
3. 实现名称/别名精确匹配、角色检查和状态返回。
4. 覆盖 resolved、not_found、ambiguous、not_eligible。

完成标志：无需 Ollama，即可稳定查询三个预设演示场景。

### Step 2：加入受控 AgentDecision

1. 定义 `AgentDecision` 和决策历史。
2. 新增 `decide` 节点及严格 JSON Prompt。
3. 查询前和查询后各允许一次决策。
4. 增加确定性 fallback 和 safety override。
5. 保持只有 `PanelRequest` 能进入 CAD 层。

完成标志：同一 Graph 会根据 Mock 查询结果选择创建、澄清或停止。

### Step 3：完成 Web 决策时间线

1. 扩展 Trace 和响应 DTO。
2. 展示两次决策与中间工具观察。
3. 显示决策来源、原因码和安全门禁结果。
4. 明确 Mock 数据源及 CAD 是否被调用。

完成标志：观众不查看日志或代码，也能理解 Agent 为什么采取当前动作。

### Step 4：固化演示脚本

1. 固定成功、歧义、不存在三组输入。
2. 在 Direct Mock 下完成完整演示。
3. 如 MCP Contract Mock 同样支持对象匹配，再复验 MCP 模式。
4. 更新演示操作手册和当前状态文档。

完成标志：三类场景均可重复展示，结果不依赖真实 CAD。

## 14. 测试重点

### 14.1 决策安全测试

- 缺少定位面时不能决定创建。
- 未执行工程查询时不能进入安全门禁。
- 查询存在歧义时不能调用 CAD。
- 查询不存在时不能调用 CAD。
- 模型输出未知动作时进入 fallback。
- 模型错误建议创建时被 safety override 拦截。
- 决策次数超过上限时停止。

### 14.2 Mock 查询测试

- 正式名称唯一匹配。
- 别名唯一匹配。
- 同一别名命中多个对象。
- 对象不存在。
- 对象存在但角色不允许。
- 对象不可用。
- 比较符不参与对象名称匹配且原样保留。

### 14.3 Web 展示测试

- 成功路径显示两次决策和一次工具观察。
- 歧义路径显示候选对象和 CAD 未调用。
- 不存在路径显示阻断原因和 CAD 未调用。
- 页面显示 `Mock Project Context`。
- 不返回模型 Prompt、堆栈或机器绝对路径。

## 15. 验收标准

本方案完成需要满足：

1. 页面能展示至少两步 Agent 决策。
2. 第一次决策能主动选择查询工程上下文。
3. 第二次决策会随查询结果改变。
4. 成功、歧义和不存在场景具有不同路由。
5. 不安全场景明确显示没有调用 CAD。
6. LLM 决策异常不会破坏现场演示。
7. 所有执行请求仍必须通过 `PanelRequest`。
8. 页面明确说明查询和创建均为 Mock。
9. 自动化测试默认不依赖 Ollama 或真实 CAD。
10. 未扩展到当前范围之外的 CAD 操作。

## 16. 推荐演示话术

成功场景：

```text
系统不是识别参数后立即创建。Agent 首先判断缺少工程事实，主动查询
Mock 工程上下文；确认定位面和边界均唯一匹配后，再次评估并选择执行。
最终 CAD 调用仍受确定性 Schema 和安全门禁控制。
```

歧义场景：

```text
同样的创建意图，因为工具观察到定位面存在多个候选，Agent 改变了下一步，
转而请求用户选择，没有擅自选择第一个对象，也没有调用 CAD。
```

不存在场景：

```text
FR999 即使看起来像合法标尺名称，也不代表它存在。Agent 查询 Mock 工程目录
后发现没有对应对象，因此安全阻止创建。
```

## 17. 后续替换路径

本次演示完成后，若获得真实 CAD 接口，只替换工程查询的数据来源：

```text
当前：inspect_project_context -> demo_project.json
未来：inspect_project_context -> MCP -> C++ CAD 当前工程
```

`AgentDecision`、Graph 决策循环、Web 时间线和安全门禁可以继续保留。真实 CAD 接入前，任何 Mock 查询结果都不能宣称为真实工程事实。

## 18. 结论

本次增强不追求功能数量，而追求一条观众可理解、结果可重复、安全边界清晰的 Agent 故事：

```text
Agent 识别目标
  -> 发现证据不足
  -> 主动查询工具
  -> 根据观察重新决策
  -> 安全执行或主动停止
```

建议优先完成 Step 1 至 Step 3。它们以较小改动即可显著改善 Demo 的 Agent 感；RAG、多 Agent、复杂规划和完整 CAD Provider 暂不进入本轮。

## 19. 详细开发方案

本节将前述产品方案收敛为可直接实施的代码方案。开发原则是尽量复用当前 `parse -> validate -> cad` 主链路，不进行大规模重构。

### 19.1 推荐实现策略：混合决策

如果查询前后都额外调用一次本地 Qwen，一次创建请求可能产生三次模型调用：参数抽取、查询前决策、查询后决策。这样会增加演示等待时间，也扩大 JSON 输出不稳定的风险。

本轮推荐采用混合方式：

```text
参数抽取：Qwen
查询前决策：确定性安全策略生成 AgentDecision
工程查询查询：确定性 Mock Tool
查询后评估：Qwen 选择下一步
最终授权：确定性安全门禁生成
```

这样仍然存在真实的 Agent 决策：模型在获得工具观察后，需要从创建、澄清和停止中选择下一步；同时首轮“先查询再执行”由安全策略稳定保证。

页面必须如实显示决策来源：

```text
policy          查询前安全策略
llm             Qwen 根据查询结果后的判断
fallback        Qwen 失败后的确定性兜底
safety_override 程序否决不安全的模型建议
```

如后续实测 Qwen 延迟可以接受，可以通过配置启用两轮 LLM 决策，但不作为首版验收要求。

### 19.2 最小 Graph 改造

当前 `validate_structure()` 已完成动作 Schema、边界原文解析、缺参检查和 `PanelRequest` 校验。首版保留这些逻辑，不强制拆分为新的 `analyze` 节点。

实际改造后的最小链路：

```text
START
  -> parse
  -> validate
       |-- 模型输出可重试错误 -> parse
       `-- 其他状态 -> decide_before_inspection
              |-- clarification / unsupported / error -> END
              `-- inspect_project_context
                       -> decide_after_inspection
                              |-- clarify / stop -> END
                              `-- safety_gate
                                      |-- rejected -> END
                                      `-- cad -> END
```

现有 `route_after_validation()` 不再在 `panel_request` 存在时直接返回 `cad`，而是进入首次决策节点。

首次决策节点规则：

```python
def decide_before_inspection(state: AgentState) -> dict:
    if state.get("error"):
        return make_stop_decision(state)

    if state.get("clarification"):
        return make_clarification_decision(state)

    action_plan = state.get("action_plan")
    if action_plan is None or action_plan.action != "create_panel":
        return make_unsupported_decision(state)

    if state.get("panel_request") is None:
        return make_stop_decision(state)

    return make_inspection_decision(state)
```

这里生成的 `make_inspection_decision()` 来源标记为 `policy`。它不是伪装成 LLM 推理，而是 Agent 的安全策略：创建前必须先获得工程对象观察。

查询后节点调用 Qwen 生成第二次 `AgentDecision`，随后由确定性规则复核。路由伪代码：

```python
def route_after_inspection_decision(state: AgentState) -> str:
    decision = state.get("decision")

    if decision is None:
        return "finish"

    if decision.next_action in {"ask_clarification", "stop"}:
        return "finish"

    if decision.next_action == "prepare_creation":
        return "safety_gate"

    return "finish"
```

### 19.3 Schema 开发

新增 `schemas/agent_decision_schema.py`：

```python
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


DecisionAction = Literal[
    "inspect_project_context",
    "ask_clarification",
    "prepare_creation",
    "stop",
]

DecisionSource = Literal[
    "policy",
    "llm",
    "fallback",
    "safety_override",
]


class AgentDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    next_action: DecisionAction
    reason_code: str = Field(min_length=1)
    observation: str = Field(min_length=1)
    evidence: list[str] = Field(default_factory=list)
    user_message: str | None = None


class AgentDecisionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence: int = Field(ge=1)
    source: DecisionSource
    decision: AgentDecision
```

`reason_code` 在正式代码中建议收紧为 `Literal`。开发初期可先使用字符串并通过测试固定现有原因码，避免反复修改枚举阻碍页面联调；功能稳定后再收紧。

新增 `schemas/project_context_schema.py`：

```python
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DemoProjectObject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    object_type: Literal["ruler_plane", "surface"]
    eligible_roles: list[Literal["reference_plane", "boundary"]]
    status: Literal["available", "unavailable"]


class ObjectMatchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    role: Literal["reference_plane", "boundary"]
    status: Literal[
        "resolved",
        "not_found",
        "ambiguous",
        "unavailable",
        "not_eligible",
    ]
    resolved_object_id: str | None = None
    resolved_name: str | None = None
    candidates: list[str] = Field(default_factory=list)


class ProjectInspectionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    revision: str
    data_source: Literal["mock"]
    reference_plane: ObjectMatchResult | None = None
    boundaries: list[ObjectMatchResult] = Field(default_factory=list)
```

通过 `model_validator` 强制：

- `resolved` 必须包含 `resolved_object_id` 和 `resolved_name`。
- 非 `resolved` 不得包含 `resolved_object_id`。
- `ambiguous` 必须至少有两个候选。
- `not_found` 的候选列表必须为空。

### 19.4 Mock 数据加载与匹配算法

新增 `tools/project_context_tools.py`，首版只需要三个公开函数：

```python
def load_demo_project_catalog() -> DemoProjectCatalog:
    ...


def resolve_demo_object(
    query: str,
    *,
    role: Literal["reference_plane", "boundary"],
    catalog: DemoProjectCatalog,
) -> ObjectMatchResult:
    ...


def inspect_project_context(
    panel: PanelRequest,
) -> ProjectInspectionResult:
    ...
```

数据路径必须使用仓库相对推导：

```python
DEFAULT_DEMO_PROJECT_PATH = (
    Path(__file__).resolve().parents[1]
    / "mock_data"
    / "demo_project.json"
)
```

不得硬编码个人用户名、盘符或当前机器绝对路径。

匹配算法保持简单、确定性：

1. 去除名称两端空白。
2. 对已知 FR/SL/LV 使用现有规范化函数。
3. 对正式名称和别名做大小写不敏感的完整匹配。
4. 不做编辑距离、向量检索或 LLM 模糊匹配。
5. 无命中返回 `not_found`。
6. 多对象命中返回 `ambiguous`。
7. 唯一对象不可用返回 `unavailable`。
8. 唯一对象不允许当前角色返回 `not_eligible`。
9. 其余返回 `resolved`。

边界表达式中的 `<`、`>` 已由现有边界模块拆分；查询工具只接收 `BoundaryConstraint.target`，不得让比较符参与对象名称匹配。最终提交 CAD 时仍使用原始 operator。

### 19.5 查询后 LLM 决策 Prompt

建议单独提供一个短 Prompt，输入只包含经过白名单过滤的结构化状态：

```text
你是船舶 CAD 板架创建 Agent 的决策节点。
你只能根据给定候选参数、输入问题和 Mock 工程查询结果选择下一步。

允许动作：
- prepare_creation：所有必填参数完整，定位面和全部边界均 resolved。
- ask_clarification：存在缺失、歧义或用户可以修正的问题。
- stop：请求不支持、状态不可用或无法安全继续。

禁止事项：
- 不得声明未查询对象存在。
- 不得忽略 not_found、ambiguous、unavailable 或 not_eligible。
- 不得修改用户给出的边界比较符。
- 不得直接声称真实 CAD 已验证或已创建。

返回严格 JSON：
{
  "next_action": "prepare_creation | ask_clarification | stop",
  "reason_code": "稳定原因码",
  "observation": "一句简短观察",
  "evidence": ["最多四条已知事实"],
  "user_message": null
}
```

Prompt 后附：

```json
{
  "panel_candidate": {},
  "input_issues": [],
  "project_inspection": {}
}
```

不得把完整历史对话、MCP 原始响应、异常堆栈或本机路径发送到决策 Prompt。

### 19.6 决策复核与安全覆盖

新增纯函数：

```python
def derive_safe_action(state: AgentState) -> DecisionAction:
    ...
```

规则：

```text
有 error                         -> stop
有 clarification                 -> ask_clarification
没有 panel_request               -> stop
没有 project_inspection          -> inspect_project_context
任一匹配 ambiguous               -> ask_clarification
任一匹配 not_found               -> ask_clarification
任一匹配 unavailable/not_eligible -> stop
全部 resolved                    -> prepare_creation
```

模型动作与安全动作不一致时：

```python
safe_action = derive_safe_action(state)

if llm_decision.next_action != safe_action:
    final_decision = build_safety_override(
        llm_decision=llm_decision,
        safe_action=safe_action,
        state=state,
    )
else:
    final_decision = llm_decision
```

不要把被否决的模型自由文本直接展示给用户，只显示经过白名单过滤的建议动作、安全覆盖动作和稳定原因码。

### 19.7 Safety Gate

`safety_gate` 必须再次检查：

1. `action_plan.action == "create_panel"`。
2. `panel_request` 已存在并通过 Pydantic 校验。
3. `project_inspection` 已存在。
4. 定位面状态为 `resolved`。
5. 每条边界状态均为 `resolved`。
6. 决策动作为 `prepare_creation`。
7. 决策次数未超过上限。

建议返回：

```python
{
    "execution_authorized": True,
    "authorization_reason": "ALL_SAFETY_CHECKS_PASSED",
}
```

失败时：

```python
{
    "execution_authorized": False,
    "authorization_reason": "PROJECT_OBJECT_NOT_RESOLVED",
    "error_code": "AGENT_SAFETY_GATE_REJECTED",
}
```

`execute_cad()` 开头增加 `execution_authorized is True` 检查。即使 Graph 路由错误，也不能产生创建副作用。

### 19.8 AgentState 具体字段

在现有状态中增加：

```python
decision: NotRequired[AgentDecision | None]
decision_history: NotRequired[list[AgentDecisionRecord]]
decision_count: NotRequired[int]
project_inspection: NotRequired[ProjectInspectionResult | None]
execution_authorized: NotRequired[bool]
authorization_reason: NotRequired[str | None]
```

每次执行 Graph 时应显式初始化：

```python
{
    "decision_history": [],
    "decision_count": 0,
    "project_inspection": None,
    "execution_authorized": False,
}
```

多轮澄清重放时不得复用上一次已经过期的查询结果。用户修改定位面或边界后，必须清空 `project_inspection` 并重新查询。

### 19.9 Web API DTO

建议新增精简展示结构：

```python
class DecisionStepView(BaseModel):
    sequence: int
    source: str
    action: str
    reason_code: str
    observation: str
    evidence: list[str]


class ProjectInspectionView(BaseModel):
    project_name: str
    revision: str
    data_source_label: str
    reference_plane: ObjectMatchView | None
    boundaries: list[ObjectMatchView]
```

Web 响应增加：

```json
{
  "decision_steps": [],
  "project_inspection": null,
  "safety_gate": {
    "authorized": false,
    "reason": null
  }
}
```

保持现有字段兼容，前端新增字段缺失时应正常降级，避免影响旧测试和已有演示结果。

### 19.10 前端开发细节

页面优先复用现有执行台，不增加复杂图形库。建议：

1. 在参数解析与 CAD 调用之间增加“Agent 决策过程”区域。
2. 使用纵向时间线渲染 `decision_steps`。
3. 每条决策显示来源标签、观察、动作和原因码。
4. 工程查询结果按对象逐项显示状态徽标。
5. 安全门禁单独显示“允许执行”或“已阻断”。
6. 页面顶部继续保留 Mock 说明。

推荐文案映射：

```javascript
const actionLabels = {
  inspect_project_context: "查询工程上下文",
  ask_clarification: "请求用户补充",
  prepare_creation: "准备创建板架",
  stop: "停止执行",
};

const sourceLabels = {
  policy: "安全策略",
  llm: "Qwen 决策",
  fallback: "稳定性兜底",
  safety_override: "安全规则覆盖",
};
```

前端不直接根据自然语言推断成功或失败，颜色和状态必须依据结构化 `action`、匹配状态和 `authorized` 字段。

### 19.11 错误和降级策略

| 故障 | 处理 | 页面展示 |
|---|---|---|
| Demo JSON 缺失或非法 | 受控停止，不调用 CAD | Mock 工程目录不可用 |
| 查询工具异常 | 返回稳定错误码 | 工程查询失败 |
| 决策 LLM 超时 | 使用 fallback | 标记“稳定性兜底” |
| 决策 JSON 非法 | 使用 fallback | 标记“稳定性兜底” |
| 模型建议与事实冲突 | safety override | 标记“安全规则覆盖” |
| CAD 返回业务失败 | 保持现有受控结果 | CAD 模拟执行失败 |
| CAD 超时或结果不确定 | 不自动重试创建 | 结果无法确认 |

建议新增错误码：

```text
PROJECT_CONTEXT_LOAD_ERROR
PROJECT_CONTEXT_INVALID
AGENT_DECISION_INVALID
AGENT_DECISION_LIMIT_REACHED
AGENT_SAFETY_GATE_REJECTED
```

### 19.12 配置建议

为了 Demo 可切换而不硬编码机器信息，建议支持：

```text
PROJECT_CONTEXT_BACKEND=demo-json
DEMO_PROJECT_PATH=<可选，默认使用仓库内相对路径>
AGENT_DECISION_MODE=hybrid
AGENT_DECISION_MAX_STEPS=2
```

首版也可以只实现默认值，不要求用户配置。任何路径值都不得写入 Web 响应。

### 19.13 开发提交拆分建议

建议按四个小批次开发，便于回滚和验收：

#### 批次 A：Mock 查询基础

- Schema。
- Demo JSON。
- 确定性匹配工具。
- 单元测试。

#### 批次 B：Agent 决策闭环

- AgentDecision。
- Graph 节点和路由。
- LLM 决策 Prompt。
- fallback、safety override、safety gate。
- Graph 测试。

#### 批次 C：Web 展示

- Trace 和 Web DTO。
- 决策时间线。
- 工程对象匹配列表。
- 安全门禁状态。
- Web 测试。

#### 批次 D：演示验收

- 三个固定场景。
- Direct Mock 完整回归。
- 可选 MCP Contract Mock 回归。
- README、操作手册、current_status 和 TODO 同步。

### 19.14 详细测试矩阵

| 编号 | 输入/条件 | 首次决策 | 查询结果 | 二次决策 | CAD |
|---|---|---|---|---|---|
| D01 | FR100 + SL10 + LV5，参数完整 | inspect | 全 resolved | prepare | 调用 |
| D02 | 缺材料 | clarify | 不查询 | — | 不调用 |
| D03 | 主甲板 | inspect | ambiguous | clarify | 不调用 |
| D04 | FR999 | inspect | not_found | clarify | 不调用 |
| D05 | 边界对象不存在 | inspect | boundary not_found | clarify | 不调用 |
| D06 | 对象不允许作为定位面 | inspect | not_eligible | stop | 不调用 |
| D07 | 对象 unavailable | inspect | unavailable | stop | 不调用 |
| D08 | 决策模型非法 JSON | inspect | all resolved | fallback prepare | 调用 |
| D09 | 模型忽略 ambiguous 并建议创建 | inspect | ambiguous | safety override clarify | 不调用 |
| D10 | 决策次数超限 | — | — | stop | 不调用 |
| D11 | unsupported 意图 | stop | 不查询 | — | 不调用 |
| D12 | CAD 模拟失败 | inspect | all resolved | prepare | 调用一次并返回失败 |

测试中通过 Mock 或依赖注入固定决策模型输出，默认不得依赖正在运行的 Ollama。

### 19.15 本轮完成定义

开发完成必须同时满足：

- 现有板架边界行为保持兼容。
- 成功场景产生两条决策记录。
- 查询后确实由结构化 AgentDecision 选择下一步。
- 决策模型不可用时 Demo 仍可完成或安全停止。
- 歧义和不存在场景不会调用 `create_panel()`。
- 页面明确区分参数解析、Mock 对象查询、Agent 决策和安全授权。
- Direct Mock 页面可以稳定演示三个预设故事。
- 完整测试通过；真实 Ollama E2E 继续保持显式开启。
- 文档和页面不把 Mock 描述成真实 CAD 集成。

### 19.16 推荐实际实施顺序

```text
先实现 Mock 查询 Schema 和工具
  -> 用离线测试固定三种查询结果
  -> 接入查询前 policy 决策
  -> 接入查询后 Qwen 决策和 fallback
  -> 加 safety gate
  -> 最后开发 Web 时间线
  -> 固化三套演示输入
```

这个顺序能先稳定事实层和安全路由，再做页面效果，避免前端先依赖尚未确定的响应结构。
