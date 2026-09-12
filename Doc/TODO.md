# AI Ship CAD Copilot TODO

更新时间：2026-09-12

已提交代码基线：`afae5a2` — 增加板架创建前智能评审、显式邻近 Mock 样本、计划调整和决策护照。

## P0：板架边界必填与匹配（当前优先）

方案：[板架边界必填与匹配实施方案 v1.0](Plan/板架边界必填与匹配实施方案_v1.0.md)。Step 1–2 已接入主流程，至少1条边界为必填。旧 `0.1-poc` 保留；用户确认优先打通通信后，MCP 默认契约已切换为本地实验版 `boundary_list_0.2.json`，对象匹配单独继续实施。

- [x] 明确边界必填、至少1条、每条为 `<`/`>` 加对象或标尺面，缺失需补充。
- [x] 明确比较符仅保留并传递给 CAD，不解释模型关系或判断几何冲突。
- [x] 生成边界实施方案，并按符号透传要求修订。
- [x] Step 1：新增独立 BoundaryCandidate、BoundaryConstraint、BoundaryValidationIssue、BoundaryParseResult 和 ValidatedBoundaries；支持4条以上，校验目标/符号、规范化后按完整项去重。PanelCandidate/PanelRequest 已切换为列表。
- [x] Step 1：实现边界文本确定性解析，保留原文位置和非法片段；复用标尺规范化，Graph 排除边界文本后核对定位面来源；同一目标不同符号分别保留。
- [x] Step 2：Graph 增加边界缺失、数量与格式校验；不合格时澄清并阻止创建，不让模型补造边界。
- [x] Step 2：将独立边界列表模块接入 PanelCandidate/PanelRequest；从整轮需求中提取边界输入并保留轮次，不能把整段会话直接传给边界表达式解析器。
- [x] Step 2：CLI/Web 共用补充和修正规则，支持追加、明确替换；保留其他参数，避免历史边界复活。
- [x] Step 3 准备：新增 contracts/boundary_list_0.2_draft.json，数组、minItems=1；保持 draft，旧契约不变。
- [x] Step 3：按用户确认启用本地实验 0.2 契约并切换 MCP 演示默认配置；本轮验证通信，对象匹配仍待实现。
- [x] Step 3：MCP 数组映射及版本兼容性拦截，集成测试直接使用已确认的0.2运行契约完成 STDIO 回归。
- [x] Step 3：Direct Mock 和 Contract Mock 在进入 CAD 前共用 Graph 层对象匹配；未知、歧义和不可用对象不能默认成功，比较符原样透传。
- [x] Step 3：Trace 记录实际契约版本；区分本地拦截、业务拒绝和结果不确定。
- [x] Step 4 部分：Web 动态边界列表、有效数量和问题提示；已移除“允许暂时为空”。
- [x] Step 4：补齐 Mock 工程查询的对象逐项匹配状态展示；来源轮次暂不进入本轮 Demo。
- [x] Step 4：更新 Direct Mock 示例、WebMCP 工具说明、测试 fixture、真实 Ollama E2E 请求及当前运行说明。
- [x] Step 4：新版 MCP 启用后修订完整 MCP 演示手册。
- [x] 解析与通信验收：缺失、1条、多条、超过4条、重复、非法符号、名称规范化、定位面缺失、多轮替换、MCP超时及异常；服务端拒绝空数组、非法符号、空目标、缺字段及多余字段。
- [x] 对象匹配验收：未知目标、歧义目标、不可用目标、角色限制及别名映射；Graph 在 Direct Mock 与 Contract Mock 前统一拦截，匹配失败不创建。
- [x] 完成真实 Ollama → LangGraph → MCP STDIO Mock → Web 演示：无边界 → 补1条；确认没有有效边界时不调用创建。
- [x] 真实 Ollama → LangGraph → Direct Mock → Web 人工验收：无边界拦截，补1条成功且其余参数保留。

## 下一轮执行顺序

下一轮改为 Demo 展示优先，详细方案见 [Agent 决策展示增强方案 v1.0](Plan/AI_Ship_CAD_Copilot_Agent决策展示增强方案_v1.0.md)。原 P0 对象匹配并入 `inspect_project_context` 的 Mock 工程查询，不重复建设两套目录和匹配逻辑。

1. [x] 定义最小工程对象目录与匹配结果 Schema，明确唯一命中、未找到、歧义、不可用和角色不允许状态。
2. [x] 新增精选 Demo 工程数据和确定性 `inspect_project_context` 只读工具；保留用户比较符，禁止未知对象默认成功。
3. [x] 增加 `AgentDecision`、最多两步的决策历史、查询后 Qwen 决策，以及 fallback、safety override 和 Safety Gate。
4. [x] 在 Web 展示两次决策、中间工具观察、对象逐项状态和 CAD 是否调用。
5. [x] 固化成功、歧义、不存在三个 Demo 场景，完成自动化回归与真实 Qwen 页面验收。

## P1：Demo Agent 决策展示增强

- [x] 形成 Demo 展示优先的产品与详细开发方案，明确最小范围、Graph、Schema、Prompt、Web DTO、测试矩阵和验收标准。
- [x] 新增 `AgentDecision`、`AgentDecisionRecord` 及状态字段；只展示结构化观察、动作和依据，不展示隐藏思维链。
- [x] 新增 Demo 工程对象 Schema、`mock_data/demo_project.json` 和确定性查询工具。
- [x] 查询前生成 `policy` 决策；查询后由 Qwen 生成结构化决策，异常时使用确定性 fallback。
- [x] 增加 safety override 和 Safety Gate，未查询、未唯一匹配或不安全状态不得调用 CAD。
- [x] Web 增加“需求理解、Agent 决策、工程查询、Agent 评估、安全校验、CAD 执行”展示链。
- [x] 固化正常创建、主甲板歧义、FR999 不存在三个演示场景。
- [x] 覆盖模型非法决策、决策超限、对象不允许、对象不可用和 CAD 失败等离线测试。
- [x] 完成 Direct Mock 真实 Qwen 页面验收；页面始终明确 Mock 工程目录与模拟 CAD 后端。

## P1：板架智能评审 Demo 增强

详细方案见 [板架智能评审 Demo 增强开发方案 v1.0](Plan/AI_Ship_CAD_Copilot_板架智能评审Demo增强开发方案_v1.0.md)。

- [x] 新增 `DesignReviewReport`、检查项、邻近样本和计划调整强类型 Schema，默认拒绝未知字段。
- [x] 新增版本化 `demo-panel-review-1.0` 规则包和人可读规则说明。
- [x] 新增 FR100 显式邻近 Mock 板架上下文；不根据 FR 编号推断真实几何关系。
- [x] 实现确定性 `review_panel_design()`，区分通过、提醒、阻断和未验证。
- [x] Graph 增加 `design_review` 节点；warning 保留用户参数继续，blocker 强制停止。
- [x] Safety Gate 要求评审存在、无 blocker 且工程版本一致；模型冲突由 safety override 覆盖。
- [x] Web 升级为七段 Agent 行为链，增加创建前评审、邻近样本、计划调整和决策护照。
- [x] 增加“评审阻断”固定示例；Direct Mock 与 MCP Inspector 的模式语义保持不变。
- [x] 覆盖相邻板厚/材料差异、无邻近样本、同对象阻断、损坏数据、版本不一致及Web白名单映射。
- [x] 完成真实Qwen浏览器验收：带提醒模拟创建和 `PANEL-DEMO-003` 阻断均符合预期。

## 历史已完成：换 PC 基线与 0.1-poc 主链路

- [x] 检查 `git status --short`，确认 MCP PoC 与文档文件均已带到新 PC。
- [x] 激活 `ai_cad_agent`，确认 Python 3.11，安装 `requirements.txt`，运行完整测试。
- [x] 在 `tools/cad_tools.py` 增加 Backend 构建/选择逻辑，默认继续使用 `mock`。
- [x] 实现 `CAD_BACKEND=mcp`，从 `MCP_CONTRACT_PATH` 和 `MCP_TIMEOUT_SECONDS` 构造 `McpCadBackend`。
- [x] 不让 Graph 依赖 MCP SDK、Tool 名称或传输细节；Graph 只调用稳定 CAD Tool 契约。
- [x] 更新 Web 执行模式，使 `/api/health` 在契约 Mock 下报告 `mcp-contract-mock`。
- [x] 页面明确显示 `MCP Contract Mock · CAD execution is simulated`，不得显示真实 CAD 已连接。
- [x] 增加固定 LLM 输出的全链路测试：Web API -> LangGraph -> MCP STDIO Mock -> Web DTO。
- [x] 使用真实 Ollama 执行成功与澄清人工测试；定位面失败和 CAD 不可用由自动化测试覆盖。
- [x] MCP 全系统通过后更新 README 和运行命令。

## 已完成：本地 MCP 契约与回环基础

- [x] 自行构造并确认 `FULL_contract_with_data.json`，版本 `0.1-poc`。
- [x] `create_panel` 输入 Schema 与 `PanelRequest` 语义对应。
- [x] 空白定位面、材料和边界字符串被契约拒绝。
- [x] 成功响应要求非空 `objectId` 且 `errorCode=null`。
- [x] 失败响应要求 `objectId=null` 且非空 `errorCode`。
- [x] 实现契约加载和 Schema 校验。
- [x] 实现独立 Mock MCP STDIO Server。
- [x] 验证 MCP `initialize`、`tools/list` 和 `tools/call`。
- [x] 实现 STDIO MCP Client。
- [x] 实现 `McpCadBackend` 字段映射。
- [x] 覆盖 MCP 成功、业务失败、超时、通信异常和非法响应测试。

## P1：浏览器演示稳定性

- [x] 修复旧五节点页面接收新版六节点 Trace 后仍显示“正在调用/等待请求”；新版页面在节点不匹配时提示刷新，并通过静态资源版本更新规避旧脚本缓存。
- [x] 将组件清单改为 `Qwen 参数解析 → Agent 首次决策 → Mock 工程查询 → Qwen 结果评估 → Safety Gate → CAD Provider` 行为链；分开展示解析与决策模型耗时。
- [x] MCP Call Inspector 区分 Direct Mock 成功、Safety Gate 阻断、MCP 发送前拦截和已发送但无可确认响应，避免把“未经过 MCP”展示成 Provider 失败。
- [x] 重新实现并验证可控 MCP Contract Mock 失败场景：CAD 不可用、定位面不存在。
- [x] 请求期间锁定提交、新建会话和示例按钮。
- [x] 每轮执行前清空旧参数、request ID 和 JSON 结果。
- [x] 浏览器超时应提示“停止等待不代表服务端取消”，避免重复创建。
- [x] 增加 MCP 演示一键启动脚本和固定演示操作手册。
- [x] 核对网页服务切换为 MCP 模式；记录停止旧服务、重启、刷新和重新提交的操作，以及 /api/health 配置检查与实际调用 Trace 的区别。
- [x] 增加五节点透明执行台、MCP 调用检查器和 Provider 替换边界。
- [x] 增加请求级 Trace、Qwen/MCP/总耗时和安全白名单响应。
- [x] 切换简约白蓝主题，移除板架示意区域并修复标题换行。
- [x] 在 1366x768 和 1920x1080 下完成人工页面验收。

## P1：未来公司 CAD 接入

- [ ] 在公司环境确认原生 CAD `create_panel` API、字段、单位和错误语义。
- [ ] 确认 `referenceName`、材料及边界列表（符号与目标）的正式参数类型和传参方式；Agent 不解释比较符的几何含义。
- [ ] 确认成功后返回对象 ID、句柄还是名称。
- [ ] 确认 CAD UI 主线程、事务和失败回滚要求。
- [ ] 在公司侧实现原生 CAD API 到 MCP Tool 的 Adapter。
- [ ] 用公司确认的正式契约替换个人 PC 实验契约，同时保留 Contract Mock 回归。

## 暂缓

- 真实 CAD 定位面目录查询、`reference_plane_id` 和旧 Resolver 接回主链路；本地 Demo JSON 查询已完成。
- `project_id`、多工程隔离、缓存和工程修订号。
- 材料目录与真实公司边界对象 Provider（本地 Mock 边界匹配已进入本轮 P0）。
- 通用 Agent 多工具选择；本轮受控决策记录和候选对照展示已完成。
- 幂等、重试、审计、认证和内网中央任务分发。
- RAG、stiffener、其他结构类型及自动强度设计。

## 安全边界

- 参数缺失或非法时不得调用 CAD Backend；边界至少1条与格式校验已接入主流程；缺失/非法/修改不明确时澄清且不调用 CAD。
- 比较符只验证格式并透传；Agent/Mock 不根据正负侧或几何推断擅自删除、翻转或拒绝边界。
- MCP/CAD 错误必须返回稳定错误码，不泄漏堆栈、路径或内部异常。
- 本地 Contract Mock 的成功结果只能描述为模拟执行。
- 未获得公司 API 资料前，不得声称实验字段与真实 CAD API 一致。
