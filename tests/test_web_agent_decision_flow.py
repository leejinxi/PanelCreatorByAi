import importlib
import json
import unittest
from unittest.mock import patch

import httpx

from schemas.panel_schema import CadExecutionResult
from webapp.app import create_app


graph_module = importlib.import_module("agent.graph")


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


def decision_output(action: str, reason: str, message: str | None = None) -> str:
    return json.dumps({
        "next_action": action,
        "reason_code": reason,
        "observation": "已根据 Mock 工程上下文重新评估。",
        "evidence": ["project_context=mock"],
        "user_message": message,
    }, ensure_ascii=False)


class WebAgentDecisionFlowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        environment = patch.dict("os.environ", {"CAD_BACKEND": "mock"})
        environment.start()
        self.addCleanup(environment.stop)
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_app()),
            base_url="http://testserver",
        )
        self.addAsyncCleanup(self.client.aclose)

    async def test_success_exposes_two_decisions_inspection_and_gate(self) -> None:
        success = CadExecutionResult(
            success=True,
            message="created",
            object_id="mock-panel-web-decision",
        )
        with (
            patch.object(type(graph_module.llm), "invoke", side_effect=[
                action_output("FR100"),
                decision_output(
                    "prepare_creation", "ALL_PRECONDITIONS_SATISFIED"
                ),
            ]),
            patch.object(graph_module, "create_panel", return_value=success),
        ):
            response = await self.client.post("/api/agent/runs", json={
                "message": "在FR100创建14mm厚AH36板架，边界 >SL10 <LV5"
            })

        payload = response.json()
        trace = payload["execution_trace"]
        self.assertEqual(payload["status"], "success")
        self.assertEqual(len(trace["decision_steps"]), 2)
        self.assertEqual(trace["decision_steps"][0]["source"], "policy")
        self.assertEqual(trace["decision_steps"][1]["source"], "llm")
        self.assertEqual(trace["project_inspection"]["data_source_label"], "Mock Project Context")
        self.assertIsNone(trace["design_review"])
        self.assertTrue(trace["safety_gate"]["authorized"])
        self.assertEqual(
            [node["name"] for node in trace["nodes"]],
            [
                "qwen_parse",
                "policy_decision",
                "project_context",
                "design_review",
                "qwen_decision",
                "safety_gate",
                "provider",
            ],
        )
        self.assertNotIn("llm_raw_output", json.dumps(payload))

    async def test_ambiguous_reference_exposes_candidates_without_cad(self) -> None:
        with (
            patch.object(type(graph_module.llm), "invoke", side_effect=[
                action_output("主甲板"),
                decision_output(
                    "ask_clarification",
                    "REFERENCE_AMBIGUOUS",
                    "请选择 Main Deck A 或 Main Deck B。",
                ),
            ]),
            patch.object(graph_module, "create_panel") as create,
        ):
            response = await self.client.post("/api/agent/runs", json={
                "message": "在主甲板创建14mm厚AH36板架，边界 >SL10"
            })

        payload = response.json()
        match = payload["execution_trace"]["project_inspection"]["reference_plane"]
        self.assertEqual(payload["status"], "clarification")
        self.assertEqual(match["status"], "ambiguous")
        self.assertEqual(match["candidates"], ["Main Deck A", "Main Deck B"])
        self.assertFalse(payload["execution_trace"]["safety_gate"]["authorized"])
        create.assert_not_called()

    async def test_legacy_review_no_longer_blocks_creation(self) -> None:
        with (
            patch.object(type(graph_module.llm), "invoke", side_effect=[
                action_output("FR100"),
                decision_output("prepare_creation", "ALL_PRECONDITIONS_SATISFIED"),
            ]),
            patch.object(graph_module, "create_panel", return_value=CadExecutionResult(success=True, message="created", object_id="mock-panel-same-object")) as create,
        ):
            response = await self.client.post("/api/agent/runs", json={
                "message": "在FR100创建14mm厚AH36板架，边界 >FR100"
            })

        payload = response.json()
        self.assertEqual(payload["status"], "success")
        self.assertIsNone(payload["execution_trace"]["design_review"])
        create.assert_called_once()

    async def test_unknown_reference_is_safety_override(self) -> None:
        with (
            patch.object(type(graph_module.llm), "invoke", side_effect=[
                action_output("FR999"),
                decision_output(
                    "prepare_creation", "ALL_PRECONDITIONS_SATISFIED"
                ),
            ]),
            patch.object(graph_module, "create_panel") as create,
        ):
            response = await self.client.post("/api/agent/runs", json={
                "message": "在FR999创建14mm厚AH36板架，边界 >SL10"
            })

        payload = response.json()
        decisions = payload["execution_trace"]["decision_steps"]
        self.assertEqual(payload["status"], "clarification")
        self.assertEqual(decisions[-1]["source"], "safety_override")
        self.assertEqual(decisions[-1]["reason_code"], "REFERENCE_NOT_FOUND")
        self.assertIsNone(payload["cad_result"])
        create.assert_not_called()


if __name__ == "__main__":
    unittest.main()
