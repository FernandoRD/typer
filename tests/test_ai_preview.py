import unittest

from autotyper.config import is_safe_ai_output, normalize_ai_output


class SafeAiOutputTests(unittest.TestCase):
    def test_plain_multiline_output_is_allowed(self):
        self.assertTrue(is_safe_ai_output("echo ready\nservice status"))

    def test_crlf_and_cr_are_normalized_before_validation(self):
        raw = "first\r\nsecond\rthird\n"
        self.assertEqual(normalize_ai_output(raw), "first\nsecond\nthird\n")
        self.assertTrue(is_safe_ai_output(raw))

    def test_automation_markers_are_rejected(self):
        self.assertFalse(is_safe_ai_output("echo ready [[key:enter]]"))
        self.assertFalse(is_safe_ai_output("echo ready ]]"))

    def test_control_and_format_characters_are_rejected(self):
        self.assertFalse(is_safe_ai_output("echo\x00ready"))
        self.assertFalse(is_safe_ai_output("echo\u202eready"))


if __name__ == "__main__":
    unittest.main()
