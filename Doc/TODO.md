# AI Ship CAD Copilot TODO

更新时间：2026-09-09

## P0：换 PC 后继续

- [ ] 检查 `git status --short`，确认 MCP PoC 与文档文件均已带到新 PC。
- [ ] 激活 `ai_cad_agent`，确认 Python 3.11，安装 `requirements.txt`，运行完整测试。
- [ ] 在 `tools/cad_tools.py` 增加 Backend 构建/选择逻辑，默认继续使用 `mock`。
- [ ] 实现 `CAD_BACKEND=mcp`，从 `MCP_CONTRACT_PATH` 和 `MCP_TIMEOUT_SECONDS` 构造 `McpCadBackend`。
- [ ] 不让 Graph 依赖 MCP SDK、Tool 名称或传输细节；Graph 只调用稳定 CAD Tool 契约。
- [ ] 更新 Web 执行模式，使 `/api/health` 在契约 Mock 下报告 `mcp-contract-mock`。
- [ ] 页面明确显示 `MCP Contract Mock · CAD execution is simulated`，不得显示真实 CAD 已连接。
- [ ] 增加固定 LLM 输出的全链路测试：Web API -> LangGraph -> MCP STDIO Mock -> Web DTO。
- [ ] 使用真实 Ollama 执行最终全系统人工测试，并记录成功、澄清、不支持、定位面失败和 CAD 不可用结果。
- [ ] MCP 全系统通过后更新 README 和运行命令。

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

- [ ] 重新实现并验证可控直接 Mock 失败场景：CAD 不可用、定位面不存在。
- [ ] 请求期间锁定提交、新建会话和示例按钮。
- [ ] 每轮执行前清空旧参数、request ID 和 JSON 结果。
- [ ] 浏览器超时应提示“停止等待不代表服务端取消”，避免重复创建。
- [ ] 在 1366x768 和 1920x1080 下完成人工页面验收。

## P1：未来公司 CAD 接入

- [ ] 在公司环境确认原生 CAD `create_panel` API、字段、单位和错误语义。
- [ ] 确认 `referenceName`、材料和四向边界的正式参数类型。
- [ ] 确认成功后返回对象 ID、句柄还是名称。
- [ ] 确认 CAD UI 主线程、事务和失败回滚要求。
- [ ] 在公司侧实现原生 CAD API 到 MCP Tool 的 Adapter。
- [ ] 用公司确认的正式契约替换个人 PC 实验契约，同时保留 Contract Mock 回归。

## 暂缓

- 定位面目录查询、`reference_plane_id` 和旧 Resolver 接回主链路。
- `project_id`、多工程隔离、缓存和工程修订号。
- 材料目录与边界对象 Provider。
- 幂等、重试、审计、认证和内网中央任务分发。
- RAG、stiffener、其他结构类型及自动强度设计。

## 安全边界

- 参数缺失或非法时不得调用 CAD Backend。
- MCP/CAD 错误必须返回稳定错误码，不泄漏堆栈、路径或内部异常。
- 本地 Contract Mock 的成功结果只能描述为模拟执行。
- 未获得公司 API 资料前，不得声称实验字段与真实 CAD API 一致。
