"""Boundary-list models shared by local validation and the 0.2-poc adapter."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from tools.ruler_plane_tools import normalize_ruler_plane_name


class BoundaryCandidate(BaseModel):
    """One source fragment, including incomplete or invalid user input."""

    model_config = ConfigDict(extra="forbid")

    raw: str
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    operator: str | None = None
    target: str | None = None


class BoundaryConstraint(BaseModel):
    """A syntactically valid expression, not proof of CAD object existence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operator: Literal["<", ">"]
    target: str

    @field_validator("target")
    @classmethod
    def normalize_target(cls, value: str) -> str:
        value = normalize_ruler_plane_name(value)
        if not value:
            raise ValueError("边界目标不能为空")
        return value


class BoundaryValidationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Literal[
        "BOUNDARY_OPERATOR_MISSING", "BOUNDARY_OPERATOR_INVALID",
        "BOUNDARY_TARGET_MISSING", "BOUNDARY_QUOTE_INVALID",
        "BOUNDARY_TARGET_INVALID", "BOUNDARY_COUNT_INSUFFICIENT",
        "BOUNDARY_EDIT_AMBIGUOUS",
    ]
    index: int | None = Field(default=None, ge=0)
    message: str


class ValidatedBoundaries(BaseModel):
    """Execution-side list for the next contract; never convert four directions."""

    model_config = ConfigDict(extra="forbid")

    boundaries: list[BoundaryConstraint] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_count(self) -> "ValidatedBoundaries":
        unique = list(dict.fromkeys(self.boundaries))
        if not unique:
            raise ValueError("至少需要1条有效边界")
        self.boundaries = unique
        return self


class BoundaryParseResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidates: list[BoundaryCandidate] = Field(default_factory=list)
    boundaries: list[BoundaryConstraint] = Field(default_factory=list)
    issues: list[BoundaryValidationIssue] = Field(default_factory=list)
    duplicate_indices: list[int] = Field(default_factory=list)

    def to_execution(self) -> ValidatedBoundaries:
        if self.issues:
            raise ValueError("边界输入仍有未解决的问题")
        return ValidatedBoundaries(boundaries=self.boundaries)
