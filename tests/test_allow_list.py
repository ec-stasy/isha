"""
F1 website allow-list: parsed-hostname matching (no substring bypasses),
subdomain coverage, the confirm gate in open_url, and the never-confirm rule
for callers without a callback (schedulers).
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import a_allow_list
import executor
from command_ir import CommandIR


def _config(allow=None, enabled=True):
    return {"allow_list": list(allow or []),
            "settings": {"allow_list_enabled": enabled}}


class MatchingTests(unittest.TestCase):
    def test_exact_and_www_and_subdomain(self):
        config = _config(["youtube.com"])
        for url in ("https://youtube.com/x", "https://www.youtube.com",
                    "https://music.youtube.com/playlist"):
            self.assertTrue(a_allow_list.is_allowed(url, config), url)

    def test_query_smuggling_rejected(self):
        config = _config(["youtube.com"])
        self.assertFalse(a_allow_list.is_allowed("https://evil.com/?q=youtube.com", config))
        self.assertFalse(a_allow_list.is_allowed("https://youtube.com.evil.com", config))

    def test_disabled_allows_everything(self):
        self.assertTrue(a_allow_list.is_allowed("https://anything.example", _config(enabled=False)))

    def test_empty_list_allows_nothing(self):
        self.assertFalse(a_allow_list.is_allowed("https://example.com", _config()))


class GateTests(unittest.TestCase):
    def _open(self, config, confirm):
        executor.set_confirm_callback(confirm)
        try:
            with mock.patch("webbrowser.open", return_value=True) as opener:
                result = executor.open_url(CommandIR(action="open_url",
                                                     target="https://example.com"), config)
            return result, opener
        finally:
            executor.set_confirm_callback(None)

    def test_allow_listed_opens_without_prompt(self):
        config = _config(["example.com"])
        confirm = mock.Mock()
        result, opener = self._open(config, confirm)
        self.assertTrue(result.success)
        opener.assert_called_once()
        confirm.assert_not_called()

    def test_unlisted_needs_affirmative(self):
        config = _config()
        result, opener = self._open(config, lambda ir: False)
        self.assertTrue(result.success)  # a decline is a calm no-op, not an error
        self.assertEqual(result.data.get("skipped"), "declined")
        opener.assert_not_called()

    def test_unlisted_opens_on_yes(self):
        config = _config()
        result, opener = self._open(config, lambda ir: True)
        self.assertTrue(result.success)
        opener.assert_called_once()

    def test_no_callback_skips_quietly(self):
        """Scheduler path: no confirm callback ever means no open, no crash."""
        config = _config()
        result, opener = self._open(config, None)
        self.assertEqual(result.data.get("skipped"), "not_allow_listed")
        opener.assert_not_called()

    def test_add_and_remove_commands(self):
        config = _config()
        with mock.patch("a_allow_list.save_config"):
            result = a_allow_list.add_allow_site(
                CommandIR(action="add_allow_site", target="https://www.YouTube.com/x"), config)
            self.assertTrue(result.success)
            self.assertIn("youtube.com", config["allow_list"])
            result = a_allow_list.remove_allow_site(
                CommandIR(action="remove_allow_site", target="youtube.com"), config)
            self.assertTrue(result.success)
            self.assertNotIn("youtube.com", config["allow_list"])


if __name__ == "__main__":
    unittest.main()
