"""Validate the runtime boundary contract through an actual STDIO server."""
import sys
import unittest

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from tools.cad_tools import DEFAULT_MCP_CONTRACT_PATH


class BoundaryMcpContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_runtime_schema_rejects_invalid_boundaries(self):
        params = StdioServerParameters(command=sys.executable, args=[
            '-m', 'mcp_mock.server', '--contract', str(DEFAULT_MCP_CONTRACT_PATH),
        ])
        base = {'referenceName': 'FR100', 'thicknessMm': 14, 'material': 'AH36'}
        async with stdio_client(params) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                listing = await session.list_tools()
                schema = listing.tools[0].inputSchema['properties']['boundaries']
                self.assertEqual(schema['type'], 'array')
                self.assertEqual(schema['minItems'], 1)
                invalid = [None, [], {'top': 'SL10'},
                           [{'operator': '>=', 'target': 'SL10'}],
                           [{'operator': '>', 'target': ' '}],
                           [{'operator': '>'}],
                           [{'operator': '>', 'target': 'SL10', 'extra': True}]]
                for boundaries in invalid:
                    with self.subTest(boundaries=boundaries):
                        result = await session.call_tool('create_panel', arguments=dict(base, boundaries=boundaries))
                        self.assertTrue(result.isError)
                        self.assertEqual(result.structuredContent['errorCode'], 'INVALID_REQUEST')
                        self.assertIsNone(result.structuredContent['objectId'])
                missing = await session.call_tool('create_panel', arguments=base)
                self.assertEqual(missing.structuredContent['errorCode'], 'INVALID_REQUEST')
                for count in (1, 5):
                    result = await session.call_tool('create_panel', arguments=dict(base, boundaries=[
                        {'operator': '>', 'target': f'SL{i}'} for i in range(count)
                    ]))
                    self.assertFalse(result.isError)
                    self.assertEqual(result.structuredContent['objectId'], 'mock-mcp-panel-001')
