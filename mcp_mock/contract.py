import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


def load_contract(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8-sig"))
    if document.get("status") != "confirmed":
        raise ValueError("MCP contract is not confirmed")
    tools = document.get("tools")
    if not isinstance(tools, list) or not tools:
        raise ValueError("MCP contract does not define tools")
    for tool in tools:
        Draft202012Validator.check_schema(tool["inputSchema"])
        Draft202012Validator.check_schema(tool["outputSchema"])
        output_validator = Draft202012Validator(tool["outputSchema"])
        for response in tool.get("mockResponses", []):
            output_validator.validate(response["result"])
    return document


def response_matches(arguments: dict[str, Any], expected: dict[str, Any]) -> bool:
    return all(arguments.get(key) == value for key, value in expected.items())
