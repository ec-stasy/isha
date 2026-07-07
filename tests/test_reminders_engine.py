"""
F5 reminders engine: natural time parsing, due detection, repeats, missed-
while-off recovery, snooze — all headless.
"""
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import a_reminders
from a_reminders import parse_time_tokens, due_reminders
from command_ir import CommandIR

NOW = datetime(2026, 7, 7, 12, 0, 0)  # a Tuesday


class ParseTests(unittest.TestCase):
    def test_clock_pm(self):
        at, repeat = parse_time_tokens(["at", "4pm"], NOW)
        self.assertEqual((at.hour, at.minute, at.day), (16, 0, 7))
        self.assertEqual(repeat, "none")

    def test_past_clock_rolls_to_tomorrow(self):
        at, _ = parse_time_tokens(["9am"], NOW)
        self.assertEqual((at.hour, at.day), (9, 8))

    def test_relative_minutes(self):
        at, _ = parse_time_tokens(["in", 20, "minutes"], NOW)
        self.assertEqual(at, NOW + timedelta(minutes=20))

    def test_tomorrow_with_time(self):
        at, _ = parse_time_tokens(["tomorrow", "9am"], NOW)
        self.assertEqual((at.day, at.hour), (8, 9))

    def test_daily_repeat(self):
        at, repeat = parse_time_tokens(["daily", "at", "8am"], NOW)
        self.assertEqual(repeat, "daily")
        self.assertEqual(at.hour, 8)

    def test_weekday(self):
        at, _ = parse_time_tokens(["friday", "5pm"], NOW)
        self.assertEqual(at.weekday(), 4)
        self.assertGreater(at, NOW)

    def test_no_time(self):
        at, repeat = parse_time_tokens([], NOW)
        self.assertIsNone(at)


class EngineTests(unittest.TestCase):
    def _record(self, **kw):
        record = {"id": "r1", "text": "stretch", "at": (NOW - timedelta(minutes=1)).isoformat(),
                  "repeat": "none", "enabled": True, "last_fired": None}
        record.update(kw)
        return record

    def test_due_fires_and_disables_one_shot(self):
        config = {"reminders": [self._record()]}
        with mock.patch("a_reminders.save_config"):
            fired = due_reminders(config, NOW)
        self.assertEqual(len(fired), 1)
        record, missed = fired[0]
        self.assertFalse(missed)
        self.assertFalse(record["enabled"])
        self.assertIsNotNone(record["last_fired"])

    def test_not_due_yet(self):
        config = {"reminders": [self._record(at=(NOW + timedelta(hours=1)).isoformat())]}
        with mock.patch("a_reminders.save_config"):
            self.assertEqual(due_reminders(config, NOW), [])

    def test_daily_advances_instead_of_disabling(self):
        config = {"reminders": [self._record(repeat="daily")]}
        with mock.patch("a_reminders.save_config"):
            fired = due_reminders(config, NOW)
        record = fired[0][0]
        self.assertTrue(record["enabled"])
        self.assertGreater(datetime.fromisoformat(record["at"]), NOW)

    def test_missed_while_off_flagged(self):
        config = {"reminders": [self._record(at=(NOW - timedelta(hours=5)).isoformat())]}
        with mock.patch("a_reminders.save_config"):
            fired = due_reminders(config, NOW, startup=True)
        self.assertTrue(fired[0][1])  # missed

    def test_disabled_never_fires(self):
        config = {"reminders": [self._record(enabled=False)]}
        with mock.patch("a_reminders.save_config"):
            self.assertEqual(due_reminders(config, NOW), [])

    def test_snooze_moves_and_reenables(self):
        record = self._record(enabled=False)
        config = {"reminders": [record]}
        with mock.patch("a_reminders.save_config"):
            a_reminders.snooze(config, "r1", minutes=10)
        self.assertTrue(record["enabled"])
        self.assertGreater(datetime.fromisoformat(record["at"]), datetime.now())

    def test_set_reminder_handler_shape(self):
        config = {"reminders": []}
        ir = CommandIR(action="set_reminder", target="stretch", params={"time": ["4pm"]})
        with mock.patch("a_reminders.save_config"):
            result = a_reminders.set_reminder(ir, config)
        self.assertTrue(result.success)
        (record,) = config["reminders"]
        for key in ("id", "text", "at", "repeat", "enabled", "last_fired"):
            self.assertIn(key, record)
        self.assertTrue(record["enabled"])


if __name__ == "__main__":
    unittest.main()
