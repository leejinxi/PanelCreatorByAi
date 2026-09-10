import unittest
from pathlib import Path
from unittest.mock import patch

from schemas.panel_schema import PanelRequest
from tests.contract_fixture import confirmed_boundary_contract
from mcp_client.stdio_client import McpProtocolError
from tools.cad_tools import CreatePanelTool
from tools.mcp_cad_backend import McpCadBackend


CONTRACT = Path(__file__).resolve().parents[1] / "contracts" / "FULL_contract_with_data.json"


def make_panel(reference_name: str = "FR100") -> PanelRequest:
    return PanelRequest(
        reference_plane=reference_name,
        thickness=14,
        material="AH36",
        boundaries=[{"operator": ">", "target": "DECK-A"}],
    )


class McpCadBackendTests(unittest.TestCase):
    def setUp(self):
        self.contract = confirmed_boundary_contract(self)

    def test_legacy_contract_stops_before_transport(self):
        backend = McpCadBackend(CONTRACT)
        with patch.object(backend.client, 'call_tool') as call:
            result = CreatePanelTool(backend).invoke(make_panel())
        self.assertEqual(result.error_code, 'MCP_CONTRACT_INCOMPATIBLE')
        call.assert_not_called()

    def test_unconfirmed_draft_stops_before_transport(self):
        backend = McpCadBackend(CONTRACT.with_name('boundary_list_0.2_draft.json'))
        with patch.object(backend.client, 'call_tool') as call:
            result = CreatePanelTool(backend).invoke(make_panel())
        self.assertEqual(result.error_code, 'CAD_BACKEND_CONFIG_ERROR')
        call.assert_not_called()

    def test_real_stdio_success(self) -> None:
        result = CreatePanelTool(McpCadBackend(self.contract)).invoke(make_panel())
        self.assertTrue(result.success)
        self.assertEqual(result.object_id, "mock-mcp-panel-001")

    def test_real_stdio_business_error_is_preserved(self) -> None:
        result = CreatePanelTool(McpCadBackend(self.contract)).invoke(make_panel("MISSING"))
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "REFERENCE_PLANE_NOT_FOUND")

    def test_maps_panel_request_to_mcp_field_names(self) -> None:
        backend = McpCadBackend(self.contract)
        payload = {"success": True, "message": "ok", "objectId": "PANEL-1", "errorCode": None}
        with patch.object(backend.client, "call_tool", return_value=payload) as call:
            result = backend.create_panel(make_panel())
        self.assertEqual(result, "PANEL-1")
        call.assert_called_once_with(
            "create_panel",
            {
                "referenceName": "FR100",
                "thicknessMm": 14.0,
                "material": "AH36",
                "boundaries": [{"operator": ">", "target": "DECK-A"}],
            },
        )

    def test_transport_and_response_failures_are_controlled(self) -> None:
        cases = [
            (TimeoutError(), "MCP_TIMEOUT"),
            (McpProtocolError('private'), "MCP_INVALID_RESPONSE"),
            (RuntimeError("secret"), "MCP_UNAVAILABLE"),
            ({"success": True}, "MCP_INVALID_RESPONSE"),
        ]
        for value, expected_code in cases:
            with self.subTest(expected_code=expected_code):
                backend = McpCadBackend(self.contract)
                mocked = (
                    patch.object(backend.client, "call_tool", return_value=value)
                    if isinstance(value, dict)
                    else patch.object(backend.client, "call_tool", side_effect=value)
                )
                with mocked:
                    result = CreatePanelTool(backend).invoke(make_panel())
                self.assertFalse(result.success)
                self.assertEqual(result.error_code, expected_code)
                self.assertNotIn("secret", result.message)
