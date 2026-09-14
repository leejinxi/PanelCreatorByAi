# AI Ship CAD Copilot

面向船舶结构设计的自然语言 Agent 原型。当前 Web 演示以“全船结构模型错误治理”为主入口，展示错误归组、受控决策、风险分流和模拟恢复结果；原有“创建板架（panel）”流程作为下钻能力和独立 CLI 保留。

**当前工程目录、错误快照、CAD 诊断和执行结果均为 Mock，尚未接入真实 CAD。** Python Agent 负责语言理解、流程编排、参数校验和工具调用；最终模型创建与几何校验必须由 C++ CAD 软件完成。

## 当前能力

### 全船模型错误治理

- 从未分组的 Mock 错误快照读取错误码、对象父子关系、工程升级事件和诊断候选，确定性归并问题，不由 LLM 编造工程事实。
- 根据诊断生成每组 `allowed_routes`，由独立 LangGraph 调用 Qwen 选择结构化路线；输出非法、越权或模型不可用时使用 fallback / safety override。
- 支持“只分析，不修改”“安全项自动处理”“所有修改需确认”三类治理策略；策略解析使用确定性规则。
- Workflow 根据复核后的计划分流，执行接口逐组检查候选与授权；只分析模式不允许修复，需要确认的组必须收到显式确认。
- 展示决策来源、依据、允许路线、授权结果、模拟恢复数量及剩余工作清单。

固定 Demo 包含 **36 条错误、4 个问题组、23 条关联错误**。默认安全策略下的分流为：

| 问题组 | 场景 | 错误数 | 默认路线 |
| --- | --- | ---: | --- |
| GROUP-A | 板架边界数据升级未完整迁移 | 15 | 确认后模拟更新 |
| GROUP-B | 可恢复的重算问题 | 11 | 低风险自动路线 |
| GROUP-C | 肘板依赖变化导致边界失效 | 6 | 转人工重选边界 |
| GROUP-D | 几何内核异常 | 4 | 转研发处理 |

路线会随治理策略、候选校验和 Qwen 合法选择变化。默认路线下，点击“执行可恢复项”并确认需授权的组后，模拟恢复 26 条、剩余 10 条。当前恢复逻辑只生成 Mock 结果，不调用真实重算、更新或修复后几何复核接口。

### 板架创建与下钻

- 解析定位面、厚度、材料和至少一条边界；支持原文边界校验、去重、缺参澄清及多轮追加/替换。
- 查询本地 Demo 工程目录，区分唯一命中、未找到、歧义、不可用和角色不允许。
- 查询前使用安全策略，查询后由 Qwen 选择创建、澄清或停止；最终经过 Execution Preflight / Safety Gate 才能调用 CAD Mock。
- Web 展示六段实际行为链及两次 Qwen 调用耗时；旧设计评审和决策护照已退出默认展示，旧评审也不再作为创建授权条件。
- GROUP-A 的“查看板架更新方案”展示只读操作快照；GROUP-B 的“板架自动更新说明”复用创建表单与决策链。该创建契约不会更新错误板架。

板架创建工具当前只支持 `create_panel`，其他意图返回 unsupported。错误治理中出现肘板、骨材等对象，不代表已支持这些结构的创建。

## 快速开始

以下命令均从仓库根目录执行。标准环境为 Python 3.11、conda 环境 `ai_cad_agent` 和本地 Ollama 模型 `qwen2.5:7b`。

首次创建环境（已有环境可跳过第一行）：

```powershell
conda create -n ai_cad_agent python=3.11 -y
conda activate ai_cad_agent
python --version
python -m pip install -r requirements.txt
ollama pull qwen2.5:7b
```

确认 Python 为 3.11，并确保 Ollama 服务运行在 `http://localhost:11434`。若服务未启动，可在另一终端运行 `ollama serve`。模型不可用时，错误治理回退到安全策略；板架解析返回受控错误。

### 启动 Web 演示

```powershell
conda activate ai_cad_agent
$env:CAD_BACKEND = "mock"
python -X utf8 run_web.py
```

打开 [本地演示工作台](http://127.0.0.1:8000)，从错误治理首页开始：

1. 点击“了解 Mock 场景”，查看版本升级背景和演示边界。
2. 选择本轮治理策略，点击“分析当前工程错误”。
3. 查看问题组、决策来源及处理路线；只分析模式下不能执行修复。
4. 在允许执行的策略下点击“执行可恢复项”，查看模拟结果与剩余清单。
5. 从问题组进入板架更新方案或自动更新说明。

### 使用 MCP Contract Mock

先用 `Ctrl+C` 停止旧 Web 服务，再运行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_mcp_demo.ps1
```

脚本使用 `ai_cad_agent`，设置 `CAD_BACKEND=mcp`、数组契约和 10 秒 MCP 超时。也可手动启动：

```powershell
conda activate ai_cad_agent
$env:CAD_BACKEND = "mcp"
$env:MCP_CONTRACT_PATH = "contracts/boundary_list_0.2.json"
$env:MCP_TIMEOUT_SECONDS = "10"
python -X utf8 run_web.py
```

**MCP 模式仅切换板架创建后端，错误治理仍使用本地 Mock 快照和模拟恢复逻辑。** Direct Mock 不产生 MCP Request/Response；MCP 模式下的板架创建通过真实 STDIO 子进程通信，但服务端仍是 Contract Mock。

代码或配置更新后应重启服务，并执行一次 `Ctrl+F5`。可通过 [健康检查](http://127.0.0.1:8000/api/health) 查看配置；健康检查不证明 MCP 调用成功，实际请求以页面 Trace 和 MCP Call Inspector 为准。

### CLI 创建板架

```powershell
conda activate ai_cad_agent
$env:CAD_BACKEND = "mock"
python -X utf8 -m agent.main "在FR100创建14mm厚AH36板架，边界 >SL10"
```

不传请求参数时进入最多 3 轮补充的交互模式：

```powershell
python -X utf8 -m agent.main
```

先输入“在第100肋位创建14mm厚AH36板架”，系统要求补充边界；再输入“边界 >SL10”，继续校验并模拟创建。

## 边界规则与契约

- 每条边界为 `<` 或 `>` 加目标，至少一条，支持超过四条；比较符只校验和透传，不解释几何关系。
- 相同符号与目标去重，同一目标的不同符号分别保留；非法片段不能被忽略。
- 澄清期间支持“追加边界 <LV2”“将 >SL10 改为 >SL12”“边界全部改为 <LV8”。修改不明确时继续澄清。
- 目标包含空格或分隔符时使用引号，例如 `<"Deck A"`；PowerShell 可用单引号包裹整条需求以保留双引号。
- 边界执行依据来自用户原文，不能使用 LLM 补造的边界；目录匹配成功不代表真实几何有效。

`contracts/boundary_list_0.2.json` 是已确认的本地实验契约，版本 `0.2-poc`，使用至少一条 `operator/target` 数组。它不代表公司 CAD API 已确认。旧 `FULL_contract_with_data.json` 四向契约和未确认的 `boundary_list_0.2_draft.json` 保留用于历史追溯及拒绝回归，运行时在发送前拦截。

## 架构与目录

```text
错误治理：Mock 错误快照 → 确定性归组与允许路线 → Qwen 路线选择
        → 计划复核与 Workflow 分流 → 执行接口逐组授权 → 模拟结果收口

板架创建：自然语言 → Qwen 参数抽取 → 原文边界与 Schema 校验
        → Mock 工程查询 → Qwen 查询后决策 → Safety Gate
        → CadBackend → Direct Mock / MCP STDIO Contract Mock
```

| 路径 | 职责 |
| --- | --- |
| `agent/model_error_graph.py` | 独立错误治理 LangGraph 与 Qwen 决策 |
| `tools/model_error_tools.py` | 确定性归组、路线复核、逐组授权和模拟恢复 |
| `agent/graph.py`、`agent/boundary_session.py` | 板架创建编排与 CLI/Web 共用边界多轮规则 |
| `schemas/` | Pydantic 领域契约 |
| `tools/project_context_tools.py` | Demo 工程对象确定性匹配 |
| `tools/cad_tools.py`、`tools/mcp_cad_backend.py` | CAD 后端契约与 MCP 适配 |
| `mcp_client/`、`mcp_mock/` | MCP STDIO 客户端与 Contract Mock 服务端 |
| `mock_data/`、`contracts/` | Mock 数据与版本化实验契约 |
| `llm/qwen_client.py` | 本地 Ollama HTTP Client |
| `webapp/` | 本地演示页面、API 和响应映射 |
| `tests/` | 单元测试与本地 STDIO 集成回归 |

错误治理 API：`POST /api/model-errors/analyze`、`POST /api/model-errors/repair/{task_id}`、`GET /api/model-errors/status/{task_id}`；只读板架操作详情为 `GET /api/operations/{operation_id}`。治理任务和操作详情保存在服务内存中，重启后不保留。

## 测试

```powershell
conda activate ai_cad_agent
python --version
python -B -X utf8 run_tests.py
```

默认测试隔离真实 Ollama/CAD，MCP 回归会启动本机 STDIO 子进程。2026-09-14 回归结果：212 项，211 项通过，1 项真实 Ollama E2E 按设计跳过。需要运行真实 Ollama E2E 时：

```powershell
$env:RUN_LOCAL_E2E = "1"
python -B -X utf8 run_tests.py
Remove-Item Env:RUN_LOCAL_E2E
```

## 当前限制与后续方向

当前不验证 CCS、结构强度、真实几何或设计正确性，也不提供正式 CAD 前端。真实工程查询、修复后复核、持久化任务、幂等、多工程隔离及 MCP/C++ CAD Provider 尚待实现。Ollama 地址、模型名和超时仍使用 `LocalQwen` 默认字段。

后续先与 CAD 团队确认错误快照、对象依赖、重算、更新和复核契约，再替换 Mock Provider。RAG 暂缓，未来也不能替代工程对象查询和几何校验。

更多背景见 [当前状态](Doc/current_status.md)、[待办](Doc/TODO.md)、[错误治理开发方案 v2.0](Doc/Plan/AI_Ship_CAD_Copilot_全船模型错误治理Agent开发方案_v2.0.md) 和 [视频演示流程](Doc/视频演示.md)。状态文档与历史方案中的旧描述应结合当前代码核对。
