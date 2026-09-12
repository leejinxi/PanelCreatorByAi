import json
import tempfile
import unittest
from pathlib import Path

from schemas.panel_schema import PanelRequest
from tools.design_review_tools import DesignReviewError, review_panel_design
from tools.project_context_tools import inspect_project_context


def panel(
    *,
    reference: str = "FR100",
    boundary: str = "SL10",
    thickness: float = 14,
    material: str = "AH36",
) -> PanelRequest:
    return PanelRequest(
        reference_plane=reference,
        boundaries=[{"operator": ">", "target": boundary}],
        thickness=thickness,
        material=material,
    )


class DesignReviewToolsTests(unittest.TestCase):
    def test_reports_neighbor_difference_without_changing_request(self) -> None:
        request = panel()
        report = review_panel_design(request, inspect_project_context(request))

        self.assertEqual(report.outcome, "passed_with_warnings")
        self.assertEqual(report.plan_revision.disposition, "proceed_with_notice")
        self.assertEqual(request.thickness, 14)
        thickness = next(
            item for item in report.items if item.rule_id == "PANEL-DEMO-004"
        )
        self.assertEqual(thickness.status, "warning")
        self.assertEqual(len(report.nearby_panels), 2)

    def test_same_resolved_object_blocks_creation(self) -> None:
        request = panel(boundary="FR100")
        report = review_panel_design(request, inspect_project_context(request))

        self.assertEqual(report.outcome, "blocked")
        self.assertTrue(report.has_blocker())
        self.assertEqual(report.plan_revision.disposition, "stopped")

    def test_missing_neighbor_context_is_not_guessed(self) -> None:
        request = panel(reference="X=10000")
        report = review_panel_design(request, inspect_project_context(request))

        comparison_items = [
            item for item in report.items
            if item.rule_id in {"PANEL-DEMO-004", "PANEL-DEMO-005"}
        ]
        self.assertTrue(all(item.status == "not_checked" for item in comparison_items))
        self.assertEqual(report.outcome, "passed")

    def test_material_difference_is_a_warning(self) -> None:
        request = panel(material="DH36")
        report = review_panel_design(request, inspect_project_context(request))
        material = next(
            item for item in report.items if item.rule_id == "PANEL-DEMO-005"
        )
        self.assertEqual(material.status, "warning")
        self.assertEqual(request.material, "DH36")

    def test_capability_boundaries_remain_not_checked(self) -> None:
        request = panel()
        report = review_panel_design(request, inspect_project_context(request))
        statuses = {
            item.rule_id: item.status for item in report.items
        }
        self.assertEqual(statuses["PANEL-DEMO-006"], "not_checked")
        self.assertEqual(statuses["PANEL-DEMO-007"], "not_checked")
        self.assertEqual(statuses["PANEL-DEMO-008"], "not_checked")

    def test_invalid_context_file_returns_controlled_error(self) -> None:
        request = panel()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "context.json"
            path.write_text("not-json", encoding="utf-8")
            with self.assertRaises(DesignReviewError) as caught:
                review_panel_design(
                    request,
                    inspect_project_context(request),
                    context_path=path,
                )
        self.assertEqual(caught.exception.error_code, "DESIGN_REVIEW_DATA_INVALID")

    def test_revision_mismatch_returns_controlled_error(self) -> None:
        request = panel()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "context.json"
            path.write_text(json.dumps({
                "project_id": "demo-ship-001",
                "revision": "old-revision",
                "data_source": "mock",
                "reference_contexts": [],
            }), encoding="utf-8")
            with self.assertRaises(DesignReviewError) as caught:
                review_panel_design(
                    request,
                    inspect_project_context(request),
                    context_path=path,
                )
        self.assertEqual(caught.exception.error_code, "DESIGN_REVIEW_REVISION_MISMATCH")


if __name__ == "__main__":
    unittest.main()
