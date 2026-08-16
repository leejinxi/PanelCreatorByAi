from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PanelBoundaries(BaseModel):
    """板架的四向边界定义。"""

    model_config = ConfigDict(extra="forbid")

    top: str | None = None
    bottom: str | None = None
    left: str | None = None
    right: str | None = None

    @field_validator("top", "bottom", "left", "right")
    @classmethod
    def normalize_boundary(cls, value: str | None) -> str | None:
        if value is None:
            return None

        normalized = value.strip()
        return normalized or None


class PanelRequest(BaseModel):
    """经过校验、可以提交给 CAD 层的板架创建请求。"""

    model_config = ConfigDict(extra="forbid")

    #输入校验
    type: Literal["panel"] = "panel"
    reference_plane: str

    # default_factory=PanelBoundaries 表示没有提供边界时，每次创建一个新的空边界对象
    boundaries: PanelBoundaries = Field(default_factory=PanelBoundaries)
    thickness: float = Field(gt=0, description="板架厚度，单位为 mm") # greater than(gt) 0
    material: str

    # 对reference_plane和material禁止空字符串
    @field_validator("reference_plane", "material") 
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        normalized = value.strip() # 去除空格
        if not normalized:
            raise ValueError("字段不能为空")
        return normalized


class CadExecutionResult(BaseModel):
    """CAD 工具统一返回结果。"""

    model_config = ConfigDict(extra="forbid")

    success: bool
    message: str
    object_id: str | None = None
    error_code: str | None = None
