"""Web/Graph/MCP 集成：固定模型输出，业务场景使用真实 STDIO 子进程。"""

import importlib
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from mcp_client.stdio_client import StdioMcpClient
from webapp.app import create_app
from agent.main import build_accumulated_request
from tests.contract_fixture import confirmed_boundary_contract


graph_module = importlib.import_module("agent.graph")
CONTRACT = Path(__file__).resolve().parents[1] / "contracts" / "FULL_contract_with_data.json"


def model_output(**overrides) -> str:
    panel = {
        "type": "panel",
        "reference_plane": "第100肋位",
        "thickness": 14,
        "material": "AH36",
        "boundaries": [{"operator": ">", "target": "DECK-A"}],
    }
    panel.update(overrides)
    return json.dumps({"action": "create_panel", "panel": panel}, ensure_ascii=False)


class WebMcpIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        environment = patch.dict("os.environ", {
            "CAD_BACKEND": "mcp",
            "MCP_CONTRACT_PATH": "",
            "MCP_TIMEOUT_SECONDS": "10",
        })
        environment.start()
        self.addCleanup(environment.stop)
        # 使用真实默认 Agent Runner，不替换 Graph、CAD Tool 或响应映射。
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_app()),
            base_url="http://testserver",
        )
        self.addAsyncCleanup(self.client.aclose)

    async def run_output(self, output: str) -> dict:
        panel = json.loads(output).get("panel") or {}
        reference = panel.get("reference_plane") or ""
        message = f"在{reference}创建板架，边界 >DECK-A"
        with patch.object(type(graph_module.llm), "invoke", return_value=output):
            response = await self.client.post(
                "/api/agent/runs", json={"message": message},
            )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["mode"], "mcp")
        self.assertEqual(len(payload["request_id"]), 32)
        self.assertNotIn("llm_raw_output", payload)
        return payload

    async def test_real_stdio_success_and_field_mapping(self) -> None:
        # spy 记录参数后继续调用真实传输，以证明请求确实到达 MCP。
        original = StdioMcpClient.call_tool
        with patch.object(StdioMcpClient, "call_tool", autospec=True,
                          side_effect=original) as call:
            result = await self.run_output(model_output())
        call.assert_called_once()
        self.assertEqual(call.call_args.args[1], "create_panel")
        self.assertEqual(call.call_args.args[2], {
            "referenceName": "FR100", "thicknessMm": 14.0, "material": "AH36",
            "boundaries": [{"operator": ">", "target": "DECK-A"}],
        })
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["panel"]["referenceName"], "FR100")
        self.assertEqual(result["panel"]["boundaries"][0]["target"], "DECK-A")
        self.assertEqual(result["cad_result"]["object_id"], "mock-mcp-panel-001")
        self.assertIn("模拟", result["message"])
        self.assertIn("模拟", result["cad_result"]["message"])
        self.assertEqual(
            [s["status"] for s in result["steps"]],
            ["success", "success", "success", "attention", "success", "success", "success"],
        )
        trace = result["execution_trace"]
        self.assertEqual(
            [node["name"] for node in trace["nodes"]],
            [
                "qwen_parse", "policy_decision", "project_context",
                "design_review", "qwen_decision", "safety_gate", "provider",
            ],
        )
        self.assertEqual(trace["provider"], "contract-mock")
        self.assertTrue(trace["simulated"])
        self.assertEqual(trace["mcp_request"]["tool"], "create_panel")
        self.assertEqual(trace['mcp_request']['contract_version'], '0.2-poc')
        self.assertEqual(
            trace["mcp_request"]["arguments"]["referenceName"],
            "FR100",
        )
        self.assertEqual(
            trace["mcp_response"]["object_id"],
            "mock-mcp-panel-001",
        )
        provider_node = next(
            node for node in trace["nodes"] if node["name"] == "provider"
        )
        self.assertEqual(provider_node["status"], "success")
        self.assertIsNotNone(provider_node["duration_ms"])

    async def test_real_stdio_reference_not_found(self) -> None:
        result = await self.run_output(model_output(reference_plane="MISSING"))
        self.assertEqual(result["panel"]["referenceName"], "MISSING")
        self.assertEqual(result["status"], "clarification")
        self.assertIn("MISSING", result["message"])
        self.assertIsNone(result["cad_result"])
        self.assertIsNone(result["execution_trace"]["mcp_request"])

    async def test_boundary_clarification_then_real_stdio_creation(self):
        turns = ['在FR100创建14mm厚AH36板架']
        with (patch.object(type(graph_module.llm), 'invoke', return_value=model_output()),
              patch.object(StdioMcpClient, 'call_tool', autospec=True,
                           side_effect=StdioMcpClient.call_tool) as call):
            for message in (turns[0], turns[0] + '，边界 >=SL10'):
                result = (await self.client.post('/api/agent/runs', json={'message': message})).json()
                self.assertEqual(result['status'], 'clarification')
                self.assertIsNone(result['execution_trace']['mcp_request'])
                call.assert_not_called()
            turns.append('边界 >SL10')
            result = (await self.client.post('/api/agent/runs', json={
                'message': build_accumulated_request(turns),
            })).json()
            self.assertEqual(result['status'], 'success')
            call.assert_called_once()
            self.assertEqual(result['execution_trace']['mcp_request']['arguments']['boundaries'],
                             [{'operator': '>', 'target': 'SL10'}])
            self.assertEqual(result['execution_trace']['mcp_request']['contract_version'], '0.2-poc')

    async def test_real_stdio_cad_unavailable(self) -> None:
        result = await self.run_output(model_output(material="UNAVAILABLE"))
        self.assert_cad_error(result, "CAD_UNAVAILABLE")

    async def test_missing_parameters_stop_before_backend(self) -> None:
        for field in ("reference_plane", "material", "thickness"):
            with self.subTest(field=field):
                with patch("tools.cad_tools.build_cad_backend") as build:
                    result = await self.run_output(model_output(**{field: None}))
                build.assert_not_called()
                self.assertEqual(result["status"], "clarification")
                self.assertIsNone(result["cad_result"])
                self.assertEqual(result["steps"][-1]["status"], "skipped")
                trace = result["execution_trace"]
                self.assertIsNone(trace["mcp_request"])
                self.assertIsNone(trace["mcp_response"])
                self.assertEqual(
                    next(
                        node["status"]
                        for node in trace["nodes"]
                        if node["name"] == "provider"
                    ),
                    "skipped",
                )

    async def test_unsupported_stops_before_backend(self) -> None:
        with patch("tools.cad_tools.build_cad_backend") as build:
            result = await self.run_output(json.dumps({"action": "unsupported", "panel": None}))
        build.assert_not_called()
        self.assertEqual(result["status"], "unsupported")
        self.assertIsNone(result["cad_result"])

    async def test_invalid_parameters_stop_before_backend(self) -> None:
        with patch("tools.cad_tools.build_cad_backend") as build:
            result = await self.run_output(model_output(thickness=-5))
        build.assert_not_called()
        self.assertEqual(result["status"], "error")
        self.assertIsNone(result["cad_result"])
        self.assertEqual(result["steps"][-1]["status"], "skipped")

    async def test_transport_failures_reach_web_safely_without_retry(self) -> None:
        # 故障注入只替换传输边界，其余链路保持真实；不依赖墙钟超时。
        for failure, code in ((TimeoutError("private detail"), "MCP_TIMEOUT"),
                              (RuntimeError("private detail"), "MCP_UNAVAILABLE")):
            with self.subTest(code=code):
                with patch.object(StdioMcpClient, "call_tool", side_effect=failure) as call:
                    result = await self.run_output(model_output())
                call.assert_called_once()
                self.assert_cad_error(result, code)
                self.assertNotIn("private detail", json.dumps(result))

    async def test_malformed_mcp_payload_reaches_web_safely(self) -> None:
        with patch.object(StdioMcpClient, "call_tool", return_value={"success": True}) as call:
            result = await self.run_output(model_output())
        call.assert_called_once()
        self.assert_cad_error(result, "MCP_INVALID_RESPONSE")

    def assert_cad_error(self, result: dict, code: str) -> None:
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error_code"], code)
        self.assertEqual(result["cad_result"]["error_code"], code)
        self.assertFalse(result["cad_result"]["success"])
        self.assertIsNone(result["cad_result"]["object_id"])
        self.assertEqual([s["status"] for s in result["steps"]],
                         ["success", "success", "success", "attention",
                          "success", "success", "error"])
