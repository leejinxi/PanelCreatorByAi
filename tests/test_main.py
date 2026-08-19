import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

from agent import main as main_module
from schemas.panel_schema import CadExecutionResult


class AgentMainTests(unittest.TestCase):
    def test_run_panel_agent_rejects_blank_input(self) -> None:
        with self.assertRaisesRegex(ValueError, "不能为空"):
            main_module.run_panel_agent("   ")

    def test_run_panel_agent_normalizes_input(self) -> None:
        with patch.object(
            main_module.graph,
            "invoke",
            return_value={"cad_result": None},
        ) as mocked_invoke:
            main_module.run_panel_agent("  创建板架  ")

        mocked_invoke.assert_called_once_with(
            {"user_input": "创建板架"}
        )

    def test_formats_success_result(self) -> None:
        output = main_module.format_agent_result(
            {
                "cad_result": CadExecutionResult(
                    success=True,
                    message="Panel created successfully",
                    object_id="PANEL-001",
                )
            }
        )

        self.assertIn("创建成功", output)
        self.assertIn("PANEL-001", output)

    def test_formats_success_without_optional_object_id(self) -> None:
        output = main_module.format_agent_result(
            {
                "cad_result": CadExecutionResult(
                    success=True,
                    message="Panel created successfully",
                )
            }
        )

        self.assertIn("创建成功", output)
        self.assertNotIn("None", output)
        self.assertNotIn("对象 ID", output)

    def test_formats_clarification(self) -> None:
        output = main_module.format_agent_result(
            {"clarification": "请提供材料。"}
        )

        self.assertEqual(output, "需要补充信息：请提供材料。")

    def test_builds_accumulated_request(self) -> None:
        request = main_module.build_accumulated_request(
            [
                "在 FR100 创建板架",
                "厚度 14，材料 AH32",
            ]
        )

        self.assertIn("初始需求：在 FR100 创建板架", request)
        self.assertIn("用户第1次补充：厚度 14，材料 AH32", request)

    def test_interactive_session_continues_after_clarification(self) -> None:
        success = CadExecutionResult(
            success=True,
            message="Panel created successfully",
            object_id="PANEL-003",
        )

        with (
            patch(
                "builtins.input",
                side_effect=[
                    "在 FR100 创建板架",
                    "厚度 14，材料 AH32",
                ],
            ),
            patch.object(
                main_module,
                "run_panel_agent",
                side_effect=[
                    {
                        "clarification": "创建板架还需要提供：厚度、材料。",
                        "error": None,
                    },
                    {
                        "cad_result": success,
                        "clarification": None,
                        "error": None,
                    },
                ],
            ) as mocked_run,
            redirect_stdout(StringIO()) as stdout,
        ):
            exit_code = main_module.main([])

        self.assertEqual(exit_code, 0)
        self.assertEqual(mocked_run.call_count, 2)
        accumulated_request = mocked_run.call_args_list[1].args[0]
        self.assertIn("在 FR100 创建板架", accumulated_request)
        self.assertIn("厚度 14，材料 AH32", accumulated_request)
        self.assertIn("PANEL-003", stdout.getvalue())

    def test_interactive_session_can_exit_after_clarification(self) -> None:
        with (
            patch(
                "builtins.input",
                side_effect=["在 FR100 创建板架", "q"],
            ),
            patch.object(
                main_module,
                "run_panel_agent",
                return_value={
                    "clarification": "请提供厚度。",
                    "error": None,
                },
            ) as mocked_run,
            redirect_stdout(StringIO()) as stdout,
        ):
            exit_code = main_module.main([])

        self.assertEqual(exit_code, 0)
        mocked_run.assert_called_once()
        self.assertIn("已退出", stdout.getvalue())

    def test_interactive_session_handles_keyboard_interrupt(self) -> None:
        with (
            patch("builtins.input", side_effect=KeyboardInterrupt),
            redirect_stdout(StringIO()) as stdout,
        ):
            exit_code = main_module.main([])

        self.assertEqual(exit_code, 130)
        self.assertIn("已取消", stdout.getvalue())

    def test_main_accepts_command_line_request(self) -> None:
        success = CadExecutionResult(
            success=True,
            message="Panel created successfully",
            object_id="PANEL-002",
        )

        with (
            patch.object(
                main_module,
                "run_panel_agent",
                return_value={"cad_result": success},
            ),
            redirect_stdout(StringIO()) as stdout,
        ):
            exit_code = main_module.main(["创建板架"])

        self.assertEqual(exit_code, 0)
        self.assertIn("PANEL-002", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
