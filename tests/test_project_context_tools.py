import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from schemas.panel_schema import PanelRequest
from tools.project_context_tools import (
    ProjectContextError,
    extract_demo_reference_query,
    inspect_project_context,
    load_demo_project_catalog,
    resolve_demo_object,
)


class ProjectContextToolsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = load_demo_project_catalog()

    def test_inspects_reference_and_boundaries(self) -> None:
        result = inspect_project_context(PanelRequest(
            reference_plane="FR100",
            boundaries=[
                {"operator": ">", "target": "SL10"},
                {"operator": "<", "target": "LV5"},
            ],
            thickness=14,
            material="AH36",
        ))
        self.assertTrue(result.all_resolved())
        self.assertEqual(result.data_source, "mock")
        self.assertEqual(result.reference_plane.resolved_object_id, "ruler-fr-100")
        self.assertEqual([item.query for item in result.boundaries], ["SL10", "LV5"])

    def test_alias_can_be_ambiguous(self) -> None:
        result = resolve_demo_object(
            "主甲板", role="reference_plane", catalog=self.catalog
        )
        self.assertEqual(result.status, "ambiguous")
        self.assertEqual(result.candidates, ["Main Deck A", "Main Deck B"])

    def test_recovers_explicit_reference_alias_from_source(self) -> None:
        self.assertEqual(
            extract_demo_reference_query("请在主甲板创建一块板架"),
            "主甲板",
        )
        self.assertEqual(
            extract_demo_reference_query("请在 FR999 创建一块板架"),
            "FR999",
        )

    def test_unknown_object_is_not_found(self) -> None:
        result = resolve_demo_object(
            "FR999", role="reference_plane", catalog=self.catalog
        )
        self.assertEqual(result.status, "not_found")

    def test_unavailable_and_role_restriction_are_distinct(self) -> None:
        unavailable = resolve_demo_object(
            "停用曲面", role="reference_plane", catalog=self.catalog
        )
        restricted = resolve_demo_object(
            "仅边界曲面", role="reference_plane", catalog=self.catalog
        )
        self.assertEqual(unavailable.status, "unavailable")
        self.assertEqual(restricted.status, "not_eligible")

    def test_ruler_normalization_preserves_negative_index(self) -> None:
        result = resolve_demo_object(
            "SL -10", role="boundary", catalog=self.catalog
        )
        self.assertEqual(result.status, "resolved")
        self.assertEqual(result.resolved_name, "SL-10")

    def test_missing_and_invalid_catalog_are_controlled(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(ProjectContextError) as missing:
                load_demo_project_catalog(root / "missing.json")
            self.assertEqual(missing.exception.error_code, "PROJECT_CONTEXT_LOAD_ERROR")

            invalid = root / "invalid.json"
            invalid.write_text("{}", encoding="utf-8")
            with self.assertRaises(ProjectContextError) as malformed:
                load_demo_project_catalog(invalid)
            self.assertEqual(malformed.exception.error_code, "PROJECT_CONTEXT_INVALID")


if __name__ == "__main__":
    unittest.main()
