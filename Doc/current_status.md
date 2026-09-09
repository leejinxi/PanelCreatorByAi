# AI Ship CAD Copilot 当前状态

更新时间：2026-09-10

## 项目定位

当前 MVP 只处理自然语言创建板架。Python Agent 负责意图抽取、参数校验和工具调用；最终 CAD 模型必须由 C++ CAD 软件创建。

当前尚未连接公司 CAD。浏览器、直接 Mock CAD 和本地 MCP Contract Mock 均为演示或原理验证能力，不得描述为真实 CAD 集成。

## 当前主运行链路

```text
用户输入
  -> LocalQwen / Ollama 提取 AgentActionPlan
  -> LangGraph 校验定位面、厚度和材料
  -> 已知 FR/SL/LV 标尺面名称规范化
  -> 构造 PanelRequest
  -> create_panel()
  -> 当前默认 MockCadBackend
```

Agent 不查询定位面目录，也不判断定位面是否真实存在。未知工程名称保持原文并交给未来 CAD Backend 判断。历史定位面 Resolver 仍保留，但不参与主 Graph。

## 已完成

### Agent 与浏览器基线

- Python 3.11、conda 环境 `ai_cad_agent`、Ollama `qwen2.5:7b`。
- LocalQwen HTTP Client、LangGraph、强类型 Schema、有限重试和多轮澄清。
- 已知标尺面规范化以及其他工程名称直传。
- FastAPI API、单页浏览器工作台和直接 `MockCadBackend` 演示模式。
- 浏览器方案 Step 1–4 已完成；Step 4 已通过真实 Qwen 成功与澄清场景验收。

### 本地 MCP 回环 PoC

- 已确认实验契约 `contracts/FULL_contract_with_data.json`，版本 `0.1-poc`，确认日期 2026-09-09。
- 契约只定义 `create_panel`，包含输入/输出 JSON Schema 和成功、定位面不存在、CAD 不可用三类数据。
- 输入拒绝空白定位面、材料和边界；输出强制成功/失败字段互斥。
- 已实现 `mcp_mock/contract.py` 和独立 STDIO Mock MCP Server。
- 已通过真实 MCP `initialize`、`tools/list`、`tools/call` 子进程回环测试。
- 已实现 `mcp_client/stdio_client.py` 和 `tools/mcp_cad_backend.py`。
- 已验证 `PanelRequest.reference_plane -> referenceName`、`thickness -> thicknessMm`、材料和边界映射。
- 已覆盖 MCP 成功、业务错误、超时、通信失败和非法返回的受控映射。

## 当前准确边界

- `McpCadBackend` 已通过 `CAD_BACKEND=mcp` 接入运行时选择，Graph 仍只依赖稳定的 CAD Tool 契约。
- Web 健康状态已区分 `mock` 与 `mcp-contract-mock`，未知配置返回 503。
- 已完成“真实 Ollama -> LangGraph -> MCP STDIO Mock -> Web 页面”的成功与澄清场景人工验收。
- 本地契约完全由个人 PC 自行拟定，不代表公司原生 CAD API。
- 公司端目前只有原生 CAD API，没有 MCP Server；真实接入仍需要公司侧 CAD Adapter/MCP Server。
- 直接 Mock 失败注入尚未实现；MCP Contract Mock 的定位面失败和 CAD 不可用场景已覆盖。

## 下一步计划

1. 修订 `AGENTS.md` 与 `README.md` 中仍保留的旧定位面查询描述，统一为“已知标尺面规范化，未知名称原文交给 CAD 判定”。
2. 增加 MCP 会话复用和更精确的协议错误分类，避免每次创建都冷启动子进程。
3. 将 Ollama 端点、模型、超时及其他机器相关参数配置化，支持换机和内网部署。
4. 等公司提供正式 CAD API 或 CAD Adapter/MCP Server 后，替换 Contract Mock，并保留现有回归测试。

## 当前测试基线

2026-09-09 在 Python 3.11.15 / `ai_cad_agent` 下验证：

```powershell
python -X utf8 run_tests.py
```

结果：115 项运行，114 项通过，1 项真实 Ollama E2E 默认跳过。MCP 专项测试会启动真实 STDIO 子进程，但不会访问真实 CAD。

真实网页验收：`CAD_BACKEND=mcp` 下，真实 Qwen 成功解析“第100肋位、14mm、AH36”并经 MCP Contract Mock 返回模拟对象；缺少材料时页面进入澄清且跳过 CAD。

## 换 PC 后首先执行

```powershell
conda activate ai_cad_agent
python --version
python -m pip install -r requirements.txt
python -X utf8 run_tests.py
ollama list
```

Python 应为 3.11，Ollama 应存在 `qwen2.5:7b`。开始修改前执行 `git status --short`，确认本批 MCP 文件已经提交或仍作为未提交改动存在。

阅读顺序：

1. `AGENTS.md`
2. `Doc/current_status.md`
3. `Doc/Plan/本地MCP回环PoC阶段性报告_2026-09-09.md`
4. `Doc/TODO.md`
5. `contracts/FULL_contract_with_data.json`
6. `Doc/Plan/内网mock数据生成.md`

