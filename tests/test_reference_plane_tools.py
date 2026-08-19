import unittest

from pydantic import ValidationError

from schemas.reference_plane_schema import (
    ReferencePlaneRecord,
    ReferencePlaneResolution,
)
from tools.reference_plane_tools import resolve_reference_plane


class ReferencePlaneResolverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.planes = [
            ReferencePlaneRecord(
                name="DATUM_ALPHA",
                aliases=["A区基准", "Alpha Datum"],
                axis="X",
                coordinate_mm=10000,
            ),
            ReferencePlaneRecord(
                name="SURFACE_20",
                aliases=["20号曲面"],
                axis="Z",
                coordinate_mm=2000,
            ),
        ]

    def test_resolves_arbitrary_project_name_from_user_input(self) -> None:
        result = resolve_reference_plane(
            user_input="以DATUM_ALPHA为定位面创建板架",
            planes=self.planes,
        )

        self.assertEqual(result.status, "resolved")
        self.assertEqual(result.resolved.name, "DATUM_ALPHA")

    def test_resolves_project_alias_from_user_input(self) -> None:
        result = resolve_reference_plane(
            user_input="以A区基准为定位面创建板架",
            planes=self.planes,
        )

        self.assertEqual(result.status, "resolved")
        self.assertEqual(result.resolved.name, "DATUM_ALPHA")

    def test_resolves_coordinate_with_unit_conversion(self) -> None:
        result = resolve_reference_plane(
            user_input="在X=10m的位置创建板架",
            planes=self.planes,
        )

        self.assertEqual(result.status, "resolved")
        self.assertEqual(result.resolved.name, "DATUM_ALPHA")

    def test_uses_llm_reference_as_fallback(self) -> None:
        result = resolve_reference_plane(
            user_input="在指定曲面创建板架",
            planes=self.planes,
            llm_reference="SURFACE_20",
        )

        self.assertEqual(result.status, "resolved")
        self.assertEqual(result.resolved.name, "SURFACE_20")

    def test_reports_ambiguous_alias(self) -> None:
        planes = [
            ReferencePlaneRecord(
                name="DATUM_A",
                aliases=["公共基准"],
            ),
            ReferencePlaneRecord(
                name="DATUM_B",
                aliases=["公共基准"],
            ),
        ]

        result = resolve_reference_plane(
            user_input="以公共基准为定位面",
            planes=planes,
        )

        self.assertEqual(result.status, "ambiguous")
        self.assertEqual(len(result.candidates), 2)

    def test_reports_name_coordinate_conflict(self) -> None:
        result = resolve_reference_plane(
            user_input="以SURFACE_20为定位面，位置X=10000",
            planes=self.planes,
        )

        self.assertEqual(result.status, "conflict")
        self.assertEqual(len(result.candidates), 2)

    def test_reports_unknown_plane(self) -> None:
        result = resolve_reference_plane(
            user_input="在一个不存在的面创建板架",
            planes=self.planes,
            llm_reference="UNKNOWN_PLANE",
        )

        self.assertEqual(result.status, "not_found")
        self.assertIsNone(result.resolved)

    def test_rejects_negative_coordinate_tolerance(self) -> None:
        with self.assertRaisesRegex(ValueError, "容差"):
            resolve_reference_plane(
                user_input="在X=10000的位置创建板架",
                planes=self.planes,
                tolerance_mm=-0.1,
            )

    def test_normalizes_record_aliases_and_coordinate_system(self) -> None:
        plane = ReferencePlaneRecord(
            name="DATUM_C",
            aliases=[" 别名 ", "别名", "  "],
            coordinate_system=" Global ",
        )

        self.assertEqual(plane.aliases, ["别名"])
        self.assertEqual(plane.coordinate_system, "Global")

    def test_rejects_inconsistent_resolution_payload(self) -> None:
        with self.assertRaises(ValidationError):
            ReferencePlaneResolution(status="resolved")

        with self.assertRaises(ValidationError):
            ReferencePlaneResolution(
                status="ambiguous",
                candidates=[self.planes[0]],
            )


if __name__ == "__main__":
    unittest.main()
