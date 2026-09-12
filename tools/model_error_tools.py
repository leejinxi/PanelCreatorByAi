import json
from pathlib import Path
from uuid import uuid4

from schemas.model_error_schema import (
    ErrorGovernanceReport,
    ErrorGovernanceSummary,
    ModelErrorSnapshot,
    PanelOperationDetail,
    PanelUpdateRequestSnapshot,
)


DATA_PATH = Path(__file__).resolve().parents[1] / "mock_data" / "demo_model_errors.json"


class ModelErrorProviderError(RuntimeError):
    pass


def load_model_error_snapshot(path: Path = DATA_PATH) -> ModelErrorSnapshot:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return ModelErrorSnapshot.model_validate(payload)
    except Exception as exc:
        raise ModelErrorProviderError("Mock CAD错误快照不可用。") from exc


def analyze_model_errors() -> ErrorGovernanceReport:
    snapshot = load_model_error_snapshot()
    errors = [item for group in snapshot.groups for item in group.objects]
    roots = {item.object_id for group in snapshot.groups for item in group.objects if item.is_root}
    by_route = {
        route: sum(len(group.objects) for group in snapshot.groups if group.route == route)
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
            root_groups=len(snapshot.groups),
            cascade_errors=len(errors) - len(roots),
            auto_recoverable=by_route["auto_execute"],
            confirmation_required=by_route["confirm_then_execute"],
            manual_required=by_route["manual"],
            provider_issues=by_route["provider_issue"],
        ),
        groups=snapshot.groups,
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
        if not group.operation_id or group.candidate is None:
            continue
        if group.candidate.operation != "update_panel":
            continue
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
            status=(
                "simulated_completed" if report.status == "completed" else "planned"
            ),
            decision_summary=(
                "CAD返回唯一替换候选；该更新会改变引用关系，归入确认后执行。"
            ),
            evidence=group.evidence,
            safety_checks=[
                "目标板架ID来自CAD错误快照",
                "替换引用候选唯一",
                "Provider预校验通过",
                "本页面只读，不会再次触发CAD调用",
            ],
            request=PanelUpdateRequestSnapshot(
                panel_id=panel_id,
                replacement_reference_id="SHELL-PORT-REV2",
                expected_project_revision=report.project_revision,
            ),
        ))
    return details
