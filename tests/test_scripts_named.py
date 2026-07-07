"""
F6 named scripts: saving never runs anything; running inherits all three
Track A1 gates (allow_scripts opt-in, live confirm callback, verbatim
approval); modes may reference a script by name with no nesting; the
resolver upgrades "run <saved-name>" to run_script on exact match only.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import a_scripts
import executor
from command_ir import CommandIR
from command_parser import command_parser


def _config(allow_scripts=True, scripts=None):
    return {"settings": {"allow_scripts": allow_scripts},
            "scripts": scripts if scripts is not None else {}}


class SaveTests(unittest.TestCase):
    def test_save_never_executes(self):
        config = _config()
        ir = CommandIR(action="save_script", params={"name": "backup", "command": "robocopy a b"})
        with mock.patch("a_scripts.save_config"), \
             mock.patch("subprocess.Popen") as popen:
            result = a_scripts.save_script(ir, config)
        self.assertTrue(result.success)
        popen.assert_not_called()
        self.assertEqual(config["scripts"]["backup"]["command"], "robocopy a b")

    def test_multiword_name_rejected(self):
        result = a_scripts.save_script(
            CommandIR(action="save_script", params={"name": "two words", "command": "x"}), _config())
        self.assertFalse(result.success)


class RunGateTests(unittest.TestCase):
    def test_run_unknown_script(self):
        result = a_scripts.run_script(CommandIR(action="run_script", target="nope"), _config())
        self.assertFalse(result.success)

    def test_disabled_setting_refuses(self):
        config = _config(allow_scripts=False, scripts={"backup": {"command": "echo hi"}})
        executor.set_confirm_callback(lambda ir: True)
        try:
            result = a_scripts.run_script(CommandIR(action="run_script", target="backup"), config)
        finally:
            executor.set_confirm_callback(None)
        self.assertEqual(result.data.get("skipped"), "disabled")

    def test_no_callback_never_runs(self):
        config = _config(scripts={"backup": {"command": "echo hi"}})
        executor.set_confirm_callback(None)
        with mock.patch("subprocess.Popen") as popen:
            result = a_scripts.run_script(CommandIR(action="run_script", target="backup"), config)
        self.assertEqual(result.data.get("skipped"), "no_confirm")
        popen.assert_not_called()

    def test_confirmed_run_sees_verbatim_command(self):
        config = _config(scripts={"backup": {"command": "echo hi"}})
        seen = {}

        def confirm(ir):
            seen["target"] = ir.target
            return True

        executor.set_confirm_callback(confirm)
        try:
            with mock.patch("executor.subprocess.Popen") as popen:
                result = a_scripts.run_script(CommandIR(action="run_script", target="backup"), config)
        finally:
            executor.set_confirm_callback(None)
        self.assertTrue(result.success)
        self.assertEqual(seen["target"], "echo hi")  # the command, never just the name
        popen.assert_called_once()


class ReferenceTests(unittest.TestCase):
    def test_mode_script_field_resolves_name(self):
        config = _config(scripts={"backup": {"command": "echo hi"}})
        self.assertEqual(a_scripts.resolve_script_reference("backup", config), "echo hi")

    def test_no_nesting(self):
        config = _config(scripts={"a": {"command": "b"}, "b": {"command": "echo deep"}})
        # one level only: "a" resolves to "b" the *text*, which is not re-resolved
        self.assertEqual(a_scripts.resolve_script_reference("a", config), "b")

    def test_raw_command_passes_through(self):
        self.assertEqual(a_scripts.resolve_script_reference("echo hi", _config()), "echo hi")


class ResolverAndParserTests(unittest.TestCase):
    def test_run_name_upgrades_to_run_script(self):
        from c_resolver_validator import resolve_and_validate
        config = _config(scripts={"backup": {"command": "echo hi"}})
        ir = resolve_and_validate(CommandIR(action="open_app", target="backup"), config)
        self.assertEqual(ir.action, "run_script")

    def test_save_script_parses(self):
        ir = command_parser(["save", "script", "backup", "as", "robocopy", "a", "b"])
        self.assertEqual(ir.action, "save_script")
        self.assertEqual(ir.params["name"], "backup")
        self.assertEqual(ir.params["command"], "robocopy a b")


if __name__ == "__main__":
    unittest.main()
