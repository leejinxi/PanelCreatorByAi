from langgraph.graph import (
    StateGraph,
    END
)
from agent.state import AgentState
from llm.qwen_client import LocalQwen
from tools.cad_tools import create_panel

llm = LocalQwen()

# =====================
# Node 1
# LLM解析需求
# =====================

def parse_structure(
        state:AgentState
):
    prompt = f"""
    你是船舶CAD结构设计助手。
    用户需求：
    {
        state['user_input']
    }
    请解析为板架创建参数。 
    只返回JSON，不要解释：
    {{
            "type":"panel",
            "reference_plane":"",
            "boundaries":
            {{
                    "top":"",
                    "bottom":"",
                    "left":"",
                    "right":""
            }},
            "thickness":0,
            "material":""
    }}
    """
    result = llm.invoke(prompt)

    import json
    data=json.loads(result)
    return {
        "structure_json": data
    }


# =====================
# Node 2
# CAD创建
# =====================

def execute_cad(
        state: AgentState
):

    data=state["structure_json"]
    result=create_panel(
        reference_plane= data["reference_plane"],
        boundaries=data["boundaries"],
        thickness= data["thickness"],
        material= data["material"]
    )

    return {
        "cad_result":result
    }


# =====================
# Build Graph
# =====================

builder=StateGraph(
    AgentState
)

builder.add_node(
    "parse",
    parse_structure
)

builder.add_node(
    "cad",
    execute_cad
)

builder.set_entry_point(
    "parse"
)

builder.add_edge(
    "parse",
    "cad"
)

builder.add_edge(
    "cad",
    END
)


graph=builder.compile()
