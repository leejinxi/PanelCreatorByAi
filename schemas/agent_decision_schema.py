"""Strongly typed, user-visible Agent decisions."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


DecisionAction = Literal[
    "inspect_project_context",
    "ask_clarification",
    "prepare_creation",
    "stop",
]
DecisionSource = Literal["policy", "llm", "fallback", "safety_override"]
DecisionReason = Literal[
    "MISSING_REQUIRED_FIELD",
    "INVALID_USER_INPUT",
    "PROJECT_CONTEXT_UNVERIFIED",
    "REFERENCE_NOT_FOUND",
    "REFERENCE_AMBIGUOUS",
    "BOUNDARY_NOT_FOUND",
    "BOUNDARY_AMBIGUOUS",
    "OBJECT_UNAVAILABLE",
    "OBJECT_NOT_ELIGIBLE",
    "ALL_PRECONDITIONS_SATISFIED",
    "UNSUPPORTED_REQUEST",
    "AGENT_ERROR",
    "DECISION_LIMIT_REACHED",
]


class AgentDecision(BaseModel):
    """One bounded next-action decision, not a hidden chain of thought."""

    model_config = ConfigDict(extra="forbid")

    next_action: DecisionAction
    reason_code: DecisionReason
    observation: str = Field(min_length=1)
    evidence: list[str] = Field(default_factory=list, max_length=4)
    user_message: str | None = None

    @model_validator(mode="after")
    def validate_user_message(self) -> "AgentDecision":
        if self.next_action == "ask_clarification":
            if self.user_message is None or not self.user_message.strip():
                raise ValueError("澄清决策必须包含用户提示")
        if self.user_message is not None:
            self.user_message = self.user_message.strip() or None
        return self


class AgentDecisionRecord(BaseModel):
    """Decision item safe to persist in state and render in the Demo UI."""

    model_config = ConfigDict(extra="forbid")

    sequence: int = Field(ge=1)
    source: DecisionSource
    decision: AgentDecision
