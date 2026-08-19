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


class AgentGraphTests(unittest.TestCase):
    def invoke_with_model_output(self, output: str) -> dict:
        with patch.object(type(graph_module.llm), "invoke", return_value=output):
            return graph_module.graph.invoke(
                {
                    "user_input": "测试用户输入",
                }
            )

    def test_valid_parameters_reach_cad(self) -> None:
        output = json.dumps(
            {
                "type": "panel",
                "reference_plane": "FR100",
                "boundaries": {},
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
                {"user_input": "创建板架"}
            )

        self.assertIsInstance(result["panel_request"], PanelRequest)
        self.assertEqual(result["cad_result"], SUCCESS_RESULT)
        self.assertIsNone(result["error"])
        panel = mocked_create_panel.call_args.args[0]
        self.assertIsInstance(panel, PanelRequest)
        self.assertEqual(panel.reference_plane, "FR100")
        self.assertEqual(panel.thickness, 14.0)

    def test_recovers_fr100_from_user_input_when_llm_misses_it(self) -> None:
        output = json.dumps(
            {
                "type": "panel",
                "reference_plane": None,
                "boundaries": {},
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
                {"user_input": "请在FR100创建一块14mm厚AH36板架"}
            )

        self.assertEqual(result["panel_request"].reference_plane, "FR100")
        self.assertEqual(
            result["reference_plane_resolution"].resolved.name,
            "FR100",
        )
        mocked_create_panel.assert_called_once()

    def test_resolves_coordinate_to_project_plane(self) -> None:
        output = json.dumps(
            {
                "type": "panel",
                "reference_plane": "X=10000",
                "boundaries": {},
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
                {"user_input": "请在X=10000的位置创建14mm厚AH36板架"}
            )

        self.assertEqual(result["panel_request"].reference_plane, "FR100")
        mocked_create_panel.assert_called_once()

    def test_resolves_surface_name_from_project_catalog(self) -> None:
        output = json.dumps(
            {
                "type": "panel",
                "reference_plane": None,
                "boundaries": {},
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
                {"user_input": "以SURFACE_20为定位面创建14mm厚AH36板架"}
            )

        self.assertEqual(
            result["panel_request"].reference_plane,
            "SURFACE_20",
        )
        mocked_create_panel.assert_called_once()

    def test_missing_material_requests_clarification(self) -> None:
        output = json.dumps(
            {
                "type": "panel",
                "reference_plane": "FR100",
                "boundaries": {},
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
                    {"user_input": "创建板架"}
                )

        self.assertIn("材料", result["clarification"])
        self.assertNotIn("panel_request", result)
        mocked_create_panel.assert_not_called()

    def test_cad_failure_is_preserved_as_structured_result(self) -> None:
        output = json.dumps(
            {
                "type": "panel",
                "reference_plane": "FR100",
                "boundaries": {},
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
            result = graph_module.graph.invoke({"user_input": "创建板架"})

        self.assertEqual(result["cad_result"], failure)
        self.assertEqual(result["error"], "CAD 服务不可用")

    def test_non_positive_thickness_stops_before_cad(self) -> None:
        output = json.dumps(
            {
                "type": "panel",
                "reference_plane": "FR100",
                "boundaries": {},
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
                    {"user_input": "创建板架"}
                )

        self.assertIn("thickness", result["error"])
        mocked_create_panel.assert_not_called()

    def test_invalid_json_stops_before_cad(self) -> None:
        with patch.object(graph_module, "create_panel") as mocked_create_panel:
            result = self.invoke_with_model_output("not-json")

        self.assertIn("JSON 格式不正确", result["error"])
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
                {"user_input": "创建板架"}
            )

        self.assertIn("本地模型调用失败", result["error"])
        mocked_create_panel.assert_not_called()


if __name__ == "__main__":
    unittest.main()
