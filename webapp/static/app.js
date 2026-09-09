"use strict";

const form = document.querySelector("#request-form");
const input = document.querySelector("#request-input");
const submitButton = document.querySelector("#submit-button");
const submitLabel = submitButton.querySelector(".button-label");
const resetButton = document.querySelector("#reset-button");
const newSessionButton = document.querySelector("#new-session-button");
const sessionNote = document.querySelector("#session-note");
const inputError = document.querySelector("#input-error");
const characterCount = document.querySelector("#character-count");
const requestId = document.querySelector("#request-id");
const agentStatus = document.querySelector("#agent-status");
const cadStatus = document.querySelector("#cad-status");
const parameterState = document.querySelector("#parameter-state");
const jsonDetails = document.querySelector("#json-details");
const jsonOutput = document.querySelector("#json-output");

const parameterFields = {
  referenceName: document.querySelector("#reference-name"),
  thicknessMm: document.querySelector("#thickness"),
  material: document.querySelector("#material"),
  top: document.querySelector("#boundary-top"),
  bottom: document.querySelector("#boundary-bottom"),
  left: document.querySelector("#boundary-left"),
  right: document.querySelector("#boundary-right"),
  diagramReference: document.querySelector("#diagram-reference"),
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

const stepOrder = ["parse", "validate", "cad"];
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

function renderPanel(panel) {
  const boundaries = panel?.boundaries ?? {};
  const referenceName = displayValue(panel?.referenceName);

  parameterFields.referenceName.textContent = referenceName;
  parameterFields.thicknessMm.textContent = displayValue(panel?.thicknessMm);
  parameterFields.material.textContent = displayValue(panel?.material);
  parameterFields.top.textContent = displayValue(boundaries.top, "未指定");
  parameterFields.bottom.textContent = displayValue(boundaries.bottom, "未指定");
  parameterFields.left.textContent = displayValue(boundaries.left, "未指定");
  parameterFields.right.textContent = displayValue(boundaries.right, "未指定");
  parameterFields.diagramReference.textContent = `REFERENCE ${referenceName}`;
  parameterState.textContent = panel ? "已提取" : "等待解析";
}

function renderResult(payload) {
  renderExecutionMode(payload.mode);
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
  renderPanel(payload.panel);

  jsonOutput.textContent = JSON.stringify(payload, null, 2);
  jsonDetails.hidden = false;
  jsonDetails.open = false;

  awaitingClarification = payload.status === "clarification";
  sessionNote.hidden = !awaitingClarification;
  input.placeholder = awaitingClarification
    ? "请补充缺少的信息，例如：材料为 AH36"
    : "例如：请在第100肋位创建一块14mm厚的AH36板架";
  submitLabel.textContent = awaitingClarification ? "提交补充信息" : "解析并创建";
}

function renderNetworkError(message) {
  renderSteps([
    { name: "parse", status: "error" },
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
  const label = { mock: "Direct Mock CAD", mcp: "MCP Contract Mock" }[mode];
  cadStatus.classList.remove("online", "offline");
  cadStatus.lastChild.textContent = label || "后端配置未确认";
  document.querySelector("#execution-mode").textContent = label
    ? `${label} · CAD execution is simulated`
    : "后端配置未确认";
  document.querySelector("#backend-step-label").textContent = label || "等待确认后端";
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
  resultElements.container.className = "execution-result neutral";
  resultElements.kicker.textContent = "正在执行";
  resultElements.message.textContent = "Agent 正在理解需求并整理 CAD 参数…";
  resultElements.meta.textContent = "请稍候，不要重复提交。";

  try {
    const response = await fetch("/api/agent/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ message: buildAccumulatedRequest(userTurns) }),
    });
    const payload = await response.json();

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
    renderNetworkError(error instanceof Error ? error.message : "无法连接本地 Agent 服务。");
    throw error;
  } finally {
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
  userTurns = [];
  awaitingClarification = false;
  input.value = "";
  input.disabled = false;
  input.placeholder = "例如：请在第100肋位创建一块14mm厚的AH36板架";
  inputError.textContent = "";
  sessionNote.hidden = true;
  submitLabel.textContent = "解析并创建";
  requestId.textContent = "REQUEST —";
  parameterState.textContent = "等待解析";
  jsonDetails.hidden = true;
  renderPanel(null);
  renderSteps([]);
  resultElements.container.className = "execution-result neutral";
  resultElements.icon.textContent = "·";
  resultElements.kicker.textContent = "等待任务";
  resultElements.message.textContent = "输入板架需求后，执行结果将在这里显示。";
  resultElements.meta.textContent = "Mock CAD 不会修改真实工程。";
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
              description: "包含定位面、厚度和材料的板架创建需求。",
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

document.querySelectorAll("[data-example]").forEach((button) => {
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
