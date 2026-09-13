from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ObjectType = Literal["panel", "stiffener", "bracket", "opening"]
RepairOperation = Literal[
    "recompute", "update_panel", "manual_boundary_reselection", "report_provider_issue"
]
RepairRoute = Literal[
    "auto_execute", "confirm_then_execute", "manual", "provider_issue"
]
DecisionSource = Literal["policy", "llm", "fallback", "safety_override"]
GovernanceMode = Literal["analyze_only", "execute_allowed"]
LowRiskPolicy = Literal["allow_auto_execute", "require_confirmation"]
WorkflowNextStep = Literal[
    "report_only", "request_confirmation", "repair_safety_gate"
]


class ErrorDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")

    missing_boundary_count: int | None = Field(default=None, ge=1)
    changed_dependency_property: Literal[
        "panel_normal", "stiffener_mount_face"
    ] | None = None
    diagnostic_id: str | None = None


class RawErrorObject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object_id: str
    object_type: ObjectType
    parent_id: str | None = None
    error_code: str
    details: ErrorDetails | None = None


class ErrorObject(RawErrorObject):
    is_root: bool = False


class ProjectChangeEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    event_type: Literal["boundary_schema_upgrade"]
    source_schema_version: str
    target_schema_version: str
    migration_batch_id: str


class ProviderDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object_id: str
    operation: RepairOperation
    provider_validation: Literal["passed", "failed", "not_run"]
    candidate_object_ids: list[str] = Field(default_factory=list)
    changes_design_intent: bool


class RepairCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    operation: RepairOperation
    provider_validation: Literal["passed", "failed", "not_run"]
    ambiguity_count: int = Field(ge=0)
    changes_design_intent: bool
    candidate_object_ids: list[str] = Field(default_factory=list)
    migration_batch_id: str | None = None
    source_schema_version: str | None = None
    target_schema_version: str | None = None


class GovernanceIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: GovernanceMode
    low_risk_policy: LowRiskPolicy


class RepairRouteDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group_id: str
    route: RepairRoute
    candidate_id: str | None = None
    reason_code: str
    observation: str = Field(min_length=1)
    evidence: list[str] = Field(default_factory=list, max_length=5)
    requires_confirmation: bool


class RepairDecisionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence: int = Field(ge=1)
    source: DecisionSource
    decision: RepairRouteDecision


class RepairPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    expected_project_revision: str
    intent: GovernanceIntent
    decisions: list[RepairRouteDecision] = Field(min_length=1)


class RepairAuthorization(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group_id: str
    authorized: bool
    reason_code: str
    checked_project_revision: str


class ErrorGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group_id: str
    title: str
    root_cause_code: str
    root_object_ids: list[str] = Field(min_length=1)
    objects: list[ErrorObject] = Field(min_length=1)
    evidence: list[str]
    allowed_routes: list[RepairRoute] = Field(min_length=1)
    route: RepairRoute
    decision_source: DecisionSource = "policy"
    decision_reason_code: str
    decision_observation: str
    requires_confirmation: bool = False
    candidate: RepairCandidate | None = None
    operation_id: str | None = None

    @model_validator(mode="after")
    def validate_roots(self) -> "ErrorGroup":
        object_ids = {item.object_id for item in self.objects}
        if not set(self.root_object_ids).issubset(object_ids):
            raise ValueError("根对象必须存在于错误对象列表")
        return self


class ModelErrorSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    project_name: str
    project_revision: str
    data_source: Literal["mock"] = "mock"
    change_events: list[ProjectChangeEvent] = Field(default_factory=list)
    errors: list[RawErrorObject] = Field(min_length=1)
    diagnostics: list[ProviderDiagnostic] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_snapshot_references(self) -> "ModelErrorSnapshot":
        error_ids = [item.object_id for item in self.errors]
        if len(error_ids) != len(set(error_ids)):
            raise ValueError("错误对象ID不能重复")
        unknown = {
            item.object_id for item in self.diagnostics
            if item.object_id not in set(error_ids)
        }
        if unknown:
            raise ValueError("诊断对象必须存在于错误快照")
        return self


class ErrorGovernanceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_errors: int = Field(ge=0)
    root_groups: int = Field(ge=0)
    cascade_errors: int = Field(ge=0)
    auto_recoverable: int = Field(ge=0)
    confirmation_required: int = Field(ge=0)
    manual_required: int = Field(ge=0)
    provider_issues: int = Field(ge=0)


class ErrorGovernanceReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    status: Literal["analyzed", "awaiting_confirmation", "completed"]
    project_id: str
    project_name: str
    project_revision: str
    data_source_label: Literal["Mock CAD Error Snapshot"] = "Mock CAD Error Snapshot"
    summary: ErrorGovernanceSummary
    intent: GovernanceIntent
    workflow_next_step: WorkflowNextStep
    groups: list[ErrorGroup]
    decision_history: list[RepairDecisionRecord] = Field(default_factory=list)
    confirmation_required_group_ids: list[str] = Field(default_factory=list)
    authorization_results: list[RepairAuthorization] = Field(default_factory=list)
    resolved_error_ids: list[str] = Field(default_factory=list)
    remaining_error_ids: list[str] = Field(default_factory=list)
    simulated: Literal[True] = True


class PanelUpdateRequestSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    panel_id: str
    operation: Literal["update_panel"] = "update_panel"
    migration_batch_id: str
    source_boundary_schema_version: str
    target_boundary_schema_version: str
    resolved_boundary_object_id: str
    expected_project_revision: str


class PanelOperationDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_id: str
    task_id: str
    group_id: str
    panel_id: str
    status: Literal["planned", "simulated_completed"]
    readonly: Literal[True] = True
    simulated: Literal[True] = True
    decision_summary: str
    evidence: list[str]
    safety_checks: list[str]
    request: PanelUpdateRequestSnapshot
