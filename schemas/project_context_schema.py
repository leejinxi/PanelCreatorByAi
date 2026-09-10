"""Schemas for the deterministic Demo project object catalog."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ObjectRole = Literal["reference_plane", "boundary"]
ObjectMatchStatus = Literal[
    "resolved",
    "not_found",
    "ambiguous",
    "unavailable",
    "not_eligible",
]


class DemoProjectObject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object_id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    object_type: Literal["ruler_plane", "surface", "coordinate_plane"]
    eligible_roles: list[ObjectRole] = Field(min_length=1)
    status: Literal["available", "unavailable"] = "available"

    @field_validator("object_id", "name")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("字段不能为空")
        return normalized

    @field_validator("aliases")
    @classmethod
    def normalize_aliases(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(value.strip() for value in values if value.strip()))


class DemoProjectCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1)
    project_name: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    data_source: Literal["mock"] = "mock"
    objects: list[DemoProjectObject] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_object_ids(self) -> "DemoProjectCatalog":
        object_ids = [item.object_id for item in self.objects]
        if len(object_ids) != len(set(object_ids)):
            raise ValueError("工程对象 ID 必须唯一")
        return self


class ObjectMatchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    role: ObjectRole
    status: ObjectMatchStatus
    resolved_object_id: str | None = None
    resolved_name: str | None = None
    candidates: list[str] = Field(default_factory=list)

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("查询名称不能为空")
        return normalized

    @model_validator(mode="after")
    def validate_status_payload(self) -> "ObjectMatchResult":
        if self.status == "resolved":
            if not self.resolved_object_id or not self.resolved_name:
                raise ValueError("resolved 状态必须包含唯一对象")
            if self.candidates:
                raise ValueError("resolved 状态不能包含候选项")
        else:
            if self.resolved_object_id is not None or self.resolved_name is not None:
                raise ValueError("非 resolved 状态不能包含唯一对象")
        if self.status == "ambiguous" and len(self.candidates) < 2:
            raise ValueError("ambiguous 状态必须至少包含两个候选项")
        if self.status == "not_found" and self.candidates:
            raise ValueError("not_found 状态不能包含候选项")
        return self


class ProjectInspectionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    project_name: str
    revision: str
    data_source: Literal["mock"] = "mock"
    reference_plane: ObjectMatchResult
    boundaries: list[ObjectMatchResult] = Field(min_length=1)

    def all_resolved(self) -> bool:
        return (
            self.reference_plane.status == "resolved"
            and all(item.status == "resolved" for item in self.boundaries)
        )
