
LLM steps:understand, analyze, generate text, or make reasoning decisions
Data steps: retrieve information from external sources
Action steps: 执行外部操作
User input steps：人工干预

state:
    状态是智能体内所有节点均可访问的共享内存。可以将其理解为智能体的记事本，用于记录流程处理过程中获取的所有信息与各项决策。
    persist across steps? If yes, it goes in state.
    Can you derive it from other data? If yes, compute it when needed instead of storing it in state. 如果能从别的数据中推理出来就现算

    状态应当存储原始数据，而非格式化文本。如有需要，在节点内部执行prompt。


普通节点（LLM + 读数据）：自动循环，不需要人管。
特权节点（写数据/执行操作）：在进入这个节点前，强制加上 interrupt() 等待人工审批