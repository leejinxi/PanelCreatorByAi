from typing import Any, NotRequired, Required, TypedDict

from schemas.agent_action_schema import AgentActionPlan
from schemas.panel_schema import CadExecutionResult, PanelRequest
from schemas.reference_plane_schema import ReferencePlaneResolution


class AgentState(TypedDict, total=False):
    """LangGraph 节点之间共享的状态。"""

    # 每次调用图时必须提供的用户原始输入
    user_input: Required[str]

    # LLM 返回的原始文本，用于诊断 JSON 输出问题
    llm_raw_output: NotRequired[str | None]

    # 模型选择的结构化动作；当前支持创建板架或明确拒绝未知任务
    action_plan: NotRequired[AgentActionPlan | None]

    # create_panel 动作中的候选参数字典；后续生成 panel_request
    structure_json: NotRequired[dict[str, Any] | None]

    # 只有通过 PanelRequest 校验的数据才允许进入标准化 CAD 工具
    panel_request: NotRequired[PanelRequest | None]

    # 用户定位表达式在当前工程标尺目录中的解析结果
    reference_plane_resolution: NotRequired[ReferencePlaneResolution | None]

    # 标准化 CAD 工具的结构化执行结果
    cad_result: NotRequired[CadExecutionResult | None]

    # 流程异常与用户澄清信息
    error: NotRequired[str | None]
    clarification: NotRequired[str | None]
    final_response: NotRequired[str | None]

    # 为后续 JSON 修复或模型重试预留
    retry_count: NotRequired[int]
