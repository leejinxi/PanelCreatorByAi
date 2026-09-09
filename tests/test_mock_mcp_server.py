import sys, unittest
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp_mock.contract import load_contract

ROOT=Path(__file__).resolve().parents[1]
CONTRACT=ROOT/"contracts"/"FULL_contract_with_data.json"
VALID={"referenceName":"FR100","thicknessMm":14,"material":"AH36","boundaries":{"top":None,"bottom":None,"left":None,"right":None}}

class MockMcpServerTests(unittest.IsolatedAsyncioTestCase):
    async def test_stdio_protocol_and_scenarios(self):
        self.assertEqual(load_contract(CONTRACT)["status"],"confirmed")
        params=StdioServerParameters(command=sys.executable,args=["-m","mcp_mock.server","--contract",str(CONTRACT)])
        async with stdio_client(params) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                listed=await session.list_tools()
                self.assertEqual([tool.name for tool in listed.tools],["create_panel"])
                success=await session.call_tool("create_panel",arguments=VALID)
                self.assertFalse(success.isError)
                self.assertEqual(success.structuredContent["objectId"],"mock-mcp-panel-001")
                failure=await session.call_tool("create_panel",arguments=dict(VALID,referenceName="MISSING"))
                self.assertTrue(failure.isError)
                self.assertEqual(failure.structuredContent["errorCode"],"REFERENCE_PLANE_NOT_FOUND")
                invalid=await session.call_tool("create_panel",arguments=dict(VALID,referenceName="   "))
                self.assertTrue(invalid.isError)
                self.assertEqual(invalid.structuredContent["errorCode"],"INVALID_REQUEST")
