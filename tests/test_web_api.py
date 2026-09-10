import importlib
import unittest
from unittest.mock import patch

import httpx

from schemas.panel_schema import CadExecutionResult, PanelRequest
from webapp.app import create_app


web_app_module = importlib.import_module("webapp.app")


class WebApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        environment = patch.dict("os.environ", {"CAD_BACKEND": "mock"})
        environment.start()
        self.addCleanup(environment.stop)
        self.received_messages: list[str] = []

        def successful_runner(message: str) -> dict:
            self.received_messages.append(message)
            return {
                "panel_request": PanelRequest(
                    boundaries=[{"operator": ">", "target": "SL10"}],
                    reference_plane="FR100",
                    thickness=14,
                    material="AH36",
                ),
                "cad_result": CadExecutionResult(
                    success=True,
                    message="Panel created successfully",
                    object_id="mock-panel-api-001",
                ),
            }

        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(
                app=create_app(agent_runner=successful_runner)
            ),
            base_url="http://testserver",
        )

    async def asyncTearDown(self) -> None:
        await self.client.aclose()

    async def test_health_check_does_not_run_agent(self) -> None:
        response = await self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "status": "ok",
                "mode": "mock",
                "agent": "ready",
                "cad_backend": "mock",
            },
        )
        self.assertEqual(self.received_messages, [])

    async def test_root_serves_browser_workbench(self) -> None:
        response = await self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("AI Ship CAD Copilot", response.text)
        self.assertIn('id="request-form"', response.text)
        self.assertIn('id="trace-pipeline"', response.text)
        self.assertIn('id="mcp-request-output"', response.text)
        self.assertIn('id="current-provider"', response.text)
        self.assertIn('id="decision-timeline"', response.text)
        self.assertIn('id="safety-gate"', response.text)
        self.assertNotIn('id="cad-preview-heading"', response.text)
        self.assertIn("DEMO MODE", response.text)

    async def test_mcp_mode_matches_health_and_simulated_result(self) -> None:
        with patch.dict("os.environ", {"CAD_BACKEND": " MCP "}):
            health = await self.client.get("/api/health")
            response = await self.client.post(
                "/api/agent/runs", json={"message": "创建板架"}
            )
        self.assertEqual(health.json()["mode"], "mcp")
        self.assertEqual(health.json()["cad_backend"], "mcp-contract-mock")
        self.assertEqual(response.json()["mode"], "mcp")
        self.assertIn("模拟", response.json()["message"])
        self.assertIn("模拟", response.json()["cad_result"]["message"])

    async def test_unknown_backend_health_is_not_ready(self) -> None:
        with patch.dict("os.environ", {"CAD_BACKEND": "unknown"}):
            response = await self.client.get("/api/health")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["mode"], "unconfigured")
        self.assertEqual(self.received_messages, [])

    async def test_mcp_health_does_not_construct_backend(self) -> None:
        with patch.dict("os.environ", {"CAD_BACKEND": "mcp"}):
            with patch("tools.cad_tools.build_cad_backend") as build:
                response = await self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        build.assert_not_called()
        self.assertEqual(self.received_messages, [])

    async def test_static_assets_are_available(self) -> None:
        css_response = await self.client.get("/static/styles.css")
        js_response = await self.client.get("/static/app.js")

        self.assertEqual(css_response.status_code, 200)
        self.assertIn("text/css", css_response.headers["content-type"])
        self.assertEqual(js_response.status_code, 200)
        self.assertIn("javascript", js_response.headers["content-type"])
        self.assertIn("当前为 Direct Mock 模式，不经过 MCP tools/call", js_response.text)
        self.assertIn("MCP Provider 未返回可确认结果", js_response.text)
        self.assertNotIn('"MCP Provider 未返回结果。"', js_response.text)

    async def test_run_endpoint_returns_stable_response(self) -> None:
        response = await self.client.post(
            "/api/agent/runs",
            json={"message": "  请在第100肋位创建板架  "},
        )

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.received_messages, ["请在第100肋位创建板架"])
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["mode"], "mock")
        self.assertEqual(payload["panel"]["referenceName"], "FR100")
        self.assertEqual(payload["panel"]["thicknessMm"], 14.0)
        self.assertEqual(payload["cad_result"]["object_id"], "mock-panel-api-001")
        self.assertEqual(len(payload["request_id"]), 32)

    async def test_blank_message_is_rejected_before_agent(self) -> None:
        response = await self.client.post(
            "/api/agent/runs",
            json={"message": "   "},
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.received_messages, [])

    async def test_unknown_request_field_is_rejected(self) -> None:
        response = await self.client.post(
            "/api/agent/runs",
            json={
                "message": "创建板架",
                "unexpected": True,
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.received_messages, [])

    async def test_oversized_message_is_rejected(self) -> None:
        response = await self.client.post(
            "/api/agent/runs",
            json={"message": "A" * 2001},
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.received_messages, [])

    async def test_response_mapping_failure_returns_safe_json(self) -> None:
        with patch("webapp.app.map_agent_state", side_effect=RuntimeError("private mapping detail")):
            response = await self.client.post(
                "/api/agent/runs",
                json={"message": "创建板架"},
            )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.headers["content-type"], "application/json")
        self.assertEqual(response.json()["error_code"], "AGENT_INTERNAL_ERROR")
        self.assertNotIn("private mapping detail", response.text)

    async def test_unexpected_runner_failure_returns_safe_error(self) -> None:
        def failing_runner(message: str) -> dict:
            raise RuntimeError("secret backend detail")

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(
                app=create_app(agent_runner=failing_runner)
            ),
            base_url="http://testserver",
        ) as client:
            with patch.object(web_app_module.logger, "exception"):
                response = await client.post(
                    "/api/agent/runs",
                    json={"message": "创建板架"},
                )

        payload = response.json()
        self.assertEqual(response.status_code, 500)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["error_code"], "AGENT_INTERNAL_ERROR")
        self.assertEqual(payload["steps"][0]["status"], "error")
        self.assertNotIn("secret backend detail", response.text)


if __name__ == "__main__":
    unittest.main()
