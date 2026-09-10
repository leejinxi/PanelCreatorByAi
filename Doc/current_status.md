# AI Ship CAD Copilot 当前状态

更新时间：2026-09-10

## 当前阶段

边界 Step 1–2 已接入主流程：用户必须提供至少1条合法边界；CLI/Web 共用按轮次重放的边界追加与替换规则。Direct Mock 与 MCP STDIO Contract Mock 均可完成本地成功与澄清流程，仍不创建真实 CAD 模型。

PanelRequest 与 MCP 0.2-poc 已统一为至少一条边界数组。用户确认本轮优先打通通信后，新增已确认的本地实验契约 contracts/boundary_list_0.2.json，并作为 MCP 默认契约。旧 0.1-poc 与历史草案保留；显式使用它们仍在发送前被拦截。对象匹配未完成，不作为本轮通信验收的前提。

## 主运行链路

用户输入 → LocalQwen 提取动作/定位面/厚度/材料 → 原文边界解析与多轮重放 → 必填和格式校验 → PanelRequest → CAD Tool → Direct Mock 或 MCP STDIO → Contract Mock。

- LLM 的 boundaries 输出不作为执行依据；边界只来自用户原文。
- 当前不查询定位面目录；已知 FR/SL/LV 名称规范化，未知名称保留。
- 定位面提取排除边界片段；用户没有提供定位面时不能从边界目标补出。
- 历史 Resolver 保留，但不在主 Graph 中。

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
本批162项：161项通过，1项真实 Ollama E2E 默认跳过。覆盖 CLI/Web 无边界拦截、补1条成功、多轮替换、模型伪造边界、后续句子中的非法边界、MCP 旧契约/草案拦截及真实 STDIO 数组回环。
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

## 下一步

1. 补齐 Direct Mock/Contract Mock 共用的对象匹配及失败场景；未知、歧义、不可用对象不能默认成功。
2. 明确来源轮次与逐项匹配状态的完整 DTO；当前页面显示有效表达式和问题，尚未展示真实对象匹配状态。
3. 对象匹配完成后补齐真实 Ollama 下的匹配澄清与拒绝验收；现有通信成功、补边界及自动化故障回归已通过。
4. 后续处理会话复用、配置化、幂等/任务查询、公司 CAD Adapter。真实 CAD、几何验证、RAG 和多工具选择尚未实现。
