# AI Ship CAD Copilot

## 本地浏览器演示与内网部署开发方案

版本：v1.0（Review 草案）  
日期：2026-09-08  
当前状态：Step 1 已确认；Step 2 已确认；Step 3 已完成代码实现，等待 Review；Step 4 的代码未保留，待重新实现
当前目标：优先交付一个可在本地浏览器展示、可录制视频，并能平滑迁移到内网的板架创建界面

---

# 1. 方案结论

本阶段采用“单页浏览器界面 + Python Web 服务 + 现有 LangGraph Agent + 可替换 CAD Backend”的结构。

本地演示时，所有组件运行在同一台电脑：

```text
浏览器
  ↓ HTTP
Python Web 服务
  ↓
LangGraph Agent
  ├─ LocalQwen → Ollama
  └─ create_panel → MockCadBackend
```

本地访问地址：

```text
http://127.0.0.1:8000
```

后续内网试用时，网页和接口保持不变，仅调整服务监听地址与 CAD Backend：

```text
内网浏览器
  ↓ HTTP/HTTPS
内网 Web/Agent 服务
  ↓
CAD Connector
  ↓
真实 CAD 软件
```

本方案不使用独立前端构建工具。后端推荐使用 FastAPI，前端使用原生 HTML、CSS 和 JavaScript，由同一个 Python 服务提供网页与 API。这样可以减少依赖、缩短开发时间，并避免前后端分别启动造成的演示风险。

完成 Step 3 后即可录制第一版展示视频，不需要等待真实 CAD 和正式内网部署完成。

---

# 2. 已确认的业务规则

## 2.1 定位面由 CAD 最终判断

现有运行链路会调用 `list_reference_planes()` 和 `resolve_reference_plane()` 查询 Mock 定位面目录，并把用户表达转换成工程正式名称。该逻辑不符合当前实际软件的调用方式。

目标规则调整为：

1. LLM 负责从用户输入中提取定位面名称。
2. 已知标尺面按照固定范围规范化：X 轴 `FR-10～FR200`、Y 轴 `SL-40～SL40`、Z 轴 `LV-5～LV50`。
3. `第N肋位` 和 `N号肋位` 在已知范围内转换为 `FRN`，例如 `第100肋位 → FR100`。
4. Agent 不查询当前 CAD 工程的定位面目录，也不根据坐标猜测标尺面。
5. 不符合已知规范化规则的工程名称保持原文，仍交给 CAD 判断。
6. Agent 校验定位面是否缺失或为空，但不判断它是否真实存在。
7. `create_panel` 调用真实 CAD 时，将规范化后的字符串映射为 CAD 接口字段 `referenceName`。
8. CAD 软件负责判断 `referenceName` 是否存在、是否唯一以及是否可作为板架定位面。
9. CAD 判断失败时，通过结构化错误返回，例如 `REFERENCE_PLANE_NOT_FOUND`。
10. 不设计或传递 `reference_plane_id`。

目标运行链路：

```text
parse → validate → cad → END
```

不再使用：

```text
parse → validate → resolve_plane → cad → END
```

现有定位面 Schema、Resolver 和独立测试暂不删除，可作为历史实现或未来高级能力保留，但不再参与主运行链路。新增的标尺面规范化是本地确定性字符串转换，不等同于查询或解析当前 CAD 工程对象。

## 2.2 材料和厚度的职责边界

- Agent 校验 `material` 非空，但暂不查询材料目录，也不判断牌号是否存在。
- Agent 校验 `thickness` 是有限的正数，单位统一为 mm。
- 材料是否被当前 CAD 工程支持，由真实 CAD Backend 最终判断。
- 缺失定位面、厚度或材料时，Agent 不调用 CAD，而是返回补充信息。
- 边界暂时允许为空，保持当前 `PanelBoundaries` 规则。

## 2.3 展示必须明确区分 Mock 与真实执行

第一版浏览器界面使用 `MockCadBackend`，页面固定显示：

```text
Demo Mode · CAD execution is simulated
```

Mock 返回的对象 ID 以 `mock-panel-` 开头。页面不得把 Mock 执行描述为真实 CAD 建模成功。

接入真实 CAD 后，运行模式改为 `CAD Connected`，并展示真实 CAD 返回的结果和错误码。

---

# 3. 当前代码基线与改造范围

当前可复用能力：

- `agent/main.py` 已提供 `run_panel_agent()`，可以被 Web 层直接调用。
- `agent/graph.py` 已实现结构提取、动作路由、参数校验、有限重试和 CAD 调用。
- `schemas/panel_schema.py` 已定义 `PanelRequest`、`PanelBoundaries` 和 `CadExecutionResult`。
- `tools/cad_tools.py` 已通过 `CadBackend` 隔离 Mock 与未来真实 CAD。
- `llm/qwen_client.py` 已封装 Ollama/Qwen 请求和错误码。
- 当前已有 84 项测试，其中 83 项离线测试通过，1 项真实 Ollama E2E 默认跳过；该 E2E 已单独启用并验证通过。

需要改造和新增的范围：

```text
PanelCreatorByAi/
├─ agent/
│  ├─ graph.py                   # 移除主链路中的定位面查询
│  └─ state.py                   # 主流程不再依赖定位面解析状态
├─ tools/
│  └─ ruler_plane_tools.py       # 已知标尺面范围和名称规范化
├─ Doc/Reference/
│  └─ AI_Ship_CAD_Copilot_可用标尺面_v1.0.md
│                                # 标尺面业务规则说明
├─ webapp/
│  ├─ app.py                     # FastAPI 应用和 API
│  ├─ schemas.py                 # Web 请求及响应 DTO
│  ├─ response_mapper.py         # AgentState → 页面响应 DTO
│  └─ static/
│     ├─ index.html              # 单页演示界面
│     ├─ styles.css              # 工业/CAD 风格视觉样式
│     └─ app.js                  # 请求、状态和多轮补充交互
├─ tests/
│  ├─ test_graph.py              # 更新定位面直传测试
│  ├─ test_ruler_plane_tools.py  # 标尺面范围和转换测试
│  ├─ test_web_response_mapper.py
│  └─ test_web_api.py
├─ requirements.txt              # 增加 Web 服务依赖
├─ run_web.py                    # 本地启动入口
└─ .gitignore                    # 允许提交 HTML、CSS 和 JavaScript
```

为了降低现有代码改动风险，内部 Schema 可以继续使用字段名 `reference_plane`；在真实 CAD Adapter 边界将其映射为软件字段 `referenceName`。页面面向用户统一显示“定位面（referenceName）”。

---

# 4. 浏览器演示界面设计

## 4.1 页面目标

页面重点展示“自然语言如何变成可执行 CAD 参数”，而不是制作通用聊天机器人。

第一版采用单页布局，包含五个区域：

1. **顶部状态栏**
   - 产品名称：AI Ship CAD Copilot
   - 当前连接状态：Ollama、Agent、CAD Backend
   - 运行模式：Demo Mode / CAD Connected

2. **需求输入区**
   - 多行自然语言输入框
   - “生成板架”主按钮
   - 三个示例场景快捷按钮

3. **执行流程区**
   - 理解需求
   - 参数提取
   - Schema 校验
   - CAD 创建
   - 每一步显示等待、进行中、成功、失败或未执行状态

4. **结构化参数区**
   - 定位面（referenceName）
   - 厚度（mm）
   - 材料
   - 上、下、左、右边界
   - 不直接向普通演示观众展示完整 Python 对象

5. **结果区**
   - 创建成功、需要补充、CAD 失败或不支持
   - CAD 对象 ID（存在时显示）
   - 稳定错误码（失败时显示）
   - 可展开查看原始 JSON，默认折叠

## 4.2 推荐视觉方向

- 深蓝灰背景，搭配青色或绿色状态高亮，体现船舶 CAD/工业软件风格。
- 使用卡片和细网格线表达工程界面，不仿制具体商业 CAD 软件。
- 页面宽度适配 1366×768 和 1920×1080，方便屏幕录制。
- 动效仅用于步骤状态切换，避免复杂动画导致录屏不稳定。
- 成功、澄清、失败分别使用绿色、黄色和红色，不只依靠文字区分。

## 4.3 第一版录屏场景

### 场景 A：完整创建请求

```text
请在第100肋位创建一块14mm厚的AH36板架
```

预期：把 `第100肋位` 规范化为 `FR100`，提取 `14 mm` 和 `AH36`，直接调用 Mock CAD，显示模拟创建成功。

关键验收点：页面和调用参数中的定位面显示为规范化后的 `FR100`。

### 场景 B：缺失材料

```text
请在FR100创建一块14mm厚的板架
```

预期：CAD 步骤不执行，页面提示补充材料；用户补充 `AH36` 后重新执行并成功。

### 场景 C：不支持的请求

```text
请解释AH36是什么材料
```

预期：不调用 CAD，页面说明当前仅支持创建板架。

### 场景 D：CAD 返回定位面错误

此场景在真实 CAD Adapter 或可配置的失败 Mock 中验证。

预期：Agent 已把用户的 `referenceName` 提交给 CAD；CAD 返回 `REFERENCE_PLANE_NOT_FOUND` 后，页面显示创建失败，而不是在 Agent 侧提前拦截。

---

# 5. Web API 方案

## 5.1 健康检查

```http
GET /api/health
```

建议响应：

```json
{
  "status": "ok",
  "mode": "mock",
  "agent": "ready",
  "cad_backend": "mock"
}
```

该接口不主动调用 LLM，只确认 Web 服务已启动。Ollama 与真实 CAD 的深度探测可以在后续阶段增加，避免首页因为外部服务较慢而无法打开。

## 5.2 执行板架创建请求

```http
POST /api/agent/runs
Content-Type: application/json
```

请求：

```json
{
  "message": "请在第100肋位创建一块14mm厚的AH36板架"
}
```

建议响应：

```json
{
  "request_id": "9cf1...",
  "status": "success",
  "mode": "mock",
  "message": "模拟 CAD 已完成板架创建。",
  "steps": [
    {"name": "parse", "status": "success"},
    {"name": "validate", "status": "success"},
    {"name": "cad", "status": "success"}
  ],
  "panel": {
    "referenceName": "FR100",
    "thicknessMm": 14.0,
    "material": "AH36",
    "boundaries": {
      "top": null,
      "bottom": null,
      "left": null,
      "right": null
    }
  },
  "cad_result": {
    "success": true,
    "message": "Panel created successfully",
    "object_id": "mock-panel-...",
    "error_code": null
  }
}
```

`status` 限定为：

| 状态 | 含义 | 是否调用 CAD |
|---|---|---:|
| `success` | CAD Backend 返回成功 | 是 |
| `clarification` | 缺少必填信息 | 否 |
| `unsupported` | 当前不支持的任务 | 否 |
| `error` | LLM、校验、Web 或 CAD 执行失败 | 视失败阶段而定 |

## 5.3 响应映射原则

Web API 不直接返回完整 `AgentState`，而是通过 `response_mapper.py` 生成稳定的页面响应。原因如下：

- `AgentState` 中包含 Pydantic 对象，不能直接作为稳定 JSON 契约。
- 内部字段会随 LangGraph 调整，页面不应与图状态强耦合。
- `llm_raw_output` 可能包含调试内容，默认不应直接展示。
- 后续增加真实 CAD、MCP 或日志字段时，不需要修改前端核心逻辑。

第一版接口采用一次请求、一次完整响应，不做 Token 流式输出。页面可以在等待期间播放步骤状态动画，后续如确有需要再增加 SSE/WebSocket。

---

# 6. 本地运行与内网迁移方案

## 6.1 本地演示模式

启动目标：

```powershell
python run_web.py
```

默认行为：

- 监听 `127.0.0.1:8000`。
- 使用本机 Ollama。
- 使用 `MockCadBackend`。
- 浏览器、API 和静态资源同源，不需要开放 CORS。
- 不开启登录，不允许其他电脑访问。

推荐配置通过环境变量或配置对象读取：

| 配置 | 默认值 | 说明 |
|---|---|---|
| `APP_HOST` | `127.0.0.1` | 服务监听地址 |
| `APP_PORT` | `8000` | 服务端口 |
| `CAD_BACKEND` | `mock` | `mock` 或未来的 `connector` |
| `OLLAMA_BASE_URL` | 当前本机地址 | Ollama 服务地址 |
| `APP_ENV` | `demo` | 页面运行模式标识 |

配置值不得硬编码到前端。前端始终使用相对路径 `/api/...`。

## 6.2 内网单工作站试用

如果真实 CAD 只能由安装它的 Windows 工作站调用，第一阶段内网试用采用：

```text
CAD 工作站
├─ 真实 CAD
├─ Web/Agent 服务
└─ CAD Connector

其他内网电脑浏览器 → CAD 工作站 IP:端口
```

需要调整：

- `APP_HOST=0.0.0.0`
- Windows 防火墙仅开放指定内网网段和端口
- `CAD_BACKEND=connector`
- 增加最小身份认证或由内网反向代理统一认证
- 记录请求人、请求时间、输入参数和 CAD 结果

## 6.3 内网中央服务模式

当需要多台 CAD 工作站并发使用时，再演进为：

```text
浏览器
  ↓
中央 Web/Agent 服务
  ↓ 任务分发
CAD Workstation Connector
  ↓
本机 CAD
```

中央服务不能默认直接操控每位工程师电脑上的 CAD。每台 CAD 工作站需要运行轻量 Connector，并具备工作站注册、心跳、任务领取、超时和结果回传能力。

该模式不属于六天最小交付范围，但当前 API、响应 DTO 和 `CadBackend` 抽象必须避免阻碍后续迁移。

## 6.4 内网安全最低要求

- 默认仅监听 `127.0.0.1`，只有明确部署时才允许 `0.0.0.0`。
- 不把 Ollama 和 CAD Connector 端口直接暴露给普通用户网段。
- 正式内网环境通过反向代理提供 HTTPS 和身份认证。
- API 限制输入长度、请求体大小和并发数量。
- 前端不渲染未经转义的模型输出，避免脚本注入。
- CAD 创建请求必须记录 request ID，便于追踪和审计。
- CAD Connector 设置调用超时，不允许 Web 请求无限等待。

---

# 7. 分步实施计划与 Review 点

每完成一个 Step 后暂停，汇报变更文件、测试结果和代码逻辑 Review，等待确认后再继续。

## Step 1：标尺面规范化与其他名称直传

状态：**已完成并确认**。

目标：让当前 Agent 与真实软件的 `referenceName` 使用方式一致。

实施内容：

- 从主运行图移除 `resolve_plane` 节点。
- `validate_structure()` 同时检查定位面、厚度和材料是否缺失。
- 在校验节点直接构造 `PanelRequest`。
- 对已知标尺面执行确定性名称规范化，不查询 CAD 工程目录。
- `第100肋位`、`100号肋位` 等已知别名转换为 `FR100`。
- 不符合已知规则的其他工程名称保持原文。
- 主流程不再写入或依赖 `reference_plane_resolution`。
- 更新 Graph 与 E2E 测试。
- 保留定位面 Resolver 源文件和独立测试，不在本 Step 删除历史能力。

完成标准：

- `第100肋位` 进入 `create_panel` 时为 `FR100`。
- `X=10000` 进入 `create_panel` 时仍为 `X=10000`。
- 未知名称仍会调用 CAD Backend。
- 空定位面会请求用户补充，不调用 CAD。
- 全部离线测试通过。

预计耗时：0.5 天。

Review 重点：主图路由是否简化正确；是否还有隐藏的定位面目录调用；已有异常与重试是否保持不变。

## Step 2：建立 Web 服务与页面响应契约

状态：**已完成，等待 Review**。

目标：把现有 `run_panel_agent()` 变成浏览器可调用的稳定 API。

实施内容：

- 增加 FastAPI 和 Uvicorn 依赖。
- 实现 `/api/health` 和 `/api/agent/runs`。
- 增加输入 Schema 和页面响应 DTO。
- 实现 `AgentState` 到 Web 响应的确定性映射。
- 统一处理空输入、LLM 异常、澄清、不支持、CAD 成功和 CAD 失败。
- 增加 API 与响应映射测试。

完成标准：通过接口可以得到稳定 JSON；Mock CAD 成功、澄清和错误场景均有测试。

预计耗时：0.5 天。

Review 重点：接口是否泄漏内部状态；错误状态映射是否准确；页面契约是否便于后续真实 CAD 替换。

## Step 3：实现可录屏的单页浏览器界面

状态：**已完成，等待 Review**。

目标：交付第一个可以展示和录制视频的完整页面。

实施内容：

- 实现输入区、示例按钮、执行步骤、参数卡片和结果区。
- 增加明显的 Demo Mode 标识。
- 支持成功、澄清、不支持和错误四类页面状态。
- 支持一次或多次补充信息，并复用当前累积请求逻辑。
- 增加重复提交保护、加载状态和基础响应式布局。
- 增加 `run_web.py` 一键启动入口。

完成标准：完成场景 A、B、C 的人工演示；页面在 1366×768 和 1920×1080 下无明显遮挡；可以开始录制第一版视频。

预计耗时：1 天。

Review 重点：展示信息是否准确；Mock 标识是否充分；交互是否能让非技术观众看懂 Agent 到 CAD 的过程。

## Step 4：演示稳定性与失败场景

状态：**代码未保留，待重新实现与验证**。

此前曾规划并实现但当前代码未保留的内容：Mock 支持 `success`、`unavailable`、`reference_not_found` 三种启动场景；请求期间锁定新建会话和示例入口；增加浏览器超时、网络错误和重复提交提示；每轮清空旧参数与结果。等待动画不再提前标记步骤成功。浏览器停止等待不代表服务端已取消，页面提示确认执行结果后再提交。

固定输入继续使用第 4.3 节的 A、B、C；场景 D 使用与 A 相同的完整输入，启动前指定失败 Mock（修改后需重启服务）：

```powershell
conda activate ai_cad_agent
$env:MOCK_CAD_SCENARIO = "reference_not_found"
python run_web.py
```

模拟 CAD 不可用时改为 `unavailable`；恢复正常演示时改为 `success`。此配置只影响 Mock，不查询真实工程。

离线验证：`python -X utf8 run_tests.py`；页面交互测试由同一入口在 Node 可用时执行，也可单独运行 `node --test tests/webapp_interactions.cjs`。已覆盖失败后成功、超时释放按钮、重复提交、澄清重试与旧结果清理。实际浏览器工具因 Windows 登录错误 1385 无法启动，页面视觉与人工演示不记为通过。

目标：保证录制时不因常见异常中断，并预演真实 CAD 错误。

实施内容：

- 增加可控失败 Mock，用于模拟 CAD 不可用和定位面不存在。
- 补充浏览器端超时、网络错误和重复请求提示。
- 验证 Ollama 未启动、LLM 非法输出和 CAD 失败页面。
- 整理固定演示输入，但不扩写额外项目文档。

完成标准：四类结果都有稳定页面表现；重复演示不会残留上一轮错误状态。

预计耗时：0.5 天。

Review 重点：错误来源是否区分清楚；Mock 失败是否不会污染正式 CAD Backend 契约。

## Step 5：接入真实 CAD Connector

目标：将 `MockCadBackend` 替换为能调用真实 CAD 的 Backend。

实施内容：

- 根据真实 CAD 接口确定进程内调用、HTTP、本机 Socket 或 MCP 连接方式。
- 把 `PanelRequest.reference_plane` 映射为 CAD 参数 `referenceName`。
- 映射厚度、材料和四向边界。
- 将真实 CAD 成功结果和错误统一转换为 `CadExecutionResult`。
- 增加连接超时、调用超时和结构化错误码。
- 保留 `CAD_BACKEND=mock`，使离线测试和录屏仍可独立运行。

完成标准：至少一条完整请求可以创建真实 CAD Panel；不存在的 `referenceName` 由 CAD 返回失败；Agent 不提前查询定位面。

预计耗时：2 天，取决于真实 CAD API 可用性。

Review 重点：真实 CAD 调用是否只位于 Backend/Connector；参数是否一一对应；异常是否会破坏 Web 服务进程。

## Step 6：内网试用准备与整体回归

目标：使同一套页面可以在受控内网环境试用。

实施内容：

- 把监听地址、端口、Ollama 地址和 Backend 模式全部配置化。
- 验证同网段另一台电脑可以访问页面。
- 限制防火墙范围，并增加基础请求日志和 request ID。
- 执行自动化测试与完整人工回归。
- 修复联调阶段发现的阻断问题。

完成标准：本机模式仍可运行；内网浏览器可访问；Mock 和真实 CAD 模式均能受控切换。

预计耗时：1.5 天，包含风险缓冲。

Review 重点：默认配置是否安全；真实 CAD 是否只能被授权服务调用；本地演示是否仍然可复现。

---

# 8. 六天时间安排

| 天数 | 主要工作 | 当天可见交付 |
|---|---|---|
| Day 1 | Step 1、Step 2 | 定位面直传完成；浏览器 API 可用 |
| Day 2 | Step 3 | 可录屏的本地网页；成功、澄清和不支持场景可展示 |
| Day 3 | Step 4；开始 Step 5 | 失败场景稳定；真实 CAD 连接链路开始联调 |
| Day 4 | Step 5 | 字段映射和真实 Panel 创建联调 |
| Day 5 | 完成 Step 5；开始 Step 6 | 真实创建闭环；开始配置内网访问 |
| Day 6 | 完成 Step 6 | 整体回归、内网试用版本和风险缓冲 |

如果真实 CAD API 在 Day 3 前仍不可用，Day 3–4 改为完善 Connector 契约和可控 Mock，不阻塞本地网页展示与视频录制。

---

# 9. 测试与验收方案

## 9.1 自动化测试

必须覆盖：

- 已知标尺面别名按规则规范化后传入 CAD Tool。
- 其他工程定位面文本原样传入 CAD Tool。
- 缺少定位面时不调用 CAD。
- 非法厚度不调用 CAD。
- 未知定位面不会在 Agent 侧被拒绝。
- Agent 成功、澄清、不支持和错误到 Web DTO 的映射。
- 空请求和过长请求的 API 拦截。
- Mock CAD 成功和结构化失败。
- 现有 CLI 功能不回归。

统一测试入口继续使用：

```powershell
python -X utf8 run_tests.py
```

## 9.2 人工测试

每次浏览器版本交付前执行：

1. 首次打开页面无控制台报错。
2. 场景 A 可以显示参数并得到 Mock 成功结果。
3. 场景 B 不调用 CAD，补充材料后成功。
4. 场景 C 不调用 CAD。
5. Ollama 未启动时页面能显示可理解的错误。
6. 连续提交两次不会把上一次状态混入本次结果。
7. 刷新页面后可以重新开始。
8. 页面明确显示当前是 Mock 还是真实 CAD。

## 9.3 内网验收

- 服务默认仍只允许本机访问。
- 修改配置后，同网段指定电脑可以访问。
- 非允许网段不能直接访问 CAD Connector。
- 前端无需改代码即可访问同源 API。
- 真实 CAD 错误可以完整回传至页面。

---

# 10. 主要风险与控制措施

| 风险 | 影响 | 控制措施 |
|---|---|---|
| 本地 Qwen 首次响应较慢 | 录屏等待时间长 | 录屏前预热模型，页面显示明确加载状态 |
| LLM 漏提取已知标尺面 | 无法调用 CAD | 从用户原文确定性提取唯一的 FR/SL/LV 标尺面；无法唯一确定时要求补充 |
| 页面显示成功但实际是 Mock | 造成误解 | 固定 Demo Mode 标签和 `mock-panel-` ID |
| 真实 CAD 只能在桌面会话运行 | Windows 服务无法调用 CAD | 先采用 CAD 工作站本机部署或独立 Connector |
| CAD API 返回格式不稳定 | Web 层出现异常 | 所有真实返回先在 Backend 中转换为 `CadExecutionResult` |
| 内网开放端口缺少保护 | 非授权创建 CAD 对象 | 默认本机监听，内网阶段增加防火墙、认证和审计 |
| 六天内真实 CAD 接口不可用 | 无法完成真实联调 | 保证 Mock 视频演示先完成；Connector 契约与真实实现解耦 |

---

# 11. 本次 Review 需要确认的内容

建议按以下方案直接实施：

1. 使用 FastAPI + 原生 HTML/CSS/JavaScript，不引入 Node 前端构建链。
2. 先实现已知标尺面规范化和其他名称直传，再建立 Web API，避免网页展示即将废弃的工程目录解析流程。
3. Web API 与静态页面由同一服务提供，第一版不配置 CORS。
4. 第一版固定使用 Mock CAD，并明确显示 Demo Mode。
5. 完成 Step 3 后先录制本地展示视频，再继续真实 CAD 和内网工作。
6. 内部继续使用 `PanelRequest.reference_plane`，只在 CAD Adapter 边界映射为 `referenceName`。
7. 当前不删除定位面 Resolver 文件，只将其退出主运行链路。
8. 每完成一个 Step 即暂停并提交变更说明、测试结果和代码逻辑 Review，等待确认后继续。

当前等待 **Step 1：标尺面规范化与其他名称直传** 的代码 Review；确认后开始 Step 2。
