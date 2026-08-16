import importlib
import json
import unittest
from unittest.mock import patch

from schemas.panel_schema import PanelRequest


graph_module = importlib.import_module("agent.graph")


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
                return_value="Panel created successfully",
            ) as mocked_create_panel,
        ):
            result = graph_module.graph.invoke(
                {"user_input": "创建板架"}
            )

        self.assertIsInstance(result["panel_request"], PanelRequest)
        self.assertEqual(result["cad_result"], "Panel created successfully")
        self.assertIsNone(result["error"])
        mocked_create_panel.assert_called_once_with(
            reference_plane="FR100",
            boundaries={
                "top": None,
                "bottom": None,
                "left": None,
                "right": None,
            },
            thickness=14.0,
            material="AH36",
        )

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
