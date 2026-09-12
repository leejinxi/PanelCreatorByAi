import json
import unittest
from unittest.mock import patch

import agent.graph as graph_module
from schemas.agent_decision_schema import AgentDecision
from schemas.agent_action_schema import AgentActionPlan
from schemas.panel_schema import CadExecutionResult
from schemas.panel_schema import PanelRequest
from tools.project_context_tools import inspect_project_context
from tools.design_review_tools import review_panel_design


SUCCESS = CadExecutionResult(
    success=True,
    message="created",
    object_id="mock-panel-decision-001",
)


def action_output(reference_plane: str) -> str:
    return json.dumps({
        "action": "create_panel",
        "panel": {
            "type": "panel",
            "reference_plane": reference_plane,
            "boundaries": [],
            "thickness": 14,
            "material": "AH36",
        },
    }, ensure_ascii=False)


def decision_output(
    action: str,
    reason: str,
    *,
    user_message: str | None = None,
) -> str:
    return json.dumps({
        "next_action": action,
        "reason_code": reason,
        "observation": "Qwen 已根据 Mock 工程查询结果完成评估。",
        "evidence": ["结构化工具观察"],
        "user_message": user_message,
    }, ensure_ascii=False)


class AgentDecisionGraphTests(unittest.TestCase):
    def test_success_records_policy_and_llm_decisions(self) -> None:
        with (
            patch.object(type(graph_module.llm), "invoke", side_effect=[
                action_output("FR100"),
                decision_output(
                    "prepare_creation", "ALL_PRECONDITIONS_SATISFIED"
                ),
            ]),
            patch.object(graph_module, "create_panel", return_value=SUCCESS) as create,
        ):
            state = graph_module.graph.invoke({
                "user_input": "在FR100创建14mm厚AH36板架，边界 >SL10 <LV5"
            })

        self.assertTrue(state["execution_authorized"])
        self.assertEqual(
            state["authorization_reason"],
            "SAFETY_CHECKS_PASSED_WITH_REVIEW_WARNING",
        )
        self.assertEqual(state["design_review"].outcome, "passed_with_warnings")
        self.assertEqual(state["panel_request"].thickness, 14)
        self.assertIn("保留用户明确参数", state["decision"].observation)
        self.assertTrue(state["project_inspection"].all_resolved())
        self.assertEqual(
            [item.source for item in state["decision_history"]],
            ["policy", "llm"],
        )
        create.assert_called_once()

    def test_ambiguous_reference_requests_selection(self) -> None:
        with (
            patch.object(type(graph_module.llm), "invoke", side_effect=[
                action_output("主甲板"),
                decision_output(
                    "ask_clarification",
                    "REFERENCE_AMBIGUOUS",
                    user_message="请选择 Main Deck A 或 Main Deck B。",
                ),
            ]),
            patch.object(graph_module, "create_panel") as create,
        ):
            state = graph_module.graph.invoke({
                "user_input": "在主甲板创建14mm厚AH36板架，边界 >SL10"
            })

        self.assertEqual(state["project_inspection"].reference_plane.status, "ambiguous")
        self.assertIn("Main Deck A", state["clarification"])
        self.assertEqual(state["decision_history"][-1].source, "llm")
        create.assert_not_called()

    def test_unsafe_llm_decision_is_overridden(self) -> None:
        with (
            patch.object(type(graph_module.llm), "invoke", side_effect=[
                action_output("FR999"),
                decision_output(
                    "prepare_creation", "ALL_PRECONDITIONS_SATISFIED"
                ),
            ]),
            patch.object(graph_module, "create_panel") as create,
        ):
            state = graph_module.graph.invoke({
                "user_input": "在FR999创建14mm厚AH36板架，边界 >SL10"
            })

        self.assertEqual(state["decision_history"][-1].source, "safety_override")
        self.assertEqual(state["decision"].reason_code, "REFERENCE_NOT_FOUND")
        self.assertIn("FR999", state["clarification"])
        create.assert_not_called()

    def test_invalid_decision_json_uses_fallback(self) -> None:
        with (
            patch.object(
                type(graph_module.llm), "invoke",
                side_effect=[action_output("FR100"), "not-json"],
            ),
            patch.object(graph_module, "create_panel", return_value=SUCCESS) as create,
        ):
            state = graph_module.graph.invoke({
                "user_input": "在FR100创建14mm厚AH36板架，边界 >SL10"
            })

        self.assertEqual(state["decision_history"][-1].source, "fallback")
        self.assertTrue(state["execution_authorized"])
        create.assert_called_once()

    def test_unavailable_object_stops_with_controlled_error(self) -> None:
        with (
            patch.object(type(graph_module.llm), "invoke", side_effect=[
                action_output("停用曲面"),
                decision_output("stop", "OBJECT_UNAVAILABLE"),
            ]),
            patch.object(graph_module, "create_panel") as create,
        ):
            state = graph_module.graph.invoke({
                "user_input": "在停用曲面创建14mm厚AH36板架，边界 >SL10"
            })

        self.assertEqual(state["error_code"], "PROJECT_OBJECT_UNAVAILABLE")
        self.assertEqual(state["decision"].reason_code, "OBJECT_UNAVAILABLE")
        create.assert_not_called()

    def test_not_eligible_object_stops_before_cad(self) -> None:
        with (
            patch.object(type(graph_module.llm), "invoke", side_effect=[
                action_output("Boundary Only Surface"),
                decision_output("stop", "OBJECT_NOT_ELIGIBLE"),
            ]),
            patch.object(graph_module, "create_panel") as create,
        ):
            state = graph_module.graph.invoke({
                "user_input": "在Boundary Only Surface创建14mm厚AH36板架，边界 >SL10"
            })

        self.assertEqual(state["error_code"], "PROJECT_OBJECT_NOT_ELIGIBLE")
        create.assert_not_called()

    def test_safety_gate_rejects_missing_inspection(self) -> None:
        state = graph_module.safety_gate({
            "user_input": "创建板架",
            "action_plan": None,
            "decision_count": 1,
        })
        self.assertFalse(state["execution_authorized"])
        self.assertEqual(state["error_code"], "AGENT_SAFETY_GATE_REJECTED")

    def test_safety_gate_rejects_review_revision_mismatch(self) -> None:
        panel = PanelRequest(
            reference_plane="FR100",
            boundaries=[{"operator": ">", "target": "SL10"}],
            thickness=14,
            material="AH36",
        )
        inspection = inspect_project_context(panel)
        review = review_panel_design(panel, inspection).model_copy(
            update={"project_revision": "stale-revision"}
        )
        update = graph_module.safety_gate({
            "user_input": "创建板架",
            "action_plan": AgentActionPlan.model_validate(
                json.loads(action_output("FR100"))
            ),
            "panel_request": panel,
            "project_inspection": inspection,
            "design_review": review,
            "decision": AgentDecision(
                next_action="prepare_creation",
                reason_code="DESIGN_REVIEW_WARNING",
                observation="携带提醒继续。",
            ),
            "decision_count": 2,
        })

        self.assertFalse(update["execution_authorized"])
        self.assertEqual(
            update["authorization_reason"],
            "DESIGN_REVIEW_REVISION_MISMATCH",
        )

    def test_decision_limit_stops_without_another_llm_call(self) -> None:
        panel = PanelRequest(
            reference_plane="FR100",
            boundaries=[{"operator": ">", "target": "SL10"}],
            thickness=14,
            material="AH36",
        )
        with patch.object(type(graph_module.llm), "invoke") as invoke:
            update = graph_module.decide_after_inspection({
                "user_input": "创建板架",
                "panel_request": panel,
                "project_inspection": inspect_project_context(panel),
                "decision_count": graph_module.MAX_DECISION_STEPS,
                "decision_history": [],
                "decision": AgentDecision(
                    next_action="inspect_project_context",
                    reason_code="PROJECT_CONTEXT_UNVERIFIED",
                    observation="等待查询。",
                ),
            })

        self.assertEqual(update["decision"].reason_code, "DECISION_LIMIT_REACHED")
        invoke.assert_not_called()

    def test_execute_cad_requires_explicit_authorization(self) -> None:
        with patch.object(graph_module, "create_panel") as create:
            result = graph_module.execute_cad({"user_input": "创建板架"})
        self.assertEqual(result["error_code"], "AGENT_SAFETY_GATE_REJECTED")
        create.assert_not_called()

    def test_design_review_blocker_stops_before_cad(self) -> None:
        with (
            patch.object(type(graph_module.llm), "invoke", side_effect=[
                action_output("FR100"),
                decision_output("prepare_creation", "ALL_PRECONDITIONS_SATISFIED"),
            ]),
            patch.object(graph_module, "create_panel") as create,
        ):
            state = graph_module.graph.invoke({
                "user_input": "在FR100创建14mm厚AH36板架，边界 >FR100"
            })

        self.assertEqual(state["design_review"].outcome, "blocked")
        self.assertEqual(state["decision"].reason_code, "DESIGN_REVIEW_BLOCKED")
        self.assertEqual(state["decision_history"][-1].source, "safety_override")
        self.assertEqual(state["error_code"], "DESIGN_REVIEW_BLOCKED")
        create.assert_not_called()


if __name__ == "__main__":
    unittest.main()
