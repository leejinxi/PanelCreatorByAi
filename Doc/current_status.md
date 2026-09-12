# AI Ship CAD Copilot 当前状态

更新时间：2026-09-12

代码基线：`afae5a2`；其后为未提交的“全船模型错误治理 Agent”工作区改动。

最新回归：在 Python 3.11.15 / `ai_cad_agent` 下运行 `python run_tests.py`，共205项，204项通过，1项真实 Ollama E2E 按设计跳过。

## 当前阶段

当前产品演示以“全船结构模型错误治理”为唯一主入口，不再使用顶部业务 Tab。错误治理读取显式 Mock CAD 错误快照，由 Agent 展示根因/级联归组、风险分流、修复编排和结果收口；原板架创建页作为自动更新说明和单对象决策详情的下钻能力保留，当前仍不接入真实 CAD，也不会修改真实模型。

固定 Demo 快照含36个错误节点、4个根因组和23个级联错误。分流结果为：11个低风险自动重算、15个确认后板架更新、6个拓扑歧义转人工、4个几何内核异常转研发。点击“执行可恢复项”后模拟恢复26个错误，剩余10个形成集中工作清单。

错误分析前可打开“了解 Mock 场景”：页面假设一艘货船详细设计模型从 `DEMO-REV-17` 升级到 `DEMO-REV-18`，以约8,000个板架、约120,000个板架下子构件说明全船人工排查的数量级，并明确36个错误只是精选 Mock 快照、不是实时 CAD 查询，也不代表特定真实船型。

错误组 `GROUP-A` 提供“查看板架决策”只读深链。它通过 `OP-REPAIR-108-01` 读取结构化操作快照，展示来源任务、根因组、目标板架、替换引用、工程版本、决策依据和安全检查；详情视图不会重新调用 CAD。对应 API 为 `/api/model-errors/analyze`、`/api/model-errors/repair/{task_id}`、`/api/model-errors/status/{task_id}` 和 `/api/operations/{operation_id}`。

自动重算组 `GROUP-B` 提供“板架自动更新说明”按钮。点击后下钻到自动更新上下文页，展示错误板架ID、CAD候选、重算/更新决策和父子对象复核顺序，并在同一页面复用现有板架创建/决策链；页面明确说明当前 Mock 创建契约不会真实更新错误板架。

“板架决策护照”展示卡已从页面删除，避免与决策时间线、Safety Gate、执行结果和只读操作记录重复。后端结构化 `AgentDecision`、执行Trace和审计字段继续保留。

原“创建前智能评审”已从默认 Graph 和 Web 主链降级：板架创建只保留参数/边界校验、工程对象查询、Agent 决策、Execution Preflight/Safety Gate 和 CAD Provider。旧 `DesignReviewReport`、规则工具和页面 DOM 暂留作兼容模块，但默认不执行、不展示，也不再作为 Safety Gate 授权条件。

页面的 MCP Call Inspector 已区分运行模式：Direct Mock 成功时显示 `DIRECT MOCK COMPLETE` 和 `RESULT · Direct Mock`，明确说明该模式不产生 MCP Request/Response；只有真实发出 MCP 请求但无响应时才显示“未返回可确认结果”。Safety Gate 阻断和发送前契约/配置拦截也使用各自文案。

`Agent 实际行为路径` 不再使用单一 Local Qwen、LangGraph、Schema 技术组件卡片，而是按真实行为展示 `Qwen 参数解析 → Agent 首次决策 → Mock 工程查询 → Qwen 结果评估 → Safety Gate → CAD Provider`。Trace 仅记录 Qwen 调用阶段和耗时，不保存 Prompt 或模型原文；解析重试累计到参数解析阶段，查询后决策单独计时。

浏览器若仍保留旧五节点页面，而服务端已返回新版六节点 Trace，旧 DOM 无法匹配节点名，曾导致请求结束后残留“正在调用/等待请求”。当前静态资源已升级为 `error-governance-v5`；创建页只显示六个实际节点，旧评审节点和决策护照不再参与结果展示。已打开的旧页面仍需执行一次 `Ctrl+F5` 才能载入新版脚本。

PanelRequest 与 MCP 0.2-poc 已统一为至少一条边界数组。用户确认本轮优先打通通信后，新增已确认的本地实验契约 contracts/boundary_list_0.2.json，并作为 MCP 默认契约。旧 0.1-poc 与历史草案保留；显式使用它们仍在发送前被拦截。Graph 层 Demo 对象匹配已完成，但不等于 Contract Mock 或真实 CAD 内部的几何验证。

## 主运行链路

板架创建：用户输入 → LocalQwen 提取动作与候选参数 → 原文边界解析与多轮重放 → `PanelRequest` 校验 → policy 首次决策 → `inspect_project_context` 查询 Demo JSON → Qwen 查询后决策（含 fallback / safety override）→ Execution Preflight / Safety Gate → CAD Tool → Direct Mock 或 MCP STDIO Contract Mock。

模型错误治理：读取 Mock CAD 错误快照 → 根因/级联归组 → 四类风险分流 → 用户点击确认可恢复批次 → 模拟执行父对象优先的恢复计划 → 统计已恢复与剩余错误 → 可选进入单板架只读操作记录。

- LLM 的 boundaries 输出不作为执行依据；边界只来自用户原文。
- 当前查询仓库内精选 Demo 工程目录；已知 FR/SL/LV 名称规范化，目录外显式查询词仍保留并返回 `not_found`。
- 定位面提取排除边界片段；用户没有提供定位面时不能从边界目标补出。
- 名称或别名支持唯一、未找到、歧义、不可用和角色不允许五类结果；比较符不参与名称匹配。
- 只有全部对象唯一匹配、最终动作为 `prepare_creation` 且未超过两步决策上限时，Safety Gate 才授权创建。
- Safety Gate 不再依赖旧设计评审报告；它仍要求参数合法、工程对象唯一匹配、决策动作允许且未超过决策上限。
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
本批205项：204项通过，1项真实 Ollama E2E 默认跳过。当前新增覆盖错误快照加载、36/4/23统计、四类分流、26/10结果收口、只读板架操作快照和API 404受控错误。板架创建回归覆盖“不再执行旧评审、Safety Gate不依赖旧评审”，既有 AgentDecision、边界多轮和 Provider 异常测试保持通过。
另使用真实 Qwen + Direct Mock 浏览器验收：FR100 / 14mm / AH36 / >SL10 显示4项通过、1项提醒、3项未验证，保留14mm并生成模拟对象及决策护照；FR100 / 14mm / AH36 / >FR100 命中 `PANEL-DEMO-003`，计划调整为停止，CAD Provider 未调用。页面控制台无错误。
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

当前优先完成“错误治理主入口 → 自动更新说明/单板架详情”页面在常用分辨率下的最终视觉验收，并冻结错误治理 Demo 数据。后续真实开发应先与 CAD 团队确认错误快照、对象依赖、重算、更新和复核契约，再用 MCP/C++ Provider 替换 Mock；不要用 RAG 或 LLM 代替工程对象事实与几何校验。
