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
        completed = execute_safe_repairs(analyze_model_errors())
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

        completed = build_panel_operation_details(execute_safe_repairs(report))[0]
        self.assertEqual(completed.status, "simulated_completed")


class ModelErrorApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_analyze_repair_and_status(self) -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_app()), base_url="http://testserver"
        ) as client:
            analyzed = await client.post("/api/model-errors/analyze")
            self.assertEqual(analyzed.status_code, 200)
            task_id = analyzed.json()["task_id"]
            repaired = await client.post(f"/api/model-errors/repair/{task_id}")
            self.assertEqual(repaired.json()["status"], "completed")
            operation = await client.get("/api/operations/OP-REPAIR-108-01")
            self.assertEqual(operation.status_code, 200)
            self.assertEqual(operation.json()["status"], "simulated_completed")
            self.assertTrue(operation.json()["readonly"])
            status = await client.get(f"/api/model-errors/status/{task_id}")
            self.assertEqual(len(status.json()["remaining_error_ids"]), 10)

    async def test_unknown_task_is_controlled(self) -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_app()), base_url="http://testserver"
        ) as client:
            response = await client.post("/api/model-errors/repair/missing")
            self.assertEqual(response.status_code, 404)
            operation = await client.get("/api/operations/missing")
            self.assertEqual(operation.status_code, 404)

    async def test_incompatible_snapshot_returns_actionable_error(self) -> None:
        with patch(
            "webapp.app.analyze_model_errors",
            side_effect=ModelErrorProviderError("private schema detail"),
        ):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=create_app()),
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
