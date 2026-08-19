import unittest

from schemas.panel_schema import PanelRequest
from tools.cad_tools import CadBackendError, CreatePanelTool, MockCadBackend


def make_panel_request() -> PanelRequest:
    return PanelRequest(
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
        result = CreatePanelTool(ExpectedFailureBackend()).invoke(
            make_panel_request()
        )

        self.assertFalse(result.success)
        self.assertEqual(result.message, "CAD 服务不可用")
        self.assertEqual(result.error_code, "CAD_UNAVAILABLE")

    def test_hides_unexpected_backend_exception_details(self) -> None:
        result = CreatePanelTool(UnexpectedFailureBackend()).invoke(
            make_panel_request()
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "CAD_INTERNAL_ERROR")
        self.assertNotIn("sensitive", result.message)

    def test_rejects_empty_backend_object_id(self) -> None:
        result = CreatePanelTool(EmptyObjectIdBackend()).invoke(
            make_panel_request()
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "CAD_INVALID_RESPONSE")

    def test_default_mock_backend_returns_mock_object_id(self) -> None:
        result = CreatePanelTool(MockCadBackend()).invoke(make_panel_request())

        self.assertTrue(result.success)
        self.assertTrue(result.object_id.startswith("mock-panel-"))


if __name__ == "__main__":
    unittest.main()
