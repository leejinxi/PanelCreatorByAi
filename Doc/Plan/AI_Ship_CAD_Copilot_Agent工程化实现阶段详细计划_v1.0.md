# AI Ship CAD Copilot

## Agent 工程化实现阶段详细计划

版本：v1.3（Agent 工程化阶段完成版）
更新时间：2026-08-19
阶段结论：强类型 Schema、工程定位面解析、CAD Tool 契约、任务路由、异常恢复、CLI 澄清和自动化测试均已完成当前阶段实现，下一阶段进入 MCP 与真实 CAD 集成。

---

# 1. 当前代码基线

本报告以仓库当前代码为准，涉及以下核心模块：

```text
PanelCreatorByAi/
├─ agent/
│  ├─ main.py                    # 示例入口
│  ├─ state.py                   # LangGraph 强类型状态定义
│  └─ graph.py                   # 解析、校验、定位面解析及 CAD 流程
├─ schemas/
│  ├─ agent_action_schema.py     # 结构化动作计划与候选参数
│  ├─ panel_schema.py            # Panel 与 CAD 执行结果 Schema
│  └─ reference_plane_schema.py  # 定位面选择器、目录记录及解析结果
├─ llm/
│  └─ qwen_client.py             # Ollama/Qwen 的 LangChain LLM 封装
├─ tools/
│  ├─ cad_tools.py               # create_panel Mock CAD 工具
│  └─ reference_plane_tools.py   # 工程定位面目录与解析算法
├─ tests/
│  ├─ test_agent_action_schema.py
│  ├─ test_agent_state.py
│  ├─ test_cad_tools.py
│  ├─ test_graph.py
│  ├─ test_local_e2e.py
│  ├─ test_main.py
│  ├─ test_panel_schema.py
│  ├─ test_qwen_client.py
│  └─ test_reference_plane_tools.py
├─ requirements.txt              # 已验证依赖版本
└─ run_tests.py                  # 统一测试入口
```

当前已实现：

- 使用 `LocalQwen` 继承 LangChain `LLM`，通过 Ollama `/api/chat` 调用 `qwen2.5:7b`。
- 请求参数启用 `format: "json"`、`temperature: 0.0`，提高结构化输出的稳定性。
- 使用 LangGraph `StateGraph` 编排 `parse`、`validate`、`resolve_plane` 和 `cad` 四个节点。
- 使用 `AgentState` 传递原始模型输出、候选 JSON、`PanelRequest`、定位面解析结果、澄清信息和 CAD 执行结果。
- 已定义 `PanelRequest`、`PanelBoundaries` 和 `CadExecutionResult` 强类型 Schema。
- 已实现定位面名称、别名和坐标解析，并支持 mm、cm、m 单位换算。
- 已处理定位面唯一匹配、多候选、未找到以及名称坐标冲突四类结果。
- LLM 漏提取定位面时，可以从用户原文和当前工程目录中恢复。
- `AgentActionPlan` 将模型动作限制为 `create_panel` 或 `unsupported`，非创建请求不会调用 CAD。
- 缺失字段、非法 JSON、Schema 校验错误和外部调用异常会受控结束，不进入 CAD。
- 非法 JSON 和非法动作计划最多自动修复重试一次。
- `create_panel()` 已绑定 `PanelRequest`，通过可替换 Backend 执行，并统一返回 `CadExecutionResult`。
- CLI 支持有限轮次参数补充、累积请求恢复、退出命令、EOF 和 Ctrl+C。
- 已建立 Schema、Resolver、Tool、Graph、CLI、Qwen Client 和可选真实 Ollama E2E 测试。

当前阶段边界：

- `list_reference_planes()` 仍使用 Mock 工程目录，尚未查询真实 CAD。
- `create_panel()` 仍由 Mock Backend 执行，尚未创建真实 CAD 对象。
- 当前本地模型不支持原生 `tool_calls`，使用结构化动作计划作为兼容实现。
- CLI 澄清通过累积输入重新运行 Graph，尚未使用 Checkpointer 做跨进程断点恢复。
- 材料仍是普通字符串，材料目录与 `resolve_material()` 已记录为后续任务。
- 定位面多候选尚未实现编号选择后的确定性状态合并。
- MCP、真实 CAD Connector、RAG 和结构化日志/请求追踪尚未接入。

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
validate：JSON、AgentActionPlan 及缺失字段判断
  ├─ unsupported → 返回能力边界，END
  ├─ 非法输出且可重试 → parse（最多一次）
  └─ create_panel → 继续
  ↓
resolve_plane：按坐标、名称、别名及 LLM 候选解析工程定位面
  ├─ ambiguous / not_found / conflict → 返回 clarification，结束
  └─ resolved → PanelRequest 强校验
  ↓
LangGraph：cad 节点
  ↓
create_panel(PanelRequest) → CreatePanelTool → CadBackend
  ↓
Mock CAD 返回 CadExecutionResult
  ↓
最终 AgentState
```

当前图结构为：

```text
START → parse → validate
                    ├─ retry → parse
                    ├─ unsupported/error/clarification → END
                    └─ create_panel → resolve_plane → cad → END
```

当前模型通过 `AgentActionPlan` 选择 `create_panel` 或 `unsupported`。这不是模型原生 `tool_calls`，但已经满足本阶段的安全路由目标：只有明确的创建板架动作通过校验后才能进入 CAD Tool。

---

# 3. 当前数据模型

## 3.1 AgentState

当前状态定义的核心字段：

```python
class AgentState(TypedDict, total=False):
    user_input: Required[str]
    llm_raw_output: NotRequired[str | None]
    action_plan: NotRequired[AgentActionPlan | None]
    structure_json: NotRequired[dict[str, Any] | None]
    panel_request: NotRequired[PanelRequest | None]
    reference_plane_resolution: NotRequired[ReferencePlaneResolution | None]
    cad_result: NotRequired[CadExecutionResult | None]
    error: NotRequired[str | None]
    error_code: NotRequired[str | None]
    retryable_error: NotRequired[bool]
    clarification: NotRequired[str | None]
    final_response: NotRequired[str | None]
    retry_count: NotRequired[int]
```

字段职责：

| 字段 | 作用 | 当前风险 |
|---|---|---|
| `user_input` | 保存用户原始需求 | 仍可补充空值、长度和输入安全限制 |
| `llm_raw_output` | 保存模型原始返回 | 便于诊断 JSON 解析问题 |
| `action_plan` | 保存模型选择的结构化动作 | Schema 限定动作范围和参数组合 |
| `structure_json` | 保存 LLM 候选参数 | 只是中间数据，不能直接提交 CAD |
| `panel_request` | 保存最终强校验请求 | 已由 `PanelRequest` 约束 |
| `reference_plane_resolution` | 保存定位面解析状态和候选项 | 为澄清与恢复执行提供依据 |
| `cad_result` | 保存 CAD 工具结果 | 已统一为 `CadExecutionResult` |
| `error` / `error_code` | 保存用户消息和稳定诊断码 | 支持模型与 CAD 错误归一化 |
| `clarification` / `final_response` | 保存澄清或非工具最终响应 | CLI 可继续补充或直接结束 |
| `retry_count` / `retryable_error` | 控制有限模型重试 | 最大自动重试一次 |

## 3.2 Panel 中间结构

当前 Prompt 生成候选结构，随后由定位面目录和 `PanelRequest` 形成最终可信结构：

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

当前 `PanelRequest` 和 `execute_cad()` 使用以下字段：

- `reference_plane`
- `boundaries`
- `thickness`
- `material`

`type` 通过 `Literal["panel"]` 校验；动作层使用 `action=create_panel` 参与任务路由。定位面解析器会把用户表达转换为实际 CAD 可识别的正式名称，再由 `PanelRequest` 传给 `create_panel()`。

---

# 4. 最新实现评估

## 4.1 已形成的工程基础

1. **模型访问层已解耦**  
   Agent 通过 `LocalQwen` 使用模型，不直接在图节点中拼装 HTTP 请求，后续可以替换模型或部署地址。

2. **状态流和校验边界已经建立**
   `parse`、`validate`、`resolve_plane` 和 `cad` 节点职责分离，候选数据只有通过工程事实解析和 Schema 校验后才能进入 CAD。

3. **业务名称已统一为 Panel**  
   当前工具和 Prompt 均以板架 `Panel` 为核心对象，符合现阶段船舶 CAD 场景。

4. **Panel Schema 与定位面解析已完成**
   已实现强类型请求、名称/别名/坐标解析、冲突拦截以及对应自动化测试。

5. **端到端安全闭环已打通**
   示例输入可以经过动作选择、模型输出检查、工程定位面解析和强校验后进入 Mock CAD；非创建请求和异常路径均不会误调用 CAD。

6. **异常恢复和测试基线已建立**
   模型输出支持一次自动修复，CLI 支持有限多轮补充；62 项离线测试和可选真实 Ollama E2E 已验证通过。

## 4.2 主要工程风险

1. 定位面以实际 CAD 支持的正式名称执行，需要保证工程目录中的名称唯一且与 CAD 一致。
2. `list_reference_planes()` 仍返回代码内 Mock 目录，没有查询当前真实 CAD 工程。
3. `create_panel()` 的 Backend 仍为 Mock，真实 CAD 的错误语义、事务和超时需要联调确认。
4. 当前结构化动作计划只支持 `create_panel` 和 `unsupported`，尚未覆盖修改、删除或其他结构对象。
5. CLI 恢复依赖累积输入重放，尚不支持跨进程状态持久化和定位面候选编号选择。
6. 材料和边界对象尚未建立类似定位面的工程目录 Resolver。
7. 模块导入时会实例化 `LocalQwen`，配置和依赖注入能力仍可继续改进。
8. 已有 Python 日志，但尚未建立请求 ID、耗时和节点级结构化日志。

---

# 5. 本阶段已实现架构

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

当前 LangGraph 流程：

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

状态：**已完成**。

计划内容：

- 定义 `PanelRequest`、`PanelBoundaries` 和 `CadExecutionResult`。
- 校验 `reference_plane` 非空且格式合理。
- 校验 `thickness > 0`，统一厚度单位为 mm。
- 校验 `material` 非空，并预留材料牌号枚举或外部规则校验。
- 明确边界字段允许为空的条件；信息不足时不得直接执行 CAD。
- 将 Schema 校验错误转换为用户可理解的澄清信息。

完成标准：非法或缺失参数不会进入 `create_panel()`。

当前交付物：

- `schemas/panel_schema.py`
- `schemas/reference_plane_schema.py`
- `tools/reference_plane_tools.py`
- `tests/test_panel_schema.py`
- `tests/test_reference_plane_tools.py`
- `Doc/Plan/Panel_Schema与定位面解析流程详细讲解_v1.0.md`

## Step 2：标准化 CAD Tool

状态：**已完成**。

改造建议：`tools/cad_tools.py`

计划内容：

- 将 `create_panel()` 声明为 LangChain Tool 或提供等价的工具描述。
- 工具入参直接绑定 Panel Schema，避免松散位置参数。
- 将 `ReferencePlaneResolution.resolved.name` 作为实际 CAD 定位面名称传入工具。
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
- 增加 Mock CAD Backend/Adapter，使 Tool 契约与具体 CAD 实现解耦。
- 将 `AgentState.cad_result` 收紧为 `CadExecutionResult | None`。
- 保持工具契约稳定，为后续 Mock、MCP 和真实 CAD 实现提供统一适配层。

完成标准：同一个 `create_panel` 工具定义可在 Mock CAD 与未来 MCP 后端之间切换。

## Step 3：升级为真正的 Tool Calling Agent

状态：**已完成兼容实现**。当前 `LocalQwen` 不支持 LangChain 原生 `tool_calls`，因此采用“结构化动作计划 + 显式条件路由”。

改造建议：`agent/graph.py`

计划内容：

- 为支持工具调用的模型绑定 `create_panel`。
- 增加 Agent 节点，根据需求决定是否调用工具。
- 增加条件边，根据 `tool_calls` 或统一动作对象决定进入 Tool 节点还是直接结束。
- 使用工具执行结果更新状态，避免固定调用 `create_panel()`。
- 若当前本地模型/接口的原生工具调用能力不足，先采用“结构化动作计划 + 显式路由”作为兼容实现。

完成标准：普通问答不调用 CAD；创建板架请求才调用 `create_panel`；未知任务返回明确说明。

当前交付：

- `AgentActionPlan` 将模型动作限制为 `create_panel` 或 `unsupported`。
- `PanelCandidate` 承载允许字段暂时缺失的 LLM 候选参数。
- 只有 `create_panel` 动作会进入定位面解析、`PanelRequest` 校验和 CAD Tool。
- 普通问答、创建其他对象和未知任务返回能力边界，不调用 CAD。
- 已使用真实 Qwen 验证创建请求与非创建请求两条路由。

## Step 4：增加异常处理与澄清流程

状态：**已完成当前阶段实现**。

计划内容：

- 捕获 Ollama 连接失败、请求超时和非 2xx 响应。
- 捕获非法 JSON，并进行有限次数的格式修复或重试。
- 对缺少基准面、厚度、材料或必要边界的请求生成澄清问题。
- 对 CAD 工具异常提供统一错误码、日志和最终用户消息。
- 在状态中增加 `error`、`retry_count`、`messages` 或等价字段。
- 保存待补全请求及定位面候选项，接收用户下一轮回复后合并状态并恢复执行。

当前已完成：

- 模型调用异常、非法 JSON、缺失字段和 Pydantic 校验错误的受控返回。
- 定位面多候选、未找到和名称坐标冲突时生成澄清文字并阻止 CAD 执行。

仍待完成：

- 当前 CLI 使用“保留多轮输入并重新执行 Graph”的兼容恢复方案；未来需要跨进程、跨界面恢复时，再引入 LangGraph Checkpointer。
- 定位面多候选的编号选择和确定性合并仍需在获得真实工程目录后完善。
- 完整结构化日志和请求追踪 ID 留待真实 CAD/MCP 接入阶段。

当前交付：

- 非法 JSON 和非法动作计划最多自动修复重试一次，失败后受控结束。
- Ollama 连接失败、超时、HTTP 错误和响应体异常统一映射为稳定错误码。
- CAD Tool 错误码同步到顶层 `AgentState`。
- CLI 支持有限轮次补充信息，并使用累积请求恢复创建流程。
- CLI 正确处理 EOF、Ctrl+C 和不包含对象 ID 的成功结果。

完成标准：常见输入或依赖异常均以受控结果结束，不向用户暴露 Python 堆栈。

## Step 5：建立自动化测试

状态：**已完成当前阶段实现**。

当前已有：

```text
tests/
├─ test_agent_action_schema.py
├─ test_agent_state.py
├─ test_cad_tools.py
├─ test_graph.py
├─ test_local_e2e.py
├─ test_main.py
├─ test_panel_schema.py
├─ test_qwen_client.py
└─ test_reference_plane_tools.py
```

统一离线测试入口：

```powershell
python -X utf8 run_tests.py
```

真实 Ollama E2E 默认跳过，需要时显式启用：

```powershell
$env:RUN_LOCAL_E2E = "1"
python -X utf8 -m unittest tests.test_local_e2e -v
```

测试范围：

- Schema：合法参数、零/负厚度、缺失材料、缺失基准面、边界格式错误。
- Tool：正确参数映射、结构化成功结果、CAD 异常转换。
- Graph：创建请求、信息不足请求、非 CAD 请求、模型返回非法 JSON。
- LLM Client：Mock HTTP 成功、超时、错误状态码和响应体缺字段。

完成标准：核心流程无需启动真实 Ollama 即可完成大部分自动化测试；另保留一项可选的本地端到端测试。

环境基线：Python 3.11，依赖版本固定在根目录 `requirements.txt`。2026-08-19 验证结果为 63 项测试，其中 62 项离线通过、1 项真实 Ollama E2E 默认跳过；显式启用 E2E 后单独运行通过。

---

# 7. 阶段任务拆解与状态

| 任务 | 当前状态 | 预计工作量 | 交付物 |
|---|---|---:|---|
| 本地 Qwen/Ollama 封装 | 已完成基础实现 | — | `llm/qwen_client.py` |
| LangGraph 四节点安全流程 | 已完成基础实现 | — | `agent/graph.py` |
| Mock `create_panel` 调用 | 已完成基础实现 | — | `tools/cad_tools.py` |
| Agent 强类型状态传递 | 已完成基础实现 | — | `agent/state.py` |
| Panel 强类型 Schema | 已完成 | — | `schemas/panel_schema.py` |
| 定位面 Schema 与解析 | 已完成 | — | Schema、Resolver 与测试 |
| Tool 标准化及结构化返回 | 已完成 | — | 可绑定的 CAD Tool |
| CAD Backend/Adapter 抽象 | 已完成基础实现 | — | Mock/MCP 可切换后端 |
| 结构化动作计划与条件路由 | 已完成兼容实现 | — | `AgentActionPlan` 与安全工具路由 |
| 模型原生 Tool Calling | 待模型能力支持 | — | 原生 `tool_calls` 绑定与执行 |
| 异常处理与有限重试 | 已完成当前阶段实现 | — | 受控错误、错误码及重试路由 |
| CLI 多轮澄清与恢复 | 已完成兼容实现 | — | 累积输入与有限轮次恢复 |
| 持久化断点恢复 | 待跨进程场景需要时实施 | — | LangGraph Checkpointer |
| 自动化测试 | 已完成当前阶段实现 | — | 统一入口、固定依赖、离线测试及可选 E2E |

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

验收结果：**通过**。动作计划选择 `create_panel`，定位面解析和 Schema 校验通过后调用标准化 CAD Tool，并返回结构化 `CadExecutionResult`。

## 场景 B：信息不足

输入：

```text
帮我创建一块板架。
```

验收结果：**通过**。缺少厚度或材料时不调用 CAD；CLI 会提示补充，并把初始需求和后续输入合并后重新执行流程。无法确定定位面时同样停止并澄清。

## 场景 C：非法业务参数

输入：

```text
在 FR100 创建一块厚度为 -5 mm 的 AH36 板架。
```

验收结果：**通过**。`PanelRequest` 校验失败，不调用 CAD，并返回厚度必须大于 0 的提示。

## 场景 D：非创建类请求

输入：

```text
AH36 是什么材料？
```

验收结果：**通过**。`AgentActionPlan.action=unsupported`，不调用 `create_panel()`，并返回当前能力边界。

## 场景 E：依赖异常

条件：Ollama 未启动或请求超时。

验收结果：**通过**。连接失败、超时、HTTP 错误和响应格式错误均转换为稳定错误码；可重试错误最多重试一次，失败后不进入 CAD。

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

以下完成条件已经全部满足，本阶段状态为：**完成**。

- Panel 请求拥有明确、可复用的强类型 Schema。
- Agent 能根据任务选择是否调用 `create_panel`，而不是固定执行 CAD 节点。
- 缺失或非法参数不会进入 CAD 层，并能触发清晰的澄清或错误响应。
- 模型服务、JSON 解析和 CAD 执行异常均得到统一处理。
- Mock CAD 返回结构化结果，接口可平滑迁移至 MCP。
- 核心 Schema、Tool 和 Graph 流程具备自动化测试。
- 至少覆盖完整创建、信息不足、非法参数、非 CAD 请求和依赖异常五类验收场景。

验证记录（2026-08-19）：

- `python -X utf8 run_tests.py`：63 项测试，62 项通过，1 项真实 Ollama E2E 默认跳过。
- `RUN_LOCAL_E2E=1`：真实 Qwen 创建/非创建两条路径通过。
- `python -m compileall`：通过。
- `pip check`：无依赖冲突。

---

# 12. 总结

当前项目已不再只是“LLM 参数解析 Demo”：最新代码已经打通自然语言输入、Qwen JSON 解析、工程定位面事实解析、Pydantic 强校验、条件拦截和 Mock CAD 调用的安全闭环。

本阶段已经完成以下工程化升级：

```text
字符串 CAD 返回 → CadExecutionResult 结构化返回
用户定位表达 → 工程正式名称解析 → 按 referenceName 执行
普通 Python 函数 → 标准化 CAD Tool Contract 与 Backend Adapter
仅面向创建请求 → 任务识别、工具选择与条件路由
单轮澄清后结束 → 累积输入、多轮补全与兼容恢复
基础异常捕获 → 有限重试与稳定错误码
部分自动化测试 → Tool/LLM Client 测试与可重复环境
```

下一阶段推荐实施顺序：

```text
确认真实 CAD 查询与创建接口
  → 用 Provider 替换 Mock 定位面目录
  → 实现 MCP/CAD Backend
  → 完成真实 CAD 联调和错误映射
  → 增加材料目录与 resolve_material
  → 根据产品形态评估 Checkpointer 和原生 tool_calls
```

当前系统已经具备向 MCP 和真实 CAD 接口迁移的稳定基础；后续工作重点是工程数据来源和真实 CAD 执行，不再是重复建设 Agent 基础流程。
