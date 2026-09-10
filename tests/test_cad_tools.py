import unittest
from pathlib import Path
from unittest.mock import patch

from schemas.panel_schema import PanelRequest
from tools.cad_tools import (
    DEFAULT_MCP_CONTRACT_PATH,
    CadBackendError,
    CreatePanelTool,
    MockCadBackend,
    build_cad_backend,
    create_panel,
)
from tools.mcp_cad_backend import McpCadBackend


def make_panel_request() -> PanelRequest:
    return PanelRequest(
        boundaries=[{"operator": ">", "target": "SL10"}],
        reference_plane="FR100",
        thickness=14,
        material="AH36",
    )


class SuccessfulBackend:
    def create_panel(self, panel: PanelRequest) -> str:
        self.received = panel
        return "PANEL-001"


class ExpectedFailureBackend:
    def create_panel(self, panel: PanelRequest) -> str:
        raise CadBackendError(
            "CAD 服务不可用",
            error_code="CAD_UNAVAILABLE",
        )


class UnexpectedFailureBackend:
    def create_panel(self, panel: PanelRequest) -> str:
        raise RuntimeError("sensitive backend details")


class EmptyObjectIdBackend:
    def create_panel(self, panel: PanelRequest) -> str:
        return "   "


class CreatePanelToolTests(unittest.TestCase):
    def test_exposes_stable_tool_metadata(self) -> None:
        tool = CreatePanelTool(SuccessfulBackend())

        self.assertEqual(tool.name, "create_panel")
        self.assertIs(tool.args_schema, PanelRequest)
        self.assertIn("定位面名称", tool.description)

    def test_maps_validated_input_to_backend_and_returns_success(self) -> None:
        backend = SuccessfulBackend()
        result = CreatePanelTool(backend).invoke(make_panel_request())

        self.assertTrue(result.success)
        self.assertEqual(result.object_id, "PANEL-001")
        self.assertIsInstance(backend.received, PanelRequest)
        self.assertEqual(backend.received.reference_plane, "FR100")

    def test_preserves_expected_backend_error_code(self) -> None:
        with self.assertLogs("tools.cad_tools", level="WARNING"):
            result = CreatePanelTool(ExpectedFailureBackend()).invoke(
                make_panel_request()
            )

        self.assertFalse(result.success)
        self.assertEqual(result.message, "CAD 服务不可用")
        self.assertEqual(result.error_code, "CAD_UNAVAILABLE")

    def test_hides_unexpected_backend_exception_details(self) -> None:
        with self.assertLogs("tools.cad_tools", level="ERROR"):
            result = CreatePanelTool(UnexpectedFailureBackend()).invoke(
                make_panel_request()
            )

        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "CAD_INTERNAL_ERROR")
        self.assertNotIn("sensitive", result.message)

    def test_rejects_empty_backend_object_id(self) -> None:
        with self.assertLogs("tools.cad_tools", level="WARNING"):
            result = CreatePanelTool(EmptyObjectIdBackend()).invoke(
                make_panel_request()
            )

        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "CAD_INVALID_RESPONSE")

    def test_default_mock_backend_returns_mock_object_id(self) -> None:
        result = CreatePanelTool(MockCadBackend()).invoke(make_panel_request())

        self.assertTrue(result.success)
        self.assertTrue(result.object_id.startswith("mock-panel-"))


class CadBackendConfigurationTests(unittest.TestCase):
    def test_defaults_to_mock_backend(self) -> None:
        backend = build_cad_backend({})

        self.assertIsInstance(backend, MockCadBackend)

    def test_explicit_mock_backend_is_case_insensitive(self) -> None:
        backend = build_cad_backend({"CAD_BACKEND": " Mock "})

        self.assertIsInstance(backend, MockCadBackend)

    def test_builds_mcp_backend_from_default_contract(self) -> None:
        backend = build_cad_backend({"CAD_BACKEND": "mcp"})

        self.assertIsInstance(backend, McpCadBackend)
        self.assertEqual(backend.client.contract_path, DEFAULT_MCP_CONTRACT_PATH)
        self.assertEqual(backend.client.timeout_seconds, 10.0)

    def test_builds_mcp_backend_from_explicit_settings(self) -> None:
        backend = build_cad_backend(
            {
                "CAD_BACKEND": "mcp",
                "MCP_CONTRACT_PATH": str(DEFAULT_MCP_CONTRACT_PATH),
                "MCP_TIMEOUT_SECONDS": "2.5",
            }
        )

        self.assertIsInstance(backend, McpCadBackend)
        self.assertEqual(backend.client.contract_path, DEFAULT_MCP_CONTRACT_PATH)
        self.assertEqual(backend.client.timeout_seconds, 2.5)

    def test_rejects_unknown_backend(self) -> None:
        with self.assertRaisesRegex(CadBackendError, "CAD_BACKEND") as raised:
            build_cad_backend({"CAD_BACKEND": "real-cad"})

        self.assertEqual(raised.exception.error_code, "CAD_BACKEND_CONFIG_ERROR")

    def test_rejects_missing_contract(self) -> None:
        with self.assertRaises(CadBackendError) as raised:
            build_cad_backend(
                {
                    "CAD_BACKEND": "mcp",
                    "MCP_CONTRACT_PATH": str(Path("missing-contract.json")),
                }
            )

        self.assertEqual(raised.exception.error_code, "CAD_BACKEND_CONFIG_ERROR")

    def test_rejects_invalid_timeout(self) -> None:
        for timeout in ("not-a-number", "0", "-1", "nan", "inf"):
            with self.subTest(timeout=timeout):
                with self.assertRaises(CadBackendError) as raised:
                    build_cad_backend(
                        {
                            "CAD_BACKEND": "mcp",
                            "MCP_TIMEOUT_SECONDS": timeout,
                        }
                    )
                self.assertEqual(
                    raised.exception.error_code,
                    "CAD_BACKEND_CONFIG_ERROR",
                )

    def test_create_panel_maps_backend_configuration_error(self) -> None:
        with patch.dict("os.environ", {"CAD_BACKEND": "invalid"}, clear=True):
            with self.assertLogs("tools.cad_tools", level="WARNING"):
                result = create_panel(make_panel_request())

        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "CAD_BACKEND_CONFIG_ERROR")

    def test_create_panel_uses_mcp_backend(self) -> None:
        with patch.dict("os.environ", {"CAD_BACKEND": "mcp"}, clear=True):
            with patch.object(
                McpCadBackend,
                "create_panel",
                return_value="mock-mcp-panel-configured",
            ) as invoke_backend:
                result = create_panel(make_panel_request())

        self.assertTrue(result.success)
        self.assertEqual(result.object_id, "mock-mcp-panel-configured")
        invoke_backend.assert_called_once()


if __name__ == "__main__":
    unittest.main()
