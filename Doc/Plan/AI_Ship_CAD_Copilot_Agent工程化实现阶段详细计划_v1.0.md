# AI Ship CAD Copilot

## Agent 工程化实现阶段详细计划

版本：v1.1（基于当前代码更新）  
更新时间：2026-08-13  
阶段目标：在现有“自然语言解析 + 固定 CAD 调用”闭环基础上，演进为具备结构化校验、工具选择、异常恢复和可测试性的工程化 Agent。

---

# 1. 当前代码基线

本报告以仓库当前代码为准，涉及以下核心模块：

```text
PanelCreatorByAi/
├─ agent/
│  ├─ main.py          # 示例入口
│  ├─ state.py         # LangGraph 状态定义
│  └─ graph.py         # 解析节点、CAD 节点及流程编排
├─ llm/
│  └─ qwen_client.py   # Ollama/Qwen 的 LangChain LLM 封装
└─ tools/
   └─ cad_tools.py     # create_panel Mock CAD 工具
```

当前已实现：

- 使用 `LocalQwen` 继承 LangChain `LLM`，通过 Ollama `/api/chat` 调用 `qwen2.5:7b`。
- 请求参数启用 `format: "json"`、`temperature: 0.0`，提高结构化输出的稳定性。
- 使用 LangGraph `StateGraph` 编排 `parse` 和 `cad` 两个节点。
- 使用 `AgentState` 在节点间传递用户输入、结构参数和 CAD 执行结果。
- 将自然语言需求解析为 Panel JSON，并调用 `create_panel()`。
- `create_panel()` 已接收基准面、边界、厚度和材料参数，并返回 Mock 成功结果。
- `agent/main.py` 已提供 FR100、14 mm、AH36 板架的端到端调用示例。

当前未实现：

- 模型原生 Tool Calling 或 LangChain Tool 绑定。
- Agent 自主选择工具及条件路由。
- 独立、强类型的 Panel Schema 与业务校验。
- JSON 解析失败、字段缺失、网络异常和 CAD 异常的恢复流程。
- 单元测试、集成测试及回归测试。
- MCP、真实 CAD Connector 和 RAG。

---

# 2. 当前实际运行链路

```text
用户输入
  ↓
agent/main.py
  ↓
LangGraph：parse 节点
  ↓
LocalQwen → Ollama → qwen2.5:7b
  ↓
json.loads() 生成 structure_json
  ↓
LangGraph：cad 节点
  ↓
create_panel(reference_plane, boundaries, thickness, material)
  ↓
Mock CAD 返回 "Panel created successfully"
  ↓
最终 AgentState
```

当前图结构为：

```text
START → parse → cad → END
```

这是一个已经可运行的固定工作流，但严格来说还不是能够自主决策的 Tool Calling Agent：`cad` 节点一定会执行，调用哪个工具也由代码预先确定。

---

# 3. 当前数据模型

## 3.1 AgentState

当前状态定义：

```python
class AgentState(TypedDict):
    user_input: str
    structure_json: Optional[dict]
    cad_result: Optional[str]
```

字段职责：

| 字段 | 作用 | 当前风险 |
|---|---|---|
| `user_input` | 保存用户原始需求 | 尚未做空值或长度检查 |
| `structure_json` | 保存 LLM 解析结果 | 使用通用 `dict`，缺少类型和业务校验 |
| `cad_result` | 保存 CAD 工具返回结果 | 仅支持字符串，难以表达错误码和对象 ID |

## 3.2 Panel 中间结构

当前 Prompt 约定的目标结构：

```json
{
  "type": "panel",
  "reference_plane": "FR100",
  "boundaries": {
    "top": "",
    "bottom": "",
    "left": "",
    "right": ""
  },
  "thickness": 14,
  "material": "AH36"
}
```

当前 `execute_cad()` 实际使用以下字段：

- `reference_plane`
- `boundaries`
- `thickness`
- `material`

`type` 目前只用于表达业务语义，尚未参与路由或校验。

---

# 4. 最新实现评估

## 4.1 已形成的工程基础

1. **模型访问层已解耦**  
   Agent 通过 `LocalQwen` 使用模型，不直接在图节点中拼装 HTTP 请求，后续可以替换模型或部署地址。

2. **状态流已经建立**  
   `parse` 节点只负责生成结构数据，`cad` 节点负责执行动作，职责边界基本清晰。

3. **业务名称已统一为 Panel**  
   当前工具和 Prompt 均以板架 `Panel` 为核心对象，符合现阶段船舶 CAD 场景。

4. **端到端最小闭环已打通**  
   示例输入可以经过模型解析后进入 Mock CAD，为下一步工具化改造提供可验证基线。

## 4.2 主要工程风险

1. `json.loads(result)` 无保护；模型输出不合法时流程会直接失败。
2. `data["字段"]` 使用强制索引；字段缺失时会触发 `KeyError`。
3. 厚度、材料、基准面和边界没有业务校验，错误数据可能直接进入 CAD 层。
4. `requests.post()` 只有超时和 HTTP 状态检查，尚未转换为 Agent 可理解的错误状态。
5. `create_panel()` 当前是普通 Python 函数，未声明为 Agent Tool，也没有结构化返回值。
6. 图中没有校验、澄清、重试或错误节点，不能处理信息不足的用户请求。
7. 模块导入时会立即实例化 `LocalQwen`，配置和依赖注入能力有限。

---

# 5. 本阶段目标架构

```text
自然语言需求
  ↓
Agent / 意图判断
  ↓
结构化参数生成
  ↓
Panel Schema 校验
  ├─ 信息不足 → 返回澄清问题
  ├─ 数据非法 → 修正或返回错误
  └─ 校验通过 → 选择 CAD Tool
                       ↓
                  create_panel
                       ↓
                Mock CAD / MCP Adapter
                       ↓
                  结构化执行结果
```

建议的 LangGraph 目标流程：

```text
START
  → agent
  → [是否调用工具？]
      ├─ 否 → clarification/finalize → END
      └─ 是 → validate → tool
                           ├─ 成功 → finalize → END
                           └─ 失败 → error_handler → END/重试
```

---

# 6. 分步实施计划

## Step 1：建立强类型 Panel Schema

新增建议：`schemas/panel_schema.py`

计划内容：

- 定义 `PanelRequest`、`PanelBoundaries` 和 `CadExecutionResult`。
- 校验 `reference_plane` 非空且格式合理。
- 校验 `thickness > 0`，统一厚度单位为 mm。
- 校验 `material` 非空，并预留材料牌号枚举或外部规则校验。
- 明确边界字段允许为空的条件；信息不足时不得直接执行 CAD。
- 将 Schema 校验错误转换为用户可理解的澄清信息。

完成标准：非法或缺失参数不会进入 `create_panel()`。

## Step 2：标准化 CAD Tool

改造建议：`tools/cad_tools.py`

计划内容：

- 将 `create_panel()` 声明为 LangChain Tool 或提供等价的工具描述。
- 工具入参直接绑定 Panel Schema，避免松散位置参数。
- 返回结构化结果，例如：

```json
{
  "success": true,
  "message": "Panel created successfully",
  "object_id": null,
  "error_code": null
}
```

- 将打印日志与业务返回值分离。
- 保持工具契约稳定，为后续 Mock、MCP 和真实 CAD 实现提供统一适配层。

完成标准：同一个 `create_panel` 工具定义可在 Mock CAD 与未来 MCP 后端之间切换。

## Step 3：升级为真正的 Tool Calling Agent

改造建议：`agent/graph.py`

计划内容：

- 为支持工具调用的模型绑定 `create_panel`。
- 增加 Agent 节点，根据需求决定是否调用工具。
- 增加条件边，根据 `tool_calls` 或统一动作对象决定进入 Tool 节点还是直接结束。
- 使用工具执行结果更新状态，避免固定调用 `create_panel()`。
- 若当前本地模型/接口的原生工具调用能力不足，先采用“结构化动作计划 + 显式路由”作为兼容实现。

完成标准：普通问答不调用 CAD；创建板架请求才调用 `create_panel`；未知任务返回明确说明。

## Step 4：增加异常处理与澄清流程

计划内容：

- 捕获 Ollama 连接失败、请求超时和非 2xx 响应。
- 捕获非法 JSON，并进行有限次数的格式修复或重试。
- 对缺少基准面、厚度、材料或必要边界的请求生成澄清问题。
- 对 CAD 工具异常提供统一错误码、日志和最终用户消息。
- 在状态中增加 `error`、`retry_count`、`messages` 或等价字段。

完成标准：常见输入或依赖异常均以受控结果结束，不向用户暴露 Python 堆栈。

## Step 5：建立自动化测试

建议新增：

```text
tests/
├─ test_panel_schema.py
├─ test_cad_tools.py
├─ test_graph.py
└─ test_qwen_client.py
```

测试范围：

- Schema：合法参数、零/负厚度、缺失材料、缺失基准面、边界格式错误。
- Tool：正确参数映射、结构化成功结果、CAD 异常转换。
- Graph：创建请求、信息不足请求、非 CAD 请求、模型返回非法 JSON。
- LLM Client：Mock HTTP 成功、超时、错误状态码和响应体缺字段。

完成标准：核心流程无需启动真实 Ollama 即可完成大部分自动化测试；另保留一项可选的本地端到端测试。

---

# 7. 阶段任务拆解与状态

| 任务 | 当前状态 | 预计工作量 | 交付物 |
|---|---|---:|---|
| 本地 Qwen/Ollama 封装 | 已完成基础实现 | — | `llm/qwen_client.py` |
| LangGraph 固定双节点流程 | 已完成 | — | `agent/graph.py` |
| Mock `create_panel` 调用 | 已完成基础实现 | — | `tools/cad_tools.py` |
| Agent 状态传递 | 已完成基础实现 | — | `agent/state.py` |
| Panel 强类型 Schema | 待实施 | 0.5～1 天 | Schema 与业务校验 |
| Tool 标准化及结构化返回 | 待实施 | 0.5～1 天 | 可绑定的 CAD Tool |
| Tool Calling 与条件路由 | 待实施 | 1～2 天 | Agent/Tool/Finalize 图流程 |
| 异常恢复与用户澄清 | 待实施 | 1 天 | 错误节点及重试策略 |
| 自动化测试 | 待实施 | 1～2 天 | 单元及流程测试集 |

以上工期为当前最小代码规模下的工程估算，不包含真实 CAD 接口联调。

---

# 8. 验收场景

## 场景 A：完整创建请求

输入：

```text
请在 FR100 创建一块 14 mm 厚的 AH36 板架。
```

期望结构参数：

```json
{
  "type": "panel",
  "reference_plane": "FR100",
  "boundaries": {
    "top": "",
    "bottom": "",
    "left": "",
    "right": ""
  },
  "thickness": 14,
  "material": "AH36"
}
```

当前版本预期：固定调用 `create_panel()`，返回 `Panel created successfully`。  
目标版本预期：Schema 校验通过后由 Agent 选择 `create_panel`，返回结构化执行结果。

## 场景 B：信息不足

输入：

```text
帮我创建一块板架。
```

目标行为：不调用 CAD，询问基准面、厚度、材料及必要边界。

## 场景 C：非法业务参数

输入：

```text
在 FR100 创建一块厚度为 -5 mm 的 AH36 板架。
```

目标行为：校验失败，不调用 CAD，返回厚度必须大于 0 的提示。

## 场景 D：非创建类请求

输入：

```text
AH36 是什么材料？
```

目标行为：不调用 `create_panel()`；在尚未接入知识库时，应明确能力边界。

## 场景 E：依赖异常

条件：Ollama 未启动或请求超时。

目标行为：返回可诊断的模型服务错误，不进入 CAD 节点。

---

# 9. MCP 迁移设计

当前链路：

```text
Agent → Python create_panel → Mock CAD
```

目标链路：

```text
Agent → 稳定 Tool Contract → MCP Client → MCP Server → CAD Connector → C++ CAD
```

迁移原则：

- Agent 依赖工具契约，不直接依赖 CAD SDK 或 MCP 传输细节。
- Mock 与 MCP 实现使用相同的请求及返回 Schema。
- Tool 层负责超时、错误码和结果归一化。
- CAD 对象创建成功后返回稳定的对象标识，便于后续查询、修改和撤销。

---

# 10. 后续能力路线

## Phase 4：MCP 与真实 CAD

- 实现 MCP Client/Server。
- 接入 CAD Connector 和 C++ CAD 能力。
- 完成对象 ID、事务、超时和错误映射。

## Phase 5：RAG 专业知识库

- 接入船舶结构知识、企业标准、材料规范和 CAD 建模规则。
- 为参数补全和设计解释提供可追溯依据。

## Phase 6：结构关系与多工具协同

- 增加 `get_reference_plane()`、`query_structure_objects()`。
- 增加 `create_stiffener()`、`create_bracket()` 等工具。
- 支持自动寻找边界、识别结构关系及多步骤建模。

---

# 11. 本阶段完成定义（Definition of Done）

满足以下条件后，可认为 Agent 工程化阶段完成：

- Panel 请求拥有明确、可复用的强类型 Schema。
- Agent 能根据任务选择是否调用 `create_panel`，而不是固定执行 CAD 节点。
- 缺失或非法参数不会进入 CAD 层，并能触发清晰的澄清或错误响应。
- 模型服务、JSON 解析和 CAD 执行异常均得到统一处理。
- Mock CAD 返回结构化结果，接口可平滑迁移至 MCP。
- 核心 Schema、Tool 和 Graph 流程具备自动化测试。
- 至少覆盖完整创建、信息不足、非法参数、非 CAD 请求和依赖异常五类验收场景。

---

# 12. 总结

当前项目已不再只是“LLM 参数解析 Demo”：最新代码已经打通自然语言输入、Qwen JSON 解析、LangGraph 状态传递和 Mock CAD 调用的最小闭环。

下一阶段的重点不是重复搭建固定流程，而是完成以下工程化升级：

```text
松散 JSON → 强类型业务 Schema
固定节点调用 → Agent 工具选择与条件路由
普通 Python 函数 → 标准化 CAD Tool Contract
异常直接中断 → 校验、澄清、重试与错误归一化
人工验证 → 自动化回归测试
```

完成上述升级后，系统将具备向 MCP 和真实 CAD 接口迁移的稳定基础。
