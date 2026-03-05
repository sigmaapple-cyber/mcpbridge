# Roblox Studio MCP Server (for Codex)

This repo gives you a ready-to-run **MCP server** that exposes Roblox automation tools like:

- `writescript`
- `getinstances`
- `change`
- `create_instance`
- `delete_instance`
- `run_command`

It is designed for local development where Codex/any MCP client talks to this server over stdio, and the server forwards tool calls to a local Roblox Studio bridge endpoint.

## What you get

- `server.py`: MCP JSON-RPC stdio server.
- `roblox_plugin/MCPBridge.server.lua`: Roblox-side action handlers (drop into Studio and wire to your HTTP listener plugin).
- `tests/test_server.py`: basic unit tests.

## Quick start

```bash
python server.py
```

The server expects a local bridge at:

- `http://127.0.0.1:8765/mcp` (default)

Override with environment variables:

```bash
export ROBLOX_BRIDGE_URL=http://127.0.0.1:8765
export ROBLOX_BRIDGE_TIMEOUT=8
```

## Hook into Codex MCP config

Example MCP client entry:

```json
{
  "mcpServers": {
    "roblox": {
      "command": "python",
      "args": ["/workspace/mcpbridge/server.py"],
      "env": {
        "ROBLOX_BRIDGE_URL": "http://127.0.0.1:8765"
      }
    }
  }
}
```

## Roblox Studio side

1. Enable `HttpService` in your place settings.
2. Insert `roblox_plugin/MCPBridge.server.lua` in `ServerScriptService`.
3. Use or build a Studio plugin that hosts an HTTP listener and forwards incoming JSON payloads to `_G.MCPBridgeHandle(action, payload)`.

Payload shape expected by `server.py`:

```json
{
  "action": "writescript",
  "payload": {
    "path": "game.ServerScriptService.MyScript",
    "source": "print('hi')"
  }
}
```

## Notes

- Roblox Studio does not expose a first-party general-purpose HTTP server API, so the listener bridge must come from a plugin or external adapter.
- `run_command` is intentionally open-ended so you can add your own specialized Studio automation commands.
