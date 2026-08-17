from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PlaneByName(BaseModel):
    """用户通过工程标尺面名称进行定位。"""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["name"] = "name"
    name: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("定位面名称不能为空")
        return normalized


class PlaneByCoordinate(BaseModel):
    """用户通过某一坐标轴上的位置进行定位。"""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["coordinate"] = "coordinate"
    axis: str
    value: float
    unit: Literal["mm", "cm", "m"] = "mm"
    coordinate_system: str | None = None

    @field_validator("axis")
    @classmethod
    def normalize_axis(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("坐标轴不能为空")
        return normalized


class PlaneByDescription(BaseModel):
    """用户通过自然语言描述或工程别名进行定位。"""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["description"] = "description"
    text: str

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("定位面描述不能为空")
        return normalized


ReferencePlaneSelector = Annotated[
    PlaneByName | PlaneByCoordinate | PlaneByDescription,
    Field(discriminator="mode"),
]


class ReferencePlaneRecord(BaseModel):
    """当前 CAD 工程中的真实标尺面记录。"""

    model_config = ConfigDict(extra="forbid")

    object_id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    axis: str | None = None
    coordinate_mm: float | None = None
    coordinate_system: str | None = None

    @field_validator("object_id", "name")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("字段不能为空")
        return normalized

    @field_validator("axis")
    @classmethod
    def normalize_optional_axis(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper()
        return normalized or None


class ReferencePlaneResolution(BaseModel):
    """定位面解析的统一结果。"""

    model_config = ConfigDict(extra="forbid")

    status: Literal["resolved", "ambiguous", "not_found", "conflict"]
    selector: ReferencePlaneSelector | None = None
    resolved: ReferencePlaneRecord | None = None
    candidates: list[ReferencePlaneRecord] = Field(default_factory=list)
    message: str | None = None
