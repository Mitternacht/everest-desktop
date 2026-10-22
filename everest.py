#!/usr/bin/env python3
"""User-level, reversible installer for Everest Desktop. Requires Python 3.11+."""
from __future__ import annotations
import argparse
import base64
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid

BEGIN = "-- BEGIN EVEREST (managed by everest-desktop)"
END = "-- END EVEREST"
BLOCK = '\n' + BEGIN + '\ndofile(os.getenv("HOME") .. "/.config/everest/hyprland.lua")\n' + END + '\n'
HYPR = ".config/hypr/hyprland.lua"
SHELL = ".config/omarchy/shell.json"
OWNED = [".config/everest", ".config/omarchy/themes/everest-dawn",
         ".config/omarchy/themes/everest-dusk"]


class Conflict(RuntimeError):
    pass


def digest(data):
    return None if data is None else hashlib.sha256(data).hexdigest()


def pack(data):
    return None if data is None else base64.b64encode(data).decode("ascii")


def unpack(data):
    return None if data is None else base64.b64decode(data, validate=True)


def strict_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise Conflict("Duplicate JSON key: " + key)
            result[key] = value
        return result
    def bad(value):
        raise Conflict("Invalid JSON number: " + value)
    result = json.loads(data, object_pairs_hook=pairs, parse_constant=bad)
    if not isinstance(result, dict):
        raise Conflict("Expected a JSON object")
    return result


def encoded(value):
    return (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()


def same(a, b):
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


class Everest:
    def __init__(self, home=None, source=None, enforce=True):
        self.home = Path(home or Path.home()).absolute()
        self.source = Path(source or Path(__file__).resolve().parent)
        self.state = self.home / ".local/state/everest"
        self.enforce = enforce

    def safe(self, path):
        path = Path(path).absolute()
        if not path.is_relative_to(self.home) or ".." in path.parts:
            raise Conflict("Path escapes home: " + str(path))
        for parent in [path, *path.parents]:
            if parent == self.home.parent:
                break
            if parent.is_symlink():
                raise Conflict("Refusing symlink: " + str(parent))
            if parent.exists() and parent != path and not parent.is_dir():
                raise Conflict("Non-directory ancestor: " + str(parent))
        if path.exists() and not path.is_file():
            raise Conflict("Expected regular file: " + str(path))
        return path

    def read(self, path):
        path = self.safe(path)
        return path.read_bytes() if path.exists() else None

    def atomic(self, path, data, mode=0o600):
        path = self.safe(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.safe(path)
        if data is None:
            path.unlink(missing_ok=True)
        else:
            fd, name = tempfile.mkstemp(prefix=".everest-", dir=path.parent)
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(data)
                    stream.flush()
                    os.fchmod(stream.fileno(), mode)
                    os.fsync(stream.fileno())
                os.replace(name, path)
            finally:
                if os.path.exists(name):
                    os.unlink(name)
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def manifest(self):
        raw = self.read(self.state / "manifest.json")
        if raw is None:
            return None
        value = strict_json(raw)
        if value.get("schema") != 1:
            raise Conflict("Unsupported manifest schema")
        return value

    def preflight(self):
        if not self.enforce:
            return
        if sys.platform != "linux" or os.geteuid() == 0:
            raise Conflict("Install as your normal user on an Omarchy Linux machine.")
        if sys.version_info < (3, 11):
            raise Conflict("Python 3.11+ required.")
        xdg = os.environ.get("XDG_CONFIG_HOME")
        if xdg and Path(xdg) != self.home / ".config":
            raise Conflict("Nondefault XDG_CONFIG_HOME is unsupported by this Omarchy integration.")
        for name in ("omarchy-version", "hyprctl", "qs", "magick", "omarchy-menu",
                     "omarchy-launch-nautilus", "omarchy-launch-browser", "xdg-terminal-exec"):
            if not shutil.which(name):
                raise Conflict("Missing Omarchy dependency: " + name)
        version = subprocess.check_output(["omarchy-version"], text=True, timeout=10).strip()
        if not re.match(r"^4\.0\.6(?:[-+]|$)", version):
            raise Conflict("Target is Omarchy 4.0.6; detected " + version +
                           ". Run doctor; a newer version needs a compatibility review.")
        upstream = Path(os.environ.get("OMARCHY_PATH", "/usr/share/omarchy"))
        for relative in ("default/hypr/bootstrap.lua", "shell/shell.qml", "default/themed/shell.toml.tpl"):
            if not (upstream / relative).is_file():
                raise Conflict("Missing upstream interface: " + relative)

    def payload(self):
        result = {".config/everest/everest.py": (self.source / "everest.py").read_bytes()}
        for name in ("hyprland.lua", "actions.py", "dock/shell.qml"):
            result[".config/everest/" + name] = (self.source / "config" / name).read_bytes()
        for appearance in ("dawn", "dusk"):
            for item in sorted((self.source / "themes" / ("everest-" + appearance)).rglob("*")):
                if item.is_file():
                    relative = item.relative_to(self.source / "themes").as_posix()
                    result[".config/omarchy/themes/" + relative] = item.read_bytes()
            svg = (self.source / "assets" / (appearance + ".svg")).read_bytes()
            if self.enforce:
                image = subprocess.check_output(
                    ["magick", "-background", "none", "svg:-", "-strip", "-define", "png:exclude-chunks=all", "png:-"], input=svg, timeout=30)
            else:
                image = b"PNG fixture; graphical rendering tested separately in CI"
            result[".config/omarchy/themes/everest-" + appearance + "/backgrounds/everest.png"] = image
        return result

    def plan_install(self):
        self.preflight()
        if self.read(self.state / "pending.json"):
            raise Conflict("Interrupted transaction found. Run recover first.")
        prior = self.manifest()
        if prior is None:
            for root in OWNED:
                target = self.home / root
                if target.exists() or target.is_symlink():
                    raise Conflict("Unowned destination exists: " + str(target))
        manifest = copy.deepcopy(prior) if prior else {
            "schema": 1, "target": "Omarchy 4.0.6", "files": {},
            "created_dirs": [], "backup_id": uuid.uuid4().hex}
        outputs = self.payload()
        hypr = self.read(self.home / HYPR)
        if hypr is None:
            raise Conflict("Missing " + HYPR)
        text = hypr.decode("utf-8")
        if prior:
            if text.count(BLOCK) != 1 or text.count(BEGIN) != 1 or text.count(END) != 1:
                raise Conflict("Everest Lua block is missing or changed.")
        else:
            if BEGIN in text or END in text or ".config/everest/hyprland.lua" in text:
                raise Conflict("Existing/malformed Everest Lua include.")
            if 'require("default.hypr.omarchy")' not in text:
                raise Conflict("Expected Omarchy Lua entry point not found.")
            outputs[HYPR] = hypr + BLOCK.encode()
        raw = self.read(self.home / SHELL)
        if raw is None:
            raise Conflict("Missing shell.json; restore Omarchy's supported user config first.")
        shell = strict_json(raw)
        if type(shell.get("version")) is not int or shell["version"] != 1:
            raise Conflict("Unsupported shell.json version")
        if not isinstance(shell.get("bar", {}), dict):
            raise Conflict("shell.json bar must be an object")
        desired = strict_json((self.source / "config/shell-bar.json").read_bytes())
        bar = shell.setdefault("bar", {})
        if prior:
            for key, value in prior["bar_after"].items():
                if key not in bar or not same(bar[key], value):
                    raise Conflict("Managed bar setting changed: " + key)
        else:
            manifest["bar_before"] = {
                key: {"exists": key in bar, "value": bar.get(key)} for key in desired}
        bar.update(desired)
        manifest["bar_after"] = desired
        outputs[SHELL] = encoded(shell)
        operations = []
        for relative, data in outputs.items():
            current = self.read(self.home / relative)
            entry = manifest["files"].get(relative)
            if entry and relative not in (HYPR, SHELL) and digest(current) != entry["after"]:
                raise Conflict("Managed file changed: " + relative)
            if entry is None:
                mode = stat.S_IMODE((self.home / relative).stat().st_mode) if current is not None else 0o644
                entry = {"before": digest(current), "mode": mode,
                         "backup": "backups/" + manifest["backup_id"] + "/" + str(len(manifest["files"]))}
                manifest["files"][relative] = entry
            entry["after"] = digest(data)
            if current != data:
                operations.append((relative, current, data, entry["mode"]))
                parent = (self.home / relative).parent
                while parent != self.home and not parent.exists():
                    rel = parent.relative_to(self.home).as_posix()
                    if rel not in manifest["created_dirs"]:
                        manifest["created_dirs"].append(rel)
                    parent = parent.parent
        return operations, manifest

    def execute(self, operations, manifest, fail_after=None):
        old = self.read(self.state / "manifest.json")
        new = None if manifest is None else encoded(manifest)
        if not operations and old == new:
            return False
        dirs = []
        journal = {"schema": 1, "old_manifest": pack(old), "new_manifest": pack(new),
                   "operations": [], "created_dirs": dirs}
        for relative, before, after, mode in operations:
            if self.read(self.home / relative) != before:
                raise Conflict("File changed during planning: " + relative)
            journal["operations"].append({"path": relative, "before": pack(before),
                                          "after": pack(after), "mode": mode})
            parent = (self.home / relative).parent
            while parent != self.home and not parent.exists():
                rel = parent.relative_to(self.home).as_posix()
                if rel not in dirs:
                    dirs.append(rel)
                parent = parent.parent
        self.atomic(self.state / "pending.json", encoded(journal))
        if manifest is not None:
            for relative, before, _, _ in operations:
                entry = manifest["files"][relative]
                backup = self.state / entry["backup"]
                if before is not None and self.read(backup) is None and entry["before"] == digest(before):
                    self.atomic(backup, before)
        for index, op in enumerate(journal["operations"], 1):
            target = self.home / op["path"]
            if self.read(target) != unpack(op["before"]):
                raise Conflict("File changed during transaction: " + op["path"])
            self.atomic(target, unpack(op["after"]), op["mode"])
            if fail_after == index:
                raise OSError("Injected interrupted transaction")
        self.atomic(self.state / "manifest.json", new)
        if fail_after == len(operations) + 1:
            raise OSError("Injected interruption after manifest")
        self.atomic(self.state / "pending.json", None)
        return True

    def recover(self):
        raw = self.read(self.state / "pending.json")
        if raw is None:
            return
        journal = strict_json(raw)
        for op in journal["operations"]:
            if self.read(self.home / op["path"]) not in (unpack(op["before"]), unpack(op["after"])):
                raise Conflict("Recovery conflict; preserving changed file: " + op["path"])
        if self.read(self.state / "manifest.json") not in (
                unpack(journal["old_manifest"]), unpack(journal["new_manifest"])):
            raise Conflict("Manifest changed during interrupted transaction.")
        for op in reversed(journal["operations"]):
            self.atomic(self.home / op["path"], unpack(op["before"]), op["mode"])
        self.atomic(self.state / "manifest.json", unpack(journal["old_manifest"]))
        self.atomic(self.state / "pending.json", None)
        self.clean_dirs(journal)

    def original(self, entry):
        if entry["before"] is None:
            return None
        data = self.read(self.state / entry["backup"])
        if digest(data) != entry["before"]:
            raise Conflict("Original backup missing/changed: " + entry["backup"])
        return data

    def plan_uninstall(self):
        if self.read(self.state / "pending.json"):
            raise Conflict("Interrupted transaction found. Run recover first.")
        manifest = self.manifest()
        if manifest is None:
            return [], None
        theme = self.read(self.home / ".local/state/omarchy/current/theme.name")
        if theme and theme.decode().strip() in ("everest-dawn", "everest-dusk"):
            raise Conflict("Select a different Omarchy theme before removal. See README.")
        operations = []
        for relative, entry in manifest["files"].items():
            current = self.read(self.home / relative)
            original = self.original(entry)
            if digest(current) == entry["after"]:
                restored = original
            elif relative == HYPR and current is not None:
                text = current.decode()
                if text.count(BLOCK) != 1 or text.count(BEGIN) != 1 or text.count(END) != 1:
                    raise Conflict("Changed Everest Lua block; preserving " + HYPR)
                restored = text.replace(BLOCK, "", 1).encode()
            elif relative == SHELL and current is not None:
                shell = strict_json(current)
                bar = shell.get("bar")
                if not isinstance(bar, dict):
                    raise Conflict("Changed bar; preserving shell.json")
                for key, expected in manifest["bar_after"].items():
                    if key not in bar or not same(bar[key], expected):
                        raise Conflict("Changed managed bar setting; preserving " + key)
                    before = manifest["bar_before"][key]
                    if before["exists"]:
                        bar[key] = before["value"]
                    else:
                        del bar[key]
                if not bar:
                    shell.pop("bar", None)
                restored = encoded(shell)
            elif current == original:
                continue
            else:
                raise Conflict("Changed managed file; preserving " + relative +
                               ". Save your edits, then restore the installed version before removal.")
            if current != restored:
                operations.append((relative, current, restored, entry["mode"]))
        return operations, manifest

    def clean_dirs(self, manifest):
        if manifest:
            for relative in sorted(manifest["created_dirs"], key=len, reverse=True):
                path = self.home / relative
                if not path.is_symlink():
                    try:
                        path.rmdir()
                    except OSError:
                        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["plan", "install", "uninstall", "rollback",
                                            "recover", "status", "doctor"])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    app = Everest()
    if args.command == "doctor":
        print("Target: Omarchy 4.0.6 / Lua Hyprland / Quickshell")
        print("Platform:", sys.platform)
        for command in ("omarchy-version", "hyprctl", "qs", "magick"):
            print(command + ":", shutil.which(command) or "missing")
        if shutil.which("omarchy-version"):
            subprocess.run(["omarchy-version"], check=False)
        for relative in (HYPR, SHELL):
            print(relative + ":", "present" if app.read(app.home / relative) is not None else "missing")
        return
    if args.command == "status":
        manifest = app.manifest()
        print("Installed" if manifest else "Not installed")
        if manifest:
            for relative, entry in manifest["files"].items():
                print(("OK      " if digest(app.read(app.home / relative)) == entry["after"]
                       else "CHANGED ") + relative)
        if app.read(app.state / "pending.json"):
            print("Interrupted transaction: run recover")
        return
    if args.command in ("plan", "install"):
        ops, manifest = app.plan_install()
        for relative, before, _, _ in ops:
            print(("CREATE " if before is None else "UPDATE ") + str(app.home / relative))
        print("Theme selection/session activation are separate; see README.")
        if args.command == "plan" or args.dry_run:
            return
    elif args.command in ("uninstall", "rollback"):
        ops, prior = app.plan_uninstall()
        for relative, _, after, _ in ops:
            print(("REMOVE " if after is None else "RESTORE ") + str(app.home / relative))
        if args.dry_run:
            return
    app.safe(app.state / "lock")
    app.state.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(app.state, 0o700)
    with open(app.state / "lock", "a", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.command == "recover":
            app.recover()
            print("Recovery complete.")
        elif args.command == "install":
            ops, manifest = app.plan_install()
            print("Installed." if app.execute(ops, manifest) else "Already up to date; no changes.")
            print("Backups and managed-file manifest:", app.state)
        else:
            ops, prior = app.plan_uninstall()
            app.execute(ops, None)
            app.clean_dirs(prior)
            print("Removed. Original backups retained at", app.state / "backups")


if __name__ == "__main__":
    try:
        main()
    except (Conflict, OSError, ValueError, subprocess.SubprocessError) as error:
        print("Everest:", error, file=sys.stderr)
        sys.exit(1)
