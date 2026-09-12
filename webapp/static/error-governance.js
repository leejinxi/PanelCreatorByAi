(() => {
  const panel = document.querySelector("#panel-tab");
  const errors = document.querySelector("#model-errors-tab");
  const analyze = document.querySelector("#analyze-errors");
  const repair = document.querySelector("#repair-errors");
  const metrics = document.querySelector("#error-metrics");
  const groups = document.querySelector("#error-groups");
  const meta = document.querySelector("#error-task-meta");
  const closure = document.querySelector("#error-closure");
  const closureContent = document.querySelector("#closure-content");
  const governanceSteps = [...document.querySelectorAll("[data-governance-step]")];
  const operationDetail = document.querySelector("#operation-detail");
  const operationFields = document.querySelector("#operation-detail-fields");
  const operationEvidence = document.querySelector("#operation-detail-evidence");
  const operationRequest = document.querySelector("#operation-request-json");
  const backToErrors = document.querySelector("#back-to-errors");
  const scenarioDialog = document.querySelector("#mock-scenario-dialog");
  const showScenario = document.querySelector("#show-mock-scenario");
  const closeScenario = document.querySelector("#close-mock-scenario");
  const startFromScenario = document.querySelector("#start-analysis-from-scenario");
  const automationContext = document.querySelector("#automation-context");
  const automationTargets = document.querySelector("#automation-targets");
  const backFromAutomation = document.querySelector("#back-from-automation");
  const initialHash = location.hash;
  let report = null;
  let activeOperationTaskId = null;

  function activate(name, hash = null) {
    panel.hidden = name !== "panel";
    errors.hidden = name !== "model-errors";
    const operationView = name === "panel" && Boolean(hash?.includes("operationId="));
    const automationView = name === "panel" && Boolean(hash?.includes("mode=auto-update"));
    panel.classList.toggle("operation-view", operationView);
    panel.classList.toggle("automation-view", automationView);
    if (!operationView) operationDetail.hidden = true;
    automationContext.hidden = !automationView;
    history.replaceState(null, "", hash || (name === "model-errors" ? "#/model-errors" : "#/panel"));
  }
  const initialPanelView = initialHash.includes("operationId=") || initialHash.includes("mode=auto-update");
  activate(
    initialPanelView ? "panel" : "model-errors",
    initialPanelView ? initialHash : null,
  );

  showScenario.addEventListener("click", () => scenarioDialog.showModal());
  closeScenario.addEventListener("click", () => scenarioDialog.close());
  scenarioDialog.addEventListener("click", event => {
    if (event.target === scenarioDialog) scenarioDialog.close();
  });
  startFromScenario.addEventListener("click", () => {
    scenarioDialog.close();
    analyze.click();
  });

  function setGovernanceProgress(lastSuccess, running = null) {
    governanceSteps.forEach((step, index) => {
      step.classList.remove("running", "success");
      if (index <= lastSuccess) step.classList.add("success");
      if (index === running) step.classList.add("running");
    });
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, character => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[character]);
  }

  async function fetchJson(url, options = {}) {
    const response = await fetch(url, options);
    const payload = await response.json().catch(() => null);
    if (!response.ok) {
      const detail = typeof payload?.detail === "string" ? payload.detail : `请求失败 (${response.status})`;
      throw new Error(detail);
    }
    return payload;
  }

  const routeLabel = {
    auto_execute: "自动重算",
    confirm_then_execute: "确认后更新",
    manual: "人工处理",
    provider_issue: "Provider异常"
  };

  function render(data) {
    report = data;
    meta.textContent = `${data.task_id} · ${data.project_name} · ${data.project_revision} · Mock CAD Error Snapshot`;
    const s = data.summary;
    const cards = [
      ["错误节点", s.total_errors], ["主要问题", s.root_groups], ["关联错误", s.cascade_errors],
      ["可自动恢复", s.auto_recoverable], ["确认后恢复", s.confirmation_required],
      ["人工处理", s.manual_required], ["Provider异常", s.provider_issues]
    ];
    metrics.innerHTML = cards.map(([label, value]) => `<div><small>${escapeHtml(label)}</small><strong>${value}</strong></div>`).join("");
    groups.innerHTML = data.groups.map(group => {
      const roots = group.root_object_ids.map(escapeHtml).join("、");
      const cascade = group.objects.length - group.root_object_ids.length;
      const panelRoot = group.objects.find(item => item.object_type === "panel" && item.is_root);
      const detail = panelRoot && group.candidate?.operation === "update_panel"
        ? `<button class="detail-link" data-operation="${escapeHtml(group.operation_id)}">查看板架更新方案</button>` : "";
      const automation = group.candidate?.operation === "recompute"
        ? `<button class="detail-link automation-link" data-group="${escapeHtml(group.group_id)}">板架自动更新说明</button>` : "";
      return `<article class="error-group route-${group.route}">
        <header><span>${escapeHtml(group.group_id)}</span><b>${routeLabel[group.route]}</b></header>
        <h3>${escapeHtml(group.title)}</h3><p>${escapeHtml(group.root_cause_code)}</p>
        <dl><div><dt>根对象</dt><dd>${roots}</dd></div><div><dt>影响对象</dt><dd>${group.objects.length}</dd></div><div><dt>级联错误</dt><dd>${cascade}</dd></div></dl>
        <ul>${group.evidence.map(item => `<li>${escapeHtml(item)}</li>`).join("")}</ul><div class="group-actions">${detail}${automation}</div></article>`;
    }).join("");
    document.querySelectorAll(".detail-link").forEach(button => button.addEventListener("click", () => {
      if (button.classList.contains("automation-link")) return;
      void showOperation(button.dataset.operation, data.task_id).catch(error => {
        meta.textContent = `操作记录读取失败：${error.message}`;
      });
    }));
    document.querySelectorAll(".automation-link").forEach(button => button.addEventListener("click", () => {
      void showAutomation(data.task_id, button.dataset.group).catch(error => {
        meta.textContent = `自动更新说明读取失败：${error.message}`;
      });
    }));
    setGovernanceProgress(data.status === "completed" ? 4 : 2);
    repair.disabled = data.status === "completed";
    if (data.status === "completed") {
      closure.hidden = false;
      closureContent.innerHTML = `<strong>处理前 ${s.total_errors} 个错误，恢复 ${data.resolved_error_ids.length} 个，剩余 ${data.remaining_error_ids.length} 个。</strong><p>剩余工作：人工重选6个肘板边界并预览形体；提交4个几何内核异常对象。</p>`;
    }
  }

  async function showOperation(operationId, taskId) {
    const detail = await fetchJson(`/api/operations/${encodeURIComponent(operationId)}`);
    activeOperationTaskId = detail.task_id;
    activate("panel", `#/panel?operationId=${encodeURIComponent(operationId)}&taskId=${encodeURIComponent(taskId)}`);
    operationDetail.hidden = false;
    document.querySelector("#request-id").textContent = detail.operation_id;
    operationFields.innerHTML = [
      ["板架对象", detail.panel_id], ["治理任务", detail.task_id],
      ["问题组", detail.group_id], ["执行状态", detail.status === "planned" ? "待确认（Mock）" : "模拟执行完成"],
      ["访问模式", "只读审计记录"], ["CAD影响", "仅Mock，不修改真实工程"]
    ].map(([label, value]) => `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>`).join("");
    operationEvidence.innerHTML = [detail.decision_summary, ...detail.evidence, ...detail.safety_checks]
      .map(item => `<li>${escapeHtml(item)}</li>`).join("");
    operationRequest.textContent = JSON.stringify(detail.request, null, 2);
    operationDetail.scrollIntoView({behavior: "smooth", block: "start"});
  }

  async function showAutomation(taskId, groupId) {
    const source = report?.task_id === taskId
      ? report
      : await fetchJson(`/api/model-errors/status/${encodeURIComponent(taskId)}`);
    const group = source.groups.find(item => item.group_id === groupId);
    if (!group) throw new Error("错误组不存在");
    activeOperationTaskId = taskId;
    automationTargets.textContent = `${group.root_object_ids.join("、")} · ${group.objects.length}个关联错误`;
    activate("panel", `#/panel?mode=auto-update&taskId=${encodeURIComponent(taskId)}&groupId=${encodeURIComponent(groupId)}`);
    window.scrollTo({top: 0, behavior: "smooth"});
  }

  async function returnToGovernance() {
    const taskHash = activeOperationTaskId
      ? `#/model-errors?taskId=${encodeURIComponent(activeOperationTaskId)}`
      : "#/model-errors";
    activate("model-errors", taskHash);
    if (activeOperationTaskId) {
      try { render(await fetchJson(`/api/model-errors/status/${encodeURIComponent(activeOperationTaskId)}`)); }
      catch (error) { meta.textContent = `治理任务读取失败：${error.message}`; }
    }
  }

  backToErrors.addEventListener("click", async () => {
    operationDetail.hidden = true;
    await returnToGovernance();
  });
  backFromAutomation.addEventListener("click", returnToGovernance);

  analyze.addEventListener("click", async () => {
    analyze.disabled = true; meta.textContent = "正在读取Mock CAD错误快照…";
    setGovernanceProgress(-1, 0);
    try { render(await fetchJson("/api/model-errors/analyze", {method: "POST"})); }
    catch (error) { meta.textContent = `分析失败：${error.message}`; setGovernanceProgress(-1); }
    finally { analyze.disabled = false; }
  });
  repair.addEventListener("click", async () => {
    if (!report) return; repair.disabled = true; setGovernanceProgress(2, 3);
    try { render(await fetchJson(`/api/model-errors/repair/${report.task_id}`, {method: "POST"})); }
    catch (error) { meta.textContent = `修复编排失败：${error.message}`; repair.disabled = false; setGovernanceProgress(2); }
  });

  const initialQuery = initialHash.split("?", 2)[1];
  if (initialQuery) {
    const params = new URLSearchParams(initialQuery);
    const operationId = params.get("operationId");
    const taskId = params.get("taskId");
    const groupId = params.get("groupId");
    if (operationId && taskId) {
      void showOperation(operationId, taskId).catch(() => {
        operationDetail.hidden = true;
      });
    } else if (initialHash.includes("mode=auto-update") && taskId && groupId) {
      void showAutomation(taskId, groupId).catch(() => {
        activate("model-errors");
      });
    } else if (initialHash.includes("model-errors") && taskId) {
      void fetchJson(`/api/model-errors/status/${encodeURIComponent(taskId)}`)
        .then(render)
        .catch(error => { meta.textContent = `治理任务读取失败：${error.message}`; });
    }
  }
})();
