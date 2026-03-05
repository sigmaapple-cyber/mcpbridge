import json
import unittest

from server import MCPServer


class FakeBridge:
    def __init__(self):
        self.calls = []

    def call(self, action, payload):
        self.calls.append((action, payload))
        return {"ok": True, "action": action, "payload": payload}


class MCPServerTests(unittest.TestCase):
    def setUp(self):
        self.bridge = FakeBridge()
        self.server = MCPServer(self.bridge)

    def test_initialize(self):
        resp = self.server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        self.assertEqual(resp["result"]["serverInfo"]["name"], "roblox-studio-mcpbridge")

    def test_tools_list(self):
        resp = self.server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        names = [t["name"] for t in resp["result"]["tools"]]
        self.assertIn("writescript", names)
        self.assertIn("getinstances", names)

    def test_tools_call_forwards(self):
        req = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "change",
                "arguments": {
                    "path": "game.Workspace.Part",
                    "property": "Anchored",
                    "value": True,
                },
            },
        }
        resp = self.server.handle(req)
        self.assertEqual(self.bridge.calls[0][0], "change")
        text = resp["result"]["content"][0]["text"]
        payload = json.loads(text)
        self.assertTrue(payload["ok"])

    def test_unknown_tool(self):
        req = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "missing", "arguments": {}},
        }
        resp = self.server.handle(req)
        self.assertIn("error", resp)


if __name__ == "__main__":
    unittest.main()
