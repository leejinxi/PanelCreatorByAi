# AI Ship CAD Copilot

一个面向船舶结构设计的自然语言 CAD Agent 原型。当前 MVP 支持从中文需求中抽取板架参数、解析工程定位面，并通过 Mock CAD 后端创建板架对象。

## 当前能力

- 识别“创建板架”意图并拒绝不支持的任务。
- 抽取厚度、材料、四向边界和定位面。
- 按工程名称、别名或 `X=10000` 等坐标表达式解析定位面。
- 检测定位面未找到、歧义和名称/坐标冲突。
- 参数不完整时支持最多 3 轮命令行补充。
- 使用 Pydantic 契约阻止未经校验的数据进入 CAD 层。

当前 `tools/reference_plane_tools.py` 中的工程目录与 `tools/cad_tools.py` 中的 CAD 后端都是 Mock，尚未连接真实 CAD 或 MCP。

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

## 架构概览

```text
用户输入
  -> 本地 Qwen 结构化抽取
  -> 动作与基础字段校验
  -> 当前工程定位面确定性解析
  -> PanelRequest 完整校验
  -> CAD 工具适配层
  -> Mock CAD Backend
```

核心代码：

- `agent/main.py`：CLI 与多轮补充入口。
- `agent/graph.py`：LangGraph 工作流与安全路由。
- `schemas/`：动作、板架、定位面和执行结果的数据契约。
- `tools/reference_plane_tools.py`：定位面解析。
- `tools/cad_tools.py`：CAD 工具契约和 Mock 后端。
- `llm/qwen_client.py`：Ollama/Qwen 客户端。

更完整的工程约定与已知限制见 `AGENTS.md`，设计资料与后续计划见 `Doc/Plan/` 和 `Doc/TODO.md`。
