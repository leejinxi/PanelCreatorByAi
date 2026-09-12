import unittest

import httpx

from tools.model_error_tools import (
    analyze_model_errors,
    build_panel_operation_details,
    execute_safe_repairs,
)
from webapp.app import create_app


class ModelErrorToolTests(unittest.TestCase):
    def test_analyzes_explicit_mock_snapshot(self) -> None:
        report = analyze_model_errors()
        self.assertEqual(report.summary.total_errors, 36)
        self.assertEqual(report.summary.root_groups, 4)
        self.assertEqual(report.summary.cascade_errors, 23)
        self.assertEqual([group.route for group in report.groups], [
            "confirm_then_execute", "auto_execute", "manual", "provider_issue"
        ])

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


if __name__ == "__main__":
    unittest.main()
