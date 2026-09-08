from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


AgentRunStatus = Literal[
    "success",
    "clarification",
    "unsupported",
    "error",
]
ExecutionMode = Literal["mock", "cad"]
StepName = Literal["parse", "validate", "cad"]
StepStatus = Literal["success", "attention", "error", "skipped"]


class AgentRunRequest(BaseModel):
    """浏览器提交给 Agent 的单次自然语言请求。"""

    model_config = ConfigDict(extra="forbid")

    message: str = Field(max_length=2000)

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("创建需求不能为空")
        return normalized


class HealthResponse(BaseModel):
    """轻量服务状态；不主动探测 LLM 或 CAD。"""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"] = "ok"
    mode: ExecutionMode
    agent: Literal["ready"] = "ready"
    cad_backend: str


class AgentStepView(BaseModel):
    """页面展示的单个 Agent 执行步骤。"""

    model_config = ConfigDict(extra="forbid")

    name: StepName
    status: StepStatus


class BoundaryView(BaseModel):
    """页面展示的板架四向边界。"""

    model_config = ConfigDict(extra="forbid")

    top: str | None = None
    bottom: str | None = None
    left: str | None = None
    right: str | None = None


class PanelView(BaseModel):
    """与内部 PanelRequest 解耦的页面参数模型。"""

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    reference_name: str | None = Field(
        default=None,
        serialization_alias="referenceName",
    )
    thickness_mm: float | None = Field(
        default=None,
        allow_inf_nan=False,
        serialization_alias="thicknessMm",
    )
    material: str | None = None
    boundaries: BoundaryView = Field(default_factory=BoundaryView)


class CadResultView(BaseModel):
    """页面可见的 CAD 执行结果。"""

    model_config = ConfigDict(extra="forbid")

    success: bool
    message: str
    object_id: str | None = None
    error_code: str | None = None


class AgentRunResponse(BaseModel):
    """浏览器只依赖此响应，不直接依赖内部 AgentState。"""

    model_config = ConfigDict(extra="forbid")

    request_id: str
    status: AgentRunStatus
    mode: ExecutionMode
    message: str
    steps: list[AgentStepView]
    panel: PanelView | None = None
    cad_result: CadResultView | None = None
    error_code: str | None = None

    @model_validator(mode="after")
    def validate_result_consistency(self) -> "AgentRunResponse":
        if self.status == "success":
            if self.cad_result is None or not self.cad_result.success:
                raise ValueError("成功响应必须包含成功的 CAD 结果")
            if self.panel is None:
                raise ValueError("成功响应必须包含板架参数")
        elif self.status in {"clarification", "unsupported"}:
            if self.cad_result is not None:
                raise ValueError(f"{self.status} 响应不能包含 CAD 结果")
        if self.status == "error" and self.error_code is None:
            raise ValueError("错误响应必须包含错误码")
        if self.status != "error" and self.error_code is not None:
            raise ValueError("非错误响应不能包含错误码")
        return self
