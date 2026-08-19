from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


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
    thickness: float = Field(
        gt=0,
        allow_inf_nan=False,
        description="板架厚度，单位为 mm",
    )
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

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("执行结果消息不能为空")
        return normalized

    @field_validator("object_id", "error_code")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def validate_success_payload(self) -> "CadExecutionResult":
        if self.success and self.error_code is not None:
            raise ValueError("成功结果不能包含错误码")
        if not self.success:
            if self.error_code is None:
                raise ValueError("失败结果必须包含错误码")
            if self.object_id is not None:
                raise ValueError("失败结果不能包含 CAD 对象 ID")
        return self
