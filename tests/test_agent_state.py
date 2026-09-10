import unittest
from typing import get_type_hints

from agent.state import AgentState
from schemas.agent_action_schema import AgentActionPlan
from schemas.panel_schema import CadExecutionResult, PanelRequest


class AgentStateTests(unittest.TestCase):
    def test_user_input_is_the_only_required_field(self) -> None:
        self.assertEqual(AgentState.__required_keys__, frozenset({"user_input"}))
        self.assertIn("panel_request", AgentState.__optional_keys__)
        self.assertIn("action_plan", AgentState.__optional_keys__)
        self.assertIn("cad_result", AgentState.__optional_keys__)
        self.assertIn("error", AgentState.__optional_keys__)

    def test_minimal_initial_state_is_supported(self) -> None:
        state: AgentState = {
            "user_input": "请在 FR100 创建一块板架",
        }

        self.assertEqual(state["user_input"], "请在 FR100 创建一块板架")
        self.assertNotIn("panel_request", state)

    def test_state_can_carry_strongly_typed_schema_objects(self) -> None:
        request = PanelRequest(
            boundaries=[{"operator": ">", "target": "SL10"}],
            reference_plane="FR100",
            thickness=14,
            material="AH36",
        )
        result = CadExecutionResult(
            success=True,
            message="Panel created successfully",
            object_id="PANEL-001",
        )
        state: AgentState = {
            "user_input": "创建板架",
            "panel_request": request,
            "cad_result": result,
            "retry_count": 0,
        }

        self.assertIsInstance(state["panel_request"], PanelRequest)
        self.assertIsInstance(state["cad_result"], CadExecutionResult)
        self.assertEqual(state["panel_request"].reference_plane, "FR100")
        self.assertEqual(state["cad_result"].object_id, "PANEL-001")

    def test_type_hints_reference_schema_classes(self) -> None:
        hints = get_type_hints(AgentState)

        self.assertIn(PanelRequest, hints["panel_request"].__args__)
        self.assertIn(AgentActionPlan, hints["action_plan"].__args__)
        self.assertIn(CadExecutionResult, hints["cad_result"].__args__)


if __name__ == "__main__":
    unittest.main()
