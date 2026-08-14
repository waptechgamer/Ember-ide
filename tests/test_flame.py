import unittest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.utils.flame_engine import convert_flame_file, validate_and_clean_code, generate_offline_fallback

class TestFlameEngine(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_target_detection_python(self):
        flame_file = self.dir_path / "hello.flame"
        flame_file.write_text("@target python\nPrint hello world", encoding="utf-8")

        # Test offline conversion
        code, target_path = convert_flame_file(flame_file)
        self.assertEqual(target_path.suffix, ".py")
        self.assertTrue(target_path.exists())
        self.assertIn("print", code)
        self.assertIn("hello world", code.lower())

    def test_target_detection_js(self):
        flame_file = self.dir_path / "hello.flame"
        flame_file.write_text("@target javascript\nlog hello world", encoding="utf-8")

        # Test offline conversion
        code, target_path = convert_flame_file(flame_file)
        self.assertEqual(target_path.suffix, ".js")
        self.assertTrue(target_path.exists())
        self.assertIn("console.log", code)

    def test_dynamic_extensions(self):
        # Testing specific mappings requested in requirements
        test_cases = [
            ("zig", ".zig"),
            ("haskell", ".hs"),
            ("react", ".jsx"),
            ("svelte", ".svelte"),
            ("elixir", ".ex"),
            ("ocaml", ".ml"),
            ("assembly", ".asm"),
        ]
        for lang, expected_ext in test_cases:
            flame_file = self.dir_path / f"test_{lang}.flame"
            flame_file.write_text(f"@target {lang}\nsome content", encoding="utf-8")
            _, target_path = convert_flame_file(flame_file)
            self.assertEqual(target_path.suffix, expected_ext)

    def test_future_language_compatibility(self):
        # A completely unknown/future language should dynamically fall back to f".{target_lang}"
        flame_file = self.dir_path / "test_future.flame"
        flame_file.write_text("@target crystal\nsome content", encoding="utf-8")
        _, target_path = convert_flame_file(flame_file)
        self.assertEqual(target_path.suffix, ".crystal")

    def test_preview_dialog_compiles(self):
        # Ensure FlamePreviewDialog compiles and is importable
        from app.main_window import FlamePreviewDialog
        from PyQt5.QtWidgets import QApplication
        import sys

        # Ensure QApplication instance exists for widget testing
        app = QApplication.instance() or QApplication(sys.argv)
        dialog = FlamePreviewDialog(
            parent=None,
            filename="test.flame",
            detected_lang="python",
            initial_code="print('hello')",
            default_export_path=self.dir_path / "test.py"
        )
        self.assertEqual(dialog.editor.toPlainText(), "print('hello')")
        self.assertFalse(dialog.run_after_export)

    def test_validate_and_clean_code(self):
        raw_md = "```python\nprint('hello')\n```"
        clean = validate_and_clean_code(raw_md, "python")
        self.assertEqual(clean, "print('hello')\n")

        raw_clean = "print('hello')"
        clean = validate_and_clean_code(raw_clean, "python")
        self.assertEqual(clean, "print('hello')\n")

    def test_real_api_mock(self):
        flame_file = self.dir_path / "hello.flame"
        flame_file.write_text("@target python\nprint something", encoding="utf-8")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "print('from mock api')"
                    }
                }
            ]
        }

        with patch("os.environ.get", return_value="fake_api_key"):
            with patch("requests.post", return_value=mock_response) as mock_post:
                code, target_path = convert_flame_file(flame_file)
                mock_post.assert_called_once()
                self.assertEqual(code, "print('from mock api')\n")
                self.assertEqual(target_path.suffix, ".py")

if __name__ == "__main__":
    unittest.main()
