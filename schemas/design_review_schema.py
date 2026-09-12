"""Strongly typed results for the deterministic Demo panel review."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ReviewStatus = Literal["passed", "warning", "blocked", "not_checked"]
ReviewOutcome = Literal["passed", "passed_with_warnings", "blocked"]
PlanDisposition = Literal["unchanged", "proceed_with_notice", "stopped"]
ReviewDataSource = Literal[
    "validated_request",
    "mock_project_context",
    "demo_rule",
    "capability_boundary",
]


class NearbyPanelSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    panel_id: str
    name: str
    reference_name: str
    thickness_mm: float = Field(gt=0, allow_inf_nan=False)
    material: str
    approval_state: Literal["demo_approved_sample"] = "demo_approved_sample"

    @field_validator("panel_id", "name", "reference_name", "material")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("字段不能为空")
        return normalized


class ReferencePanelContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference_name: str
    nearby_panels: list[NearbyPanelSnapshot] = Field(default_factory=list)

    @field_validator("reference_name")
    @classmethod
    def normalize_reference_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("定位面名称不能为空")
        return normalized


class DemoPanelContextCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    revision: str
    data_source: Literal["mock"] = "mock"
    reference_contexts: list[ReferencePanelContext] = Field(default_factory=list)

    @field_validator("project_id", "revision")
    @classmethod
    def normalize_catalog_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("字段不能为空")
        return normalized

    @model_validator(mode="after")
    def validate_unique_contexts(self) -> "DemoPanelContextCatalog":
        names = [item.reference_name.casefold() for item in self.reference_contexts]
        if len(names) != len(set(names)):
            raise ValueError("定位面上下文必须唯一")
        return self


class DemoReviewRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str
    title: str
    severity: Literal["info", "warning", "blocker"]
    description: str

    @field_validator("rule_id", "title", "description")
    @classmethod
    def normalize_rule_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("规则字段不能为空")
        return normalized


class DemoReviewRuleset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    data_source: Literal["demo_rule"] = "demo_rule"
    rules: list[DemoReviewRule] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_rules(self) -> "DemoReviewRuleset":
        ids = [item.rule_id for item in self.rules]
        if len(ids) != len(set(ids)):
            raise ValueError("评审规则 ID 必须唯一")
        return self


class DesignReviewItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str
    title: str
    status: ReviewStatus
    summary: str
    evidence: list[str] = Field(default_factory=list, max_length=4)
    data_source: ReviewDataSource

    @field_validator("rule_id", "title", "summary")
    @classmethod
    def normalize_review_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("评审字段不能为空")
        return normalized


class PlanRevision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    changed: bool
    disposition: PlanDisposition
    original_plan: list[str] = Field(min_length=1, max_length=4)
    revised_plan: list[str] = Field(min_length=1, max_length=5)
    trigger_rule_ids: list[str] = Field(default_factory=list)
    summary: str

    @model_validator(mode="after")
    def validate_change_state(self) -> "PlanRevision":
        if self.changed and not self.trigger_rule_ids:
            raise ValueError("计划发生变化时必须包含触发规则")
        if not self.changed and self.trigger_rule_ids:
            raise ValueError("计划未变化时不能包含触发规则")
        return self


class DesignReviewReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ruleset_version: str
    project_revision: str
    data_source: Literal["mock"] = "mock"
    outcome: ReviewOutcome
    items: list[DesignReviewItem] = Field(min_length=1)
    nearby_panels: list[NearbyPanelSnapshot] = Field(default_factory=list)
    plan_revision: PlanRevision

    def has_blocker(self) -> bool:
        return any(item.status == "blocked" for item in self.items)

    @model_validator(mode="after")
    def validate_outcome(self) -> "DesignReviewReport":
        has_blocker = self.has_blocker()
        has_warning = any(item.status == "warning" for item in self.items)
        expected: ReviewOutcome = (
            "blocked" if has_blocker
            else "passed_with_warnings" if has_warning
            else "passed"
        )
        if self.outcome != expected:
            raise ValueError("评审总体状态与检查项不一致")
        if has_blocker and self.plan_revision.disposition != "stopped":
            raise ValueError("存在阻断项时计划必须停止")
        return self
