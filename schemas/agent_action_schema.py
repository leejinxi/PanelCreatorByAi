from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from schemas.boundary_schema import BoundaryConstraint


class PanelCandidate(BaseModel):
    """LLM 提取的候选板架参数；允许必填业务字段暂时缺失。"""

    model_config = ConfigDict(extra="forbid")

    type: Literal["panel"] = "panel"
    reference_plane: str | None = None
    boundaries: list[BoundaryConstraint] = Field(default_factory=list)
    thickness: float | None = Field(default=None, allow_inf_nan=False)
    material: str | None = None


class AgentActionPlan(BaseModel):
    """本地模型不支持原生 tool_calls 时使用的结构化动作计划。"""

    model_config = ConfigDict(extra="forbid")

    action: Literal["create_panel", "unsupported"]
    panel: PanelCandidate | None = None

    @model_validator(mode="after")
    def validate_action_payload(self) -> "AgentActionPlan":
        if self.action == "create_panel" and self.panel is None:
            raise ValueError("create_panel 动作必须包含 panel 参数")
        if self.action == "unsupported" and self.panel is not None:
            raise ValueError("unsupported 动作不能包含 panel 参数")
        return self
