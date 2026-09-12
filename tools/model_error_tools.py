import json
from collections import defaultdict
from pathlib import Path
from uuid import uuid4

from schemas.model_error_schema import (
    ErrorGovernanceReport,
    ErrorGovernanceSummary,
    ErrorGroup,
    ErrorObject,
    ModelErrorSnapshot,
    PanelOperationDetail,
    PanelUpdateRequestSnapshot,
    ProviderDiagnostic,
    RepairCandidate,
)


DATA_PATH = Path(__file__).resolve().parents[1] / "mock_data" / "demo_model_errors.json"

CAUSE_ORDER = (
    "PANEL_BOUNDARY_SCHEMA_MIGRATION_INCOMPLETE",
    "PANEL_RECOMPUTE_REQUIRED",
    "BRACKET_BOUNDARY_INVALID_AFTER_SUPPORT_UPDATE",
    "GEOMETRY_KERNEL_ERROR",
)
CAUSE_TITLES = {
    "PANEL_BOUNDARY_SCHEMA_MIGRATION_INCOMPLETE": "板架边界数据升级未完整迁移",
    "PANEL_RECOMPUTE_REQUIRED": "父板架需要重新计算",
    "BRACKET_BOUNDARY_INVALID_AFTER_SUPPORT_UPDATE": "肘板边界在关联更新后失效",
    "GEOMETRY_KERNEL_ERROR": "几何内核运行异常",
}
ROOT_ERROR_TO_CAUSE = {
    "BOUNDARY_DATA_MIGRATION_FAILED": "PANEL_BOUNDARY_SCHEMA_MIGRATION_INCOMPLETE",
    "RECOMPUTE_REQUIRED": "PANEL_RECOMPUTE_REQUIRED",
    "PANEL_NORMAL_CHANGED": "BRACKET_BOUNDARY_INVALID_AFTER_SUPPORT_UPDATE",
    "STIFFENER_MOUNT_FACE_CHANGED": "BRACKET_BOUNDARY_INVALID_AFTER_SUPPORT_UPDATE",
    "GEOMETRY_KERNEL_ERROR": "GEOMETRY_KERNEL_ERROR",
}


class ModelErrorProviderError(RuntimeError):
    pass


def load_model_error_snapshot(path: Path = DATA_PATH) -> ModelErrorSnapshot:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return ModelErrorSnapshot.model_validate(payload)
    except Exception as exc:
        raise ModelErrorProviderError("Mock CAD错误快照不可用。") from exc


def _find_error_root_id(object_id: str, errors_by_id: dict) -> str:
    current = errors_by_id[object_id]
    visited = {object_id}
    while current.parent_id in errors_by_id:
        if current.parent_id in visited:
            raise ModelErrorProviderError("Mock CAD错误关系存在循环引用。")
        visited.add(current.parent_id)
        current = errors_by_id[current.parent_id]
    return current.object_id


def _diagnostics_for_roots(
    root_ids: list[str], diagnostics: list[ProviderDiagnostic]
) -> list[ProviderDiagnostic]:
    by_id = {item.object_id: item for item in diagnostics}
    return [by_id[root_id] for root_id in root_ids if root_id in by_id]


def _candidate_for_group(
    group_id: str,
    cause: str,
    diagnostics: list[ProviderDiagnostic],
    snapshot: ModelErrorSnapshot,
) -> RepairCandidate | None:
    if not diagnostics:
        return None
    operations = {item.operation for item in diagnostics}
    if len(operations) != 1:
        raise ModelErrorProviderError("同一问题组包含互相冲突的修复操作。")
    validation = (
        "failed" if any(item.provider_validation == "failed" for item in diagnostics)
        else "passed" if all(item.provider_validation == "passed" for item in diagnostics)
        else "not_run"
    )
    candidate_object_ids = list(dict.fromkeys(
        object_id
        for item in diagnostics
        for object_id in item.candidate_object_ids
    ))
    migration = snapshot.change_events[0] if (
        cause == "PANEL_BOUNDARY_SCHEMA_MIGRATION_INCOMPLETE"
        and snapshot.change_events
    ) else None
    operation = diagnostics[0].operation
    return RepairCandidate(
        candidate_id=f"AGENT-{group_id}-{operation.upper()}",
        operation=operation,
        provider_validation=validation,
        ambiguity_count=max(
            (max(len(item.candidate_object_ids) - 1, 0) for item in diagnostics),
            default=0,
        ),
        changes_design_intent=any(item.changes_design_intent for item in diagnostics),
        candidate_object_ids=candidate_object_ids,
        migration_batch_id=migration.migration_batch_id if migration else None,
        source_schema_version=migration.source_schema_version if migration else None,
        target_schema_version=migration.target_schema_version if migration else None,
    )


def _route_for_group(cause: str, candidate: RepairCandidate | None) -> str:
    if cause == "GEOMETRY_KERNEL_ERROR":
        return "provider_issue"
    if candidate is None or candidate.provider_validation == "failed":
        return "provider_issue"
    if cause == "BRACKET_BOUNDARY_INVALID_AFTER_SUPPORT_UPDATE":
        return "manual"
    if (
        cause == "PANEL_RECOMPUTE_REQUIRED"
        and candidate.provider_validation == "passed"
        and not candidate.changes_design_intent
    ):
        return "auto_execute"
    if (
        cause == "PANEL_BOUNDARY_SCHEMA_MIGRATION_INCOMPLETE"
        and candidate.provider_validation == "passed"
        and candidate.ambiguity_count == 0
        and len(candidate.candidate_object_ids) == 1
        and not candidate.changes_design_intent
    ):
        return "confirm_then_execute"
    return "manual"


def _evidence_for_group(
    cause: str,
    objects: list[ErrorObject],
    candidate: RepairCandidate | None,
) -> list[str]:
    if cause == "PANEL_BOUNDARY_SCHEMA_MIGRATION_INCOMPLETE":
        missing = sum(
            item.details.missing_boundary_count
            for item in objects
            if item.details and item.details.missing_boundary_count
        )
        resolved = candidate.candidate_object_ids[0] if (
            candidate and len(candidate.candidate_object_ids) == 1
        ) else "无唯一候选"
        source_version = candidate.source_schema_version if candidate else "未知版本"
        target_version = candidate.target_schema_version if candidate else "未知版本"
        return [
            "CAD错误码：BOUNDARY_DATA_MIGRATION_FAILED",
            f"工程边界数据由{source_version}升级为{target_version}",
            f"主要错误板架有{missing}条旧边界未写入新版列表",
            f"CAD诊断候选：{resolved}",
        ]
    if cause == "PANEL_RECOMPUTE_REQUIRED":
        root_count = sum(item.is_root for item in objects)
        return [
            "CAD错误码：RECOMPUTE_REQUIRED",
            f"{root_count}个父板架共享同一低风险重算策略",
            f"Provider预校验：{candidate.provider_validation if candidate else '缺失'}",
        ]
    if cause == "BRACKET_BOUNDARY_INVALID_AFTER_SUPPORT_UPDATE":
        panel_normal = sum(item.error_code == "PANEL_NORMAL_CHANGED" for item in objects)
        mount_face = sum(item.error_code == "STIFFENER_MOUNT_FACE_CHANGED" for item in objects)
        return [
            f"{panel_normal}个肘板依赖的板架正方向发生变化",
            f"{mount_face}个肘板依赖的骨材安装面已变化",
            "CAD无法安全沿用原肘板边界",
            "需要设计人员重选边界并预览形体",
        ]
    return [
        f"{len(objects)}个对象报告GEOMETRY_KERNEL_ERROR",
        "CAD未返回可验证修复候选",
        "保留对象、诊断编号和工程版本用于研发排查",
    ]


def group_model_errors(snapshot: ModelErrorSnapshot) -> list[ErrorGroup]:
    """从未分组CAD错误、父子关系和诊断候选生成问题组与处理路线。"""
    errors_by_id = {item.object_id: item for item in snapshot.errors}
    root_for_error = {
        item.object_id: _find_error_root_id(item.object_id, errors_by_id)
        for item in snapshot.errors
    }
    roots_by_cause: dict[str, list[str]] = defaultdict(list)
    for root_id in dict.fromkeys(root_for_error.values()):
        root = errors_by_id[root_id]
        cause = ROOT_ERROR_TO_CAUSE.get(root.error_code)
        if cause is None:
            raise ModelErrorProviderError(f"无法归类错误对象：{root_id}")
        roots_by_cause[cause].append(root_id)

    groups: list[ErrorGroup] = []
    for index, cause in enumerate(CAUSE_ORDER):
        root_ids = roots_by_cause.get(cause, [])
        if not root_ids:
            continue
        group_id = f"GROUP-{chr(ord('A') + index)}"
        root_id_set = set(root_ids)
        objects = [
            ErrorObject(**item.model_dump(), is_root=item.object_id in root_id_set)
            for item in snapshot.errors
            if root_for_error[item.object_id] in root_id_set
        ]
        diagnostics = _diagnostics_for_roots(root_ids, snapshot.diagnostics)
        candidate = _candidate_for_group(group_id, cause, diagnostics, snapshot)
        operation_id = None
        if candidate and candidate.operation == "update_panel" and len(root_ids) == 1:
            suffix = root_ids[0].removeprefix("PANEL-FR")
            operation_id = f"OP-REPAIR-{suffix}-01"
        groups.append(ErrorGroup(
            group_id=group_id,
            title=CAUSE_TITLES[cause],
            root_cause_code=cause,
            root_object_ids=root_ids,
            objects=objects,
            evidence=_evidence_for_group(cause, objects, candidate),
            route=_route_for_group(cause, candidate),
            candidate=candidate,
            operation_id=operation_id,
        ))
    return groups


def analyze_model_errors() -> ErrorGovernanceReport:
    snapshot = load_model_error_snapshot()
    groups = group_model_errors(snapshot)
    errors = snapshot.errors
    roots = {root_id for group in groups for root_id in group.root_object_ids}
    by_route = {
        route: sum(len(group.objects) for group in groups if group.route == route)
        for route in ("auto_execute", "confirm_then_execute", "manual", "provider_issue")
    }
    return ErrorGovernanceReport(
        task_id=f"ERROR-GOV-{uuid4().hex[:8].upper()}",
        status="analyzed",
        project_id=snapshot.project_id,
        project_name=snapshot.project_name,
        project_revision=snapshot.project_revision,
        summary=ErrorGovernanceSummary(
            total_errors=len(errors),
            root_groups=len(groups),
            cascade_errors=len(errors) - len(roots),
            auto_recoverable=by_route["auto_execute"],
            confirmation_required=by_route["confirm_then_execute"],
            manual_required=by_route["manual"],
            provider_issues=by_route["provider_issue"],
        ),
        groups=groups,
        remaining_error_ids=[item.object_id for item in errors],
    )


def execute_safe_repairs(report: ErrorGovernanceReport) -> ErrorGovernanceReport:
    resolved = [
        item.object_id
        for group in report.groups
        if group.route in {"auto_execute", "confirm_then_execute"}
        for item in group.objects
    ]
    remaining = [
        item.object_id
        for group in report.groups
        if group.route in {"manual", "provider_issue"}
        for item in group.objects
    ]
    return report.model_copy(update={
        "status": "completed",
        "resolved_error_ids": resolved,
        "remaining_error_ids": remaining,
    })


def build_panel_operation_details(
    report: ErrorGovernanceReport,
) -> list[PanelOperationDetail]:
    """为错误治理中的板架更新生成不可执行的只读审计快照。"""
    details: list[PanelOperationDetail] = []
    for group in report.groups:
        candidate = group.candidate
        if not group.operation_id or candidate is None or candidate.operation != "update_panel":
            continue
        if not (
            candidate.migration_batch_id
            and candidate.source_schema_version
            and candidate.target_schema_version
            and len(candidate.candidate_object_ids) == 1
        ):
            raise ModelErrorProviderError("板架更新候选缺少迁移或唯一边界信息。")
        panel_id = next(
            item.object_id
            for item in group.objects
            if item.object_type == "panel" and item.is_root
        )
        details.append(PanelOperationDetail(
            operation_id=group.operation_id,
            task_id=report.task_id,
            group_id=group.group_id,
            panel_id=panel_id,
            status=("simulated_completed" if report.status == "completed" else "planned"),
            decision_summary=(
                "Agent沿错误依赖关系找到主要错误板架；CAD诊断返回唯一恢复对象，"
                "因此生成更新现有板架并关联重算子构件的确认方案。"
            ),
            evidence=group.evidence,
            safety_checks=[
                "目标板架ID由Agent沿CAD错误父子关系确定",
                "旧边界到新版边界对象的映射唯一",
                "目标边界列表满足0.2-poc结构约束",
                "Provider预校验通过",
                "本页面只读，不会再次触发CAD调用",
            ],
            request=PanelUpdateRequestSnapshot(
                panel_id=panel_id,
                migration_batch_id=candidate.migration_batch_id,
                source_boundary_schema_version=candidate.source_schema_version,
                target_boundary_schema_version=candidate.target_schema_version,
                resolved_boundary_object_id=candidate.candidate_object_ids[0],
                expected_project_revision=report.project_revision,
            ),
        ))
    return details
