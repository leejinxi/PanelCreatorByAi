from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ObjectType = Literal["panel", "stiffener", "bracket", "opening"]
RepairRoute = Literal[
    "auto_execute", "confirm_then_execute", "manual", "provider_issue"
]


class ErrorObject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object_id: str
    object_type: ObjectType
    parent_id: str | None = None
    error_code: str
    is_root: bool = False


class RepairCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    operation: Literal[
        "recompute", "update_panel", "manual_topology_selection", "report_provider_issue"
    ]
    provider_validation: Literal["passed", "failed", "not_run"]
    ambiguity_count: int = Field(ge=0)
    changes_design_intent: bool


class ErrorGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group_id: str
    title: str
    root_cause_code: str
    root_object_ids: list[str] = Field(min_length=1)
    objects: list[ErrorObject] = Field(min_length=1)
    evidence: list[str]
    route: RepairRoute
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
    groups: list[ErrorGroup]


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
    status: Literal["analyzed", "completed"]
    project_id: str
    project_name: str
    project_revision: str
    data_source_label: Literal["Mock CAD Error Snapshot"] = "Mock CAD Error Snapshot"
    summary: ErrorGovernanceSummary
    groups: list[ErrorGroup]
    resolved_error_ids: list[str] = Field(default_factory=list)
    remaining_error_ids: list[str] = Field(default_factory=list)


class PanelUpdateRequestSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    panel_id: str
    operation: Literal["update_panel"] = "update_panel"
    replacement_reference_id: str
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
