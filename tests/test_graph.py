import importlib
import json
import unittest
from unittest.mock import patch

from schemas.panel_schema import (
    CadExecutionResult,
    PanelRequest,
)


graph_module = importlib.import_module("agent.graph")


SUCCESS_RESULT = CadExecutionResult(
    success=True,
    message="Panel created successfully",
    object_id="PANEL-001",
)


def create_panel_output(panel: dict) -> str:
    return json.dumps(
        {
            "action": "create_panel",
            "panel": panel,
        }
    )


class AgentGraphTests(unittest.TestCase):
    def invoke_with_model_output(self, output: str) -> dict:
        with patch.object(type(graph_module.llm), "invoke", return_value=output):
            return graph_module.graph.invoke(
                {
                    "user_input": "在FR100创建板架，边界 >SL10",
                }
            )

    def test_valid_parameters_reach_cad(self) -> None:
        output = create_panel_output(
            {
                "type": "panel",
                "reference_plane": "FR100",
                "boundaries": [],
                "thickness": 14,
                "material": "AH36",
            }
        )

        with (
            patch.object(type(graph_module.llm), "invoke", return_value=output),
            patch.object(
                graph_module,
                "create_panel",
                return_value=SUCCESS_RESULT,
            ) as mocked_create_panel,
        ):
            result = graph_module.graph.invoke(
                {"user_input": "在FR100创建板架，边界 >SL10"}
            )

        self.assertIsInstance(result["panel_request"], PanelRequest)
        self.assertEqual(result["cad_result"], SUCCESS_RESULT)
        self.assertIsNone(result["error"])
        panel = mocked_create_panel.call_args.args[0]
        self.assertIsInstance(panel, PanelRequest)
        self.assertEqual(panel.reference_plane, "FR100")
        self.assertEqual(panel.thickness, 14.0)

    def test_missing_reference_plane_requests_clarification(self) -> None:
        output = create_panel_output(
            {
                "type": "panel",
                "reference_plane": None,
                "boundaries": [],
                "thickness": 14,
                "material": "AH36",
            }
        )

        with patch.object(graph_module, "create_panel") as mocked_create_panel:
            with patch.object(
                type(graph_module.llm),
                "invoke",
                return_value=output,
            ):
                result = graph_module.graph.invoke(
                    {"user_input": "请创建一块14mm厚AH36板架，边界 >SL10"}
                )

        self.assertIn("定位面", result["clarification"])
        self.assertNotIn("panel_request", result)
        mocked_create_panel.assert_not_called()

    def test_recovers_known_ruler_plane_when_model_misses_it(self) -> None:
        output = create_panel_output(
            {
                "type": "panel",
                "reference_plane": None,
                "boundaries": [],
                "thickness": 14,
                "material": "AH36",
            }
        )

        with (
            patch.object(type(graph_module.llm), "invoke", return_value=output),
            patch.object(
                graph_module,
                "create_panel",
                return_value=SUCCESS_RESULT,
            ) as mocked_create_panel,
        ):
            result = graph_module.graph.invoke(
                {"user_input": "请在第100肋位创建14mm厚AH36板架，边界 >SL10"}
            )

        self.assertEqual(result["panel_request"].reference_plane, "FR100")
        panel = mocked_create_panel.call_args.args[0]
        self.assertEqual(panel.reference_plane, "FR100")
        mocked_create_panel.assert_called_once()

    def test_coordinate_reference_is_passed_through(self) -> None:
        output = create_panel_output(
            {
                "type": "panel",
                "reference_plane": "X=10000",
                "boundaries": [],
                "thickness": 14,
                "material": "AH36",
            }
        )

        with (
            patch.object(type(graph_module.llm), "invoke", return_value=output),
            patch.object(
                graph_module,
                "create_panel",
                return_value=SUCCESS_RESULT,
            ) as mocked_create_panel,
        ):
            result = graph_module.graph.invoke(
                {"user_input": "请在X=10000的位置创建14mm厚AH36板架，边界 >SL10"}
            )

        self.assertEqual(result["panel_request"].reference_plane, "X=10000")
        panel = mocked_create_panel.call_args.args[0]
        self.assertEqual(panel.reference_plane, "X=10000")
        mocked_create_panel.assert_called_once()

    def test_chinese_frame_name_is_normalized(self) -> None:
        output = create_panel_output(
            {
                "type": "panel",
                "reference_plane": "第100肋位",
                "boundaries": [],
                "thickness": 14,
                "material": "AH36",
            }
        )

        with (
            patch.object(type(graph_module.llm), "invoke", return_value=output),
            patch.object(
                graph_module,
                "create_panel",
                return_value=SUCCESS_RESULT,
            ) as mocked_create_panel,
        ):
            result = graph_module.graph.invoke(
                {"user_input": "请在第100肋位创建14mm厚AH36板架，边界 >SL10"}
            )

        self.assertEqual(
            result["panel_request"].reference_plane,
            "FR100",
        )
        panel = mocked_create_panel.call_args.args[0]
        self.assertEqual(panel.reference_plane, "FR100")
        mocked_create_panel.assert_called_once()

    def test_unknown_reference_plane_reaches_cad(self) -> None:
        output = create_panel_output(
            {
                "type": "panel",
                "reference_plane": "UNKNOWN_PLANE_999",
                "boundaries": [],
                "thickness": 14,
                "material": "AH36",
            }
        )

        with (
            patch.object(type(graph_module.llm), "invoke", return_value=output),
            patch.object(
                graph_module,
                "create_panel",
                return_value=SUCCESS_RESULT,
            ) as mocked_create_panel,
        ):
            result = graph_module.graph.invoke(
                {"user_input": "在UNKNOWN_PLANE_999创建板架，边界 >SL10"}
            )

        self.assertIsNone(result["error"])
        panel = mocked_create_panel.call_args.args[0]
        self.assertEqual(panel.reference_plane, "UNKNOWN_PLANE_999")
        mocked_create_panel.assert_called_once()

    def test_missing_material_requests_clarification(self) -> None:
        output = create_panel_output(
            {
                "type": "panel",
                "reference_plane": "FR100",
                "boundaries": [],
                "thickness": 14,
                "material": "",
            }
        )

        with patch.object(graph_module, "create_panel") as mocked_create_panel:
            with patch.object(
                type(graph_module.llm),
                "invoke",
                return_value=output,
            ):
                result = graph_module.graph.invoke(
                    {"user_input": "在FR100创建板架，边界 >SL10"}
                )

        self.assertIn("材料", result["clarification"])
        self.assertNotIn("panel_request", result)
        mocked_create_panel.assert_not_called()

    def test_cad_failure_is_preserved_as_structured_result(self) -> None:
        output = create_panel_output(
            {
                "type": "panel",
                "reference_plane": "FR100",
                "boundaries": [],
                "thickness": 14,
                "material": "AH36",
            }
        )
        failure = CadExecutionResult(
            success=False,
            message="CAD 服务不可用",
            error_code="CAD_UNAVAILABLE",
        )

        with (
            patch.object(type(graph_module.llm), "invoke", return_value=output),
            patch.object(
                graph_module,
                "create_panel",
                return_value=failure,
            ),
        ):
            result = graph_module.graph.invoke({"user_input": "在FR100创建板架，边界 >SL10"})

        self.assertEqual(result["cad_result"], failure)
        self.assertEqual(result["error"], "CAD 服务不可用")
        self.assertEqual(result["error_code"], "CAD_UNAVAILABLE")

    def test_non_positive_thickness_stops_before_cad(self) -> None:
        output = create_panel_output(
            {
                "type": "panel",
                "reference_plane": "FR100",
                "boundaries": [],
                "thickness": -5,
                "material": "AH36",
            }
        )

        with patch.object(graph_module, "create_panel") as mocked_create_panel:
            with patch.object(
                type(graph_module.llm),
                "invoke",
                return_value=output,
            ):
                result = graph_module.graph.invoke(
                    {"user_input": "在FR100创建板架，边界 >SL10"}
                )

        self.assertIn("thickness", result["error"])
        mocked_create_panel.assert_not_called()

    def test_invalid_json_stops_before_cad(self) -> None:
        with patch.object(graph_module, "create_panel") as mocked_create_panel:
            result = self.invoke_with_model_output("not-json")

        self.assertIn("JSON 格式不正确", result["error"])
        self.assertEqual(result["error_code"], "LLM_INVALID_JSON")
        self.assertEqual(result["retry_count"], 2)
        mocked_create_panel.assert_not_called()

    def test_invalid_json_is_retried_once_and_can_recover(self) -> None:
        repaired_output = create_panel_output(
            {
                "type": "panel",
                "reference_plane": "FR100",
                "boundaries": [],
                "thickness": 14,
                "material": "AH36",
            }
        )

        with (
            patch.object(
                type(graph_module.llm),
                "invoke",
                side_effect=["not-json", repaired_output],
            ) as mocked_invoke,
            patch.object(
                graph_module,
                "create_panel",
                return_value=SUCCESS_RESULT,
            ) as mocked_create_panel,
        ):
            result = graph_module.graph.invoke({"user_input": "在FR100创建板架，边界 >SL10"})

        self.assertEqual(mocked_invoke.call_count, 2)
        self.assertEqual(result["retry_count"], 1)
        self.assertIsNone(result["error"])
        mocked_create_panel.assert_called_once()

    def test_non_creation_request_does_not_call_cad(self) -> None:
        output = json.dumps(
            {
                "action": "unsupported",
                "panel": None,
            }
        )

        with patch.object(graph_module, "create_panel") as mocked_create_panel:
            result = self.invoke_with_model_output(output)

        self.assertEqual(result["action_plan"].action, "unsupported")
        self.assertIn("仅支持创建板架", result["final_response"])
        self.assertNotIn("panel_request", result)
        mocked_create_panel.assert_not_called()

    def test_invalid_action_plan_does_not_call_cad(self) -> None:
        output = json.dumps(
            {
                "action": "create_panel",
                "panel": None,
            }
        )

        with patch.object(graph_module, "create_panel") as mocked_create_panel:
            result = self.invoke_with_model_output(output)

        self.assertIn("动作计划不合法", result["error"])
        mocked_create_panel.assert_not_called()

    def test_model_exception_becomes_state_error(self) -> None:
        with (
            patch.object(
                type(graph_module.llm),
                "invoke",
                side_effect=RuntimeError("Ollama unavailable"),
            ),
            patch.object(graph_module, "create_panel") as mocked_create_panel,
        ):
            result = graph_module.graph.invoke(
                {"user_input": "在FR100创建板架，边界 >SL10"}
            )

        self.assertIn("本地模型调用失败", result["error"])
        mocked_create_panel.assert_not_called()


if __name__ == "__main__":
    unittest.main()
