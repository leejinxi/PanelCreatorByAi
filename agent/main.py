import argparse
from collections.abc import Sequence
from typing import Any

from agent.graph import graph
from schemas.panel_schema import CadExecutionResult


EXIT_COMMANDS = frozenset({"q", "quit", "exit", "退出"})
MAX_CLARIFICATION_ROUNDS = 3


def run_panel_agent(user_input: str) -> dict[str, Any]:
    """运行一次板架创建流程并返回完整状态，便于界面层和测试复用。"""

    normalized_input = user_input.strip()
    if not normalized_input:
        raise ValueError("板架创建需求不能为空")

    return graph.invoke({"user_input": normalized_input})


def build_accumulated_request(user_turns: Sequence[str]) -> str:
    """把初始需求和后续补充组织成模型可理解的完整请求。"""

    if not user_turns:
        raise ValueError("至少需要一条用户输入")

    if len(user_turns) == 1:
        return user_turns[0]

    lines = [f"初始需求：{user_turns[0]}"]
    lines.extend(
        f"用户第{index}次补充：{turn}"
        for index, turn in enumerate(user_turns[1:], start=1)
    )
    return "\n".join(lines)


def format_agent_result(result: dict[str, Any]) -> str:
    """将内部 AgentState 转换为面向用户的简洁结果。"""

    cad_result = result.get("cad_result")
    if isinstance(cad_result, CadExecutionResult):
        if cad_result.success:
            return (
                f"创建成功：{cad_result.message}\n"
                f"CAD 对象 ID：{cad_result.object_id}"
            )

        return (
            f"创建失败：{cad_result.message}\n"
            f"错误码：{cad_result.error_code}"
        )

    error = result.get("error")
    if error:
        return f"执行失败：{error}"

    clarification = result.get("clarification")
    if clarification:
        return f"需要补充信息：{clarification}"

    final_response = result.get("final_response")
    if final_response:
        return str(final_response)

    return "流程已结束，但没有产生板架创建结果。"


def run_interactive_session(
    *,
    max_clarification_rounds: int = MAX_CLARIFICATION_ROUNDS,
) -> int:
    """运行可连续补充缺失参数的命令行会话。"""

    if max_clarification_rounds < 1:
        raise ValueError("最大补充轮数必须大于 0")

    user_turns: list[str] = []
    clarification_rounds = 0
    prompt = "请输入板架创建需求："

    while True:
        try:
            user_input = input(prompt).strip()
        except EOFError:
            print("执行失败：没有读取到板架创建需求。")
            return 2

        if user_input.casefold() in EXIT_COMMANDS:
            print("已退出板架创建会话，未执行新的 CAD 操作。")
            return 0

        if not user_input:
            print("输入不能为空，请重新输入；输入 q 可退出。")
            prompt = "请输入板架创建需求：" if not user_turns else "请继续补充："
            continue

        user_turns.append(user_input)
        result = run_panel_agent(build_accumulated_request(user_turns))
        print(format_agent_result(result))

        if result.get("error"):
            return 1

        if not result.get("clarification"):
            return 0

        clarification_rounds += 1
        if clarification_rounds >= max_clarification_rounds:
            print("已达到最大补充次数，本次创建会话结束。")
            return 2

        prompt = "请继续补充（输入 q 退出）："


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="AI Ship CAD Copilot 板架创建 Agent",
    )
    parser.add_argument(
        "request",
        nargs="?",
        help="板架创建需求；省略时进入交互输入模式",
    )
    args = parser.parse_args(argv)

    if args.request is None:
        return run_interactive_session()

    try:
        result = run_panel_agent(args.request)
    except ValueError as exc:
        print(f"执行失败：{exc}")
        return 2

    print(format_agent_result(result))
    return 1 if result.get("error") else 0


if __name__ == "__main__":
    raise SystemExit(main())
