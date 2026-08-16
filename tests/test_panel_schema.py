import unittest

from pydantic import ValidationError

from schemas.panel_schema import (
    CadExecutionResult,
    PanelRequest,
)


class PanelRequestTests(unittest.TestCase):
    def test_accepts_and_normalizes_valid_request(self) -> None:
        request = PanelRequest.model_validate(
            {
                "type": "panel",
                "reference_plane": "  FR100  ",
                "boundaries": {
                    "top": " Deck-A ",
                    "bottom": "",
                    "left": None,
                    "right": "Longitudinal-1",
                },
                "thickness": 14,
                "material": " AH36 ",
            }
        )

        self.assertEqual(request.reference_plane, "FR100")
        self.assertEqual(request.material, "AH36")
        self.assertEqual(request.thickness, 14.0)
        self.assertEqual(request.boundaries.top, "Deck-A")
        self.assertIsNone(request.boundaries.bottom)

    def test_rejects_non_positive_thickness(self) -> None:
        for thickness in (0, -1):
            with self.subTest(thickness=thickness):
                with self.assertRaises(ValidationError):
                    PanelRequest(
                        reference_plane="FR100",
                        thickness=thickness,
                        material="AH36",
                    )

    def test_rejects_blank_required_text(self) -> None:
        for field_name in ("reference_plane", "material"):
            data = {
                "reference_plane": "FR100",
                "thickness": 14,
                "material": "AH36",
            }
            data[field_name] = "   "

            with self.subTest(field=field_name):
                with self.assertRaises(ValidationError):
                    PanelRequest.model_validate(data)

    def test_rejects_unknown_fields(self) -> None:
        with self.assertRaises(ValidationError):
            PanelRequest.model_validate(
                {
                    "reference_plane": "FR100",
                    "thickness": 14,
                    "material": "AH36",
                    "unexpected": "value",
                }
            )

    def test_rejects_unsupported_structure_type(self) -> None:
        with self.assertRaises(ValidationError):
            PanelRequest.model_validate(
                {
                    "type": "plate",
                    "reference_plane": "FR100",
                    "thickness": 14,
                    "material": "AH36",
                }
            )


class CadExecutionResultTests(unittest.TestCase):
    def test_accepts_structured_success_result(self) -> None:
        result = CadExecutionResult(
            success=True,
            message="Panel created successfully",
            object_id="PANEL-001",
        )

        self.assertTrue(result.success)
        self.assertEqual(result.object_id, "PANEL-001")
        self.assertIsNone(result.error_code)


if __name__ == "__main__":
    unittest.main()
