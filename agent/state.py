from typing import TypedDict, Optional


class AgentState(TypedDict):
    # 用户输入
    user_input: str
    # AI解析后的结构参数
    structure_json: Optional[dict]
    # CAD执行结果
    cad_result: Optional[str]
