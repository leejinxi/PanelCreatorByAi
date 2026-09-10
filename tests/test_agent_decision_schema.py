import unittest

from pydantic import ValidationError

from schemas.agent_decision_schema import AgentDecision, AgentDecisionRecord


class AgentDecisionSchemaTests(unittest.TestCase):
    def test_accepts_bounded_decision_record(self) -> None:
        record = AgentDecisionRecord(
            sequence=1,
            source="policy",
            decision=AgentDecision(
                next_action="inspect_project_context",
                reason_code="PROJECT_CONTEXT_UNVERIFIED",
                observation="工程对象尚未查询。",
                evidence=["reference_plane=FR100"],
            ),
        )
        self.assertEqual(record.decision.next_action, "inspect_project_context")

    def test_clarification_requires_user_message(self) -> None:
        with self.assertRaises(ValidationError):
            AgentDecision(
                next_action="ask_clarification",
                reason_code="REFERENCE_AMBIGUOUS",
                observation="定位面存在歧义。",
            )

    def test_rejects_unknown_action_and_extra_fields(self) -> None:
        with self.assertRaises(ValidationError):
            AgentDecision.model_validate({
                "next_action": "delete_panel",
                "reason_code": "AGENT_ERROR",
                "observation": "invalid",
                "private_reasoning": "hidden",
            })


if __name__ == "__main__":
    unittest.main()
