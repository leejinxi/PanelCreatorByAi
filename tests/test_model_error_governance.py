import json
import unittest
from unittest.mock import patch

import httpx

from tools.model_error_tools import (
    DATA_PATH,
    analyze_model_errors,
    build_panel_operation_details,
    execute_safe_repairs,
    group_model_errors,
    load_model_error_snapshot,
    ModelErrorProviderError,
)
from agent.model_error_graph import run_model_error_agent
from webapp.app import create_app


class ModelErrorToolTests(unittest.TestCase):
    def test_mock_snapshot_contains_raw_facts_not_pregrouped_decisions(self) -> None:
        payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        serialized = DATA_PATH.read_text(encoding="utf-8")

        self.assertEqual(len(payload["errors"]), 36)
        self.assertNotIn("groups", payload)
        self.assertNotIn("root_cause_code", serialized)
        self.assertNotIn('"route"', serialized)
        self.assertNotIn('"is_root"', serialized)

    def test_analyzes_explicit_mock_snapshot(self) -> None:
        report = analyze_model_errors()
        self.assertEqual(report.summary.total_errors, 36)
        self.assertEqual(report.summary.root_groups, 4)
        self.assertEqual(report.summary.cascade_errors, 23)
        self.assertEqual([group.route for group in report.groups], [
            "confirm_then_execute", "auto_execute", "manual", "provider_issue"
        ])
        self.assertEqual(
            report.groups[0].root_cause_code,
            "PANEL_BOUNDARY_SCHEMA_MIGRATION_INCOMPLETE",
        )
        self.assertEqual(
            report.groups[2].root_cause_code,
            "BRACKET_BOUNDARY_INVALID_AFTER_SUPPORT_UPDATE",
        )
        self.assertTrue(all(
            item.object_type == "bracket" for item in report.groups[2].objects
        ))
        self.assertEqual(
            report.groups[2].candidate.operation,
            "manual_boundary_reselection",
        )
        self.assertEqual(
            sum(item.is_root for group in report.groups for item in group.objects),
            13,
        )

    def test_agent_route_changes_when_provider_validation_fails(self) -> None:
        snapshot = load_model_error_snapshot()
        diagnostics = [
            item.model_copy(update={"provider_validation": "failed"})
            if item.object_id == "PANEL-FR108" else item
            for item in snapshot.diagnostics
        ]
        regrouped = group_model_errors(
            snapshot.model_copy(update={"diagnostics": diagnostics})
        )

        self.assertEqual(regrouped[0].route, "provider_issue")
        self.assertEqual(regrouped[0].candidate.provider_validation, "failed")

    def test_safe_repair_closes_two_groups(self) -> None:
        completed = execute_safe_repairs(
            analyze_model_errors(),
            confirmed_group_ids=["GROUP-A"],
        )
        self.assertEqual(completed.status, "completed")
        self.assertEqual(len(completed.resolved_error_ids), 26)
        self.assertEqual(len(completed.remaining_error_ids), 10)

    def test_builds_readonly_panel_operation_snapshot(self) -> None:
        report = analyze_model_errors()
        detail = build_panel_operation_details(report)[0]
        self.assertEqual(detail.operation_id, "OP-REPAIR-108-01")
        self.assertEqual(detail.panel_id, "PANEL-FR108")
        self.assertTrue(detail.readonly)
        self.assertEqual(detail.status, "planned")
        self.assertEqual(
            detail.request.target_boundary_schema_version,
            "0.2-poc",
        )
        self.assertEqual(detail.request.resolved_boundary_object_id, "LONG-BHD-02")

        completed = build_panel_operation_details(
            execute_safe_repairs(report, confirmed_group_ids=["GROUP-A"])
        )[0]
        self.assertEqual(completed.status, "simulated_completed")

    def test_user_policy_changes_low_risk_route(self) -> None:
        automatic = analyze_model_errors("安全项自动处理")
        confirmed = analyze_model_errors("所有修改都必须先确认")
        analysis_only = analyze_model_errors("只分析，不要修改模型")

        self.assertEqual(automatic.groups[1].route, "auto_execute")
        self.assertEqual(confirmed.groups[1].route, "confirm_then_execute")
        self.assertEqual(analysis_only.workflow_next_step, "report_only")

    def test_analysis_only_never_authorizes_repair(self) -> None:
        report = analyze_model_errors("只分析，不要修改模型")
        result = execute_safe_repairs(report, confirmed_group_ids=["GROUP-A", "GROUP-B"])

        self.assertEqual(result.status, "analyzed")
        self.assertEqual(result.resolved_error_ids, [])
        self.assertTrue(all(not item.authorized for item in result.authorization_results))

    def test_llm_selects_route_within_allowed_routes(self) -> None:
        class DecisionModel:
            def invoke(self, prompt: str) -> str:
                return json.dumps({
                    "project_id": "DEMO-SHIP-001",
                    "expected_project_revision": "DEMO-REV-18",
                    "intent": {
                        "mode": "execute_allowed",
                        "low_risk_policy": "require_confirmation",
                    },
                    "decisions": [
                        self._decision("GROUP-A", "confirm_then_execute", "AGENT-GROUP-A-UPDATE_PANEL", True),
                        self._decision("GROUP-B", "confirm_then_execute", "AGENT-GROUP-B-RECOMPUTE", True),
                        self._decision("GROUP-C", "manual", "AGENT-GROUP-C-MANUAL_BOUNDARY_RESELECTION", False),
                        self._decision("GROUP-D", "provider_issue", "AGENT-GROUP-D-REPORT_PROVIDER_ISSUE", False),
                    ],
                }, ensure_ascii=False)

            @staticmethod
            def _decision(group_id, route, candidate_id, confirmation):
                return {
                    "group_id": group_id,
                    "route": route,
                    "candidate_id": candidate_id,
                    "reason_code": "TEST_DECISION",
                    "observation": "依据结构化事实选择允许路线。",
                    "evidence": ["provider_validation=passed"],
                    "requires_confirmation": confirmation,
                }

        report = run_model_error_agent(
            "所有修改都必须先确认",
            decision_model=DecisionModel(),
        )

        self.assertEqual(report.groups[1].route, "confirm_then_execute")
        self.assertTrue(all(item.source == "llm" for item in report.decision_history))

    def test_llm_policy_violation_is_safely_overridden(self) -> None:
        class UnsafeDecisionModel:
            def invoke(self, prompt: str) -> str:
                payload = json.loads(DecisionModel().invoke(prompt))
                payload["decisions"][1]["route"] = "auto_execute"
                payload["decisions"][1]["requires_confirmation"] = False
                return json.dumps(payload, ensure_ascii=False)

        class DecisionModel:
            def invoke(self, prompt: str) -> str:
                baseline = analyze_model_errors("所有修改都必须先确认")
                return json.dumps({
                    "project_id": baseline.project_id,
                    "expected_project_revision": baseline.project_revision,
                    "intent": baseline.intent.model_dump(),
                    "decisions": [record.decision.model_dump() for record in baseline.decision_history],
                }, ensure_ascii=False)

        report = run_model_error_agent(
            "所有修改都必须先确认",
            decision_model=UnsafeDecisionModel(),
        )

        self.assertEqual(report.groups[1].route, "confirm_then_execute")
        self.assertEqual(report.groups[1].decision_source, "safety_override")


class ModelErrorApiTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _app():
        return create_app(
            governance_runner=lambda message: analyze_model_errors(message)
        )

    async def test_analyze_repair_and_status(self) -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self._app()), base_url="http://testserver"
        ) as client:
            analyzed = await client.post(
                "/api/model-errors/analyze",
                json={"message": "安全项自动处理"},
            )
            self.assertEqual(analyzed.status_code, 200)
            task_id = analyzed.json()["task_id"]
            repaired = await client.post(
                f"/api/model-errors/repair/{task_id}",
                json={"confirmed_group_ids": ["GROUP-A"]},
            )
            self.assertEqual(repaired.json()["status"], "completed")
            operation = await client.get("/api/operations/OP-REPAIR-108-01")
            self.assertEqual(operation.status_code, 200)
            self.assertEqual(operation.json()["status"], "simulated_completed")
            self.assertTrue(operation.json()["readonly"])
            status = await client.get(f"/api/model-errors/status/{task_id}")
            self.assertEqual(len(status.json()["remaining_error_ids"]), 10)

    async def test_unknown_task_is_controlled(self) -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self._app()), base_url="http://testserver"
        ) as client:
            response = await client.post("/api/model-errors/repair/missing")
            self.assertEqual(response.status_code, 404)
            operation = await client.get("/api/operations/missing")
            self.assertEqual(operation.status_code, 404)

    async def test_incompatible_snapshot_returns_actionable_error(self) -> None:
        def failing_runner(message: str):
            raise ModelErrorProviderError("private schema detail")

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(
                app=create_app(governance_runner=failing_runner)
            ),
            base_url="http://testserver",
        ) as client:
            response = await client.post("/api/model-errors/analyze")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"],
            "错误快照与当前服务版本不兼容，请重启演示服务后重试。",
        )


if __name__ == "__main__":
    unittest.main()
