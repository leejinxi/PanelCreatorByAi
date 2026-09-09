import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from jsonschema import ValidationError, validate
from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from mcp_mock.contract import load_contract, response_matches


def build_server(contract: dict[str, Any]) -> Server:
    definitions = {tool["name"]: tool for tool in contract["tools"]}
    server = Server(contract["server"]["name"], version=contract["server"]["version"])

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [types.Tool(name=tool["name"], description=tool.get("description"), inputSchema=tool["inputSchema"], outputSchema=tool.get("outputSchema")) for tool in definitions.values()]

    @server.call_tool(validate_input=False)
    async def call_tool(name: str, arguments: dict[str, Any] | None) -> types.CallToolResult:
        tool = definitions.get(name)
        if tool is None:
            return make_error("TOOL_NOT_FOUND", f"Unknown MCP tool: {name}")
        actual = arguments or {}
        try:
            validate(actual, tool["inputSchema"])
        except ValidationError:
            return make_error("INVALID_REQUEST", "Tool arguments do not match inputSchema.")
        response = next((item["result"] for item in tool["mockResponses"] if response_matches(actual, item["match"])), None)
        if response is None:
            return make_error("MOCK_SCENARIO_NOT_FOUND", "No mock response matches the arguments.")
        validate(response, tool["outputSchema"])
        return make_result(response)

    return server


def make_error(code: str, message: str) -> types.CallToolResult:
    return make_result({"success": False, "message": message, "objectId": None, "errorCode": code})


def make_result(payload: dict[str, Any]) -> types.CallToolResult:
    content = types.TextContent(type="text", text=json.dumps(payload, ensure_ascii=False))
    return types.CallToolResult(content=[content], structuredContent=payload, isError=not payload["success"])


async def run_server(contract_path: Path) -> None:
    server = build_server(load_contract(contract_path))
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> None:
    parser = argparse.ArgumentParser(description="Contract-driven Mock MCP Server")
    parser.add_argument("--contract", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(run_server(args.contract.resolve()))


if __name__ == "__main__":
    main()
