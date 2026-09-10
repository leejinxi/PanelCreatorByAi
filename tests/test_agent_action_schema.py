import unittest

from pydantic import ValidationError

from schemas.agent_action_schema import AgentActionPlan


class AgentActionPlanTests(unittest.TestCase):
    def test_accepts_create_panel_action_with_candidate(self) -> None:
        plan = AgentActionPlan.model_validate(
            {
                "action": "create_panel",
                "panel": {
                    "type": "panel",
                    "reference_plane": "FR100",
                    "boundaries": [],
                    "thickness": 14,
                    "material": "AH36",
                },
            }
        )

        self.assertEqual(plan.action, "create_panel")
        self.assertEqual(plan.panel.reference_plane, "FR100")

    def test_accepts_unsupported_action_without_panel(self) -> None:
        plan = AgentActionPlan(
            action="unsupported",
            panel=None,
        )

        self.assertEqual(plan.action, "unsupported")
        self.assertIsNone(plan.panel)

    def test_rejects_action_payload_mismatch(self) -> None:
        with self.assertRaises(ValidationError):
            AgentActionPlan(action="create_panel", panel=None)

        with self.assertRaises(ValidationError):
            AgentActionPlan.model_validate(
                {
                    "action": "unsupported",
                    "panel": {
                        "type": "panel",
                    },
                }
            )

    def test_rejects_unknown_action(self) -> None:
        with self.assertRaises(ValidationError):
            AgentActionPlan.model_validate(
                {
                    "action": "delete_panel",
                    "panel": None,
                }
            )


if __name__ == "__main__":
    unittest.main()
