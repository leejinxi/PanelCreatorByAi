# AI Ship CAD Copilot 当前状态

更新时间：2026-08-21

本文档记录仓库当前可确认的实现状态、范围边界和近期方向。它是状态快照，不替代 `Doc/Plan/` 的详细设计或 `Doc/TODO.md` 的待办管理。若描述不一致，应先以当前代码和测试为准，再同步文档。

## 项目定位

当前 MVP 只聚焦“AI + 创建板架（panel）”：理解中文需求、抽取板架参数、确认工程定位面、完成安全校验，然后调用 CAD 工具契约。

当前不是正式 CAD 集成产品。定位面目录和 CAD 创建后端仍是 Mock；MCP 与真实 C++ CAD Provider 尚未接入。最终 CAD 模型必须由 C++ CAD 软件创建，Python Agent 不承担正式几何建模。

## 当前已完成

### 开发与模型环境

- 目标运行环境为 Python 3.11，标准 conda 环境名称为 `ai_cad_agent`。
- 本地模型运行方式为 Ollama，当前模型为 `qwen2.5:7b`。
- 已实现自定义 `LocalQwen` HTTP Client，通过 Ollama `/api/chat` 接口请求结构化结果。
- 已建立 `requirements.txt` 和统一测试入口 `run_tests.py`。

### Agent 基础框架

- 已建立 LangGraph 工作流和共享状态。
- 已实现单次命令行请求及最多 3 轮补充信息的交互入口。
- 已实现 `create_panel` 与 `unsupported` 的动作边界。
- 模型结构化输出无效时支持有限重试；流程错误以受控消息返回。

### 板架、定位面与 CAD 契约

- 已定义动作、板架、边界、定位面解析和 CAD 执行结果等 Pydantic 契约。
- 已具备板厚、材料、边界和定位面等基础字段的抽取与校验链路。
- 已实现按名称、别名和坐标解析定位面，并处理未找到、歧义及名称/坐标冲突。
- 解析优先依据用户原文；只有完整 `PanelRequest` 且定位面唯一解析成功时才允许进入 CAD 节点。
- 已定义 `CadBackend` 和 `create_panel()` 契约，并实现不会创建真实模型的 `MockCadBackend`。
- 已有 Schema、Graph、定位面解析、Qwen Client、CLI、CAD 工具及本地端到端测试。

## 当前执行链路

```text
用户输入
  -> LocalQwen 提取 AgentActionPlan
  -> LangGraph 校验动作和基础参数
  -> 确定性解析当前工程定位面
  -> 组装并完整校验 PanelRequest
  -> create_panel / CadBackend
  -> 当前为 Mock；未来通过 MCP 调用 C++ CAD 软件
```

参数缺失或非法、定位面不存在或不唯一、名称与坐标冲突、模型输出不可恢复、Provider 不可用或执行失败时，必须澄清或返回受控错误，不得创建对象。

## 尚未完成与近期主线

### 参数、边界和校验

- 继续完善板架边界表达、工程单位、坐标系、容差和业务规则。
- 扩充真实表达的回归样例，并完善候选定位面的多轮选择和流程恢复。

### Mock 与 Provider

- 增加 `project_id` 隔离、刷新策略和稳定对象 ID。
- 将硬编码定位面目录替换为可切换 Provider。
- 增加超时、错误码、幂等、日志和缓存失效策略。

### MCP 与 C++ CAD

- 定义定位面查询和板架创建的 MCP Tool、Schema、错误码及版本策略。
- 打通 Python Agent 到 C++ CAD 软件的通信。
- 由 C++ CAD 软件查询工程事实并创建最终模型；Agent 只提交经过验证的强类型请求。
- 建立真实 CAD 集成测试环境，同时保留 Mock 快速回归。

### RAG

- 在核心执行链稳定后引入 RAG。
- RAG 只用于设计规则、行业术语、命名规范和专业解释，不替代实时工程对象目录。
- 知识文档与当前 CAD 工程状态冲突时，以 CAD Provider 的工程事实为准。

## 当前不做

- 前端（FE）或完整产品界面。
- 自动强度设计、校核或优化。
- stiffener（扶强材）创建与布置。
- 板架之外的其他结构类型和泛化 CAD Agent。
- 在 Python 中直接生成最终 CAD 几何模型。

这些方向只有在板架 MVP、MCP 和真实 C++ CAD 链路稳定并明确调整范围后才进入计划。

## 环境与运行

```powershell
conda activate ai_cad_agent
python --version
python -m pip install -r requirements.txt
python run_tests.py
```

Python 版本应为 3.11。完整本地推理还需要：

```powershell
ollama pull qwen2.5:7b
python -m agent.main "在 FR100 创建板架，厚度 14mm，材料 AH36"
```

跨电脑工作时禁止把个人目录、盘符或其他机器专属绝对路径写入代码和配置。

## 接手与核验

- 先阅读根目录 `AGENTS.md`，再阅读本文档、`README.md` 和任务相关设计文档。
- 修改前检查 Git 状态，保留其他人的未提交内容。
- `Doc/TODO.md` 部分事项可能已由代码实现但尚未同步勾选；开始工作前需核对实现与测试。
- 修改行为必须补充或更新测试，并确保安全停止分支仍然成立。
- 对外说明必须明确 Mock 与真实集成的区别，不能声称当前已经连接真实 CAD 或 MCP。
