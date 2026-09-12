# Demo 板架评审规则说明

版本：`demo-panel-review-1.0`

本规则包只服务于 AI Ship CAD Copilot 本地板架创建演示。它不是 CCS 条款、公司正式设计标准或真实 CAD 几何规则。

运行时规则元数据位于 `mock_data/demo_panel_review_rules.json`，条件由 Python 确定性代码执行，不由 LLM 自由判断。

- `PANEL-DEMO-001`：请求必须先通过 `PanelRequest` 校验。
- `PANEL-DEMO-002`：定位面和全部边界必须唯一匹配、可用且角色合法。
- `PANEL-DEMO-003`：Demo 中定位面与边界解析到同一对象时阻断创建。
- `PANEL-DEMO-004`：板厚与显式邻近 Mock 样本不同时提醒，不修改用户板厚。
- `PANEL-DEMO-005`：材料与显式邻近 Mock 样本不同时提醒，不修改用户材料。
- `PANEL-DEMO-006`：CCS 规范符合性固定显示为未验证。
- `PANEL-DEMO-007`：结构强度固定显示为未验证。
- `PANEL-DEMO-008`：真实 CAD 几何与碰撞固定显示为未验证。

Mock 中的“邻近”关系由 `demo_panel_context.json` 显式声明，不根据 FR 编号推断真实空间关系。所有创建结果均为模拟结果。
