"""Deterministic pre-creation review for the panel Demo."""

import json
from pathlib import Path

from pydantic import ValidationError

from schemas.design_review_schema import (
    DemoPanelContextCatalog,
    DemoReviewRule,
    DemoReviewRuleset,
    DesignReviewItem,
    DesignReviewReport,
    NearbyPanelSnapshot,
    PlanRevision,
)
from schemas.panel_schema import PanelRequest
from schemas.project_context_schema import ProjectInspectionResult


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTEXT_PATH = PROJECT_ROOT / "mock_data" / "demo_panel_context.json"
DEFAULT_RULES_PATH = PROJECT_ROOT / "mock_data" / "demo_panel_review_rules.json"
REQUIRED_RULE_IDS = tuple(f"PANEL-DEMO-{number:03d}" for number in range(1, 9))


class DesignReviewError(RuntimeError):
    def __init__(self, message: str, *, error_code: str) -> None:
        super().__init__(message)
        self.error_code = error_code


def load_panel_context(
    path: Path | None = None,
) -> DemoPanelContextCatalog:
    return _load_json_model(
        path or DEFAULT_CONTEXT_PATH,
        DemoPanelContextCatalog,
        label="Mock 板架上下文",
    )


def load_review_rules(
    path: Path | None = None,
) -> DemoReviewRuleset:
    ruleset = _load_json_model(
        path or DEFAULT_RULES_PATH,
        DemoReviewRuleset,
        label="Demo 评审规则",
    )
    actual_ids = {rule.rule_id for rule in ruleset.rules}
    missing = [rule_id for rule_id in REQUIRED_RULE_IDS if rule_id not in actual_ids]
    if missing:
        raise DesignReviewError(
            f"Demo 评审规则缺少必需项：{'、'.join(missing)}。",
            error_code="DESIGN_REVIEW_RULESET_INVALID",
        )
    return ruleset


def review_panel_design(
    request: PanelRequest,
    inspection: ProjectInspectionResult,
    *,
    context_path: Path | None = None,
    rules_path: Path | None = None,
) -> DesignReviewReport:
    """Run bounded Demo checks without mutating the validated request."""

    context = load_panel_context(context_path)
    ruleset = load_review_rules(rules_path)
    if context.project_id != inspection.project_id:
        raise DesignReviewError(
            "Mock 板架上下文与工程目录不属于同一工程。",
            error_code="DESIGN_REVIEW_PROJECT_MISMATCH",
        )
    if context.revision != inspection.revision:
        raise DesignReviewError(
            "Mock 板架上下文与工程目录版本不一致。",
            error_code="DESIGN_REVIEW_REVISION_MISMATCH",
        )

    rules = {rule.rule_id: rule for rule in ruleset.rules}
    nearby_panels = _nearby_panels(context, inspection)
    items = [
        _item(
            rules["PANEL-DEMO-001"],
            status="passed",
            summary="请求已通过 PanelRequest 强类型校验。",
            evidence=[
                f"reference={request.reference_plane}",
                f"boundary_count={len(request.boundaries)}",
            ],
            data_source="validated_request",
        ),
        _object_resolution_item(rules["PANEL-DEMO-002"], inspection),
        _same_object_item(rules["PANEL-DEMO-003"], inspection),
        _thickness_item(rules["PANEL-DEMO-004"], request, nearby_panels),
        _material_item(rules["PANEL-DEMO-005"], request, nearby_panels),
        _not_checked_item(
            rules["PANEL-DEMO-006"],
            "未接入 CCS 规范检索与条款适用性校核。",
        ),
        _not_checked_item(
            rules["PANEL-DEMO-007"],
            "未接入结构强度计算工具。",
        ),
        _not_checked_item(
            rules["PANEL-DEMO-008"],
            "未连接真实 CAD，未执行几何与碰撞检查。",
        ),
    ]

    blockers = [item.rule_id for item in items if item.status == "blocked"]
    warnings = [item.rule_id for item in items if item.status == "warning"]
    if blockers:
        outcome = "blocked"
        plan_revision = PlanRevision(
            changed=True,
            disposition="stopped",
            original_plan=["查询工程对象", "准备创建板架"],
            revised_plan=["查询工程对象", "执行创建前评审", "停止创建"],
            trigger_rule_ids=blockers,
            summary="创建前评审发现阻断项，Agent 已将计划调整为停止创建。",
        )
    elif warnings:
        outcome = "passed_with_warnings"
        plan_revision = PlanRevision(
            changed=True,
            disposition="proceed_with_notice",
            original_plan=["查询工程对象", "准备创建板架"],
            revised_plan=["查询工程对象", "执行创建前评审", "保留用户参数并携带提醒创建"],
            trigger_rule_ids=warnings,
            summary="Agent 保留用户明确参数，并在携带设计差异提醒后继续模拟创建。",
        )
    else:
        outcome = "passed"
        plan_revision = PlanRevision(
            changed=False,
            disposition="unchanged",
            original_plan=["查询工程对象", "准备创建板架"],
            revised_plan=["查询工程对象", "准备创建板架"],
            summary="未发现需要调整执行计划的已检查问题。",
        )

    return DesignReviewReport(
        ruleset_version=ruleset.version,
        project_revision=inspection.revision,
        outcome=outcome,
        items=items,
        nearby_panels=nearby_panels,
        plan_revision=plan_revision,
    )


def _load_json_model(path: Path, model: type, *, label: str):
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        return model.model_validate(data)
    except FileNotFoundError as exc:
        raise DesignReviewError(
            f"{label}文件不存在。",
            error_code="DESIGN_REVIEW_DATA_UNAVAILABLE",
        ) from exc
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise DesignReviewError(
            f"{label}无效。",
            error_code="DESIGN_REVIEW_DATA_INVALID",
        ) from exc


def _nearby_panels(
    context: DemoPanelContextCatalog,
    inspection: ProjectInspectionResult,
) -> list[NearbyPanelSnapshot]:
    resolved_name = inspection.reference_plane.resolved_name
    if resolved_name is None:
        return []
    for item in context.reference_contexts:
        if item.reference_name.casefold() == resolved_name.casefold():
            return list(item.nearby_panels)
    return []


def _object_resolution_item(
    rule: DemoReviewRule,
    inspection: ProjectInspectionResult,
) -> DesignReviewItem:
    matches = [inspection.reference_plane, *inspection.boundaries]
    if inspection.all_resolved():
        return _item(
            rule,
            status="passed",
            summary="定位面和全部边界均唯一匹配、可用且角色合法。",
            evidence=[f"resolved_count={len(matches)}"],
            data_source="mock_project_context",
        )
    problem = next(item for item in matches if item.status != "resolved")
    return _item(
        rule,
        status="blocked",
        summary=f"对象“{problem.query}”未达到可执行状态。",
        evidence=[f"status={problem.status}", f"role={problem.role}"],
        data_source="mock_project_context",
    )


def _same_object_item(
    rule: DemoReviewRule,
    inspection: ProjectInspectionResult,
) -> DesignReviewItem:
    reference_id = inspection.reference_plane.resolved_object_id
    duplicates = [
        item.query
        for item in inspection.boundaries
        if reference_id is not None and item.resolved_object_id == reference_id
    ]
    if duplicates:
        return _item(
            rule,
            status="blocked",
            summary="定位面与边界解析到了同一个 Mock 工程对象。",
            evidence=[f"reference_id={reference_id}", f"boundary={duplicates[0]}"],
            data_source="demo_rule",
        )
    return _item(
        rule,
        status="passed",
        summary="定位面与边界未解析到同一个 Mock 工程对象。",
        evidence=[],
        data_source="demo_rule",
    )


def _thickness_item(
    rule: DemoReviewRule,
    request: PanelRequest,
    nearby_panels: list[NearbyPanelSnapshot],
) -> DesignReviewItem:
    if not nearby_panels:
        return _item(
            rule,
            status="not_checked",
            summary="Mock 工程未提供该定位面的邻近板架样本。",
            evidence=[],
            data_source="mock_project_context",
        )
    values = sorted({item.thickness_mm for item in nearby_panels})
    differs = any(value != request.thickness for value in values)
    return _item(
        rule,
        status="warning" if differs else "passed",
        summary=(
            "用户板厚与部分显式邻近样本不同；Agent 保留用户指定值。"
            if differs else "用户板厚与全部显式邻近样本一致。"
        ),
        evidence=[
            f"requested={request.thickness:g}mm",
            "nearby=" + ",".join(f"{value:g}mm" for value in values),
        ],
        data_source="mock_project_context",
    )


def _material_item(
    rule: DemoReviewRule,
    request: PanelRequest,
    nearby_panels: list[NearbyPanelSnapshot],
) -> DesignReviewItem:
    if not nearby_panels:
        return _item(
            rule,
            status="not_checked",
            summary="Mock 工程未提供该定位面的邻近板架样本。",
            evidence=[],
            data_source="mock_project_context",
        )
    values = sorted({item.material for item in nearby_panels})
    differs = any(value.casefold() != request.material.casefold() for value in values)
    return _item(
        rule,
        status="warning" if differs else "passed",
        summary=(
            "用户材料与部分显式邻近样本不同；Agent 保留用户指定值。"
            if differs else "用户材料与全部显式邻近样本一致。"
        ),
        evidence=[f"requested={request.material}", "nearby=" + ",".join(values)],
        data_source="mock_project_context",
    )


def _not_checked_item(rule: DemoReviewRule, summary: str) -> DesignReviewItem:
    return _item(
        rule,
        status="not_checked",
        summary=summary,
        evidence=[],
        data_source="capability_boundary",
    )


def _item(
    rule: DemoReviewRule,
    *,
    status: str,
    summary: str,
    evidence: list[str],
    data_source: str,
) -> DesignReviewItem:
    return DesignReviewItem(
        rule_id=rule.rule_id,
        title=rule.title,
        status=status,
        summary=summary,
        evidence=evidence[:4],
        data_source=data_source,
    )
