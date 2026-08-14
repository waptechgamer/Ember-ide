import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from app.lsp.client import LspClient
from app.lsp.types import Range, Position, CodeAction, WorkspaceEdit, DocumentSymbol, SymbolInformation, SymbolKind

class TestLspClient(unittest.TestCase):
    def setUp(self):
        self.client = LspClient(command=["pylsp"])

    def test_initialization(self):
        with patch.object(self.client, "_call", return_value={"capabilities": {}}) as mock_call:
            res = self.client.initialize({"some_option": True})
            mock_call.assert_called_once()
            self.assertEqual(res, {"capabilities": {}})
            # Verify capabilities structure
            args, kwargs = mock_call.call_args
            self.assertIn("initializationOptions", args[1])
            self.assertEqual(args[1]["initializationOptions"], {"some_option": True})

    def test_notification_handling(self):
        mock_handler = MagicMock()
        self.client.register_notification_handler("textDocument/publishDiagnostics", mock_handler)

        # Manually trigger notification logic by calling _notification_handlers check
        # simulate receiving a message in _read_loop
        import json
        msg = {
            "jsonrpc": "2.0",
            "method": "textDocument/publishDiagnostics",
            "params": {"uri": "file://a.py", "diagnostics": []}
        }

        # Let's call the notification handler logic directly to test
        method = msg["method"]
        params = msg["params"]
        if method in self.client._notification_handlers:
            self.client._notification_handlers[method](params)

        mock_handler.assert_called_once_with(params)

    def test_rename(self):
        with patch.object(self.client, "_call", return_value={"changes": {}}) as mock_call:
            res = self.client.rename("file://a.py", 1, 2, "new_name")
            mock_call.assert_called_once_with("textDocument/rename", {
                "textDocument": {"uri": "file://a.py"},
                "position": {"line": 1, "character": 2},
                "newName": "new_name",
            })
            self.assertIsInstance(res, WorkspaceEdit)

    def test_signature_help(self):
        with patch.object(self.client, "_call", return_value={"signatures": []}) as mock_call:
            res = self.client.signature_help("file://a.py", 1, 2)
            mock_call.assert_called_once_with("textDocument/signatureHelp", {
                "textDocument": {"uri": "file://a.py"},
                "position": {"line": 1, "character": 2},
            })
            self.assertIsNotNone(res)

    def test_document_symbol(self):
        mock_response = [
            {
                "name": "MyClass",
                "kind": 5,
                "range": {"start": {"line": 0, "character": 0}, "end": {"line": 10, "character": 0}},
                "selectionRange": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 10}},
                "children": []
            }
        ]
        with patch.object(self.client, "_call", return_value=mock_response) as mock_call:
            res = self.client.document_symbol("file://a.py")
            mock_call.assert_called_once_with("textDocument/documentSymbol", {
                "textDocument": {"uri": "file://a.py"},
            })
            self.assertEqual(len(res), 1)
            self.assertIsInstance(res[0], DocumentSymbol)

    def test_workspace_symbol(self):
        mock_response = [
            {
                "name": "MyClass",
                "kind": 5,
                "location": {
                    "uri": "file://a.py",
                    "range": {"start": {"line": 0, "character": 0}, "end": {"line": 10, "character": 0}}
                }
            }
        ]
        with patch.object(self.client, "_call", return_value=mock_response) as mock_call:
            res = self.client.workspace_symbol("MyClass")
            mock_call.assert_called_once_with("workspace/symbol", {
                "query": "MyClass",
            })
            self.assertEqual(len(res), 1)
            self.assertIsInstance(res[0], SymbolInformation)

    def test_code_action(self):
        mock_response = [
            {
                "title": "Fix import",
                "kind": "quickfix"
            }
        ]
        with patch.object(self.client, "_call", return_value=mock_response) as mock_call:
            rng = Range(Position(0, 0), Position(0, 10))
            res = self.client.code_action("file://a.py", rng, {"diagnostics": []})
            mock_call.assert_called_once_with("textDocument/codeAction", {
                "textDocument": {"uri": "file://a.py"},
                "range": rng.to_lsp(),
                "context": {"diagnostics": []},
            })
            self.assertEqual(len(res), 1)
            self.assertIsInstance(res[0], CodeAction)

if __name__ == "__main__":
    unittest.main()
