"""Validate an MCP catalogue as inventory, without granting execution authority."""

import re
from collections.abc import Mapping


_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_.:-]{0,127}", re.ASCII)


def catalogue_names(payload: object) -> list[str]:
    """Return validated tool names in their original order.

    Names are inventory data only. No tool is invoked or authorized.
    """
    if not isinstance(payload, Mapping):
        raise TypeError("payload must be a mapping")
    if "tools" not in payload:
        raise ValueError("payload is missing tools")
    tools = payload["tools"]
    if not isinstance(tools, list):
        raise TypeError("tools must be a list")
    if not 1 <= len(tools) <= 2000:
        raise ValueError("tools must contain between 1 and 2000 descriptors")

    names: list[str] = []
    seen: set[str] = set()
    for descriptor in tools:
        if not isinstance(descriptor, dict):
            raise TypeError("each tool descriptor must be a dictionary")
        if "name" not in descriptor or "inputSchema" not in descriptor:
            raise ValueError("each descriptor requires name and inputSchema")
        name = descriptor["name"]
        if not isinstance(name, str):
            raise TypeError("tool name must be a string")
        if _NAME.fullmatch(name) is None:
            raise ValueError("invalid tool name")
        schema = descriptor["inputSchema"]
        if not isinstance(schema, dict):
            raise TypeError("inputSchema must be a dictionary")
        if "type" not in schema:
            raise ValueError("inputSchema is missing type")
        if not isinstance(schema["type"], str) or schema["type"] != "object":
            raise ValueError("inputSchema type must be object")
        if name in seen:
            raise ValueError("duplicate tool name")
        seen.add(name)
        names.append(name)
    return names
