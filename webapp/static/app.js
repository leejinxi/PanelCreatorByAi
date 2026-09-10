"use strict";

const form = document.querySelector("#request-form");
const input = document.querySelector("#request-input");
const submitButton = document.querySelector("#submit-button");
const submitLabel = submitButton.querySelector(".button-label");
const resetButton = document.querySelector("#reset-button");
const newSessionButton = document.querySelector("#new-session-button");
const exampleButtons = [...document.querySelectorAll("[data-example]")];
const sessionNote = document.querySelector("#session-note");
const inputError = document.querySelector("#input-error");
const characterCount = document.querySelector("#character-count");
const requestId = document.querySelector("#request-id");
const agentStatus = document.querySelector("#agent-status");
const cadStatus = document.querySelector("#cad-status");
const parameterState = document.querySelector("#parameter-state");
const jsonDetails = document.querySelector("#json-details");
const jsonOutput = document.querySelector("#json-output");
const traceTotal = document.querySelector("#trace-total");
const mcpCallState = document.querySelector("#mcp-call-state");
const mcpRequestOutput = document.querySelector("#mcp-request-output");
const mcpResponseOutput = document.querySelector("#mcp-response-output");
const currentProvider = document.querySelector("#current-provider");
const decisionTimeline = document.querySelector("#decision-timeline");
const inspectionProject = document.querySelector("#inspection-project");
const inspectionResults = document.querySelector("#inspection-results");
const safetyGate = document.querySelector("#safety-gate");
const safetyGateState = document.querySelector("#safety-gate-state");
const safetyGateReason = document.querySelector("#safety-gate-reason");
const traceElements = new Map(
  [...document.querySelectorAll("[data-trace]")].map((element) => [
    element.dataset.trace,
    element,
  ]),
);

const parameterFields = {
  referenceName: document.querySelector("#reference-name"),
  thicknessMm: document.querySelector("#thickness"),
  material: document.querySelector("#material"),
};

const resultElements = {
  container: document.querySelector("#execution-result"),
  icon: document.querySelector("#result-icon"),
  kicker: document.querySelector("#result-kicker"),
  message: document.querySelector("#result-message"),
  meta: document.querySelector("#result-meta"),
};

let userTurns = [];
let awaitingClarification = false;
let loadingTimer = null;
let isExecuting = false;
let executionMode = "unconfigured";

const DEMO_REQUEST_TIMEOUT_MS = 150000;

const stepOrder = ["parse", "decision", "inspect", "evaluate", "validate", "cad"];
const resultPresentation = {
  success: { className: "success", icon: "✓", kicker: "创建完成" },
  clarification: { className: "attention", icon: "!", kicker: "需要补充" },
  unsupported: { className: "attention", icon: "—", kicker: "未执行 CAD" },
  error: { className: "error", icon: "×", kicker: "执行失败" },
};

function setCharacterCount() {
  characterCount.textContent = String(input.value.length);
}

function buildAccumulatedRequest(turns) {
  if (turns.length === 1) {
    return turns[0];
  }

  const lines = [`初始需求：${turns[0]}`];
  turns.slice(1).forEach((turn, index) => {
    lines.push(`用户第${index + 1}次补充：${turn}`);
  });
  return lines.join("\n");
}

function setLoading(isLoading) {
  submitButton.disabled = isLoading;
  resetButton.disabled = isLoading;
  newSessionButton.disabled = isLoading;
  exampleButtons.forEach((button) => { button.disabled = isLoading; });
  input.disabled = isLoading;
  submitLabel.textContent = isLoading
    ? "Agent 正在执行"
    : awaitingClarification
      ? "提交补充信息"
      : "解析并创建";

  if (!isLoading) {
    window.clearInterval(loadingTimer);
    loadingTimer = null;
    return;
  }

  let activeIndex = 0;
  renderLoadingStep(activeIndex);
  loadingTimer = window.setInterval(() => {
    activeIndex = Math.min(activeIndex + 1, stepOrder.length - 1);
    renderLoadingStep(activeIndex);
  }, 900);
}

function clearPreviousResultForExecution() {
  requestId.textContent = "REQUEST —";
  parameterState.textContent = "等待解析";
  renderPanel(null);
  jsonDetails.hidden = true;
  jsonDetails.open = false;
  jsonOutput.textContent = "";
  clearExecutionTrace();
  const llmNode = traceElements.get("llm");
  if (llmNode) {
    llmNode.classList.add("running");
    llmNode.querySelector("small").textContent = "正在调用本地模型…";
  }
}

function renderLoadingStep(activeIndex) {
  stepOrder.forEach((stepName, index) => {
    const element = document.querySelector(`[data-step="${stepName}"]`);
    element.className = "step";
    if (index < activeIndex) {
      element.classList.add("success");
    } else if (index === activeIndex) {
      element.classList.add("running");
    }
  });
}

function renderSteps(steps = []) {
  const statusByName = new Map(steps.map((step) => [step.name, step.status]));
  stepOrder.forEach((stepName) => {
    const element = document.querySelector(`[data-step="${stepName}"]`);
    element.className = "step";
    const status = statusByName.get(stepName);
    if (status) {
      element.classList.add(status);
    }
  });
}

function displayValue(value, fallback = "—") {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }
  return String(value);
}

function renderPanel(panel, inspection = null) {
  const boundaries = panel?.boundaries ?? [];
  const referenceName = displayValue(panel?.referenceName);

  parameterFields.referenceName.textContent = referenceName;
  parameterFields.thicknessMm.textContent = displayValue(panel?.thicknessMm);
  parameterFields.material.textContent = displayValue(panel?.material);
  document.querySelector("#boundary-count").textContent = `有效边界 ${boundaries.length} / 至少1条`;
  const list = document.querySelector("#boundary-list");
  list.replaceChildren();
  boundaries.forEach((boundary) => {
    const item = document.createElement("li");
    const match = (inspection?.boundaries || []).find(
      (entry) => entry.query === boundary.target,
    );
    const status = match ? matchStatusLabel(match.status) : "待工程查询";
    item.textContent = `${boundary.operator}${boundary.target} · ${status}`;
    list.append(item);
  });
  const issues = document.querySelector("#boundary-issues");
  issues.replaceChildren();
  (panel?.boundary_issues || []).forEach((issue) => {
    const item = document.createElement("li");
    item.textContent = issue.message;
    issues.append(item);
  });
  parameterState.textContent = panel ? "已提取" : "等待解析";
}

const actionLabels = {
  inspect_project_context: "查询工程上下文",
  ask_clarification: "请求用户补充",
  prepare_creation: "准备创建板架",
  stop: "停止执行",
};

const sourceLabels = {
  policy: "安全策略",
  llm: "Qwen 决策",
  fallback: "稳定性兜底",
  safety_override: "安全规则覆盖",
};

function matchStatusLabel(status) {
  return {
    resolved: "Mock 对象已唯一匹配",
    not_found: "Mock 对象未找到",
    ambiguous: "存在多个候选",
    unavailable: "对象不可用",
    not_eligible: "对象角色不允许",
  }[status] || "状态未知";
}

function renderDecisionLoop(trace) {
  const decisions = trace?.decision_steps || [];
  decisionTimeline.replaceChildren();
  if (!decisions.length) {
    const empty = document.createElement("li");
    empty.className = "decision-empty";
    empty.textContent = "本次请求没有形成可展示的 Agent 决策。";
    decisionTimeline.append(empty);
  }
  decisions.forEach((step) => {
    const item = document.createElement("li");
    item.className = `decision-item ${step.source}`;
    const heading = document.createElement("div");
    heading.className = "decision-item-heading";
    const index = document.createElement("span");
    index.textContent = `DECISION ${String(step.sequence).padStart(2, "0")}`;
    const source = document.createElement("b");
    source.textContent = sourceLabels[step.source] || step.source;
    heading.append(index, source);
    const observation = document.createElement("p");
    observation.textContent = step.observation;
    const action = document.createElement("strong");
    action.textContent = `下一步：${actionLabels[step.action] || step.action}`;
    const reason = document.createElement("small");
    reason.textContent = `依据：${step.reason_code}`;
    item.append(heading, observation, action, reason);
    if (step.evidence?.length) {
      const evidence = document.createElement("ul");
      step.evidence.forEach((value) => {
        const evidenceItem = document.createElement("li");
        evidenceItem.textContent = value;
        evidence.append(evidenceItem);
      });
      item.append(evidence);
    }
    decisionTimeline.append(item);
  });

  const inspection = trace?.project_inspection;
  inspectionResults.replaceChildren();
  if (!inspection) {
    inspectionProject.textContent = "未执行查询";
    const empty = document.createElement("li");
    empty.className = "inspection-empty";
    empty.textContent = "只读 Mock 工程查询未执行。";
    inspectionResults.append(empty);
  } else {
    inspectionProject.textContent = `${inspection.project_name} · ${inspection.revision}`;
    const matches = [inspection.reference_plane, ...(inspection.boundaries || [])];
    matches.forEach((match) => {
      const item = document.createElement("li");
      item.className = `match-${match.status}`;
      const role = match.role === "reference_plane" ? "定位面" : "边界";
      const target = match.resolved_name || match.candidates?.join(" / ") || "—";
      const query = document.createElement("span");
      query.textContent = `${role} · ${match.query}`;
      const status = document.createElement("strong");
      status.textContent = matchStatusLabel(match.status);
      const resolved = document.createElement("small");
      resolved.textContent = target;
      item.append(query, status, resolved);
      inspectionResults.append(item);
    });
  }

  const gate = trace?.safety_gate || { authorized: false, reason: null };
  safetyGate.className = `safety-gate ${gate.authorized ? "authorized" : decisions.length ? "blocked" : "neutral"}`;
  safetyGateState.textContent = gate.authorized ? "允许执行" : decisions.length ? "未授权执行" : "等待评估";
  safetyGateReason.textContent = gate.reason || (
    gate.authorized ? "所有安全检查已通过" : "只有工程对象唯一匹配后才允许创建"
  );
}

function renderExecutionTrace(trace) {
  const nodes = new Map((trace?.nodes || []).map((node) => [node.name, node]));
  traceElements.forEach((element, name) => {
    const node = nodes.get(name);
    element.className = "trace-node";
    if (!node) return;
    element.classList.add(node.status);
    element.querySelector("strong").textContent = node.label;
    const duration = node.duration_ms === null || node.duration_ms === undefined
      ? "" : ` · ${node.duration_ms}ms`;
    element.querySelector("small").textContent = `${node.summary}${duration}`;
  });
  traceTotal.textContent = trace?.total_ms === null || trace?.total_ms === undefined
    ? "TOTAL —" : `TOTAL ${trace.total_ms}ms`;
}

function renderMcpInspector(trace) {
  const request = trace?.mcp_request;
  const response = trace?.mcp_response;
  mcpRequestOutput.textContent = request
    ? JSON.stringify(request, null, 2)
    : "安全路由未产生 MCP tools/call。";
  mcpResponseOutput.textContent = response
    ? JSON.stringify(response, null, 2)
    : "MCP Provider 未返回结果。";
  mcpCallState.textContent = request
    ? response ? "TOOLS/CALL COMPLETE" : "TOOLS/CALL FAILED"
    : "SKIPPED";
}

function renderProviderBoundary(trace) {
  const provider = trace?.provider || "unconfigured";
  currentProvider.innerHTML = provider === "contract-mock"
    ? "Contract Mock<small>当前模拟执行</small>"
    : provider === "direct-mock"
      ? "Direct Mock<small>当前模拟执行</small>"
      : "Unconfigured<small>等待后端配置</small>";
}


function clearExecutionTrace() {
  traceElements.forEach((element) => {
    element.className = "trace-node";
    element.querySelector("small").textContent = "等待请求";
  });
  traceTotal.textContent = "TOTAL —";
  mcpCallState.textContent = "WAITING";
  mcpRequestOutput.textContent = "等待通过安全校验的请求…";
  mcpResponseOutput.textContent = "尚未调用 MCP Provider。";
  renderDecisionLoop(null);
}

function renderResult(payload) {
  renderExecutionMode(payload.mode);
  renderExecutionTrace(payload.execution_trace);
  renderMcpInspector(payload.execution_trace);
  renderProviderBoundary(payload.execution_trace);
  renderDecisionLoop(payload.execution_trace);
  const presentation = resultPresentation[payload.status] ?? resultPresentation.error;
  resultElements.container.className = `execution-result ${presentation.className}`;
  resultElements.icon.textContent = presentation.icon;
  resultElements.kicker.textContent = payload.status === "success"
    ? "模拟创建完成" : presentation.kicker;
  resultElements.message.textContent = payload.message || "没有返回结果。";

  const objectId = payload.cad_result?.object_id;
  const errorCode = payload.error_code;
  resultElements.meta.textContent = objectId
    ? `模拟对象 ID：${objectId}`
    : errorCode
      ? `错误码：${errorCode}`
      : "Mock CAD 不会修改真实工程。";

  requestId.textContent = payload.request_id
    ? `REQUEST ${payload.request_id.slice(0, 8).toUpperCase()}`
    : "REQUEST —";
  renderSteps(payload.steps);
  renderPanel(payload.panel, payload.execution_trace?.project_inspection);

  jsonOutput.textContent = JSON.stringify(payload, null, 2);
  jsonDetails.hidden = false;
  jsonDetails.open = false;

  awaitingClarification = payload.status === "clarification";
  sessionNote.hidden = !awaitingClarification;
  input.placeholder = awaitingClarification
    ? (payload.panel?.boundary_issues?.length
      ? "例如：边界 >SL10；修正已有边界可输入：边界全部改为 >SL10"
      : "请补充缺少的信息，例如：材料为 AH36")
    : "例如：请在第100肋位创建一块14mm厚的AH36板架，边界 >SL10";
  submitLabel.textContent = awaitingClarification ? "提交补充信息" : "解析并创建";
}

function renderNetworkError(message) {
  renderSteps([
    { name: "parse", status: "error" },
    { name: "decision", status: "skipped" },
    { name: "inspect", status: "skipped" },
    { name: "evaluate", status: "skipped" },
    { name: "validate", status: "skipped" },
    { name: "cad", status: "skipped" },
  ]);
  resultElements.container.className = "execution-result error";
  resultElements.icon.textContent = "×";
  resultElements.kicker.textContent = "连接失败";
  resultElements.message.textContent = message;
  resultElements.meta.textContent = "请确认本地服务和 Ollama 已启动。";
  agentStatus.classList.remove("online");
  agentStatus.classList.add("offline");
}

function renderExecutionMode(mode) {
  executionMode = mode;
  const label = { mock: "Direct Mock CAD", mcp: "MCP Contract Mock" }[mode];
  cadStatus.classList.remove("online", "offline");
  cadStatus.classList.add(label ? "online" : "offline");
  cadStatus.lastChild.textContent = label || "后端配置未确认";
  document.querySelector("#execution-mode").textContent = label
    ? `${label} · CAD execution is simulated`
    : "后端配置未确认";
  document.querySelector("#backend-step-label").textContent = label || "等待确认后端";
}

function simulatedBackendNote() {
  return executionMode === "mcp"
    ? "MCP Contract Mock 不会修改真实工程。"
    : "Direct Mock CAD 不会修改真实工程。";
}

async function checkHealth() {
  try {
    const response = await fetch("/api/health", { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error("health check failed");
    const payload = await response.json();
    agentStatus.classList.add("online");
    renderExecutionMode(payload.mode);
  } catch {
    renderExecutionMode("unconfigured");
    agentStatus.classList.add("offline");
    cadStatus.classList.add("offline");
  }
}

async function executeAgentTurn(turn, { startNewSession = false } = {}) {
  if (isExecuting) {
    throw new Error("已有板架任务正在执行，请等待当前任务完成。");
  }

  isExecuting = true;
  const previousTurns = [...userTurns];
  if (awaitingClarification && !startNewSession) {
    userTurns.push(turn);
  } else {
    userTurns = [turn];
  }

  setLoading(true);
  clearPreviousResultForExecution();
  resultElements.container.className = "execution-result neutral";
  resultElements.kicker.textContent = "正在执行";
  resultElements.message.textContent = "Agent 正在理解需求并整理 CAD 参数…";
  resultElements.meta.textContent = "请稍候，不要重复提交。";

  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), DEMO_REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch("/api/agent/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ message: buildAccumulatedRequest(userTurns) }),
      signal: controller.signal,
    });
    const contentType = response.headers.get("content-type") || "";
    if (!contentType.includes("application/json")) {
      throw new Error(`服务返回了非 JSON 响应（HTTP ${response.status}）。请查看启动窗口中的错误日志。`);
    }

    let payload;
    try {
      payload = await response.json();
    } catch {
      throw new Error(`服务返回了无效 JSON（HTTP ${response.status}）。请查看启动窗口中的错误日志。`);
    }

    if (!response.ok && !payload.status) {
      const detail = Array.isArray(payload.detail) ? payload.detail[0]?.msg : null;
      throw new Error(detail || `服务返回 HTTP ${response.status}`);
    }

    renderResult(payload);
    input.value = "";
    setCharacterCount();
    if (awaitingClarification) input.focus();
    return payload;
  } catch (error) {
    userTurns = previousTurns;
    const message = error?.name === "AbortError"
      ? "页面已停止等待。服务端任务可能仍在执行，请确认结果后再重新提交。"
      : error instanceof Error ? error.message : "无法连接本地 Agent 服务。";
    renderNetworkError(message);
    throw error;
  } finally {
    window.clearTimeout(timeoutId);
    isExecuting = false;
    setLoading(false);
  }
}

async function submitRequest(event) {
  event.preventDefault();
  inputError.textContent = "";
  const turn = input.value.trim();

  if (!turn) {
    inputError.textContent = awaitingClarification ? "请输入补充信息。" : "请输入板架创建需求。";
    input.focus();
    return;
  }

  try {
    await executeAgentTurn(turn);
  } catch {
    // executeAgentTurn 已经把错误显示到页面，并恢复会话状态。
  }
}

function resetSession() {
  if (isExecuting) return;
  userTurns = [];
  awaitingClarification = false;
  input.value = "";
  input.disabled = false;
  input.placeholder = "例如：请在第100肋位创建一块14mm厚的AH36板架，边界 >SL10";
  inputError.textContent = "";
  sessionNote.hidden = true;
  submitLabel.textContent = "解析并创建";
  requestId.textContent = "REQUEST —";
  parameterState.textContent = "等待解析";
  jsonDetails.hidden = true;
  renderPanel(null);
  renderSteps([]);
  clearExecutionTrace();
  resultElements.container.className = "execution-result neutral";
  resultElements.icon.textContent = "·";
  resultElements.kicker.textContent = "等待任务";
  resultElements.message.textContent = "输入板架需求后，执行结果将在这里显示。";
  resultElements.meta.textContent = simulatedBackendNote();
  setCharacterCount();
  input.focus();
}

function validateWebMcpInput(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new TypeError("输入必须是包含 message 的对象。");
  }
  const keys = Object.keys(value);
  if (keys.length !== 1 || keys[0] !== "message") {
    throw new TypeError("只允许提供 message 字段。");
  }
  if (typeof value.message !== "string") {
    throw new TypeError("message 必须是字符串。");
  }
  const message = value.message.trim();
  if (!message || message.length > 2000) {
    throw new RangeError("message 长度必须在 1 到 2000 个字符之间。");
  }
  return message;
}

function registerWebMcpTool() {
  const context = document.modelContext;
  if (!context?.registerTool) return;

  const lifecycle = new AbortController();
  const reportError = (error) => {
    console.warn("WebMCP tool registration failed", error);
  };

  try {
    void Promise.resolve(context.registerTool(
      {
        name: "create_panel_from_text",
        title: "创建 CAD 板架",
        description: "根据一段自然语言需求创建板架，并同步更新当前工作台。",
        inputSchema: {
          type: "object",
          properties: {
            message: {
              type: "string",
              minLength: 1,
              maxLength: 2000,
              description: "包含定位面、厚度、材料及至少一条边界（如 >SL10）的板架创建需求。",
            },
          },
          required: ["message"],
          additionalProperties: false,
        },
        annotations: {
          readOnlyHint: false,
          untrustedContentHint: true,
        },
        async execute(value) {
          const message = validateWebMcpInput(value);
          resetSession();
          input.value = message;
          setCharacterCount();
          const payload = await executeAgentTurn(
            message,
            { startNewSession: true },
          );
          return {
            requestId: payload.request_id,
            status: payload.status,
            message: payload.message,
            referenceName: payload.panel?.referenceName ?? null,
            objectId: payload.cad_result?.object_id ?? null,
            errorCode: payload.error_code ?? null,
          };
        },
      },
      { signal: lifecycle.signal },
    )).catch(reportError);
  } catch (error) {
    reportError(error);
  }

  window.addEventListener(
    "beforeunload",
    () => lifecycle.abort(),
    { once: true },
  );
}

exampleButtons.forEach((button) => {
  button.addEventListener("click", () => {
    resetSession();
    input.value = button.dataset.example;
    setCharacterCount();
    input.focus();
  });
});

input.addEventListener("input", setCharacterCount);
form.addEventListener("submit", submitRequest);
resetButton.addEventListener("click", resetSession);
newSessionButton.addEventListener("click", resetSession);

setCharacterCount();
checkHealth();
registerWebMcpTool();
