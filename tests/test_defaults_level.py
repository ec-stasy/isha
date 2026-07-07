"""
F2: leveled actions with no level fall back to settings.defaults.level
(default 50); explicit levels are untouched.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from c_resolver_validator import validate
from command_ir import CommandIR


class DefaultLevelTests(unittest.TestCase):
    def test_missing_level_defaults_to_50(self):
        ir = validate(CommandIR(action="set_value", target="volume",
                                warnings=["No Level Found!"]), {"settings": {}})
        self.assertEqual(ir.params["level"], 50)
        self.assertNotIn("No Level Found!", ir.warnings)

    def test_user_configured_default(self):
        config = {"settings": {"defaults": {"level": 30}}}
        ir = validate(CommandIR(action="set_value", target="brightness"), config)
        self.assertEqual(ir.params["level"], 30)

    def test_explicit_level_untouched(self):
        ir = validate(CommandIR(action="set_value", target="volume",
                                params={"level": 80}), {"settings": {}})
        self.assertEqual(ir.params["level"], 80)

    def test_garbage_default_falls_back_to_50(self):
        config = {"settings": {"defaults": {"level": "loud"}}}
        ir = validate(CommandIR(action="set_value", target="volume"), config)
        self.assertEqual(ir.params["level"], 50)

    def test_out_of_range_default_clamped(self):
        config = {"settings": {"defaults": {"level": 250}}}
        ir = validate(CommandIR(action="set_value", target="volume"), config)
        self.assertEqual(ir.params["level"], 100)

    def test_non_leveled_action_unaffected(self):
        ir = validate(CommandIR(action="open_app", target="chrome"), {"settings": {}})
        self.assertNotIn("level", ir.params)


if __name__ == "__main__":
    unittest.main()
