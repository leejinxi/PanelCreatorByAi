以下是完整的操作方案，分为**内网操作清单**和**JSON契约文档编写指南**两部分。

---

## 第一部分：在内网需要做的事情（详细清单）

### 阶段一：准备环境（预计10分钟）

- [ ] **确认MCP服务器可访问**：确保目标软件已启动，且其MCP服务器端口/进程正常运行。
- [ ] **准备Python环境**（如果公司PC有Python）：
    ```bash
    # 安装MCP Python SDK
    pip install mcp
    ```
- [ ] **或准备Node.js环境**（如果公司PC有Node.js）：
    ```bash
    npm install @modelcontextprotocol/sdk
    ```

---

### 阶段二：导出工具契约（预计15分钟）

**核心目标**：调用MCP的 `tools/list` 方法，将所有工具定义（名称、描述、参数Schema）导出为一个JSON文件。

**方案A：使用Python脚本（推荐，最简单）**

在公司PC上创建 `export_contract.py`：

```python
import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def export_tools():
    # 修改为你的MCP服务器启动方式
    server_params = StdioServerParameters(
        command="python",  # 或 "node"，根据实际情况
        args=["path/to/your/mcp_server.py"]  # 替换为实际路径
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()

            # 提取工具定义
            tools_export = []
            for tool in result.tools:
                tools_export.append({
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.inputSchema  # 已经是JSON Schema格式
                })

            # 保存为JSON文件
            with open("mcp_contract.json", "w", encoding="utf-8") as f:
                json.dump({"tools": tools_export}, f, indent=2, ensure_ascii=False)

            print(f"✅ 成功导出 {len(tools_export)} 个工具到 mcp_contract.json")

if __name__ == "__main__":
    asyncio.run(export_tools())
```

**方案B：使用MCP Inspector（可视化操作）**

```bash
npx @modelcontextprotocol/inspector python your_server.py
```
在打开的浏览器界面中，点击“List Tools”按钮，手动复制所有工具定义。

**方案C：使用TypeScript脚本**

```typescript
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import fs from "fs";

const transport = new StdioClientTransport({
    command: "python",
    args: ["your_server.py"]
});

const client = new Client({ name: "exporter", version: "1.0" });
await client.connect(transport);
const { tools } = await client.listTools();
fs.writeFileSync("mcp_contract.json", JSON.stringify({ tools }, null, 2));
```

---

### 阶段三：录制真实返回数据（预计20分钟，强烈推荐）

为了让Mock服务器返回逼真的数据，你需要为**每个工具**录制至少一组真实的调用结果。

- [ ] **方法1：手动调用工具**
    - 使用MCP Inspector的“Call Tool”功能，输入参数，记录返回结果。
- [ ] **方法2：编写录制脚本**

```python
# 在阶段二的脚本基础上扩展
async def record_tool_calls():
    # ... 连接服务器 ...
    tools = await session.list_tools()

    # 对每个工具，手动构造测试参数
    test_cases = {
        "create_plate": {"length": 1000, "width": 500, "thickness": 10},
        "get_plate_info": {"plate_id": "PLATE-001"},
        # 为每个工具添加一组测试参数
    }

    recordings = {}
    for tool in tools.tools:
        if tool.name in test_cases:
            result = await session.call_tool(tool.name, arguments=test_cases[tool.name])
            recordings[tool.name] = {
                "input": test_cases[tool.name],
                "output": result.content[0].text if result.content else None
            }

    with open("mcp_recordings.json", "w") as f:
        json.dump(recordings, f, indent=2)
```

- [ ] **方法3：从应用日志中提取**
    - 如果公司软件有日志系统，从日志中查找真实的工具调用记录。

---

### 阶段四：导出文件并带出内网

- [ ] **确认导出的文件**：
    - `mcp_contract.json` —— 工具定义（必带）
    - `mcp_recordings.json` —— 录制数据（强烈推荐）
- [ ] **通过公司允许的介质**（U盘、刻录光盘、打印后手动录入等）将文件带到个人PC。

---

## 第二部分：JSON契约文档编写指南

### 1. 完整的契约文档结构

```json
{
  "version": "1.0",
  "server": {
    "name": "船舶板架设计系统",
    "description": "内网船舶板架设计MCP服务器"
  },
  "tools": [
    {
      "name": "create_plate",
      "description": "创建船舶板架结构",
      "inputSchema": {
        "type": "object",
        "properties": {
          "length": {
            "type": "number",
            "description": "板架长度（mm）",
            "minimum": 100,
            "maximum": 10000
          },
          "width": {
            "type": "number",
            "description": "板架宽度（mm）",
            "minimum": 100,
            "maximum": 5000
          },
          "thickness": {
            "type": "number",
            "description": "板厚（mm）",
            "minimum": 1,
            "maximum": 50
          },
          "material": {
            "type": "string",
            "description": "材料类型",
            "enum": ["Q235", "Q345", "不锈钢304"]
          }
        },
        "required": ["length", "width"]
      },
      "mock_responses": [
        {
          "input": {"length": 1000, "width": 500, "thickness": 10},
          "output": {
            "type": "text",
            "text": "板架创建成功，ID: PLATE-2026-001，重量: 45.2kg，材料: Q235"
          }
        },
        {
          "input": {"length": 2000, "width": 1000, "thickness": 15},
          "output": {
            "type": "text",
            "text": "板架创建成功，ID: PLATE-2026-002，重量: 180.5kg，材料: Q345"
          }
        }
      ]
    },
    {
      "name": "get_plate_info",
      "description": "查询已有板架的详细信息",
      "inputSchema": {
        "type": "object",
        "properties": {
          "plate_id": {
            "type": "string",
            "description": "板架ID",
            "pattern": "^PLATE-\\d{4}-\\d{3}$"
          }
        },
        "required": ["plate_id"]
      },
      "mock_responses": [
        {
          "input": {"plate_id": "PLATE-2026-001"},
          "output": {
            "type": "text",
            "text": "板架详情：ID=PLATE-2026-001，长度=1000mm，宽度=500mm，厚度=10mm，材料=Q235，重量=45.2kg，创建时间=2026-09-08"
          }
        }
      ]
    }
  ]
}
```

### 2. inputSchema 的JSON Schema规范

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `type` | string | ✅ | 固定为 `"object"` |
| `properties` | object | ✅ | 定义每个参数 |
| `required` | array | ❌ | 必填参数名称列表 |
| `additionalProperties` | boolean | ❌ | 是否允许额外参数，默认true |

**参数属性的常用字段**：

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `type` | string | 参数类型 | `"string"`, `"number"`, `"integer"`, `"boolean"`, `"array"`, `"object"` |
| `description` | string | 参数说明 | `"板架长度（mm）"` |
| `minimum` / `maximum` | number | 数值范围 | `"minimum": 100` |
| `enum` | array | 枚举值列表 | `["Q235", "Q345"]` |
| `pattern` | string | 正则表达式 | `"^PLATE-\\d{4}-\\d{3}$"` |
| `items` | object | 数组元素类型 | `{"type": "string"}` |
| `default` | any | 默认值 | `"default": 10` |

### 3. mock_responses 的格式规范

每个工具下的 `mock_responses` 数组，每个元素包含：

| 字段 | 类型 | 说明 |
|------|------|------|
| `input` | object | 调用时的输入参数（用于匹配） |
| `output` | object | 对应的返回结果 |
| `output.type` | string | 返回类型：`"text"`, `"image"`, `"embedded_resource"` |
| `output.text` | string | 当type为text时的返回内容 |
| `output.isError` | boolean | 是否为错误响应 |

### 4. 最佳实践

1. **参数描述要详细**：让LangGraph的LLM能理解每个参数的含义。
2. **提供多个mock样本**：覆盖不同输入场景（正常值、边界值、错误情况）。
3. **使用enum限制参数**：如果参数只有有限选项，用 `enum` 明确列出。
4. **保持契约与实际服务器一致**：当内网软件升级时，重新导出契约。

---

## 第三部分：回到个人PC后的操作

拿到 `mcp_contract.json` 后，参考之前方案一的方法，在个人PC上启动Mock服务器即可开始本地回环测试。

**极简Mock服务器示例（使用FastMCP）**：

```python
import json
from mcp.server.fastmcp import FastMCP

with open("mcp_contract.json") as f:
    contract = json.load(f)

mcp = FastMCP("MockServer")

for tool in contract["tools"]:
    # 动态注册每个工具
    @mcp.tool(
        name=tool["name"],
        description=tool["description"],
        inputSchema=tool["inputSchema"]
    )
    def mock_handler(**kwargs):
        # 简单匹配：返回第一个mock_response
        if "mock_responses" in tool and tool["mock_responses"]:
            return tool["mock_responses"][0]["output"]["text"]
        return f"工具 {tool['name']} 被调用，参数: {kwargs}"

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

---

## 总结：文件流转图

```
内网PC                                   个人PC
┌─────────────────┐                    ┌─────────────────┐
│  真实MCP服务器   │                    │   LangGraph     │
│  (船舶设计软件)  │                    │   Agent         │
└────────┬────────┘                    └────────┬────────┘
         │                                      │
         ▼                                      ▼
┌─────────────────┐   U盘/打印   ┌─────────────────┐
│ tools/list导出   │ ───────────▶ │ 契约JSON文件     │
│ + 录制真实数据   │              │ (几KB~几十KB)   │
└─────────────────┘              └────────┬────────┘
                                          │
                                          ▼
                                   ┌─────────────────┐
                                   │  Mock服务器     │
                                   │  (本地回环)     │
                                   └─────────────────┘
```

整个过程中，**带出内网的只有纯文本的JSON文件**，不包含任何代码、二进制文件或公司软件本体，完全符合网络安全规定。
---

## 个人 PC 原理验证（当前采用）

当前无法从公司电脑取得接口定义或数据，因此本仓库中的 `contracts/FULL_contract_with_data.json` 是个人 PC 上自行拟定的实验契约，不代表公司 CAD API。

验证链路：浏览器 → FastAPI → LangGraph → 本机 Ollama → `McpCadBackend` → MCP STDIO Client → 独立 Mock MCP Server → 契约数据 → 页面结果。

启动：

```powershell
conda activate ai_cad_agent
python -m pip install -r requirements.txt
$env:CAD_BACKEND = "mcp"
$env:MCP_CONTRACT_PATH = "contracts/FULL_contract_with_data.json"
python run_web.py
```

浏览器访问 `http://127.0.0.1:8000`。健康接口应显示 `mode=mcp` 和 `cad_backend=mcp-contract-mock`；成功结果的对象 ID 为 `mock-mcp-panel-001`。

可直接编辑契约的 `inputSchema`、`outputSchema` 和 `mockResponses`。响应按顺序匹配，第一个满足 `match` 中全部字段的场景生效，因此空 `match` 必须放在最后。修改契约后无需重新构建代码；下一次 MCP 调用会启动新进程并重新读取取文件。

推荐手工输入：

- 成功：`请在第100肋位创建一块14mm厚的AH36板架`
- 定位面失败：`请在MISSING创建一块14mm厚的AH36板架`
- CAD 不可用：`请在FR100创建一块14mm厚的UNAVAILABLE材料板架`

以上错误触发词仅属于本约，不是公司 CAD 规则。自动验证执行 `python -X utf8 run_tests.py`。真实 Ollama 测试需要本机服务和 `qwen2.5:7b`；普通测试使用固定模型输出，保持离线可重复。
