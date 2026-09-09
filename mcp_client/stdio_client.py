import asyncio
import sys
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class McpProtocolError(RuntimeError):
    pass


class StdioMcpClient:
    def __init__(self, contract_path: Path, timeout_seconds: float = 10.0) -> None:
        if timeout_seconds <= 0:
            raise ValueError("MCP timeout must be positive")
        self.contract_path = contract_path.resolve()
        self.timeout_seconds = timeout_seconds

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return asyncio.run(self._call_tool(name, arguments))

    async def _call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "mcp_mock.server", "--contract", str(self.contract_path)],
        )
        async with asyncio.timeout(self.timeout_seconds):
            async with stdio_client(params) as streams:
                async with ClientSession(*streams) as session:
                    await session.initialize()
                    listed = await session.list_tools()
                    if name not in {tool.name for tool in listed.tools}:
                        raise McpProtocolError(f"MCP tool is not advertised: {name}")
                    result = await session.call_tool(name, arguments=arguments)
                    if not isinstance(result.structuredContent, dict):
                        raise McpProtocolError("MCP response has no structuredContent")
                    return result.structuredContent
