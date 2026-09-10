import unittest

from pydantic import ValidationError

from schemas.boundary_schema import BoundaryConstraint, ValidatedBoundaries
from tools.boundary_tools import mask_boundary_text, parse_boundary_expressions
from tools.ruler_plane_tools import extract_known_ruler_plane_name


class BoundaryToolsTests(unittest.TestCase):
    def test_normalization_preserves_operators_and_source_offsets(self):
        text = '＞ sl -10，<SL10; >LV2\n<"Deck A" >第100肋位'
        result = parse_boundary_expressions(text)
        self.assertFalse(result.issues)
        self.assertEqual([(b.operator, b.target) for b in result.boundaries], [
            (">", "SL-10"), ("<", "SL10"), (">", "LV2"),
            ("<", "Deck A"), (">", "FR100"),
        ])
        self.assertEqual(len(result.to_execution().boundaries), 5)
        for item in result.candidates:
            self.assertEqual(text[item.start:item.end], item.raw)

    def test_duplicates_count_once_and_opposite_operators_remain(self):
        result = parse_boundary_expressions('<sl 10 <SL10 >SL10 >LV2 <LV8')
        self.assertEqual(result.duplicate_indices, [1])
        self.assertEqual(len(result.to_execution().boundaries), 4)
        self.assertEqual(result.boundaries[0].operator, "<")
        self.assertEqual(result.boundaries[1].operator, ">")

    def test_missing_boundaries_cannot_execute(self):
        for text in ('', ' '):
            with self.subTest(text=text):
                result = parse_boundary_expressions(text)
                self.assertIn('BOUNDARY_COUNT_INSUFFICIENT', [i.code for i in result.issues])
                with self.assertRaises(ValueError):
                    result.to_execution()

    def test_one_or_more_boundaries_can_execute(self):
        for text, count in (('>SL10', 1), ('>SL10 <LV2', 2),
                            ('>SL10 <LV2 >LV8', 3),
                            ('<SL10 <sl 10 <SL10 <SL10', 1)):
            with self.subTest(text=text):
                result = parse_boundary_expressions(text)
                self.assertFalse(result.issues)
                self.assertEqual(len(result.to_execution().boundaries), count)

    def test_invalid_fragment_blocks_even_with_one_valid_item(self):
        result = parse_boundary_expressions('>SL10 >=LV2')
        self.assertEqual(len(result.boundaries), 1)
        with self.assertRaises(ValueError):
            result.to_execution()

    def test_invalid_fragment_blocks_even_with_four_valid_items(self):
        for invalid in ('SL20', '>', '<   ', '>=SL10', '<=LV2', '>>SL10',
                        '> =SL10', '<""', '<"Deck A', '<"Deck A"tail', '<Deck"A'):
            with self.subTest(invalid=invalid):
                result = parse_boundary_expressions('>SL-10 <SL10 >LV2 <LV8; ' + invalid)
                self.assertTrue(result.issues)
                with self.assertRaises(ValueError):
                    result.to_execution()
                self.assertTrue(any(item.raw.strip() == invalid.strip() for item in result.candidates))

    def test_unknown_names_and_quoted_delimiters_are_preserved(self):
        result = parse_boundary_expressions('>sl 999 <"Deck A, < FR100" >舱壁A <LV8')
        self.assertEqual(result.boundaries[0].target, 'sl 999')
        self.assertEqual(result.boundaries[1].target, 'Deck A, < FR100')
        self.assertFalse(result.issues)

    def test_execution_schema_rejects_invalid_operator_empty_target_and_extra_fields(self):
        for data in ({'operator': '>=', 'target': 'SL10'},
                     {'operator': '<', 'target': ' '},
                     {'operator': '<', 'target': 'SL10', 'exists': True}):
            with self.subTest(data=data), self.assertRaises(ValidationError):
                BoundaryConstraint.model_validate(data)

    def test_execution_schema_cannot_bypass_unique_count(self):
        for boundaries in ([], None,
                           {'top': 'SL10', 'bottom': None, 'left': None, 'right': None}):
            with self.subTest(boundaries=boundaries), self.assertRaises(ValidationError):
                ValidatedBoundaries(boundaries=boundaries)

    def test_execution_schema_accepts_one_and_deduplicates(self):
        for boundaries in ([{'operator': '<', 'target': 'SL10'}],
                           [{'operator': '<', 'target': 'SL10'}] * 4):
            self.assertEqual(len(ValidatedBoundaries(boundaries=boundaries).boundaries), 1)

    def test_mask_retains_only_positioning_plane(self):
        for text in ('在FR100创建板架，边界 >SL-10 <SL10 >LV2 <LV8',
                     '在第100肋位创建板架 >SL-10 <SL10 >LV2 <LV8',
                     '边界 >SL-10 <SL10，定位面为FR100，厚度14mm',
                     '在FR100创建板架，边界 <"FR200, Deck A" >LV8'):
            with self.subTest(text=text):
                masked = mask_boundary_text(text)
                self.assertEqual(len(masked), len(text))
                self.assertEqual(extract_known_ruler_plane_name(masked), 'FR100')

    def test_missing_plane_is_not_recovered_from_boundary(self):
        for text in ('创建板架，边界 >SL10', '创建板架 >SL10',
                     '创建板架，边界 SL10', '创建板架，边界 <"FR100"',
                     '创建板架，边界 <"材料:FR100" >LV2',
                     '创建板架，边界 >材料:FR100',
                     '创建板架，边界:\nSL10',
                     '创建板架\n用户第1次补充：边界 >SL10'):
            with self.subTest(text=text):
                self.assertIsNone(extract_known_ruler_plane_name(mask_boundary_text(text)))


    def test_mask_preserves_later_turn_positioning_plane(self):
        text = '初始需求：创建板架，边界 >SL10\n用户第1次补充：在FR100创建'
        self.assertEqual(extract_known_ruler_plane_name(mask_boundary_text(text)), 'FR100')


if __name__ == '__main__':
    unittest.main()
