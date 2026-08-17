from agent.graph import graph

result = graph.invoke(
    {
        "user_input":
            "请使用SURFACE_200为定位面，创建一块14mm厚AH36板架"
    }
)



print("LLM原始返回:", result)
