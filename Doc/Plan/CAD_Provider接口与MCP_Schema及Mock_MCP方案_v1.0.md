# AI Ship CAD Copilot

## Provider 接口、MCP Schema 与 Mock MCP 实施方案

版本：v1.0  
更新时间：2026-08-21  
状态：外网开发与内网联调准备方案

---

# 1. 目标与范围

本方案用于在外网仓库中提前建立 Python Agent 与内网 C++ CAD 软件之间的稳定边界，降低进入内网后的接口返工成本。

本阶段完成：

- 建立 CAD 工程事实查询的 Provider 抽象。
- 以定位面查询作为第一个最小可运行能力。
- 为板架边界引用多种 CAD 对象预留通用契约。
- 定义第一版 MCP 请求、响应、错误和版本 Schema。
- 使用 Mock Provider、Mock MCP Client/Server 验证正常及安全停止路径。
- 准备用于内网真实 CAD 联调的源码、协议和测试材料。

本阶段不完成：

- 不连接真实 C++ CAD 软件。
- 不声称 Mock MCP 是真实 CAD 集成。
- 不在 Python 中创建正式 CAD 几何模型。
- 不扩展 stiffener、bracket 或其他结构类型。
- 不引入 RAG、前端或自动强度设计。

当前明确采用一对一运行模式：

```text
一个 Python Agent
  -> 一个 MCP Server
  -> 一个 C++ CAD 进程
  -> 一个当前打开的工程
```

因此第一版不设计 `project_id`、多工程隔离、工程修订、目录缓存和幂等机制。这些能力只在未来出现实际需求时扩展。

---

# 2. 核心认识

## 2.1 Provider 的位置

Provider 不负责用户输入，也不负责 LLM 推理。它是 Python Agent 内部访问 CAD 工程事实的业务接口，位于 LangGraph 与 MCP Client 之间：

```text
用户输入
  -> LLM：识别意图并抽取候选表达
  -> LangGraph：校验、澄清和安全路由
  -> CAD Project Provider：查询工程事实
  -> MCP Client：完成协议通信
  -> MCP Server / C++ CAD：查询真实工程或执行创建
```

LLM 输出只是候选参数。定位面、边界对象及其他工程对象是否存在，必须由 Provider 从 CAD 工程数据中确定。

## 2.2 ReferencePlaneProvider 是最小切入点

`ReferencePlaneProvider` 适合当前 MVP，但不是未来完整 CAD Provider 的全部能力。

板架边界可能引用：

- 定位面、肋位面或纵剖面。
- 甲板、板架、已有板或其他结构对象。
- Surface、几何面、曲线或边。
- 坐标面、偏移面或其他构造引用。
- CAD 对象的 Face、Edge 等子元素。

因此长期概念应为 `CadProjectProvider`，通过若干小接口提供工程上下文、定位面目录和通用对象查询。当前只实现定位面查询，避免在尚未确认真实 CAD API 时过度设计。

---

# 3. 推荐架构

```text
                         +----------------------------+
用户输入 -> LLM -> Graph | Boundary/Plane Resolvers   |
                         +-------------+--------------+
                                       |
                    +------------------+------------------+
                    |                                     |
          CadProjectProvider                     CadCommandBackend
          查询工程事实                           执行 CAD 修改
                    |                                     |
                    +------------------+------------------+
                                       |
                                  MCP Client
                                       |
                              MCP Server / C++ CAD
```

建议使用小接口组合，而不是立即建立包含所有 CAD 能力的巨型接口：

```python
class ReferencePlaneProvider(Protocol):
    def list_reference_planes(self) -> list[ReferencePlaneRecord]:
        ...


class CadObjectProvider(Protocol):
    def query_objects(
        self,
        request: CadObjectQuery,
    ) -> CadObjectQueryResult:
        ...

    def get_object(
        self,
        object_id: str,
    ) -> CadObjectReference:
        ...


class CadCommandBackend(Protocol):
    def create_panel(
        self,
        request: PanelRequest,
    ) -> CadExecutionResult:
        ...
```

第一轮只要求 `ReferencePlaneProvider` 可运行；`CadObjectProvider` 先定义最小 Schema 骨架，等内网确认边界对象 API 后再实现。

---

# 4. 一对一工程上下文

第一版由 MCP Server 直接操作其连接的 CAD 进程和当前打开工程。用户、LLM、Graph 和 Tool 请求均不传递 `project_id`。

如果 CAD 没有打开工程，Provider 必须返回受控错误，并阻止后续创建。当前不处理多个工程并存、工程切换、跨工程缓存或长时间会话一致性问题。

每次创建请求在解析工程对象前实时获取一次所需目录。同一次请求内复用查询结果，不为定位面维护本地 JSON 或跨请求缓存。

---
# 5. 工程对象引用模型

## 5.1 定位面记录

建议在现有 `ReferencePlaneRecord` 中预留稳定对象 ID：

```python
class ReferencePlaneRecord(BaseModel):
    object_id: str | None = None
    name: str
    aliases: list[str] = []
    axis: Literal["X", "Y", "Z"] | None = None
    coordinate_mm: float | None = None
    coordinate_system: str | None = None
```

约束：

- Mock 数据使用固定、可重复的对象 ID，不使用随机值。
- 真实 CAD 若提供稳定 ID，创建请求优先使用该 ID。
- 如果真实 CAD 不提供稳定 ID，再明确正式名称是否可作为引用键。
- `object_id=None` 仅作为外网草案兼容状态，不直接视为正式协议结论。

## 5.2 名称和别名唯一性

已确认真实工程中不存在两个具有相同别名的定位面。Provider 契约应规定：

- 当前 CAD 工程内定位面正式名称唯一。
- 当前 CAD 工程内定位面别名唯一。
- Provider 返回重复名称或重复别名属于目录数据异常。
- 发生目录数据异常时必须停止创建，不应要求用户从重复别名中选择。

解析器仍可保留歧义处理作为防御性保护，以确保面对异常或非正式数据时不会误执行 CAD。

## 5.3 板架边界候选与执行引用分离

当前 `PanelBoundaries` 使用字符串，适合作为 LLM 候选表达，但不应直接作为长期 CAD 执行引用。

候选层示例：

```python
class PanelBoundaryCandidate(BaseModel):
    top: str | None = None
    bottom: str | None = None
    left: str | None = None
    right: str | None = None
```

已解析对象示例：

```python
class CadObjectReference(BaseModel):
    object_id: str
    name: str
    object_type: str
```

未来的边界引用可能是联合类型：

```text
object          完整 CAD 对象
subelement      Face、Edge 等子元素
coordinate      坐标面或轴向位置
offset          基于对象的偏移引用
```

外网阶段只定义可扩展结构，不假设 C++ CAD 最终接受对象、子元素还是几何表达式。该结论必须在内网根据真实 CAD API 确认。

---

# 6. Graph 依赖注入

当前 Graph 直接使用模块级 `LocalQwen`、`list_reference_planes()` 和 `create_panel()`。建议改为构建函数：

```python
def build_graph(
    *,
    llm: LlmClient,
    reference_plane_provider: ReferencePlaneProvider,
    cad_backend: CadBackend,
):
    ...
```

本地默认组合：

```python
graph = build_graph(
    llm=LocalQwen(),
    reference_plane_provider=MockReferencePlaneProvider(),
    cad_backend=MockCadBackend(),
)
```

真实组合：

```text
McpReferencePlaneProvider -> MCP Client -> MCP Server
McpCadBackend             -> MCP Client -> MCP Server
```

Graph 只依赖业务接口，不依赖 MCP Tool 名称、SDK 类型、传输格式或 C++ 异常细节。

---

# 7. MCP Schema 草案

外网版本使用 `schema_version: "0.1-draft"`。进入内网确认真实 CAD API 后再冻结为稳定版本。

当前一对一模式只要求两个 MCP Tool：

```text
list_reference_planes()
create_panel(panel)
```

`get_active_project`、`project_id`、工程修订和幂等字段不进入第一版协议。为多类型边界预留的 `query_cad_objects` 和 `get_cad_object` 等确认真实 CAD API 后再增加。

## 7.1 通用字段

请求保留协议版本和诊断用请求 ID：

```json
{
  "schema_version": "0.1-draft",
  "request_id": "req-001"
}
```

`request_id` 用于日志关联，不代表幂等或工程身份。

## 7.2 list_reference_planes

请求：

```json
{
  "schema_version": "0.1-draft",
  "request_id": "req-001"
}
```

响应：

```json
{
  "schema_version": "0.1-draft",
  "request_id": "req-001",
  "success": true,
  "reference_planes": [
    {
      "object_id": "plane-fr100",
      "name": "FR100",
      "aliases": ["FR 100", "第100肋位"],
      "axis": "X",
      "coordinate_mm": 10000.0,
      "coordinate_system": "SHIP"
    }
  ],
  "error": null
}
```

MCP Server 始终查询其连接的 CAD 进程当前打开的工程。没有打开工程时返回 `NO_ACTIVE_PROJECT`。

## 7.3 create_panel

请求草案：

```json
{
  "schema_version": "0.1-draft",
  "request_id": "req-002",
  "panel": {
    "type": "panel",
    "reference_plane": {
      "object_id": "plane-fr100",
      "name": "FR100"
    },
    "boundaries": {
      "top": null,
      "bottom": null,
      "left": null,
      "right": null
    },
    "thickness_mm": 14.0,
    "material": "AH36"
  }
}
```

成功响应：

```json
{
  "schema_version": "0.1-draft",
  "request_id": "req-002",
  "success": true,
  "object": {
    "object_id": "panel-123",
    "name": "PANEL_123",
    "object_type": "panel"
  },
  "error": null
}
```

边界字段的最终结构必须等内网确认 C++ CAD 对对象、Face、Edge、曲面和偏移面的实际引用方式后再冻结。第一版允许继续使用当前候选字符串或空值，但未经确定性解析的边界不得被当作已确认的 CAD 对象引用。

---
# 8. 错误模型

建议统一错误结构：

```python
class ProviderError(BaseModel):
    code: str
    message: str
    retryable: bool = False
    details: dict[str, object] | None = None
```

首批稳定错误码建议：

```text
NO_ACTIVE_PROJECT
REFERENCE_PLANE_NOT_FOUND
REFERENCE_PLANE_CATALOG_INVALID
CAD_OBJECT_NOT_FOUND
INVALID_REQUEST
UNSUPPORTED_SCHEMA_VERSION
CAD_UNAVAILABLE
CAD_TIMEOUT
CAD_EXECUTION_FAILED
INVALID_RESPONSE
INTERNAL_ERROR
```

错误响应不得泄露 Python/C++ 堆栈、个人路径、内部 SDK 异常或敏感工程信息。

---

# 9. Mock MCP 分层

Mock MCP 应分为三层，避免把单元桩误称为真实 MCP 集成。

## 9.1 Mock Provider

不经过 MCP SDK或网络，直接返回固定工程数据，用于 Resolver 和 Graph 快速测试。

## 9.2 Mock MCP Client

实现与真实 MCP Client 相同的最小调用协议，在内存中返回 Schema 响应，用于验证：

- `McpReferencePlaneProvider` 的响应转换。
- `McpCadBackend` 的请求映射。
- MCP 错误到领域错误的归一化。
- Graph 在 Provider/CAD 异常时安全停止。

## 9.3 Mock MCP Server

在选定具体 MCP SDK 和传输方式后，启动本地测试 Server，验证序列化、工具注册、超时、断连和非法响应。

Mock Server 仍不创建真实 CAD 对象，只返回固定或内存记录的结果。

---

# 10. 测试计划

## 10.1 Provider 契约测试

- 当前 CAD 工程返回唯一定位面目录。
- CAD 没有打开工程时返回受控错误。
- 重复正式名称或别名被判定为目录数据异常。
- Provider 不可用时不进入 CAD 创建。
- 返回记录缺少必要字段时拒绝使用。
- 同一次创建请求只查询一次定位面目录。

## 10.2 MCP Schema 测试

- 请求和响应拒绝未知字段。
- 缺少 `schema_version` 或 `request_id` 时失败。
- 不支持的 Schema 版本被拒绝。
- 成功结果与错误结果字段互斥。
- `request_id` 在响应中保持一致。
- 坐标、单位和坐标系通过强类型验证。
- 创建成功必须返回有效对象 ID。

## 10.3 Mock MCP 集成测试

- 当前工程的定位面目录查询成功并转换为 `ReferencePlaneRecord`。
- CAD 未打开工程、超时、断连及非法响应均受控结束。
- 定位面解析成功后提交固定 `PanelRequest`。
- CAD Backend 失败时返回 `CadExecutionResult`，不泄露内部异常。
- 任一工程事实不确定时都不会调用创建 Tool。

现有离线测试必须继续不依赖正在运行的 Ollama 或真实 CAD。

---

# 11. 建议文件结构

第一轮保持最小改动：

```text
providers/
  __init__.py
  reference_plane_provider.py

schemas/
  mcp_schema.py

mcp_client/
  __init__.py
  protocol.py
  mock_client.py

tests/
  test_reference_plane_provider.py
  test_mcp_schema.py
  test_mock_mcp.py
```

当真实 MCP Client 出现后再增加：

```text
providers/mcp_reference_plane_provider.py
tools/mcp_cad_backend.py
mcp_client/client.py
tests/test_mcp_reference_plane_provider.py
tests/test_mcp_cad_backend.py
```

---

# 12. 分步实施顺序

## 第一批：Provider 基础

1. 为定位面记录增加固定 Mock `object_id`。
2. 定义 `ReferencePlaneProvider`。
3. 将硬编码目录迁移到 `MockReferencePlaneProvider`。
4. 通过依赖注入让 Graph 使用 Provider。
5. 增加无当前工程、目录异常和 Provider 失败测试。

## 第二批：MCP 契约

1. 定义通用请求、响应、错误和版本 Schema。
2. 定义 `list_reference_planes` 和 `create_panel` 草案。
3. 为多类型边界预留 `CadObjectReference` 与 `get_cad_object` 契约。
4. 增加完整 Schema 契约测试。
5. 编写 SDK 无关的 MCP Client Protocol。

## 第三批：Mock MCP

1. 实现内存 Mock MCP Client。
2. 实现 `McpReferencePlaneProvider` 和 `McpCadBackend`。
3. 验证请求映射、响应转换和错误归一化。
4. 选定具体 MCP SDK 后实现本地 Mock MCP Server。
5. 验证无当前工程、超时、断连和非法响应场景。

## 第四批：内网联调

1. 确认真实 CAD 查询和创建 API。
2. 确认对象 ID、名称、边界引用及线程模型。
3. 调整并冻结 MCP Schema 1.0。
4. 用真实 MCP Server/CAD Connector 替换 Mock。
5. 建立真实 CAD 集成测试，同时保留 Mock 快速回归。

---

# 13. 内网联调前必须确认的问题

- 定位面对象是否具有稳定 ID。
- 正式名称是否唯一，重命名后引用是否保持有效。
- 别名从哪个 CAD 属性或配置来源取得。
- 板架边界可引用哪些对象类型。
- 边界需要传对象、子元素还是几何表达式。
- C++ CAD 创建是否必须在 UI 主线程运行。
- 创建失败是否需要事务或显式回滚。
- MCP Server 运行在 CAD 进程内还是独立进程。
- CAD 对象创建成功后如何返回和验证对象 ID。

---

# 14. 完成标准

外网阶段完成需满足：

- Graph 不再直接依赖硬编码定位面目录。
- Mock 与 MCP Provider 遵守同一业务接口。
- Provider 和 MCP Tool 默认操作唯一连接的 CAD 进程及其当前工程。
- MCP 草案具有强类型请求、响应、版本和错误模型。
- 定位面正式名称及别名唯一性得到 Provider 校验。
- 为未来多类型板架边界保留通用 CAD 对象引用能力。
- Mock MCP 覆盖正常、无当前工程、超时、非法响应和禁止误创建路径。
- 所有离线测试在没有 Ollama、MCP Server 和真实 CAD 的环境中可运行。
- 文档明确当前仍为 Mock，不将其描述为真实 CAD 集成。

完成以上内容后，内网阶段的主要工作应是实现 C++ CAD Connector、确认并冻结协议，而不是重写 Agent 主流程。
