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
