#!/usr/bin/env python3
"""Roblox Studio MCP bridge server.

This server exposes MCP tools for editing Roblox instances/scripts by forwarding
requests to a local Roblox Studio bridge (typically an HttpService endpoint
provided by a Studio plugin/script).
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

JSONRPC_VERSION = "2.0"


@dataclass
class BridgeConfig:
    base_url: str = os.environ.get("ROBLOX_BRIDGE_URL", "http://127.0.0.1:8765")
    timeout_s: float = float(os.environ.get("ROBLOX_BRIDGE_TIMEOUT", "8"))


class RobloxBridgeClient:
    def __init__(self, config: Optional[BridgeConfig] = None) -> None:
        self.config = config or BridgeConfig()

    def call(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        body = json.dumps({"action": action, "payload": payload}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.config.base_url}/mcp",
            method="POST",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout_s) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {"ok": True}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Bridge HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                "Could not reach Roblox bridge. Is Studio running with the bridge script enabled?"
            ) from exc


TOOL_DEFS: List[Dict[str, Any]] = [
    {
        "name": "writescript",
        "description": "Create or overwrite the Source of a Script/LocalScript/ModuleScript by path.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Full instance path, e.g. game.ServerScriptService.MyScript"},
                "source": {"type": "string", "description": "Lua source to write."},
                "createIfMissing": {"type": "boolean", "default": False},
                "className": {"type": "string", "default": "Script"},
            },
            "required": ["path", "source"],
        },
    },
    {
        "name": "getinstances",
        "description": "Search instances in DataModel by class and/or name pattern.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "rootPath": {"type": "string", "default": "game"},
                "className": {"type": "string"},
                "nameContains": {"type": "string"},
                "maxResults": {"type": "integer", "default": 100},
            },
            "required": [],
        },
    },
    {
        "name": "change",
        "description": "Change a property on an instance path.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "property": {"type": "string"},
                "value": {"description": "JSON-serializable value"},
            },
            "required": ["path", "property", "value"],
        },
    },
    {
        "name": "create_instance",
        "description": "Create a new instance under a parent path.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "parentPath": {"type": "string"},
                "className": {"type": "string"},
                "name": {"type": "string"},
            },
            "required": ["parentPath", "className"],
        },
    },
    {
        "name": "delete_instance",
        "description": "Delete an instance by path.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "run_command",
        "description": "Run a custom bridge command for advanced workflows.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "args": {"type": "object", "default": {}},
            },
            "required": ["command"],
        },
    },
]


class MCPServer:
    def __init__(self, bridge: Optional[RobloxBridgeClient] = None) -> None:
        self.bridge = bridge or RobloxBridgeClient()

    def _result(self, req_id: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {"jsonrpc": JSONRPC_VERSION, "id": req_id, "result": payload}

    def _error(self, req_id: Any, code: int, message: str) -> Dict[str, Any]:
        return {
            "jsonrpc": JSONRPC_VERSION,
            "id": req_id,
            "error": {"code": code, "message": message},
        }

    def handle(self, request: Dict[str, Any]) -> Dict[str, Any]:
        req_id = request.get("id")
        method = request.get("method")

        if method == "initialize":
            return self._result(
                req_id,
                {
                    "protocolVersion": "2025-03-26",
                    "serverInfo": {"name": "roblox-studio-mcpbridge", "version": "0.1.0"},
                    "capabilities": {"tools": {}},
                },
            )

        if method == "tools/list":
            return self._result(req_id, {"tools": TOOL_DEFS})

        if method == "tools/call":
            params = request.get("params", {})
            tool_name = params.get("name")
            args = params.get("arguments", {})
            if not tool_name:
                return self._error(req_id, -32602, "Missing tool name")
            try:
                output = self._execute_tool(tool_name, args)
            except Exception as exc:  # noqa: BLE001 - transport error surfacing
                return self._error(req_id, -32000, str(exc))

            return self._result(
                req_id,
                {
                    "content": [{"type": "text", "text": json.dumps(output, ensure_ascii=False)}],
                    "isError": False,
                },
            )

        return self._error(req_id, -32601, f"Method not found: {method}")

    def _execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        if tool_name == "writescript":
            return self.bridge.call("writescript", args)
        if tool_name == "getinstances":
            return self.bridge.call("getinstances", args)
        if tool_name == "change":
            return self.bridge.call("change", args)
        if tool_name == "create_instance":
            return self.bridge.call("create_instance", args)
        if tool_name == "delete_instance":
            return self.bridge.call("delete_instance", args)
        if tool_name == "run_command":
            return self.bridge.call("run_command", args)
        raise ValueError(f"Unknown tool: {tool_name}")


def main() -> int:
    server = MCPServer()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue
        response = server.handle(request)
        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
