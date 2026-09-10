import unittest

from agent.boundary_session import resolve_boundary_session, recover_missing_scalars
from agent.main import build_accumulated_request


class BoundarySessionTests(unittest.TestCase):
    def resolve(self, *turns):
        return resolve_boundary_session(build_accumulated_request(turns))

    def test_missing_then_one_boundary(self):
        initial = '在FR100创建14mm厚AH36板架'
        self.assertTrue(self.resolve(initial).issues)
        result = self.resolve(initial, '边界 >SL10')
        self.assertFalse(result.issues)
        self.assertEqual(result.boundaries[0].target, 'SL10')

    def test_append_and_unrelated_turn_preserve_boundaries(self):
        result = self.resolve('创建板架，边界 >SL10', '追加边界 <LV2', '材料AH36')
        self.assertFalse(result.issues)
        self.assertEqual([b.target for b in result.boundaries], ['SL10', 'LV2'])

    def test_whole_replacement_does_not_resurrect_old_items(self):
        result = self.resolve('边界 >SL10 <LV2', '边界全部改为 >LV8', '材料AH36')
        self.assertFalse(result.issues)
        self.assertEqual([b.target for b in result.boundaries], ['LV8'])

    def test_single_replacement_normalizes_old_target(self):
        result = self.resolve('边界 <sl 10 >LV2', '将 <SL10 改为 <SL12')
        self.assertFalse(result.issues)
        self.assertEqual([b.target for b in result.boundaries], ['SL12', 'LV2'])

    def test_ambiguous_update_cannot_execute_until_explicitly_resolved(self):
        result = self.resolve('边界 >SL10', '边界 >LV2', '材料AH36')
        self.assertTrue(result.issues)
        self.assertEqual(result.boundaries[0].target, 'SL10')
        result = self.resolve('边界 >SL10', '边界 >LV2', '边界全部改为 >LV8')
        self.assertFalse(result.issues)
        self.assertEqual(result.boundaries[0].target, 'LV8')

    def test_unmatched_replacement_is_not_an_append(self):
        result = self.resolve('边界 >SL10', '将 >LV2 改为 >LV8')
        self.assertTrue(result.issues)
        self.assertEqual(result.boundaries[0].target, 'SL10')

    def test_bad_fragment_survives_append_and_can_be_replaced(self):
        result = self.resolve('边界 >SL10 >=LV2', '追加边界 <LV8')
        self.assertTrue(result.issues)
        fixed = self.resolve('边界 >SL10 >=LV2', '将 >=LV2 改为 <LV2')
        self.assertFalse(fixed.issues)
        fixed = self.resolve('边界 SL10', '将 SL10 改为 >SL10')
        self.assertFalse(fixed.issues)

    def test_scalar_recovery_never_takes_coordinates_as_thickness(self):
        data = {'material': None, 'thickness': None}
        recover_missing_scalars(data, build_accumulated_request(['在X=10000mm创建板架', '材料AH36']))
        self.assertIsNone(data['thickness'])

    def test_conflicting_scalar_history_is_not_guessed(self):
        data = {'material': None, 'thickness': None}
        recover_missing_scalars(data, build_accumulated_request([
            '材料AH36，厚度14mm', '材料改为EH36，厚度改为16mm',
        ]))
        self.assertIsNone(data['material'])
        self.assertIsNone(data['thickness'])

    def test_expression_with_later_scalar_fields(self):
        result = self.resolve('边界 >SL10，材料AH36，定位面FR100，厚度14mm')
        self.assertFalse(result.issues)
        self.assertEqual(len(result.boundaries), 1)

    def test_quoted_keywords_are_not_edit_operations(self):
        result = self.resolve('边界 >"边界全部改为 A"')
        self.assertFalse(result.issues)
        self.assertEqual(result.boundaries[0].target, '边界全部改为 A')

    def test_quote_and_unknown_fragments_are_not_silently_dropped(self):
        for text in ('边界 >SL10 garbage', '边界 >SL10 <"Deck A', '边界 SL10'):
            with self.subTest(text=text):
                self.assertTrue(self.resolve(text).issues)

    def test_later_boundary_clauses_are_not_ignored(self):
        self.assertTrue(self.resolve('边界 >SL10。边界 >=LV2').issues)
        result = self.resolve('边界 >SL10，材料AH36，边界 <LV2')
        self.assertFalse(result.issues)
        self.assertEqual([b.target for b in result.boundaries], ['SL10', 'LV2'])
