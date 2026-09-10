# 工程上下文：AI Ship CAD Copilot

## 项目目标

本项目是面向船舶 CAD 结构设计的自然语言 Agent 原型。当前 MVP 只处理“创建板架（panel）”：从用户描述中抽取板架参数，解析当前工程中的定位面，校验参数后调用 CAD 工具。

不要把当前原型描述为真实 CAD 集成。工程对象目录、Direct Mock 与 MCP Contract Mock 均为模拟能力；真实 CAD Provider 尚未接入。本地实验契约 boundary_list_0.2.json 已按用户确认启用，旧四向契约仍被拦截。

## 当前执行链路

入口为 `agent/main.py`，核心 LangGraph 在 `agent/graph.py`：

1. `parse`：调用本地 Qwen，把用户输入解析为 `AgentActionPlan` JSON。
2. `validate`：校验动作与基础参数；从用户原文重放边界追加/替换，强制至少1条合法边界；模型结构无效时最多重试1次。
3. `decide_before_inspection`：安全策略生成首次 `AgentDecision`，决定是否查询工程上下文。
4. `inspect_project_context`：在仓库内 Demo JSON 中确定性匹配定位面和全部边界；当前仍是 Mock。
5. `decide_after_inspection`：Qwen 根据结构化查询结果选择创建、澄清或停止；确定性 fallback / safety override 负责兜底。
6. `safety_gate`：复核请求、对象匹配、最终动作和决策步数，显式授权后才进入 `cad`。
7. `cad`：调用稳定 `create_panel()` 契约；Direct Mock 或 MCP Contract Mock 都不创建真实模型。

安全边界：参数缺失、边界非法或修改不明确时停止并澄清；Demo 目录中对象未找到、歧义、不可用或角色不允许时不得创建；Provider 拒绝和运行异常返回受控错误。Mock 目录匹配不等于真实工程事实，也不验证几何有效性。

## 目录职责

- `agent/`：LangGraph 编排、共享状态、CLI 和多轮补充逻辑。
- `schemas/`：Pydantic 领域契约。跨层数据优先使用这里的强类型模型。
- `tools/reference_plane_tools.py`：历史定位面目录与确定性解析，不在主 Graph 中。
- `agent/boundary_session.py`：CLI/Web 共用的原文边界多轮规则。
- `tools/project_context_tools.py`：Demo 工程目录加载、确定性对象匹配与只读查询。
- `mock_data/demo_project.json`：为页面演示精选的 Mock 工程对象，不代表实时 CAD 工程。
- `tools/cad_tools.py`：稳定 CAD 工具契约、后端协议和 Mock 后端。
- `llm/qwen_client.py`：通过 Ollama HTTP API 调用本地 `qwen2.5:7b`。
- `tests/`：基于标准库 `unittest` 的单元测试和本地端到端测试。
- `Doc/Plan/`：设计方案和阶段计划；`Doc/TODO.md` 记录待办。

## 本地运行

建议使用 Python 3.11。安装依赖：

```powershell
python -m pip install -r requirements.txt
```

完整运行需要本地 Ollama 服务监听 `http://localhost:11434/api/chat`，并准备模型 `qwen2.5:7b`。运行单次请求：

```powershell
python -m agent.main "在 FR100 创建板架，厚度 14mm，材料 AH36，边界 >SL10"
```

不传请求参数时进入最多 3 轮补充的交互模式：

```powershell
python -m agent.main
```

运行测试：

```powershell
python run_tests.py
```

## 实现约定

- 保持 LLM 只负责语言理解；工程对象是否存在必须由 CAD/Provider 数据和确定性解析确认。
- 用户明确给出的定位面原文不得由模型擅自改名。
- 新增跨层请求或结果时，先在 `schemas/` 定义 Pydantic 模型，并默认拒绝未知字段。
- 只有通过 `PanelRequest` 校验的数据才能进入 CAD 层。
- CAD 层对外返回 `CadExecutionResult`，不要把后端异常直接泄漏给调用方。
- Provider 替换应保持 `CadBackend` 和定位面解析层的稳定契约，避免让 Graph 依赖具体 CAD 实现。
- 新行为必须补充 `tests/test_*.py`；测试默认不得依赖正在运行的 Ollama 或真实 CAD。
- 项目文件统一使用 UTF-8。读取中文文档时在 Windows PowerShell 中显式使用 `Get-Content -Encoding UTF8`。

## 当前已知限制与优先事项

- `list_reference_planes()` 使用硬编码 Mock 数据，且尚无 `project_id` 隔离。
- `MockCadBackend` 只生成随机对象 ID，不创建真实模型。
- Qwen 地址、模型名和超时时间目前写在 `LocalQwen` 默认字段中，尚未配置化。
- 当前只支持 `create_panel`；其他意图必须返回 unsupported，不能隐式扩展执行范围。
- 定位面缓存、工程切换、稳定 object ID、幂等和真实 CAD 集成仍待实现。MCP 超时与异常映射已有回归，新版数组契约已启用，对象匹配仍待实现。

详细设计依据见 `Doc/Plan/Panel_Schema与定位面解析流程详细讲解_v1.0.md` 和 `Doc/Plan/AI_Ship_CAD_Copilot_Agent工程化实现阶段详细计划_v1.0.md`。

## 项目范围补充

当前 MVP 聚焦“AI + 创建板架（panel）”。标准开发环境为 Python 3.11、conda 环境 `ai_cad_agent`、Ollama `qwen2.5:7b`，自定义 `LocalQwen` HTTP Client 与 LangGraph Agent 基础框架已经完成。

后续主线为：完善参数/边界解析与校验；完善 Mock CAD 和稳定 Provider 契约；设计 MCP 并打通 Python Agent 与 C++ CAD 软件；在核心执行链稳定后引入 RAG。

最终 CAD 模型必须由 C++ CAD 软件创建。Python Agent 只负责自然语言理解、流程编排、参数校验和工具调用，不得替代正式 CAD 几何建模。现有 Web 仅为本地演示工作台；不扩展正式 CAD 前端、自动强度设计、stiffener（扶强材）和其他结构类型。

## 架构与责任边界

```text
用户自然语言
  -> LocalQwen / Ollama：意图和字段抽取
  -> LangGraph：状态、校验、澄清和安全路由
  -> 确定性 Provider：确认定位面等工程事实
  -> CadBackend / MCP：提交经过校验的请求
  -> C++ CAD 软件：创建最终 CAD 模型
```

- LLM 输出是候选参数，不是工程事实或可直接执行的 CAD 指令。
- RAG 未来用于专业知识、设计规则和术语解释，不得代替 CAD 工程对象查询。
- MCP 是 Agent 与真实 CAD 能力之间的通信边界；Graph 不应依赖具体 C++ 实现。
- Mock 与真实 Provider 应保持稳定契约，切换后不应迫使上层流程重写。

## 跨 PC 开发规则

- 禁止在代码、配置、测试和文档命令中硬编码个人用户名、盘符或机器专属绝对路径，例如 `C:\Users\某人` 或 `D:\某仓库`。
- 运行时路径应由仓库相对路径、`pathlib.Path(__file__)`、工作目录、环境变量或显式配置推导。
- Ollama 地址、模型名、超时、CAD/MCP 端点等机器相关信息应逐步配置化；不得增加新的硬编码点。
- 不提交 conda/虚拟环境、缓存、密钥或机器专属配置。新电脑应以 `requirements.txt` 重建依赖，不复制环境目录。
- 文档命令应能从仓库根目录运行，并优先使用跨机器可复现的相对路径。

## 测试与运行原则

- 执行 Python 命令前确认已激活 `ai_cad_agent` 且 `python --version` 为 3.11，防止系统旧版 Python 被误用。
- 默认运行 `python run_tests.py`；单元测试应以 Mock、桩或依赖注入隔离 Ollama 和真实 CAD。
- 完整本地运行需要 Ollama 和 `qwen2.5:7b`；服务缺失时应返回受控错误。
- 修改 Graph、Schema、定位面解析或 CAD 契约时，必须覆盖成功、缺参、歧义、冲突、超时和后端异常等安全分支。
- 正式建模必须由 C++ CAD 软件完成；不得把 RAG 结果直接当作工程对象或执行参数。
- 提交前检查 `git diff`、运行相关测试，并确认没有把 Mock 描述成真实集成。

## Codex 接手顺序

1. 根目录 `AGENTS.md`：范围、约束、架构边界和工作规则。
2. `Doc/current_status.md`：当前完成度、已知限制和近期主线。
3. `README.md`：运行入口和仓库概览。
4. `Doc/TODO.md`：候选待办；部分条目可能晚于代码更新才会勾选。
5. 与任务相关的 `Doc/Plan/` 文档：板架 Schema/定位面任务优先阅读 `Panel_Schema与定位面解析流程详细讲解_v1.0.md`，整体工程化任务优先阅读 `AI_Ship_CAD_Copilot_Agent工程化实现阶段详细计划_v1.0.md`。

阅读后必须检查 Git 状态、相关实现和测试，避免覆盖未提交改动，也不要只依据旧计划判断现状。`Doc/current_status.md` 是当前状态入口；旧计划用于理解设计背景。
