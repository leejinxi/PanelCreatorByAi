# AI Ship CAD Copilot

面向船舶结构设计的自然语言板架创建原型。当前支持 Direct Mock 和 MCP STDIO Contract Mock 模拟创建，尚未连接真实 CAD。

## 当前能力

- 创建板架意图识别、定位面名称规范化、厚度和材料抽取。
- 必须提供至少一条边界，如 >SL10；符号只保留并传递，不解释几何关系。
- 原文确定性解析、去重、缺参澄清及多轮边界追加/替换。
- 使用仓库内 `mock_data/demo_project.json` 模拟当前工程对象目录，确定性区分唯一命中、未找到、歧义、不可用和角色不允许。
- 查询前由安全策略决定先观察，查询后由 Qwen 在创建、澄清和停止中选择；模型异常或不安全建议由 fallback / safety override 接管。
- 只有有效 `PanelRequest`、所有工程对象唯一匹配且最终决策允许时，Safety Gate 才授权 CAD Mock。
- CLI 与浏览器共用同一 Graph；Web 展示两次决策、Mock 工程查询、安全门禁和 CAD 是否调用。

## 本地运行

~~~powershell
conda activate ai_cad_agent
python --version
python -m pip install -r requirements.txt
ollama pull qwen2.5:7b
$env:CAD_BACKEND = "mock"
python -X utf8 -m agent.main "在FR100创建14mm厚AH36板架，边界 >SL10"
~~~

Python 应为3.11，Ollama 服务需在本机运行。进入多轮补充：

~~~powershell
python -X utf8 -m agent.main
~~~

先输入“在FR100创建14mm厚AH36板架”，系统应要求补充边界；再输入“边界 >SL10”即可继续校验并模拟创建。

浏览器 MCP 演示（先用 Ctrl+C 停止旧网页服务）：

~~~powershell
powershell -ExecutionPolicy Bypass -File scripts/start_mcp_demo.ps1
~~~

脚本使用 ai_cad_agent 环境并显式选择 MCP 后端。保持终端运行，刷新浏览器；顶部应显示 MCP Contract Mock。

访问 http://127.0.0.1:8000 。

## 边界追加与替换

会话仍在澄清阶段时：

- 追加：追加边界 <LV2
- 单项替换：将 >SL10 改为 >SL12
- 整体替换：边界全部改为 <LV8

目标包含空格或分隔符时，用引号包裹，例如 <"Deck A"。PowerShell 的整条命令可用单引号包裹需求，以保留内部双引号。不要在 < 前加入反斜杠。

## MCP 运行契约

CAD_BACKEND=mcp 默认加载 contracts/boundary_list_0.2.json（已确认的本地实验契约），boundaries 为至少一条 operator/target 数组。MCP_CONTRACT_PATH 可显式覆盖；旧四向契约和未确认草案仍被拒绝。

也可从已激活的 ai_cad_agent 终端手动启动：

~~~powershell
$env:CAD_BACKEND = "mcp"
$env:MCP_CONTRACT_PATH = "contracts/boundary_list_0.2.json"
python run_web.py
~~~

创建成功时页面显示 tools/call、耗时及 0.2-poc 请求，结果来自 STDIO Mock Server。未设置 CAD_BACKEND 时仍默认 Direct Mock。Agent 会先查询本地 Demo 工程目录，但不验证几何；固定模拟 ID 不是持久化对象标识。

旧 contracts/FULL_contract_with_data.json 和 boundary_list_0.2_draft.json 保留作历史/拒绝回归，不是当前演示入口。详细场景见 Doc/Plan/本地MCP演示操作手册_2026-09-10.md。

## 测试

~~~powershell
python -X utf8 run_tests.py
~~~

默认隔离真实 Ollama/CAD，MCP 回归会启动本机 STDIO 子进程。真实 Ollama E2E 需显式设置 RUN_LOCAL_E2E=1。

Direct Mock 页面内置三个主要演示：`FR100 + SL10 + LV5` 正常创建、`主甲板` 返回两个候选、`FR999` 返回不存在。主逻辑见 agent/graph.py，Mock 查询见 tools/project_context_tools.py，边界多轮规则见 agent/boundary_session.py。最新完成度与待办见 Doc/current_status.md 和 Doc/TODO.md。
