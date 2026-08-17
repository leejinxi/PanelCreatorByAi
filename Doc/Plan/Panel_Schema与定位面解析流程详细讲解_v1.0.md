# AI Ship CAD Copilot

## Panel Schema 与定位面解析流程详细讲解

版本：v1.0  
更新时间：2026-08-17  
适用对象：刚开始学习 Python、Pydantic、LangGraph 和 AI Agent 开发的开发者

---

# 1. 这套代码要解决什么问题

用户不会按照固定 JSON 格式向 CAD 系统下命令，用户通常会说：

```text
请在 FR100 创建一块 14mm 厚的 AH36 板架。
```

或者：

```text
请在 X=10000 的位置创建一块 14mm 厚的 AH36 板架。
```

而 CAD 接口需要明确、稳定的参数，例如：

```json
{
  "type": "panel",
  "reference_plane": "FR100",
  "boundaries": {
    "top": null,
    "bottom": null,
    "left": null,
    "right": null
  },
  "thickness": 14,
  "material": "AH36"
}
```

因此，系统需要完成四件事：

1. 使用大语言模型从自然语言中提取候选参数。
2. 使用工程标尺目录确定定位面是否真实存在。
3. 使用 Schema 校验厚度、材料和定位面等数据是否合法。
4. 只有校验成功后才调用 CAD 创建函数。

当前完整流程可以概括为：

```text
用户自然语言
  ↓
Qwen 提取候选 JSON
  ↓
JSON 基础检查
  ↓
定位面解析
  ├─ 按坐标匹配
  ├─ 按工程名称或别名匹配
  └─ 使用 LLM 提取值兜底
  ↓
Pydantic PanelRequest 强校验
  ↓
create_panel Mock CAD
```

这里最重要的设计原则是：

> LLM 负责理解语言，工程目录负责提供事实，Schema 负责校验数据，CAD Tool 负责执行动作。

不要让 LLM 同时承担所有职责。LLM 可能漏字段、写错名称或生成不存在的对象，因此它的输出不能直接提交给 CAD。

---

# 2. 什么是 Schema

Schema 可以理解为“数据合同”或“数据说明书”。

它明确规定：

- 数据有哪些字段；
- 每个字段是什么类型；
- 哪些字段必填；
- 哪些值是合法的；
- 收到错误数据时应该拒绝还是转换。

例如，板架厚度必须是数字并且大于 0：

```python
thickness: float = Field(gt=0)
```

如果传入：

```python
thickness=-5
```

Pydantic 会抛出 `ValidationError`，错误数据就不会进入 CAD。

当前项目使用 Pydantic v2 定义 Schema，主要代码位于：

```text
schemas/panel_schema.py
schemas/reference_plane_schema.py
```

---

# 3. Pydantic 基础 API 讲解

## 3.1 BaseModel

`BaseModel` 是所有 Pydantic 数据模型的基类：

```python
from pydantic import BaseModel


class Example(BaseModel):
    name: str
    value: float
```

创建对象时，Pydantic 会自动校验输入：

```python
example = Example(name="test", value=10)
```

如果类型可以安全转换，Pydantic 也会进行转换：

```python
example = Example(name="test", value="10")
print(example.value)
# 10.0
```

## 3.2 ConfigDict(extra="forbid")

当前 Schema 都使用：

```python
model_config = ConfigDict(extra="forbid")
```

`extra="forbid"` 表示禁止未定义字段。

例如，`PanelRequest` 没有 `color` 字段，如果模型输出：

```json
{
  "reference_plane": "FR100",
  "thickness": 14,
  "material": "AH36",
  "color": "red"
}
```

Pydantic 会拒绝该数据，而不是悄悄忽略 `color`。

这对 Agent 很重要，因为 LLM 可能生成代码中没有定义的字段。禁止额外字段能帮助开发者尽早发现模型输出偏差。

## 3.3 Field

`Field` 用于为字段添加约束、默认值和说明。

```python
thickness: float = Field(
    gt=0,
    description="板架厚度，单位为 mm",
)
```

其中：

- `gt=0`：greater than 0，数值必须大于 0；
- `description`：字段说明，可用于生成 JSON Schema 或工具描述。

当前边界字段使用：

```python
boundaries: PanelBoundaries = Field(
    default_factory=PanelBoundaries,
)
```

`default_factory` 表示每次创建 `PanelRequest` 时生成一个新的空 `PanelBoundaries` 对象。

不要写成共享的可变对象，否则多个请求可能意外共享同一份数据。

## 3.4 field_validator

`field_validator` 用于编写自定义字段校验或字段标准化逻辑。

```python
@field_validator("reference_plane", "material")
@classmethod
def validate_required_text(cls, value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("字段不能为空")
    return normalized
```

这个方法完成两件事：

1. 使用 `strip()` 删除字符串前后的空格；
2. 如果删除空格后为空，则拒绝该字段。

例如：

```python
material=" AH36 "
```

最终会被保存为：

```python
material="AH36"
```

而：

```python
material="   "
```

会触发 `ValidationError`。

## 3.5 Literal

`Literal` 用于限制字段只能取指定值：

```python
type: Literal["panel"] = "panel"
```

这意味着：

```python
type="panel"
```

合法，而：

```python
type="plate"
```

不合法。

定位面选择器中的 `mode` 也使用 `Literal`：

```python
mode: Literal["name"]
mode: Literal["coordinate"]
mode: Literal["description"]
```

## 3.6 model_validate

`model_validate()` 用于把普通字典转换成经过校验的 Pydantic 对象：

```python
panel_request = PanelRequest.model_validate(data)
```

其中 `data` 通常来自：

```python
data = json.loads(llm_raw_output)
```

如果数据合法，返回 `PanelRequest`；如果不合法，抛出 `ValidationError`。

## 3.7 model_dump

`model_dump()` 将 Pydantic 对象转换回 Python 字典：

```python
boundaries = panel_request.boundaries.model_dump()
```

结果类似：

```python
{
    "top": None,
    "bottom": None,
    "left": None,
    "right": None,
}
```

当前 `execute_cad()` 使用该 API，把 `PanelBoundaries` 转换成 Mock CAD 能接收的字典。

---

# 4. Panel Schema 详细讲解

## 4.1 PanelBoundaries

代码位置：`schemas/panel_schema.py`

```python
class PanelBoundaries(BaseModel):
    top: str | None = None
    bottom: str | None = None
    left: str | None = None
    right: str | None = None
```

它描述板架的四向边界。

`str | None` 表示字段既可以是字符串，也可以是 `None`。

例如：

```python
PanelBoundaries(
    top="Deck-A",
    bottom=None,
    left="Longitudinal-1",
    right=None,
)
```

边界校验器：

```python
@field_validator("top", "bottom", "left", "right")
@classmethod
def normalize_boundary(cls, value):
    if value is None:
        return None

    normalized = value.strip()
    return normalized or None
```

处理结果：

| 输入 | 保存结果 |
|---|---|
| `None` | `None` |
| `" Deck-A "` | `"Deck-A"` |
| `""` | `None` |
| `"   "` | `None` |

这样可以避免空字符串和 `None` 同时表示“没有边界”。内部统一使用 `None`，后续逻辑更简单。

## 4.2 PanelRequest

`PanelRequest` 表示已经通过校验、可以提交给 CAD 的板架创建请求：

```python
class PanelRequest(BaseModel):
    type: Literal["panel"] = "panel"
    reference_plane: str
    boundaries: PanelBoundaries
    thickness: float
    material: str
```

字段含义：

| 字段 | 类型 | 说明 |
|---|---|---|
| `type` | `Literal["panel"]` | 当前业务对象固定为板架 |
| `reference_plane` | `str` | 已解析为工程正式名称的定位面 |
| `boundaries` | `PanelBoundaries` | 四向边界 |
| `thickness` | `float` | 厚度，单位 mm，必须大于 0 |
| `material` | `str` | 材料牌号，例如 AH36 |

这里的 `reference_plane` 不是未经确认的用户原文。进入 `PanelRequest` 前，定位面解析器必须先把用户表达转换成当前工程中的正式名称。

例如：

```text
用户输入：在 X=10000 的位置
工程目录解析：FR100
PanelRequest.reference_plane：FR100
```

创建示例：

```python
request = PanelRequest(
    reference_plane="FR100",
    thickness=14,
    material="AH36",
)
```

## 4.3 CadExecutionResult

```python
class CadExecutionResult(BaseModel):
    success: bool
    message: str
    object_id: str | None = None
    error_code: str | None = None
```

它是规划中的 CAD 统一返回结构：

```json
{
  "success": true,
  "message": "Panel created successfully",
  "object_id": "PANEL-001",
  "error_code": null
}
```

当前 `create_panel()` 仍然返回普通字符串：

```python
"Panel created successfully"
```

因此 `CadExecutionResult` 已定义，但还没有完全接入 CAD Tool。后续标准化工具时，应让 `create_panel()` 返回该对象。

---

# 5. 定位面 Schema 详细讲解

定位面相关模型位于：

```text
schemas/reference_plane_schema.py
```

定位面名称因工程而异，所以代码不能写死 `FR`、`LV`、`SL` 等类型。当前设计将“用户如何表达定位面”和“工程中真实存在的定位面”分开建模。

## 5.1 PlaneByName

表示用户使用名称定位：

```json
{
  "mode": "name",
  "name": "SURFACE_20"
}
```

对应：

```python
class PlaneByName(BaseModel):
    mode: Literal["name"] = "name"
    name: str
```

## 5.2 PlaneByCoordinate

表示用户使用坐标定位：

```json
{
  "mode": "coordinate",
  "axis": "X",
  "value": 10000,
  "unit": "mm",
  "coordinate_system": null
}
```

对应：

```python
class PlaneByCoordinate(BaseModel):
    mode: Literal["coordinate"] = "coordinate"
    axis: str
    value: float
    unit: Literal["mm", "cm", "m"] = "mm"
    coordinate_system: str | None = None
```

`axis` 校验器会执行：

```python
value.strip().upper()
```

因此 `" x "` 会转换成 `"X"`。

## 5.3 PlaneByDescription

表示用户或 LLM 提供的是描述性文字：

```json
{
  "mode": "description",
  "text": "主甲板中心面"
}
```

描述必须继续与工程名称或别名目录匹配，不能直接认为它是真实 CAD 对象。

## 5.4 ReferencePlaneSelector

```python
ReferencePlaneSelector = Annotated[
    PlaneByName | PlaneByCoordinate | PlaneByDescription,
    Field(discriminator="mode"),
]
```

这里使用了两个 Python/Pydantic 概念。

`A | B | C` 表示联合类型，即数据可以是三种模型中的任意一种。

`discriminator="mode"` 表示 Pydantic 根据 `mode` 判断应该使用哪一个模型：

```text
mode=name        → PlaneByName
mode=coordinate  → PlaneByCoordinate
mode=description → PlaneByDescription
```

这种结构称为“带判别字段的联合类型”。它比一个模型中放很多可选字段更安全。

## 5.5 ReferencePlaneRecord

`ReferencePlaneRecord` 表示当前 CAD 工程中真实存在的标尺面：

```python
class ReferencePlaneRecord(BaseModel):
    object_id: str
    name: str
    aliases: list[str]
    axis: str | None
    coordinate_mm: float | None
    coordinate_system: str | None
```

字段含义：

| 字段 | 说明 |
|---|---|
| `object_id` | CAD 内部稳定对象 ID |
| `name` | 工程正式名称 |
| `aliases` | 用户可能使用的别名 |
| `axis` | 所属坐标轴 |
| `coordinate_mm` | 在该轴上的坐标，统一为 mm |
| `coordinate_system` | 坐标系名称，可为空 |

当前 Mock 示例：

```python
ReferencePlaneRecord(
    object_id="mock-plane-fr100",
    name="FR100",
    aliases=["FR 100", "第100肋位", "100号肋位"],
    axis="X",
    coordinate_mm=10000,
)
```

这意味着下面四种表达都可以指向同一个 CAD 对象：

```text
FR100
FR 100
第100肋位
X=10000
```

## 5.6 ReferencePlaneResolution

定位面解析不会只返回一个字符串，而是返回完整状态：

```python
class ReferencePlaneResolution(BaseModel):
    status: Literal[
        "resolved",
        "ambiguous",
        "not_found",
        "conflict",
    ]
    selector: ReferencePlaneSelector | None
    resolved: ReferencePlaneRecord | None
    candidates: list[ReferencePlaneRecord]
    message: str | None
```

状态说明：

| 状态 | 含义 | 后续行为 |
|---|---|---|
| `resolved` | 唯一匹配成功 | 可以创建 Panel |
| `ambiguous` | 匹配多个标尺面 | 返回候选项，让用户选择 |
| `not_found` | 没有匹配 | 提示用户重新指定 |
| `conflict` | 名称与坐标指向不同对象 | 阻止创建并请求确认 |

---

# 6. 定位面解析算法

代码位置：

```text
tools/reference_plane_tools.py
```

## 6.1 list_reference_planes()

```python
def list_reference_planes() -> list[ReferencePlaneRecord]:
```

功能：获取当前工程中真实存在的标尺面目录。

当前实现返回代码中写好的 Mock 列表，便于在没有真实 CAD 的情况下测试。

未来接入 MCP 后，该函数应该调用真实 CAD：

```text
Agent
  ↓
MCP Client
  ↓
CAD MCP Server
  ↓
查询当前工程标尺面
  ↓
list[ReferencePlaneRecord]
```

只要返回值仍然是 `list[ReferencePlaneRecord]`，后面的解析算法无需重写。

## 6.2 normalize_plane_text()

```python
def normalize_plane_text(value: str) -> str:
    return re.sub(r"[\s_\-]+", "", value).casefold()
```

它用于名称匹配时的标准化：

- 删除空格；
- 删除下划线；
- 删除短横线；
- 使用 `casefold()` 忽略大小写差异。

例如：

```text
SURFACE_20
surface-20
Surface 20
```

都会转换成接近：

```text
surface20
```

注意：它只用于比较，不会修改 CAD 中保存的正式名称。

## 6.3 extract_coordinate_selector()

功能：使用正则表达式从用户原文提取坐标定位方式。

支持示例：

```text
X=10000
X = 10000mm
Y=-2500
Z=12.5m
```

正则表达式会提取：

- `axis`：轴名；
- `value`：带正负号的小数或整数；
- `unit`：mm、cm、m、毫米、厘米或米。

坐标轴列表不是完全写死的。代码会读取工程目录中出现的轴名，并补充常见的 X、Y、Z。

## 6.4 extract_catalog_name_selector()

功能：直接在用户原文中查找工程正式名称或别名。

算法：

```text
取得用户原文
  ↓
对原文做名称标准化
  ↓
遍历工程中的每个 ReferencePlaneRecord
  ↓
检查 name 和 aliases 是否出现在原文中
  ↓
多个文本同时匹配时优先采用最长文本
```

最长匹配可以避免短别名覆盖更明确的长名称。

## 6.5 resolve_reference_plane()

这是定位面解析的主入口：

```python
resolve_reference_plane(
    user_input=...,
    planes=...,
    llm_reference=...,
    tolerance_mm=0.1,
)
```

参数说明：

| 参数 | 作用 |
|---|---|
| `user_input` | 用户原始输入，确定性解析以此为准 |
| `planes` | 当前工程标尺面目录 |
| `llm_reference` | LLM 提取出的候选定位面，作为兜底 |
| `tolerance_mm` | 坐标匹配容差，默认 0.1mm |

解析优先级：

```text
1. 从原文提取坐标
2. 从原文匹配工程名称或别名
3. 使用 LLM 提取结果匹配目录
4. 没有结果则返回 not_found
```

如果名称和坐标同时存在：

```text
以 FR100 为定位面，位置 X=10000
```

算法会分别解析名称和坐标，再比较两边的 `object_id`。

两者指向同一对象：

```text
status=resolved
```

两者指向不同对象：

```text
status=conflict
```

这样可以避免用户写错名称或坐标时创建到错误位置。

## 6.6 坐标单位换算

内部统一使用毫米：

```python
factors = {
    "mm": 1.0,
    "cm": 10.0,
    "m": 1000.0,
}
```

例如：

```text
X=10m
```

会被换算为：

```text
10000mm
```

然后与 `ReferencePlaneRecord.coordinate_mm` 比较。

匹配条件是：

```python
abs(plane.coordinate_mm - target_mm) <= tolerance_mm
```

默认允许 0.1mm 的坐标误差。

---

# 7. AgentState 如何传递数据

代码位置：

```text
agent/state.py
```

`AgentState` 是 LangGraph 所有节点共享的状态字典。

```python
class AgentState(TypedDict, total=False):
    user_input: Required[str]
    llm_raw_output: NotRequired[str | None]
    structure_json: NotRequired[dict[str, Any] | None]
    panel_request: NotRequired[PanelRequest | None]
    reference_plane_resolution: NotRequired[
        ReferencePlaneResolution | None
    ]
    cad_result: NotRequired[CadExecutionResult | str | None]
    error: NotRequired[str | None]
    clarification: NotRequired[str | None]
    retry_count: NotRequired[int]
```

## 7.1 TypedDict

`TypedDict` 表示这是一个带字段类型说明的字典。

它本身不像 Pydantic 那样在运行时强制校验，主要用于：

- IDE 自动提示；
- 静态类型检查；
- LangGraph 理解状态结构；
- 开发者查看节点之间传递什么数据。

## 7.2 Required 与 NotRequired

```python
user_input: Required[str]
```

表示启动 Graph 时必须提供用户输入。

其他字段使用 `NotRequired`，因为它们会随着节点执行逐步产生。

状态变化示例：

```text
调用开始：
{
  user_input
}

parse 后：
{
  user_input,
  llm_raw_output
}

validate 后：
{
  user_input,
  llm_raw_output,
  structure_json
}

resolve_plane 后：
{
  ...,
  reference_plane_resolution,
  panel_request
}

cad 后：
{
  ...,
  cad_result
}
```

---

# 8. LangGraph 算法流程

代码位置：

```text
agent/graph.py
```

当前图结构：

```text
START
  ↓
parse
  ↓
validate
  ├─ error/clarification → END
  ↓
resolve_plane
  ├─ ambiguous/not_found/conflict → END
  ↓
cad
  ↓
END
```

## 8.1 parse_structure()

功能：构造 Prompt，并通过 `LocalQwen.invoke()` 调用本地模型。

主要 API：

```python
result = llm.invoke(prompt)
```

`invoke()` 是 LangChain LLM 的统一调用接口。对于当前 `LocalQwen`，它最终会进入 `_call()`。

节点返回：

```python
{
    "llm_raw_output": result,
    "error": None,
    "clarification": None,
}
```

LangGraph 会把这个字典合并到 `AgentState`。

模型调用异常时，异常被转换成：

```python
{
    "error": "本地模型调用失败：...",
    "llm_raw_output": None,
}
```

## 8.2 validate_structure()

功能：把 LLM 返回的 JSON 字符串转换为 Python 字典，并检查基本字段。

关键 API：

```python
data = json.loads(raw_output)
```

`json.loads()` 的输入是字符串，输出是 Python 对象。

非法 JSON 会抛出：

```python
json.JSONDecodeError
```

当前节点先检查厚度和材料是否缺失，但暂时不要求 LLM 必须提取出定位面。

原因是：小模型可能漏掉 `FR100`，后续 `resolve_plane` 会重新从用户原文和工程目录中确定性提取。

## 8.3 resolve_plane()

功能：加载工程标尺目录，解析用户的定位表达式，并创建最终 `PanelRequest`。

调用：

```python
planes = list_reference_planes()
resolution = resolve_reference_plane(
    user_input=state["user_input"],
    planes=planes,
    llm_reference=llm_reference,
)
```

如果解析成功：

```python
resolved_data = {
    **data,
    "reference_plane": resolution.resolved.name,
}
```

`**data` 表示复制原字典字段，再用工程正式名称覆盖 `reference_plane`。

随后执行最终强校验：

```python
panel_request = PanelRequest.model_validate(resolved_data)
```

如果解析失败，节点设置 `clarification`，Graph 不进入 CAD。

## 8.4 execute_cad()

功能：从状态中取得经过校验的 `PanelRequest`，调用 CAD 工具。

```python
result = create_panel(
    reference_plane=panel_request.reference_plane,
    boundaries=panel_request.boundaries.model_dump(),
    thickness=panel_request.thickness,
    material=panel_request.material,
)
```

此时传给 CAD 的数据已经满足：

- 定位面能够在当前工程目录中唯一解析；
- 厚度大于 0；
- 材料非空；
- 没有未知字段。

## 8.5 StateGraph API

创建 Graph：

```python
builder = StateGraph(AgentState)
```

注册节点：

```python
builder.add_node("parse", parse_structure)
builder.add_node("validate", validate_structure)
builder.add_node("resolve_plane", resolve_plane)
builder.add_node("cad", execute_cad)
```

设置入口：

```python
builder.set_entry_point("parse")
```

添加固定连线：

```python
builder.add_edge("parse", "validate")
```

添加条件连线：

```python
builder.add_conditional_edges(
    "resolve_plane",
    route_after_plane_resolution,
    {
        "cad": "cad",
        "finish": END,
    },
)
```

条件函数返回 `"cad"` 时进入 CAD，返回 `"finish"` 时结束。

最后编译：

```python
graph = builder.compile()
```

运行：

```python
result = graph.invoke(
    {
        "user_input": "请在FR100创建一块14mm厚AH36板架"
    }
)
```

---

# 9. LocalQwen 与 Ollama API

代码位置：

```text
llm/qwen_client.py
```

`LocalQwen` 继承 LangChain 的 `LLM`：

```python
class LocalQwen(LLM):
```

当业务代码调用：

```python
llm.invoke(prompt)
```

LangChain 会调用自定义 `_call()`：

```python
def _call(self, prompt, stop=None, **kwargs):
```

内部使用 Requests：

```python
response = requests.post(
    self.url,
    json=payload,
    timeout=120,
)
```

当前请求地址：

```text
http://localhost:11434/api/chat
```

关键请求字段：

```json
{
  "model": "qwen2.5:7b",
  "messages": [
    {
      "role": "user",
      "content": "Prompt内容"
    }
  ],
  "stream": false,
  "format": "json",
  "options": {
    "temperature": 0.0
  }
}
```

字段作用：

| 字段 | 功能 |
|---|---|
| `model` | 指定 Ollama 模型 |
| `messages` | Chat 格式的消息列表 |
| `stream=false` | 等模型完整生成后一次性返回 |
| `format=json` | 要求模型返回 JSON |
| `temperature=0.0` | 降低随机性，提高结构化抽取稳定性 |
| `timeout=120` | 最长等待 120 秒 |

HTTP 错误检查：

```python
response.raise_for_status()
```

当 HTTP 状态不是成功状态时，该 API 会抛出异常。

读取模型内容：

```python
response.json()["message"]["content"]
```

注意：`format="json"` 只能提高 JSON 输出概率，不能保证字段内容一定正确，所以仍然需要后续 Schema 和工程目录校验。

---

# 10. 三个完整示例

## 10.1 按工程名称定位

输入：

```text
请在 FR100 创建一块 14mm 厚的 AH36 板架。
```

流程：

```text
Qwen 提取厚度和材料
  ↓
原文匹配工程目录中的 FR100
  ↓
resolution.status = resolved
  ↓
PanelRequest.reference_plane = FR100
  ↓
create_panel()
```

即使 Qwen 把 `reference_plane` 返回为 `null`，名称解析器仍然可以直接从用户原文找到 `FR100`。

## 10.2 按坐标定位

输入：

```text
请在 X=10000 的位置创建一块 14mm 厚的 AH36 板架。
```

流程：

```text
正则提取 axis=X、value=10000、unit=mm
  ↓
查询工程目录
  ↓
找到 axis=X 且 coordinate_mm=10000 的 FR100
  ↓
PanelRequest.reference_plane = FR100
  ↓
create_panel()
```

## 10.3 名称与坐标冲突

假设 `SURFACE_20` 不是 X=10000，而用户输入：

```text
以 SURFACE_20 为定位面，位置 X=10000。
```

流程：

```text
名称解析 → SURFACE_20
坐标解析 → FR100
object_id 不一致
  ↓
resolution.status = conflict
  ↓
设置 clarification
  ↓
不调用 CAD
```

---

# 11. 如何为其他工程增加标尺面

当前 Mock 数据位于：

```python
def list_reference_planes():
```

增加一个工程标尺面：

```python
ReferencePlaneRecord(
    object_id="mock-plane-project-a",
    name="PROJECT_DATUM_A",
    aliases=[
        "A区定位面",
        "第一装配基准",
    ],
    axis="X",
    coordinate_mm=12500,
)
```

增加后可支持：

```text
以 PROJECT_DATUM_A 为定位面
以 A区定位面 创建板架
在 X=12500 的位置创建板架
```

正式接入 CAD 后，不建议手工维护该列表。应该让 CAD/MCP 返回当前打开工程的标尺面目录。

---

# 12. 如何测试

激活环境：

```powershell
conda activate ai_cad_agent
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
```

运行全部自动化测试：

```powershell
python -X utf8 -m unittest discover -s tests -v
```

预期：

```text
Ran 25 tests
OK
```

运行真实 Qwen 和 Mock CAD：

```powershell
python -X utf8 -m agent.main
```

正常创建时应看到：

```text
CREATE PANEL
Plane: FR100
Thickness: 14.0
Material: AH36
```

定位面解析测试位于：

```text
tests/test_reference_plane_tools.py
```

Graph 流程测试位于：

```text
tests/test_graph.py
```

测试中使用 `unittest.mock.patch` 替换真实 LLM 和 CAD 调用，因此测试不依赖 Ollama 是否启动，也不会创建真实 CAD 对象。

---

# 13. 当前实现的边界与后续改进

当前已经实现：

- Panel 参数强类型校验；
- 定位面名称、别名和坐标解析；
- mm、cm、m 单位换算；
- 多候选、未找到和名称坐标冲突处理；
- LLM 漏提取定位面时从用户原文恢复；
- 非法数据进入 CAD 前拦截；
- 自动化测试。

当前尚未实现：

1. `list_reference_planes()` 仍然是 Mock 数据，不是真实 CAD 查询。
2. `create_panel()` 仍然返回字符串，没有正式返回 `CadExecutionResult`。
3. 定位面对象 ID 目前只用于解析结果，还没有传给 `create_panel()`。
4. 多候选时只生成澄清文字，还没有保存用户选择并恢复原流程。
5. 坐标系目前可记录但尚未从用户输入或工程环境自动确定。
6. 尚未接入 MCP 和真实 CAD Connector。
7. 当前还不是模型原生 Tool Calling Agent，而是 LangGraph 固定流程加条件路由。

推荐下一步：

```text
标准化 create_panel
  ↓
使用 resolved.object_id 而不是定位面名称
  ↓
CadExecutionResult 结构化返回
  ↓
将 list_reference_planes 替换为 MCP/CAD 查询
  ↓
增加多轮澄清与恢复执行
```

---

# 14. 初学者应记住的核心概念

1. **Prompt 不是 Schema**  
   Prompt 只是告诉模型应该输出什么，Schema 才负责真正校验。

2. **LLM 输出不是事实**  
   LLM 提取出的定位面必须与当前 CAD 工程目录核对。

3. **Schema 不负责查数据库或 CAD**  
   Schema 只负责数据类型和业务约束，真实对象查询由 Tool 或 Resolver 完成。

4. **AgentState 是流程中的共享数据**  
   每个 LangGraph 节点读取已有状态，并返回自己新增或修改的字段。

5. **条件路由负责决定下一步**  
   成功进入 CAD，缺失、冲突或异常则结束并要求用户处理。

6. **对象 ID 比名称稳定**  
   名称适合用户阅读，对象 ID 适合 CAD 系统执行。正式版本应优先使用对象 ID。

7. **测试中应 Mock 外部依赖**  
   Schema 和 Graph 测试不应该每次都依赖真实 Ollama 或 CAD。

最终目标不是让 LLM 直接控制 CAD，而是建立一条可验证、可追踪、可拒绝错误输入的安全调用链：

```text
自然语言
  → 候选结构
  → 工程事实解析
  → Schema 校验
  → CAD Tool
  → 结构化结果
```
