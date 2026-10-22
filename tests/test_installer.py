import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


installer = load("everest", ROOT / "everest.py")
actions = load("actions", ROOT / "config/actions.py")


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / "home"
        (self.home / ".config/hypr").mkdir(parents=True)
        (self.home / ".config/omarchy").mkdir(parents=True)
        self.hypr = self.home / installer.HYPR
        self.shell = self.home / installer.SHELL
        self.hypr.write_bytes(b'-- personal config\r\nrequire("default.hypr.omarchy")\r\n')
        self.hypr.chmod(0o640)
        self.shell.write_text(json.dumps({
            "version": 1, "idle": {"lock": 900}, "plugins": [{"id": "personal.widget"}],
            "disabledPlugins": ["omarchy.weather"],
            "bar": {"position": "bottom", "customSetting": "keep", "transparent": None}
        }) + "\n")
        self.before = self.snapshot()
        self.app = installer.Everest(self.home, ROOT, enforce=False)

    def snapshot(self):
        return {p.relative_to(self.home).as_posix(): p.read_bytes()
                for p in self.home.rglob("*") if p.is_file()
                and not p.is_relative_to(self.home / ".local/state/everest")}

    def install(self):
        ops, manifest = self.app.plan_install()
        self.app.execute(ops, manifest)
        return ops, manifest

    def uninstall(self):
        ops, manifest = self.app.plan_uninstall()
        self.app.execute(ops, None)
        self.app.clean_dirs(manifest)

    def test_plan_is_read_only(self):
        with patch("subprocess.check_output", side_effect=AssertionError("Unexpected process")):
            self.app.plan_install()
        self.assertEqual(self.snapshot(), self.before)
        self.assertFalse(self.app.state.exists())

    def test_fresh_idempotent_and_exact_uninstall(self):
        self.install()
        installed = self.snapshot()
        state = self.app.read(self.app.state / "manifest.json")
        ops, manifest = self.app.plan_install()
        self.assertEqual(ops, [])
        self.assertFalse(self.app.execute(ops, manifest))
        self.assertEqual(self.snapshot(), installed)
        self.assertEqual(self.app.read(self.app.state / "manifest.json"), state)
        shell = json.loads(self.shell.read_text())
        self.assertEqual(shell["idle"]["lock"], 900)
        self.assertEqual(shell["plugins"], [{"id": "personal.widget"}])
        self.assertEqual(shell["disabledPlugins"], ["omarchy.weather"])
        self.assertEqual(shell["bar"]["customSetting"], "keep")
        self.uninstall()
        self.assertEqual(self.snapshot(), self.before)
        self.assertEqual(self.hypr.stat().st_mode & 0o777, 0o640)
        self.assertTrue((self.app.state / "backups").is_dir())
        self.uninstall()  # Removal is idempotent too.

    def test_outside_edits_survive_removal(self):
        self.install()
        self.hypr.write_bytes(self.hypr.read_bytes() + b"\n-- a later personal setting\n")
        shell = json.loads(self.shell.read_text())
        shell["idle"]["lock"] = 1200
        shell["bar"]["personalExtra"] = 42
        self.shell.write_text(json.dumps(shell))
        self.uninstall()
        self.assertIn(b"-- a later personal setting", self.hypr.read_bytes())
        self.assertNotIn(installer.BEGIN.encode(), self.hypr.read_bytes())
        result = json.loads(self.shell.read_text())
        self.assertEqual(result["idle"]["lock"], 1200)
        self.assertEqual(result["bar"]["personalExtra"], 42)
        self.assertEqual(result["bar"]["position"], "bottom")
        self.assertIsNone(result["bar"]["transparent"])

    def test_reinstall_preserves_later_unrelated_edits_on_removal(self):
        self.install()
        value = json.loads(self.shell.read_text())
        value["idle"]["lock"] = 1234
        value["plugins"].append({"id": "later.plugin"})
        value["bar"]["laterSetting"] = "preserve"
        self.shell.write_text(json.dumps(value))
        self.install()
        self.uninstall()
        value = json.loads(self.shell.read_text())
        self.assertEqual(value["idle"]["lock"], 1234)
        self.assertIn({"id": "later.plugin"}, value["plugins"])
        self.assertEqual(value["bar"]["laterSetting"], "preserve")
        self.assertEqual(value["bar"]["position"], "bottom")

    def test_empty_original_bar_restores_exactly(self):
        self.shell.write_bytes(b'{"version":1,"bar":{}}\n')
        original = self.shell.read_bytes()
        self.install()
        self.uninstall()
        self.assertEqual(self.shell.read_bytes(), original)

    def test_managed_bar_keys_can_be_added_and_retired_by_update(self):
        self.install()
        source = Path(self.temp.name) / "changed-source"
        shutil.copytree(ROOT, source, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        config = source / "config/shell-bar.json"
        desired = json.loads(config.read_text())
        desired.pop("position")
        desired["futureSetting"] = True
        config.write_text(json.dumps(desired))
        self.app.source = source
        self.install()
        current = json.loads(self.shell.read_text())
        self.assertEqual(current["bar"]["position"], "bottom")
        self.assertTrue(current["bar"]["futureSetting"])
        current["idle"]["lock"] = 1201
        self.shell.write_text(json.dumps(current))
        self.uninstall()
        restored = json.loads(self.shell.read_text())
        self.assertEqual(restored["idle"]["lock"], 1201)
        self.assertEqual(restored["bar"]["position"], "bottom")
        self.assertNotIn("futureSetting", restored["bar"])

    def test_recovery_dry_run_is_read_only(self):
        ops, manifest = self.app.plan_install()
        with self.assertRaises(OSError):
            self.app.execute(ops, manifest, fail_after=1)
        snapshot = self.snapshot()
        journal = self.app.read(self.app.state / "pending.json")
        self.assertEqual(self.app.recover(dry_run=True), [op[0] for op in ops])
        self.assertEqual(self.snapshot(), snapshot)
        self.assertEqual(self.app.read(self.app.state / "pending.json"), journal)

    def test_uninstall_detaches_first_and_retains_recovery_cli(self):
        self.install()
        ops, _ = self.app.plan_uninstall()
        self.assertEqual([op[0] for op in ops[:2]], [installer.HYPR, installer.SHELL])
        self.assertEqual(ops[-1][0], ".config/everest/everest.py")
        self.assertTrue((self.app.state / "recover.py").is_file())

    def test_modified_owned_file_blocks_all_removal(self):
        self.install()
        path = self.home / ".config/everest/actions.py"
        path.write_text(path.read_text() + "\n# my edit\n")
        before = self.snapshot()
        with self.assertRaises(installer.Conflict):
            self.app.plan_uninstall()
        self.assertEqual(self.snapshot(), before)

    def test_modified_bar_blocks_removal(self):
        self.install()
        value = json.loads(self.shell.read_text())
        value["bar"]["layout"]["left"].append({"id": "my.widget"})
        self.shell.write_text(json.dumps(value))
        before = self.snapshot()
        with self.assertRaises(installer.Conflict):
            self.app.plan_uninstall()
        self.assertEqual(self.snapshot(), before)

    def test_unknown_payload_file_is_preserved(self):
        self.install()
        path = self.home / ".config/everest/notes.txt"
        path.write_text("my notes")
        self.uninstall()
        self.assertEqual(path.read_text(), "my notes")

    def test_existing_owned_directory_refused(self):
        (self.home / ".config/everest").mkdir()
        with self.assertRaises(installer.Conflict):
            self.app.plan_install()

    def test_symlink_file_and_ancestor_refused(self):
        self.hypr.unlink()
        self.hypr.symlink_to(self.shell)
        with self.assertRaises(installer.Conflict):
            self.app.plan_install()
        self.hypr.unlink()
        self.hypr.write_bytes(self.before[installer.HYPR])
        themes = self.home / ".config/omarchy/themes"
        themes.symlink_to(self.home / ".config/hypr", target_is_directory=True)
        with self.assertRaises(installer.Conflict):
            self.app.plan_install()

    def test_bad_json_and_schema_refused_before_writes(self):
        for raw in ('{"version":1,"version":1}', '{"version":1,"x":NaN}',
                    '{"version":true}', '[]', '{"version":1,"bar":5}'):
            with self.subTest(raw=raw):
                self.shell.write_text(raw)
                with self.assertRaises((installer.Conflict, ValueError)):
                    self.app.plan_install()
                self.assertFalse((self.home / ".config/everest").exists())

    def test_bad_markers_refused(self):
        self.hypr.write_bytes(self.hypr.read_bytes() + installer.BEGIN.encode())
        with self.assertRaises(installer.Conflict):
            self.app.plan_install()

    def test_recovery_at_every_install_boundary(self):
        count = len(self.app.plan_install()[0])
        for index in range(1, count + 2):
            with self.subTest(boundary=index):
                ops, manifest = self.app.plan_install()
                with self.assertRaises(OSError):
                    self.app.execute(ops, manifest, fail_after=index)
                self.app.recover()
                self.app.recover()
                self.assertEqual(self.snapshot(), self.before)
                self.assertIsNone(self.app.manifest())

    def test_recovery_at_every_uninstall_boundary(self):
        self.install()
        installed = self.snapshot()
        count = len(self.app.plan_uninstall()[0])
        for index in range(1, count + 2):
            with self.subTest(boundary=index):
                ops, _ = self.app.plan_uninstall()
                with self.assertRaises(OSError):
                    self.app.execute(ops, None, fail_after=index)
                self.app.recover()
                self.assertEqual(self.snapshot(), installed)
                self.assertIsNotNone(self.app.manifest())

    def test_recovery_does_not_overwrite_new_edit(self):
        ops, manifest = self.app.plan_install()
        with self.assertRaises(OSError):
            self.app.execute(ops, manifest, fail_after=1)
        target = self.home / ops[0][0]
        target.write_text("outside edit")
        with self.assertRaises(installer.Conflict):
            self.app.recover()
        self.assertEqual(target.read_text(), "outside edit")

    def test_stale_plan_is_rejected(self):
        ops, manifest = self.app.plan_install()
        self.hypr.write_text(self.hypr.read_text() + "-- edit")
        with self.assertRaises(installer.Conflict):
            self.app.execute(ops, manifest)
        self.assertFalse((self.home / ".config/everest").exists())

    def test_update_preserves_original_backups(self):
        self.install()
        source = Path(self.temp.name) / "source"
        shutil.copytree(ROOT, source, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        action = source / "config/actions.py"
        action.write_text(action.read_text() + "\n# next release\n")
        self.app.source = source
        ops, manifest = self.app.plan_install()
        self.assertEqual([op[0] for op in ops], [".config/everest/actions.py"])
        self.app.execute(ops, manifest)
        self.uninstall()
        self.assertEqual(self.snapshot(), self.before)

    def test_active_theme_must_be_switched_before_removal(self):
        self.install()
        target = self.home / ".local/state/omarchy/current/theme.name"
        target.parent.mkdir(parents=True)
        target.write_text("everest-dusk\n")
        with self.assertRaises(installer.Conflict):
            self.app.plan_uninstall()

    def test_production_wallpaper_render_is_deterministic(self):
        if not shutil.which("magick"):
            self.skipTest("ImageMagick 7 is supplied by the Arch CI job")
        app = installer.Everest(self.home, ROOT, enforce=True)
        first = app.payload()
        second = app.payload()
        for name in ("dawn", "dusk"):
            key = ".config/omarchy/themes/everest-" + name + "/backgrounds/everest.png"
            self.assertTrue(first[key].startswith(b"\x89PNG\r\n\x1a\n"))
            self.assertEqual(first[key], second[key])


class SwitchingTests(unittest.TestCase):
    def setUp(self):
        self.clients = [
            {"address": "0x1", "class": "A", "workspace": {"id": 1}, "focusHistoryID": 2},
            {"address": "0x2", "class": "A", "workspace": {"id": 2}, "focusHistoryID": 1},
            {"address": "0x3", "class": "B", "workspace": {"id": 1}, "focusHistoryID": 0},
            {"address": "0x4", "class": "C", "workspace": {"id": -99}, "focusHistoryID": 3},
        ]

    def test_app_cycle_uses_distinct_classes_and_mru_window(self):
        self.assertEqual(actions.choose("next-app", self.clients, self.clients[0])["address"], "0x3")
        self.assertEqual(actions.choose("next-app", self.clients, self.clients[2])["address"], "0x2")
        self.assertEqual(actions.choose("previous-app", self.clients, {})["address"], "0x3")

    def test_window_cycle_stays_in_app_and_wraps(self):
        self.assertEqual(actions.choose("next-window", self.clients, self.clients[0])["address"], "0x2")
        self.assertEqual(actions.choose("previous-window", self.clients, self.clients[0])["address"], "0x2")

    def test_lua_ipc_and_textual_errors(self):
        import subprocess
        with patch.object(actions.subprocess, "run",
                          return_value=subprocess.CompletedProcess([], 0, "ok\n", "")) as run:
            actions.move(self.clients[0], actions.SHELF)
            expression = run.call_args.args[0][-1]
            self.assertIn("hl.dsp.window.move(", expression)
            self.assertIn('"address:0x1"', expression)
            self.assertNotIn("movetoworkspacesilent", expression)
        with patch.object(actions.subprocess, "run",
                          return_value=subprocess.CompletedProcess([], 0, "Invalid dispatcher", "")):
            with self.assertRaises(RuntimeError):
                actions.dispatch("hl.dsp.window.bring_to_top()")
        with patch.object(actions.subprocess, "run") as run:
            with self.assertRaises(RuntimeError):
                actions.move({"address": "bad"}, "1")
            run.assert_not_called()

    def test_empty_session_is_harmless(self):
        self.assertIsNone(actions.choose("next-app", [], {}))
        self.assertIsNone(actions.choose("next-window", [], {}))


if __name__ == "__main__":
    unittest.main()
