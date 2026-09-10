import importlib
import json
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

from schemas.panel_schema import CadExecutionResult
from agent.main import build_accumulated_request
from agent.main import run_interactive_session

graph_module = importlib.import_module('agent.graph')


class BoundaryReferenceIsolationTests(unittest.TestCase):
    def run_case(self, text, reference):
        output = json.dumps({'action': 'create_panel', 'panel': {
            'reference_plane': reference, 'thickness': 14, 'material': 'AH36',
        }})
        with (patch.object(type(graph_module.llm), 'invoke', return_value=output),
              patch.object(graph_module, 'create_panel', return_value=CadExecutionResult(
                  success=True, message='mock', object_id='mock-1')) as create):
            state = graph_module.graph.invoke({'user_input': text})
        return state, create

    def test_boundary_cannot_supply_missing_plane_even_if_model_claims_it(self):
        for reference in (None, 'SL10', 'FR100', 'Deck A'):
            with self.subTest(reference=reference):
                state, create = self.run_case(
                    '创建14mm厚AH36板架，边界 >SL10 <FR100 >LV2 <"Deck A"', reference)
                self.assertIn('定位面', state['clarification'])
                create.assert_not_called()

    def test_unlabelled_expression_cannot_supply_missing_plane(self):
        state, create = self.run_case('创建14mm厚AH36板架 >SL10', None)
        self.assertIn('定位面', state['clarification'])
        create.assert_not_called()

    def test_actual_plane_is_recovered_without_boundary_pollution(self):
        for reference in (None, 'SL10', 'FR100'):
            with self.subTest(reference=reference):
                state, create = self.run_case(
                    '在第100肋位创建14mm厚AH36板架，边界 >SL10 <LV2', reference)
                self.assertEqual(state['panel_request'].reference_plane, 'FR100')
                create.assert_called_once()

    def test_unknown_positioning_name_still_passes_through(self):
        state, create = self.run_case('在Deck A创建板架，边界 >SL10', 'Deck A')
        self.assertEqual(state['panel_request'].reference_plane, 'Deck A')
        create.assert_called_once()

    def test_missing_boundary_stops_creation(self):
        state, create = self.run_case('在FR100创建14mm厚AH36板架', 'FR100')
        self.assertIn('至少1条', state['clarification'])
        create.assert_not_called()

    def test_one_boundary_is_sufficient(self):
        state, create = self.run_case('在FR100创建14mm厚AH36板架，边界 >SL10', 'FR100')
        self.assertEqual(state['panel_request'].boundaries[0].target, 'SL10')
        create.assert_called_once()

    def test_invalid_boundary_stops_even_with_valid_item(self):
        state, create = self.run_case('在FR100创建14mm厚AH36板架，边界 >SL10 >=LV2', 'FR100')
        self.assertIn('符号', state['clarification'])
        create.assert_not_called()

    def test_replacement_then_scalar_supplement_keeps_only_new_boundary(self):
        text = build_accumulated_request([
            '在FR100创建14mm厚板架，边界 >SL10',
            '边界全部改为 <LV2', '材料AH36',
        ])
        state, create = self.run_case(text, 'FR100')
        self.assertEqual([b.target for b in state['panel_request'].boundaries], ['LV2'])
        create.assert_called_once()

    def test_model_cannot_invent_or_flip_boundaries(self):
        output = json.dumps({'action':'create_panel', 'panel':{
            'reference_plane':'FR100', 'material':'AH36', 'thickness':14,
            'boundaries':[{'operator':'<','target':'SL10'}],
        }})
        with (patch.object(type(graph_module.llm), 'invoke', return_value=output),
              patch.object(graph_module, 'create_panel', return_value=CadExecutionResult(
                  success=True, message='mock', object_id='mock-1')) as create):
            missing = graph_module.graph.invoke({'user_input':'在FR100创建板架'})
            create.assert_not_called()
            self.assertTrue(missing['clarification'])
            state = graph_module.graph.invoke({'user_input':'在FR100创建板架，边界 >SL10'})
        self.assertEqual(state['panel_request'].boundaries[0].operator, '>')

    def test_boundary_supplement_recovers_unambiguous_source_scalars(self):
        output = json.dumps({'action':'create_panel', 'panel':{
            'reference_plane':None, 'material':None, 'thickness':None,
        }})
        text = build_accumulated_request(['在FR100创建14mm厚AH36板架', '边界 >SL10'])
        with (patch.object(type(graph_module.llm), 'invoke', return_value=output),
              patch.object(graph_module, 'create_panel', return_value=CadExecutionResult(
                  success=True, message='mock', object_id='mock-1')) as create):
            state = graph_module.graph.invoke({'user_input':text})
        self.assertEqual(state['panel_request'].thickness, 14)
        self.assertEqual(state['panel_request'].material, 'AH36')
        create.assert_called_once()

    def test_real_cli_loop_uses_shared_boundary_validation(self):
        output = json.dumps({'action':'create_panel','panel':{
            'reference_plane':'FR100', 'thickness':14, 'material':'AH36',
        }})
        with (patch('builtins.input', side_effect=['在FR100创建14mm厚AH36板架', '边界 >SL10']),
              patch.object(type(graph_module.llm), 'invoke', return_value=output),
              patch.object(graph_module, 'create_panel', return_value=CadExecutionResult(
                  success=True, message='mock', object_id='mock-1')) as create,
              redirect_stdout(StringIO()) as stdout):
            code = run_interactive_session()
        self.assertEqual(code, 0)
        create.assert_called_once()
        self.assertIn('至少1条', stdout.getvalue())
        self.assertIn('定位面：FR100', stdout.getvalue())
        self.assertIn('边界：>SL10', stdout.getvalue())


if __name__ == '__main__':
    unittest.main()
