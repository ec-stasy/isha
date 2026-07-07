"""
Schema v2 migration (NEW_VERSION_ROADMAP.md §5.F7): v1 configs upgrade in
place without losing any user choice; the migration is idempotent; the
allow-list is seeded from mode websites so working modes keep working.
"""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config_store
from config_store import _migrate_v1_to_v2, _normalize_host, _default_config


def _v1_config() -> dict:
    return {
        "schema_version": 1,
        "modes": {
            "study": {
                "apps": [
                    {"type": "app", "name": "chrome", "path": "C:/x/chrome.exe"},
                    {"type": "website", "name": "youtube", "url": "https://www.youtube.com/feed"},
                ],
                "script": None,
            },
        },
        "active_mode": None,
        "aliases": {"yt": "youtube"},
        "hotkeys": {},
        "settings": {"onboarded": True, "allow_mode_scripts": True, "hotkey": "ctrl+alt+i"},
        "reminders": [{"text": "stretch", "time": "2026-07-08T16:00:00"}],
        "triggers": [],
        "snippets": {"sig": "regards"},
        "license": None,
    }


class MigrationTests(unittest.TestCase):
    def test_upgrades_version_and_renames_allow_scripts(self):
        config = _migrate_v1_to_v2(_v1_config())
        self.assertEqual(config["schema_version"], 2)
        self.assertTrue(config["settings"]["allow_scripts"])
        self.assertNotIn("allow_mode_scripts", config["settings"])

    def test_seeds_allow_list_from_mode_websites(self):
        config = _migrate_v1_to_v2(_v1_config())
        self.assertIn("youtube.com", config["allow_list"])

    def test_preserves_user_choices(self):
        config = _migrate_v1_to_v2(_v1_config())
        self.assertEqual(config["aliases"], {"yt": "youtube"})
        self.assertEqual(config["snippets"], {"sig": "regards"})
        self.assertTrue(config["settings"]["onboarded"])
        self.assertEqual(config["settings"]["hotkey"], "ctrl+alt+i")

    def test_new_defaults_present(self):
        config = _migrate_v1_to_v2(_v1_config())
        s = config["settings"]
        self.assertEqual(s["defaults"]["level"], 50)
        self.assertEqual(s["audio"]["mute_behavior"], "halve_all")
        self.assertEqual(s["screenshot"]["after"], "save")
        self.assertEqual(s["screenshot"]["prtscr"], "off")
        self.assertTrue(s["allow_list_enabled"])
        self.assertEqual(s["ui"]["theme"], "auto")
        self.assertIn("scripts", config)

    def test_reminders_upgraded_to_v2_shape(self):
        config = _migrate_v1_to_v2(_v1_config())
        (rec,) = config["reminders"]
        for key in ("id", "text", "at", "repeat", "enabled", "last_fired"):
            self.assertIn(key, rec)
        self.assertEqual(rec["text"], "stretch")
        self.assertEqual(rec["at"], "2026-07-08T16:00:00")

    def test_idempotent(self):
        once = _migrate_v1_to_v2(_v1_config())
        twice = _migrate_v1_to_v2(copy.deepcopy(once))
        self.assertEqual(once, twice)

    def test_default_config_is_already_v2(self):
        config = _default_config()
        self.assertEqual(config["schema_version"], config_store.SCHEMA_VERSION)
        self.assertEqual(config["schema_version"], 2)


class HostNormalizationTests(unittest.TestCase):
    def test_strips_scheme_www_and_path(self):
        self.assertEqual(_normalize_host("https://www.YouTube.com/watch?v=1"), "youtube.com")
        self.assertEqual(_normalize_host("youtube.com"), "youtube.com")

    def test_query_smuggling_does_not_leak_host(self):
        # the classic bypass this design exists to prevent
        self.assertEqual(_normalize_host("https://evil.com/?q=youtube.com"), "evil.com")

    def test_idn_is_punycoded(self):
        self.assertEqual(_normalize_host("münchen.de"), "xn--mnchen-3ya.de")

    def test_empty_and_garbage(self):
        self.assertEqual(_normalize_host(""), "")
        self.assertEqual(_normalize_host("   "), "")


if __name__ == "__main__":
    unittest.main()
