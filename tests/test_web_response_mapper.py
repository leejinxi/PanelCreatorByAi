import unittest

from schemas.panel_schema import CadExecutionResult, PanelRequest
from webapp.response_mapper import map_agent_state


class WebResponseMapperTests(unittest.TestCase):
    def test_maps_success_without_exposing_internal_state(self) -> None:
        response = map_agent_state(
            {
                "llm_raw_output": "sensitive-debug-output",
                "panel_request": PanelRequest(
                    reference_plane="FR100",
                    thickness=14,
                    material="AH36",
                ),
                "cad_result": CadExecutionResult(
                    success=True,
                    message="Panel created successfully",
                    object_id="mock-panel-001",
                ),
            },
            request_id="REQ-001",
        )

        payload = response.model_dump(mode="json", by_alias=True)

        self.assertEqual(response.status, "success")
        self.assertEqual(response.message, "模拟 CAD 已完成板架创建。")
        self.assertEqual(payload["panel"]["referenceName"], "FR100")
        self.assertEqual(payload["panel"]["thicknessMm"], 14.0)
        self.assertNotIn("llm_raw_output", payload)
        self.assertEqual(
            [step.status for step in response.steps],
            ["success", "success", "success"],
        )

    def test_maps_clarification_with_partial_panel(self) -> None:
        response = map_agent_state(
            {
                "structure_json": {
                    "type": "panel",
                    "reference_plane": "FR100",
                    "boundaries": {},
                    "thickness": 14,
                    "material": None,
                },
                "clarification": "创建板架还需要提供：材料。",
            },
            request_id="REQ-002",
        )

        self.assertEqual(response.status, "clarification")
        self.assertEqual(response.panel.reference_name, "FR100")
        self.assertIsNone(response.panel.material)
        self.assertIsNone(response.cad_result)
        self.assertEqual(response.steps[1].status, "attention")
        self.assertEqual(response.steps[2].status, "skipped")

    def test_maps_unsupported_result_without_cad(self) -> None:
        response = map_agent_state(
            {
                "final_response": "当前仅支持创建板架。",
            },
            request_id="REQ-003",
        )

        self.assertEqual(response.status, "unsupported")
        self.assertIsNone(response.cad_result)
        self.assertEqual(response.steps[2].status, "skipped")

    def test_maps_llm_error_to_parse_step(self) -> None:
        response = map_agent_state(
            {
                "error": "无法连接本地模型服务。",
                "error_code": "LLM_UNAVAILABLE",
            },
            request_id="REQ-004",
        )

        self.assertEqual(response.status, "error")
        self.assertEqual(response.error_code, "LLM_UNAVAILABLE")
        self.assertEqual(response.steps[0].status, "error")
        self.assertEqual(response.steps[1].status, "skipped")

    def test_maps_cad_failure_to_cad_step(self) -> None:
        response = map_agent_state(
            {
                "panel_request": PanelRequest(
                    reference_plane="FR100",
                    thickness=14,
                    material="AH36",
                ),
                "cad_result": CadExecutionResult(
                    success=False,
                    message="定位面不存在。",
                    error_code="REFERENCE_PLANE_NOT_FOUND",
                ),
                "error": "定位面不存在。",
                "error_code": "REFERENCE_PLANE_NOT_FOUND",
            },
            request_id="REQ-005",
        )

        self.assertEqual(response.status, "error")
        self.assertEqual(response.error_code, "REFERENCE_PLANE_NOT_FOUND")
        self.assertEqual(response.steps[2].status, "error")

    def test_maps_empty_state_to_controlled_error(self) -> None:
        response = map_agent_state({}, request_id="REQ-006")

        self.assertEqual(response.status, "error")
        self.assertEqual(response.error_code, "AGENT_EMPTY_RESULT")
        self.assertEqual(response.steps[0].status, "error")

    def test_adds_fallback_code_to_unclassified_agent_error(self) -> None:
        response = map_agent_state(
            {"error": "Agent 执行失败。"},
            request_id="REQ-007",
        )

        self.assertEqual(response.status, "error")
        self.assertEqual(response.error_code, "AGENT_EXECUTION_ERROR")
        self.assertEqual(response.steps[0].status, "error")


if __name__ == "__main__":
    unittest.main()
