import unittest
from math import inf

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
                "boundaries": [{"operator": ">", "target": " Deck-A "}],
                "thickness": 14,
                "material": " AH36 ",
            }
        )

        self.assertEqual(request.reference_plane, "FR100")
        self.assertEqual(request.material, "AH36")
        self.assertEqual(request.thickness, 14.0)
        self.assertEqual(request.boundaries[0].target, "Deck-A")
        self.assertEqual(request.boundaries[0].operator, ">")

    def test_rejects_non_positive_thickness(self) -> None:
        for thickness in (0, -1, inf):
            with self.subTest(thickness=thickness):
                with self.assertRaises(ValidationError):
                    PanelRequest(
                        boundaries=[{"operator": ">", "target": "SL10"}],
                        reference_plane="FR100",
                        thickness=thickness,
                        material="AH36",
                    )

    def test_rejects_blank_required_text(self) -> None:
        for field_name in ("reference_plane", "material"):
            data = {
                "boundaries": [{"operator": ">", "target": "SL10"}],
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
                    "boundaries": [{"operator": ">", "target": "SL10"}],
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
                    "boundaries": [{"operator": ">", "target": "SL10"}],
                    "reference_plane": "FR100",
                    "thickness": 14,
                    "material": "AH36",
                }
            )


    def test_rejects_missing_empty_and_legacy_boundaries(self):
        base = {'reference_plane':'FR100', 'thickness':14, 'material':'AH36'}
        for update in ({}, {'boundaries':[]}, {'boundaries':None}, {'boundaries':{'top':'SL10'}}):
            with self.subTest(update=update), self.assertRaises(ValidationError):
                PanelRequest.model_validate(base | update)


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

    def test_rejects_inconsistent_failure_result(self) -> None:
        with self.assertRaises(ValidationError):
            CadExecutionResult(
                success=False,
                message="创建失败",
            )

        with self.assertRaises(ValidationError):
            CadExecutionResult(
                success=False,
                message="创建失败",
                object_id="PANEL-001",
                error_code="CAD_ERROR",
            )



if __name__ == "__main__":
    unittest.main()
