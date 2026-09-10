import importlib
import json
import unittest
from unittest.mock import patch

import httpx

from agent.main import build_accumulated_request
from webapp.app import create_app

graph_module = importlib.import_module('agent.graph')


class WebBoundaryFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_then_one_boundary_calls_backend_only_once(self):
        output = json.dumps({'action': 'create_panel', 'panel': {
            'reference_plane': 'FR100', 'thickness': 14, 'material': 'AH36',
        }})
        original = graph_module.create_panel
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app()), base_url='http://test') as client:
            with (patch.dict('os.environ', {'CAD_BACKEND': 'mock'}),
                  patch.object(type(graph_module.llm), 'invoke', return_value=output),
                  patch.object(graph_module, 'create_panel', wraps=original) as call):
                turns = ['在FR100创建14mm厚AH36板架']
                first = (await client.post('/api/agent/runs', json={'message': turns[0]})).json()
                self.assertEqual(first['status'], 'clarification')
                self.assertEqual(first['panel']['boundaries'], [])
                self.assertTrue(first['panel']['boundary_issues'])
                call.assert_not_called()
                turns.append('边界 >SL10')
                second = (await client.post('/api/agent/runs', json={'message': build_accumulated_request(turns)})).json()
                self.assertEqual(second['status'], 'success')
                self.assertEqual(second['panel']['boundaries'], [{'operator': '>', 'target': 'SL10'}])
                self.assertEqual(second['panel']['material'], 'AH36')
                call.assert_called_once()

    async def test_old_mcp_contract_is_a_controlled_local_rejection(self):
        output = json.dumps({'action':'create_panel', 'panel':{
            'reference_plane':'FR100', 'thickness':14, 'material':'AH36',
        }})
        from tools.cad_tools import DEFAULT_MCP_CONTRACT_PATH
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app()), base_url='http://test') as client:
            with (patch.dict('os.environ', {'CAD_BACKEND':'mcp', 'MCP_CONTRACT_PATH': str(DEFAULT_MCP_CONTRACT_PATH.with_name('FULL_contract_with_data.json'))}),
                  patch.object(type(graph_module.llm), 'invoke', return_value=output),
                  patch('mcp_client.stdio_client.StdioMcpClient.call_tool') as call):
                response = (await client.post('/api/agent/runs', json={'message':'在FR100创建板架，边界 >SL10'})).json()
                self.assertEqual(response['error_code'], 'MCP_CONTRACT_INCOMPATIBLE')
                self.assertIsNone(response['execution_trace']['mcp_request'])
                call.assert_not_called()
