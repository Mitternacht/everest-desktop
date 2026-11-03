"""Walk the keyboard one light id at a time and record which key answers.

Each id lights red on a dim keyboard. The person taps the key that lit,
so the answer comes straight from evdev instead of from a guessed map.
Keys are taken on release, alone, so Ctrl+C never records Ctrl. A key that
types something only counts if it also reached this terminal, and a silent
key (Shift, Super, ...) only while this terminal has focus, so keys pressed
in another window are ignored.

  tap the red key          that key owns this id
  Esc Esc                  nothing visibly lit
  Tab Tab                  a key lit but sends nothing (Fn); type its name
  Backspace Backspace      go back one id
  Ctrl+C                   stop; answers so far are kept
"""

from __future__ import annotations

import json
import os
import re
import select
import struct
import sys
import termios
import time
import tty
from pathlib import Path

from .protocol import Keyboard, find_key_events

EVENT_STRUCT = struct.Struct("llHHi")
EV_KEY = 1
KEY_ESC, KEY_BACKSPACE, KEY_TAB = 1, 14, 15
DOUBLE_TAP = 0.45
# Keys that never type into a terminal, so they cannot be checked against it:
# Ctrl, Shift, Alt, Super, Caps, Compose, Fn, Macro, Print and the audio keys.
SILENT = {29, 97, 42, 54, 56, 100, 125, 126, 58, 127, 464, 112, 99, 113, 114, 115, 190, 248}
DIM = (0, 0, 36)
LIT = (255, 0, 0)
ALL_IDS = tuple(range(0, 160))


def results_path() -> Path:
    root = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(root) / "everest" / "keymap-calibration.json"


def key_names() -> dict[int, str]:
    names: dict[int, str] = {}
    try:
        text = Path("/usr/include/linux/input-event-codes.h").read_text(encoding="utf-8")
    except OSError:
        return names
    for name, value in re.findall(r"#define\s+((?:KEY|BTN)_\w+)\s+(0x[0-9a-fA-F]+|\d+)\b", text):
        names.setdefault(int(value, 0), name)
    return names


def _load() -> dict:
    path = results_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = {}
    except json.JSONDecodeError:
        path.rename(path.with_suffix(".bad"))
        raise SystemExit(f"{path} was damaged; kept it as {path.with_suffix('.bad')}. Run again to start over.")
    data.setdefault("keyboard", "0d62:babc")
    data.setdefault("lights", {})
    return data


def _save(data: dict) -> None:
    path = results_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


class Keys:
    """Releases from the keyboard's event nodes, one lone key at a time."""

    def __init__(self):
        self.fds = []
        for node in find_key_events():
            try:
                self.fds.append(os.open(node, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC))
            except OSError:
                continue
        if not self.fds:
            raise SystemExit("Cannot read the keyboard event node.")
        self.down: set[int] = set()
        self.chord = False
        self.pressed_at: dict[int, float] = {}
        self.typed_at = 0.0
        # Updated from the terminal's focus reports (CSI I / CSI O). A
        # terminal without them never reports, and the tab counts as focused.
        self.focused = True

    def close(self) -> None:
        for fd in self.fds:
            os.close(fd)

    def drain(self) -> None:
        while True:
            readable, _, _ = select.select([*self.fds, sys.stdin], [], [], 0)
            if not readable:
                break
            for fd in readable:
                if fd is sys.stdin:
                    self._read_stdin()
                else:
                    os.read(fd, 4096)
        self.down.clear()
        self.chord = False

    def _read_stdin(self) -> None:
        data = os.read(sys.stdin.fileno(), 1024)
        for report, focused in ((b"\x1b[I", True), (b"\x1b[O", False)):
            if report in data:
                self.focused = focused
                data = data.replace(report, b"")
        if data:
            self.typed_at = time.time()

    def _typed_here(self, code: int) -> bool:
        """True if the key's own text arrived on this terminal's stdin."""
        since = self.pressed_at.get(code, 0.0) - 0.05
        deadline = time.monotonic() + 0.3
        while self.typed_at < since:
            wait = deadline - time.monotonic()
            if wait <= 0 or not select.select([sys.stdin], [], [], wait)[0]:
                return False
            self._read_stdin()
        return True

    def next(self, timeout: float | None) -> int | None:
        """Return the next key released with no other key held, or None."""
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            wait = None if deadline is None else max(0.0, deadline - time.monotonic())
            readable, _, _ = select.select([*self.fds, sys.stdin], [], [], wait)
            if sys.stdin in readable:
                self._read_stdin()
            for fd in readable:
                if fd is sys.stdin:
                    continue
                try:
                    packet = os.read(fd, EVENT_STRUCT.size * 64)
                except OSError:
                    continue
                for index in range(len(packet) // EVENT_STRUCT.size):
                    sec, usec, kind, code, value = EVENT_STRUCT.unpack_from(packet, index * EVENT_STRUCT.size)
                    if kind != EV_KEY:
                        continue
                    if value == 1:
                        if self.down:
                            self.chord = True
                        self.down.add(code)
                        self.pressed_at[code] = sec + usec / 1e6
                    elif value == 0 and code in self.down:
                        self.down.discard(code)
                        lone = not self.chord
                        if not self.down:
                            self.chord = False
                        if not lone:
                            continue
                        if code in SILENT and self.focused or code not in SILENT and self._typed_here(code):
                            return code
                        print("(ignored a key typed outside this tab) ", end="", flush=True)
            if deadline is not None and time.monotonic() >= deadline:
                return None


def _answer(keys: Keys) -> tuple[str, int | None]:
    code = keys.next(None)
    if code in (KEY_ESC, KEY_TAB, KEY_BACKSPACE):
        if keys.next(DOUBLE_TAP) == code:
            return {KEY_ESC: "none", KEY_TAB: "label", KEY_BACKSPACE: "back"}[code], None
    return "key", code


def _label(light_id: int) -> str:
    termios.tcflush(sys.stdin, termios.TCIFLUSH)
    attrs = termios.tcgetattr(sys.stdin)
    cooked = list(attrs)
    cooked[3] |= termios.ECHO | termios.ICANON
    termios.tcsetattr(sys.stdin, termios.TCSANOW, cooked)
    try:
        return input(f"    name the key lit by id {light_id}: ").strip() or "unnamed"
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSANOW, attrs)


def run(ids: list[int] | None = None) -> None:
    data = _load()
    lights: dict = data["lights"]
    todo = ids or [light_id for light_id in ALL_IDS if str(light_id) not in lights]
    if not todo:
        print(f"Every id already has an answer in {results_path()}.")
        print("Pass ids to redo some, for example: everest-lights calibrate 16,19,60")
        return
    names = key_names()
    keyboard = Keyboard()
    keys = Keys()
    saved = termios.tcgetattr(sys.stdin)
    tty.setcbreak(sys.stdin.fileno())
    attrs = termios.tcgetattr(sys.stdin)
    attrs[3] &= ~termios.ECHO
    termios.tcsetattr(sys.stdin, termios.TCSANOW, attrs)
    sys.stdout.write("\x1b[?1004h")
    print(__doc__.split("\n\n", 1)[1])
    print(f"{len(todo)} ids to check. Answers go to {results_path()}\n")
    try:
        keyboard.paint({light_id: DIM for light_id in ALL_IDS}, restart=True)
        index = 0
        while index < len(todo):
            light_id = todo[index]
            keyboard.paint({light_id: LIT})
            print(f"id {light_id:3d} ({index + 1}/{len(todo)}) ... ", end="", flush=True)
            keys.drain()
            kind, code = _answer(keys)
            keyboard.paint({light_id: DIM})
            if kind == "back":
                print("back")
                index = max(0, index - 1)
                continue
            if kind == "none":
                lights[str(light_id)] = {"none": True}
                print("nothing lit")
            elif kind == "label":
                print()
                lights[str(light_id)] = {"label": _label(light_id)}
            else:
                name = names.get(code, f"code {code}")
                lights[str(light_id)] = {"code": code, "key": name}
                print(name)
            _save(data)
            index += 1
        print(f"\nDone. All {len(todo)} ids answered. You can close this tab.")
    except KeyboardInterrupt:
        print("\nStopped. Answers so far are saved; run it again to continue.")
    finally:
        sys.stdout.write("\x1b[?1004l")
        termios.tcsetattr(sys.stdin, termios.TCSANOW, saved)
        keys.close()
        keyboard.close()
        print("The keyboard is left in the test pattern. Start the lights again with:")
        print("  systemctl --user start everest-lights.service")
