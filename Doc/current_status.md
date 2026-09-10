# AI Ship CAD Copilot 当前状态

更新时间：2026-09-11

代码基线：`ecfbf8e` — 完成 Agent 决策展示增强，并修正 Direct Mock 与 MCP 调用状态的页面语义。

最新回归：在 Python 3.11.15 / `ai_cad_agent` 下运行 `python -B -X utf8 run_tests.py`，共184项，183项通过，1项真实 Ollama E2E 按设计跳过。

## 当前阶段

Agent 决策展示增强已接入主流程。用户必须提供至少1条合法边界；参数校验后 Agent 先决定查询 Mock 工程上下文，再根据定位面和边界的逐项查询结果选择创建、澄清或停止。Direct Mock 与 MCP STDIO Contract Mock 均仍只模拟创建，不创建真实 CAD 模型。

页面的 MCP Call Inspector 已区分运行模式：Direct Mock 成功时显示 `DIRECT MOCK COMPLETE` 和 `RESULT · Direct Mock`，明确说明该模式不产生 MCP Request/Response；只有真实发出 MCP 请求但无响应时才显示“未返回可确认结果”。Safety Gate 阻断和发送前契约/配置拦截也使用各自文案。

PanelRequest 与 MCP 0.2-poc 已统一为至少一条边界数组。用户确认本轮优先打通通信后，新增已确认的本地实验契约 contracts/boundary_list_0.2.json，并作为 MCP 默认契约。旧 0.1-poc 与历史草案保留；显式使用它们仍在发送前被拦截。对象匹配未完成，不作为本轮通信验收的前提。

## 主运行链路

用户输入 → LocalQwen 提取动作与候选参数 → 原文边界解析与多轮重放 → `PanelRequest` 校验 → policy 首次决策 → `inspect_project_context` 查询 Demo JSON → Qwen 查询后决策（含 fallback / safety override）→ Safety Gate → CAD Tool → Direct Mock 或 MCP STDIO Contract Mock。

- LLM 的 boundaries 输出不作为执行依据；边界只来自用户原文。
- 当前查询仓库内精选 Demo 工程目录；已知 FR/SL/LV 名称规范化，目录外显式查询词仍保留并返回 `not_found`。
- 定位面提取排除边界片段；用户没有提供定位面时不能从边界目标补出。
- 名称或别名支持唯一、未找到、歧义、不可用和角色不允许五类结果；比较符不参与名称匹配。
- 只有全部对象唯一匹配、最终动作为 `prepare_creation` 且未超过两步决策上限时，Safety Gate 才授权创建。
- Web 只展示结构化观察、动作、依据和数据源，不展示隐藏思维链。

## 已实现边界行为

- 每条为 < 或 > 加目标；支持全角符号、引用含空格目标、超过4条。
- 已知名称规范化；相同符号与目标去重，同一目标不同符号分别保留。
- 缺失边界、非法符号、空目标、引号不完整或其他非法片段均澄清；有合法项也不能忽略非法项。
- PanelRequest 强制非空数组并拒绝旧四向对象；比较符不作几何解释。
- 多轮支持“追加边界 …”“将 <SL10 改为 <SL12”“边界全部改为 …”。不明确的修改要求澄清；整体替换后旧项不复活。
- CLI/Web 继续提交累积用户原文，由同一个 boundary_session 模块按轮次处理，不依赖模型合并边界。
- 模型被要求保留未修改的其他字段；多轮中可从明确且无冲突的原文恢复遗漏的厚度和材料。历史存在不同候选值时不猜测。
- Web 展示边界列表、有效数量和输入问题；“格式有效”不代表对象存在。

## MCP 运行契约与兼容性

- contracts/FULL_contract_with_data.json：已确认的 0.1-poc 历史基线，保持四向可空对象。
- contracts/boundary_list_0.2.json：已确认的本地运行契约，boundaries 为 operator/target 数组，minItems=1；不代表公司 CAD API 已确认。
- contracts/boundary_list_0.2_draft.json：历史未确认草案，保留用于拒绝回归。
- 运行时拒绝未确认草案和四向契约，不静默更改 confirmed 状态或推断方向映射。
- MCP 适配器已支持数组；集成测试直接使用同一运行契约验证真实 STDIO 子进程。未设置 CAD_BACKEND 时仍默认 mock；演示脚本显式使用 mcp。
- Trace 使用实际加载版本，并区分发送前拦截、业务失败和无法确认 Provider 结果。
- Contract Mock 仍为指定失败条件加默认成功，不包含边界对象匹配；Direct Mock 也不验证真实对象。

## 当前测试

Python 3.11.15 / ai_cad_agent 下运行 python -B -X utf8 run_tests.py。
本批184项：183项通过，1项真实 Ollama E2E 默认跳过。新增覆盖 AgentDecision Schema、Mock 目录加载与匹配、成功/歧义/不存在、不可用、角色限制、模型非法 JSON、safety override、决策上限、Safety Gate、Web DTO 与六步展示链；原有 CLI/Web、边界多轮与 MCP STDIO 回归保持通过。
显式设置 `RUN_LOCAL_E2E=1` 后，真实 Ollama 成功创建与 unsupported 两段端到端测试通过。
另通过真实 Qwen 浏览器人工验收：初始“在第100肋位创建14mm厚AH36板架”要求补充边界；补充“边界 >SL10”后 Direct Mock 成功，FR100/14mm/AH36 保留。本轮另通过真实 Qwen + MCP 浏览器验收：无边界时未调用 MCP，补“边界 >SL10”后成功；请求版本0.2-poc，MCP耗时846ms，总耗时6061ms，返回mock-mcp-panel-001。真实 CAD 未验证。服务端空数组、非法符号、空目标、缺字段和多余字段拒绝已通过真实 STDIO 回归，超时和异常通过故障注入验证。
历史基线：边界开发前118项；Step 1后132项；最低数量改为1条后135项。

## 手动验证

从仓库根目录执行：

~~~powershell
conda activate ai_cad_agent
$env:CAD_BACKEND = "mock"
python -X utf8 -m agent.main
~~~

依次输入：

1. 在第100肋位创建14mm厚AH36板架
2. 边界 >SL10

第一轮应澄清边界，第二轮应模拟创建。网页 MCP 演示请先停止旧服务，再执行 powershell -ExecutionPolicy Bypass -File scripts/start_mcp_demo.ps1，访问 http://127.0.0.1:8000 并刷新页面。第四步应显示实际 tools/call 和耗时。
测试追加/替换时可先不提供材料，使会话停留在澄清阶段；完成创建后下一次请求属于新的创建任务。

模式排查：仅更新代码或刷新网页不会改变旧服务进程中的 CAD_BACKEND。若第四步显示 Direct Mock，应停止旧服务，用 MCP 脚本重启后重新提交请求；历史请求不会自动重新执行。可访问 /api/health 核对 mode=mcp、cad_backend=mcp-contract-mock。该接口只报告配置，不证明 STDIO 调用成功；实际执行以请求 Trace 中的 MCP Request/Response 为准。本次会话已在8000端口启动 MCP 模式并核对上述配置。

## 下一步

当前 Demo 主线已经完成。下一阶段应优先保持演示稳定，并在获得公司 CAD API 信息后用 MCP/C++ Provider 替换 `demo_project.json` 数据源；Graph、`AgentDecision`、Web 时间线与 Safety Gate 契约应保持稳定。真实工程接入前不扩展 RAG、多 Agent、自动几何推断或其他结构类型。
