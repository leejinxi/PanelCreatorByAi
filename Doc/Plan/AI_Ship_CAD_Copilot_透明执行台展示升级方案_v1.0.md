# AI Ship CAD Copilot 透明执行台展示升级方案

版本：v1.0
日期：2026-09-10
状态：待实施
目标：在没有真实 CAD 接口的条件下，把已经跑通的 Ollama、LangGraph、强类型 Schema、MCP STDIO 和 Contract Mock 链路转化为直观、可信、可录屏的展示成果。

---

# 1. 背景与问题

当前系统已经跑通以下链路：

~~~text
浏览器
  -> FastAPI
  -> LangGraph
  -> 本地 Ollama / Qwen
  -> PanelRequest 校验
  -> McpCadBackend
  -> MCP STDIO Contract Mock Server
  -> 模拟 CAD 结果
  -> Web 页面
~~~

当前页面主要展示输入、三个步骤、结构化参数和最终 JSON。技术链路虽然真实运行，但观众只能看到“创建成功”和模拟对象 ID，难以判断 Ollama、LangGraph、Schema 和 MCP 是否真正参与执行。

由于公司环境目前只有原生 CAD API，尚无可供个人 PC 调用的 CAD Adapter 或 MCP Server，本阶段不能展示真实 CAD 软件中的模型变化。继续把页面包装成 CAD 建模结果会削弱可信度。

因此，本阶段的展示重点调整为：

> 展示自然语言如何经过本地模型理解、安全校验和标准 MCP 调用，形成一份可以交给未来公司 CAD Adapter 执行的结构化请求。

---

# 2. 展示目标

升级后的页面要让非技术观众在一次操作中看懂五件事：

1. 用户只输入自然语言。
2. 本地 Qwen 提取板架参数，不把模型输出直接当作 CAD 指令。
3. LangGraph 和 Pydantic 决定请求能否继续执行。
4. 系统真实执行 MCP STDIO 的 tools/call。
5. 当前最后一步是 Contract Mock；未来只替换 CAD Provider，不重写上层链路。

页面必须持续显示“SIMULATED”或“MCP Contract Mock”，不能暗示已经连接真实 CAD。

---

# 3. 方案结论

采用“透明执行台 + MCP 调用检查器 + 模拟 CAD 预览 + Provider 替换说明”的单页方案。

保留当前原生 HTML、CSS、JavaScript 和 FastAPI，不引入 React、Vue、WebSocket、SSE 或新的前端构建链。

本阶段仍采用一次 HTTP 请求返回完整结果。页面在等待期间播放流程状态，收到响应后用真实返回的 execution_trace 填充每个节点。

目标页面结构：

~~~text
┌─────────────────────────────────────────────────────────────────┐
│ AI Ship CAD Copilot   LOCAL QWEN   LANGGRAPH   MCP STDIO   MOCK │
├───────────────────────┬─────────────────────────────────────────┤
│ 01 自然语言命令       │ 02 透明执行链路                         │
│                       │                                         │
│ [输入框]              │ Qwen -> LangGraph -> Schema -> MCP -> CAD│
│ [开始执行]            │ 每个节点显示状态、耗时和关键输出          │
│ [固定演示场景]        │                                         │
├───────────────────────┼─────────────────────────────────────────┤
│ 03 MCP 调用检查器     │ 04 SIMULATED CAD PREVIEW                │
│ Request / Response    │ 板架示意、FR100、t=14、AH36、对象 ID     │
├───────────────────────┴─────────────────────────────────────────┤
│ 05 Provider 替换边界：Contract Mock -> Company CAD Adapter      │
└─────────────────────────────────────────────────────────────────┘
~~~

---

# 4. 页面信息架构

## 4.1 顶部可信状态栏

显示：

- Local Model：Qwen 2.5 7B
- Orchestrator：LangGraph
- Contract：Panel Contract 0.1-poc
- MCP Transport：STDIO
- Provider：Contract Mock
- 状态水印：CAD EXECUTION SIMULATED

健康接口当前只确认运行模式，不探测 Ollama 或 MCP 实际连接。页面文字应使用“配置完成”或“本次请求已执行”，不使用“真实 CAD 已连接”。

## 4.2 自然语言命令区

保留当前输入和多轮澄清能力。

固定快捷场景：

- 完整创建：在第100肋位创建14mm厚AH36板架
- 缺少材料：在第100肋位创建14mm厚板架
- 能力边界：请解释AH36是什么材料

执行期间锁定输入、清空、新任务和示例按钮。新请求开始时清空旧参数、旧 Request ID、旧 Trace 和旧 MCP 报文。

## 4.3 透明执行链路

将当前三个步骤扩展为五个可解释节点：

| 节点 | 页面标题 | 展示内容 |
|---|---|---|
| 1 | Local Qwen | 自然语言已解析、模型名称、耗时 |
| 2 | LangGraph | 实际路由，例如 parse -> validate -> cad |
| 3 | Pydantic Schema | PanelRequest 校验通过或缺少字段 |
| 4 | MCP STDIO | initialize、tools/list、tools/call 的执行摘要 |
| 5 | CAD Provider | Contract Mock 成功、业务失败或跳过 |

状态限定为：

- waiting
- running
- success
- attention
- error
- skipped

澄清场景必须突出：Schema 节点拦截，MCP 和 CAD Provider 均为 SKIPPED。这是安全价值的核心展示。

## 4.4 MCP 调用检查器

默认展示经过脱敏和白名单筛选的 MCP 请求：

~~~json
{
  "transport": "stdio",
  "method": "tools/call",
  "tool": "create_panel",
  "contractVersion": "0.1-poc",
  "arguments": {
    "referenceName": "FR100",
    "thicknessMm": 14,
    "material": "AH36",
    "boundaries": {
      "top": null,
      "bottom": null,
      "left": null,
      "right": null
    }
  }
}
~~~

响应区域展示：

~~~json
{
  "success": true,
  "objectId": "mock-mcp-panel-001",
  "errorCode": null
}
~~~

不展示：

- MCP 子进程绝对路径
- Python 解释器路径
- traceback
- 原始异常
- 完整 Prompt
- 未经筛选的 LLM 原始输出

这样既能证明 MCP 调用存在，也不会把内部实现和机器信息暴露到展示页面。

## 4.5 模拟 CAD 预览

保留现有 SVG 板架示意，并强化状态变化：

- 等待：灰色线框。
- 校验通过：显示定位面、材料和厚度。
- MCP 调用中：边框脉冲。
- 成功：板架填充高亮，显示模拟对象 ID。
- 失败：板架保持线框，显示错误码。
- 澄清：不生成板架实体。

预览区域固定显示：

~~~text
SIMULATED CAD PREVIEW
NO REAL CAD MODEL WAS MODIFIED
~~~

预览只根据已经校验的 PanelRequest 渲染，不承担几何建模，也不声称与真实 CAD 视图一致。

## 4.6 Provider 替换边界

页面底部增加静态对比：

~~~text
当前 PoC
McpCadBackend -> MCP STDIO -> Contract Mock Server

公司内网目标
McpCadBackend -> MCP -> Company CAD Adapter -> Native CAD API
~~~

用颜色区分：

- 绿色：已经在个人 PC 实测的组件。
- 黄色：当前模拟的 CAD Provider。
- 灰色虚线：等待公司环境接入的组件。

同时显示：

| 保持不变 | 公司侧替换 |
|---|---|
| Web 页面 | Contract Mock Server |
| Local Qwen | Company CAD Adapter |
| LangGraph | Native CAD API 映射 |
| PanelRequest | 正式返回对象 ID |
| MCP Client | 正式错误语义 |

---

# 5. 后端数据方案

## 5.1 新增展示 DTO

不向前端返回完整 AgentState。建议在 webapp/schemas.py 增加只用于展示的模型：

~~~python
class TraceNodeView(BaseModel):
    name: Literal["llm", "graph", "schema", "mcp", "provider"]
    label: str
    status: StepStatus
    duration_ms: int | None = None
    summary: str
    details: dict[str, Any] | None = None

class McpCallView(BaseModel):
    transport: Literal["stdio"]
    method: Literal["tools/call"]
    tool: Literal["create_panel"]
    contract_version: str
    arguments: dict[str, Any]

class McpResponseView(BaseModel):
    success: bool
    object_id: str | None
    error_code: str | None

class ExecutionTraceView(BaseModel):
    nodes: list[TraceNodeView]
    mcp_request: McpCallView | None = None
    mcp_response: McpResponseView | None = None
    provider: Literal["contract-mock", "direct-mock"]
    simulated: Literal[True] = True
~~~

AgentRunResponse 增加：

~~~python
execution_trace: ExecutionTraceView
~~~

## 5.2 Trace 数据来源

第一版不实现实时事件流。各层返回结果后，由 Web 映射层生成展示 Trace。

| Trace 字段 | 来源 |
|---|---|
| Qwen 状态 | action_plan、error_code |
| Graph 路由 | panel_request、cad_result、最终状态 |
| Schema 状态 | PanelRequest 是否生成、缺失字段 |
| MCP 请求 | McpCadBackend 已执行的白名单参数 |
| MCP 响应 | CadExecutionResult |
| Provider | CAD_BACKEND 配置 |
| 耗时 | Web 请求内的阶段计时；无法准确测量时留空 |

为了展示真实 MCP 报文，不能由前端根据 PanelRequest 猜测。建议让 CAD 执行层返回一个安全的调用摘要，或通过请求级 Trace Collector 记录已经发送给 StdioMcpClient 的字段。

PoC 最小实现建议使用请求级 Trace Collector：

1. Web 创建 request_id。
2. 调用 Agent 前初始化空 TraceContext。
3. McpCadBackend 在 call_tool 前写入白名单请求摘要。
4. MCP 返回后写入白名单响应摘要。
5. response_mapper 读取 TraceContext 并生成 ExecutionTraceView。
6. 请求结束后立即清理 TraceContext。

不得使用单一全局可变字典，以免并发请求串数据。可使用 contextvars.ContextVar。

## 5.3 计时方案

只记录对展示有意义的近似耗时：

- total_ms：Web 请求总耗时。
- llm_ms：LocalQwen HTTP 调用耗时。
- mcp_ms：StdioMcpClient call_tool 总耗时。

本阶段不拆分 MCP 子进程启动、initialize、tools/list 和 tools/call 的精确耗时。页面可显示它们已执行，但只给出 MCP 总耗时，避免为展示投入过多工程改造。

## 5.4 安全规则

- details 只允许预定义字段。
- 异常只展示稳定错误码和可读消息。
- LLM 原始输出默认不进入 DTO。
- 不返回本地文件路径、环境变量、Prompt 或堆栈。
- MCP Contract Mock 始终标记 simulated=true。
- 缺参、非法参数和 unsupported 场景中 mcp_request 必须为 null。

---

# 6. 前端实现方案

## 6.1 HTML

在现有 index.html 中增加：

- 五节点 pipeline 容器。
- MCP Request 和 Response 双栏检查器。
- Provider replacement 区域。
- SIMULATED CAD PREVIEW 水印。
- 总耗时和 request_id。

保留当前输入区、参数卡片和多轮补充逻辑。

## 6.2 CSS

延续当前深蓝工业风格，不全面重写。

新增视觉规则：

- pipeline 用横向连线和节点灯。
- success 为绿色，running 为蓝色，attention 为黄色，error 为红色，skipped 为灰色。
- MCP 检查器使用等宽字体和有限高度滚动区。
- 当前 Provider 用黄色边框，未来 Company CAD 用虚线灰框。
- 成功后的板架 SVG 增加一次短促高亮动画。
- 所有动画支持 prefers-reduced-motion。

布局要求：

- 1920x1080：输入、链路、MCP 检查器和预览首屏可见。
- 1366x768：核心链路和结果可见，详细 JSON 允许折叠或滚动。
- 窄屏：pipeline 改为纵向。

## 6.3 JavaScript

新增：

- renderExecutionTrace(trace)
- renderMcpInspector(request, response)
- renderProviderBoundary(provider)
- renderSimulatedPreview(panel, cadResult)
- clearExecutionTrace()

前端只渲染服务端 DTO，不自行构造“真实 MCP 请求”。

如果服务端返回旧版 DTO 或 execution_trace 缺失，页面降级为现有三步骤显示，不阻断基本演示。

---

# 7. 固定演示脚本

## 7.1 第一幕：自然语言转工程参数

输入：

~~~text
在第100肋位创建14mm厚AH36板架
~~~

讲解顺序：

1. Qwen 在本地完成参数提取。
2. 第100肋位由确定性规则规范化为 FR100。
3. PanelRequest 通过强类型校验。
4. MCP 检查器出现实际 tools/call 参数。
5. Contract Mock 返回模拟对象 ID。
6. SVG 板架高亮，但始终保留 SIMULATED 水印。

## 7.2 第二幕：安全停止

输入：

~~~text
在第100肋位创建14mm厚板架
~~~

讲解重点：

- Qwen 可以理解创建意图。
- Schema 检测到材料缺失。
- LangGraph 停止执行。
- MCP 和 Provider 节点明确显示 SKIPPED。
- 证明 LLM 无法绕过校验直接操作 CAD。

随后补充：

~~~text
材料为AH36
~~~

累积上下文后完成创建，展示多轮恢复。

## 7.3 第三幕：迁移边界

不依赖不稳定的英文哨兵自然语言输入。直接讲解页面底部替换图：

~~~text
个人 PC：Contract Mock
公司内网：Company CAD Adapter -> Native CAD API
~~~

说明 Web、Qwen、LangGraph、PanelRequest 和 MCP Client 保持不变。

定位面不存在和 CAD 不可用通过自动化测试证明，不作为现场主流程的必演场景。

---

# 8. 分步实施计划

## Step 1：展示 DTO 与 Trace Collector

工作内容：

- 定义 ExecutionTraceView、TraceNodeView 和 MCP 请求/响应视图。
- 使用 ContextVar 建立请求级 TraceContext。
- 在 LocalQwen、Graph/Web 映射和 McpCadBackend 写入安全摘要。
- 保持 AgentRunResponse 原字段兼容。

完成标准：

- 成功请求返回五个 Trace 节点。
- MCP 请求参数来自实际 call_tool 边界。
- 澄清请求不包含 MCP 请求和响应。
- 不返回路径、Prompt、异常和 llm_raw_output。

预计：0.5 天。

## Step 2：透明执行台页面

工作内容：

- 增加五节点 pipeline。
- 增加 MCP Request/Response 检查器。
- 增加 Provider 替换边界图。
- 增强模拟 CAD SVG 和水印。
- 接入 execution_trace 渲染及旧 DTO 降级。

完成标准：

- 成功、澄清、unsupported 和 error 均有稳定页面表现。
- 一眼可见 Qwen、LangGraph、Schema、MCP、Provider。
- 页面不会暗示连接真实 CAD。

预计：0.5 至 1 天。

## Step 3：固定演示与验收

工作内容：

- 用真实 Qwen 执行成功、澄清、补充后成功三个场景。
- 验证 MCP 请求检查器显示 referenceName=FR100、thicknessMm=14、material=AH36。
- 验证缺参时 MCP 节点为 SKIPPED。
- 在 1366x768 和 1920x1080 人工检查布局。
- 更新一键启动脚本、演示手册、README 和 current_status。

完成标准：

- 从启动到完成展示不需要修改代码或手工准备数据。
- 固定输入连续演示三次无旧状态残留。
- 可以录制一段 2 至 3 分钟演示视频。

预计：0.5 天。

---

# 9. 测试与验收清单

自动化验证：

- [ ] execution_trace Schema 拒绝未知字段。
- [ ] 成功请求包含五节点及 MCP 请求/响应。
- [ ] MCP arguments 与实际 call_tool 参数一致。
- [ ] 缺材料时 MCP 请求为 null，节点为 skipped。
- [ ] unsupported 时 Schema、MCP 和 Provider 按规则跳过。
- [ ] MCP 业务失败保留稳定错误码。
- [ ] Web 500 始终返回 JSON。
- [ ] Trace 不包含绝对路径、Prompt、llm_raw_output 或 traceback。
- [ ] 旧字段 panel、cad_result、steps 保持兼容。

人工验收：

- [ ] 页面明确显示 MCP Contract Mock 和 SIMULATED。
- [ ] 成功时流程节点按顺序高亮。
- [ ] MCP 请求和响应无需展开完整 Web JSON 即可看见。
- [ ] 板架预览显示 FR100、14mm、AH36 和模拟对象 ID。
- [ ] 澄清时 MCP 和 Provider 显示 SKIPPED。
- [ ] Provider 替换边界能在 20 秒内向观众说明清楚。
- [ ] 1366x768 与 1920x1080 无关键内容遮挡。
- [ ] 页面刷新和重复演示无旧状态残留。

---

# 10. 本阶段明确不做

为了尽快形成可展示成果，本阶段不做：

- 真实 CAD 几何建模。
- MCP 长连接或会话复用。
- SSE、WebSocket 和真实逐节点流式事件。
- 完整日志平台和分布式 Trace。
- 用户认证、审计和多工程隔离。
- RAG、扶强材和其他结构类型。
- 高精度三维 CAD 渲染。
- 通过特殊自然语言强行触发 Mock 错误。

---

# 11. 交付物

实施完成后应包含：

- 支持 execution_trace 的 Web API。
- 透明执行链路页面。
- MCP 请求/响应检查器。
- 带 SIMULATED 水印的板架预览。
- Provider 替换边界图。
- 一键启动脚本。
- 固定演示操作手册。
- 自动化测试和人工验收记录。
- 2 至 3 分钟录屏所需的固定讲解脚本。

最终展示结论应表述为：

> 当前 PoC 已在个人 PC 上真实跑通本地 Qwen、LangGraph、强类型校验和 MCP STDIO 调用。CAD 执行由 Contract Mock 模拟。进入公司内网后，需要新增原生 CAD API 到 MCP Tool 的 Adapter，上层 Agent 与 Web 展示链路可以保持不变。
