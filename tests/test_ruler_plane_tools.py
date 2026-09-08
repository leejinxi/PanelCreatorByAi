import unittest

from tools.ruler_plane_tools import (
    extract_known_ruler_plane_name,
    normalize_ruler_plane_name,
)


class RulerPlaneToolsTests(unittest.TestCase):
    def test_normalizes_chinese_frame_name(self) -> None:
        self.assertEqual(
            normalize_ruler_plane_name("第100肋位"),
            "FR100",
        )
        self.assertEqual(
            normalize_ruler_plane_name("100号肋位"),
            "FR100",
        )

    def test_normalizes_known_canonical_names(self) -> None:
        self.assertEqual(normalize_ruler_plane_name("fr 100"), "FR100")
        self.assertEqual(normalize_ruler_plane_name("sl -40"), "SL-40")
        self.assertEqual(normalize_ruler_plane_name("lv 50"), "LV50")

    def test_accepts_range_boundaries(self) -> None:
        self.assertEqual(normalize_ruler_plane_name("第-10肋位"), "FR-10")
        self.assertEqual(normalize_ruler_plane_name("FR200"), "FR200")
        self.assertEqual(normalize_ruler_plane_name("SL40"), "SL40")
        self.assertEqual(normalize_ruler_plane_name("LV-5"), "LV-5")

    def test_preserves_names_outside_known_ranges(self) -> None:
        self.assertEqual(
            normalize_ruler_plane_name("第201肋位"),
            "第201肋位",
        )
        self.assertEqual(normalize_ruler_plane_name("CUSTOM_A"), "CUSTOM_A")

    def test_extracts_unique_known_name_from_user_input(self) -> None:
        self.assertEqual(
            extract_known_ruler_plane_name(
                "请在第100肋位创建一块14mm厚的AH36板架"
            ),
            "FR100",
        )

    def test_does_not_guess_when_multiple_planes_are_present(self) -> None:
        self.assertIsNone(
            extract_known_ruler_plane_name("范围从FR10延伸到FR20")
        )


if __name__ == "__main__":
    unittest.main()
