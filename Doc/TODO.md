# AI Ship CAD Copilot TODO

更新时间：2026-09-10

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
- [x] Step 3 准备：MCP 数组映射及版本兼容性拦截，使用临时测试契约完成 STDIO 回归。
- [ ] Step 3：直接 Mock 和 Contract Mock 共用对象匹配；未知、歧义和不可用对象不能默认成功，比较符原样透传。
- [x] Step 3：Trace 记录实际契约版本；区分本地拦截、业务拒绝和结果不确定。
- [x] Step 4 部分：Web 动态边界列表、有效数量和问题提示；已移除“允许暂时为空”。
- [ ] Step 4：补齐来源轮次和 Provider 逐项匹配状态展示。
- [x] Step 4：更新 Direct Mock 示例、WebMCP 工具说明、测试 fixture、真实 Ollama E2E 请求及当前运行说明。
- [x] Step 4：新版 MCP 启用后修订完整 MCP 演示手册。
- [ ] 验收：缺失、1条、多条、超过4条、重复、非法符号、名称规范化、定位面缺失、多轮替换、Provider匹配失败、MCP超时及异常。
- [x] 完成真实 Ollama → LangGraph → MCP STDIO Mock → Web 演示：无边界 → 补1条；确认没有有效边界时不调用创建。
- [x] 真实 Ollama → LangGraph → Direct Mock → Web 人工验收：无边界拦截，补1条成功且其余参数保留。

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

- [x] 重新实现并验证可控 MCP Contract Mock 失败场景：CAD 不可用、定位面不存在。
- [x] 请求期间锁定提交、新建会话和示例按钮。
- [x] 每轮执行前清空旧参数、request ID 和 JSON 结果。
- [x] 浏览器超时应提示“停止等待不代表服务端取消”，避免重复创建。
- [x] 增加 MCP 演示一键启动脚本和固定演示操作手册。
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

- 定位面目录查询、`reference_plane_id` 和旧 Resolver 接回主链路。
- `project_id`、多工程隔离、缓存和工程修订号。
- 材料目录与真实公司边界对象 Provider（本地 Mock 边界匹配已进入本轮 P0）。
- Agent 多工具选择、候选对照及决策记录展示；仅讨论，待边界闭环完成后推进。
- 幂等、重试、审计、认证和内网中央任务分发。
- RAG、stiffener、其他结构类型及自动强度设计。

## 安全边界

- 参数缺失或非法时不得调用 CAD Backend；边界至少1条与格式校验已接入主流程；缺失/非法/修改不明确时澄清且不调用 CAD。
- 比较符只验证格式并透传；Agent/Mock 不根据正负侧或几何推断擅自删除、翻转或拒绝边界。
- MCP/CAD 错误必须返回稳定错误码，不泄漏堆栈、路径或内部异常。
- 本地 Contract Mock 的成功结果只能描述为模拟执行。
- 未获得公司 API 资料前，不得声称实验字段与真实 CAD API 一致。
