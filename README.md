# AI Ship CAD Copilot

一个面向船舶结构设计的自然语言 CAD Agent 原型。当前 MVP 支持从中文需求中抽取板架参数，并通过直接 Mock 或本地 MCP Contract Mock 模拟创建板架。

## 当前能力

- 识别“创建板架”意图并拒绝不支持的任务。
- 抽取厚度、材料、四向边界和定位面。
- 将已知标尺面（FR/SL/LV）表达规范化；未知定位面名称原文交给 CAD Backend 判断。
- 通过 CAD Backend 返回定位面不存在、CAD 不可用等稳定错误码。
- 参数不完整时支持最多 3 轮命令行补充。
- 使用 Pydantic 契约阻止未经校验的数据进入 CAD 层。

当前 `tools/cad_tools.py` 的默认后端是 Direct Mock；本地 MCP Contract Mock 可通过配置启用，尚未连接真实 CAD。

## 快速开始

环境建议：Python 3.11、Ollama、`qwen2.5:7b`。

```powershell
python -m pip install -r requirements.txt
ollama pull qwen2.5:7b
python -m agent.main "在 FR100 创建板架，厚度 14mm，材料 AH36"
```

进入交互补充模式：

```powershell
python -m agent.main
```

运行测试：

```powershell
python run_tests.py
```

启用本地 MCP Contract Mock：

推荐使用一键演示脚本：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_mcp_demo.ps1
```

也可以手动设置环境变量：

```powershell
$env:CAD_BACKEND = "mcp"
$env:MCP_CONTRACT_PATH = "contracts/FULL_contract_with_data.json"
$env:MCP_TIMEOUT_SECONDS = "10"
python run_web.py
```

## 架构概览

```text
用户输入
  -> 本地 Qwen 结构化抽取
  -> 动作与基础字段校验
  -> 已知标尺面规范化，未知名称原文直传
  -> PanelRequest 完整校验
  -> CAD 工具适配层
  -> Mock CAD Backend
```

核心代码：

- `agent/main.py`：CLI 与多轮补充入口。
- `agent/graph.py`：LangGraph 工作流与安全路由。
- `schemas/`：动作、板架、定位面和执行结果的数据契约。
- `tools/reference_plane_tools.py`：历史定位面解析模块，当前不参与主 Graph。
- `tools/cad_tools.py`：CAD 工具契约和 Mock 后端。
- `tools/mcp_cad_backend.py`：本地 MCP Contract Mock 适配器。
- `llm/qwen_client.py`：Ollama/Qwen 客户端。

浏览器页面会显示 `Direct Mock CAD` 或 `MCP Contract Mock`，两者都只模拟执行，不修改真实 CAD 工程。更完整的工程约定与已知限制见 `AGENTS.md`，设计资料与后续计划见 `Doc/Plan/` 和 `Doc/TODO.md`。
