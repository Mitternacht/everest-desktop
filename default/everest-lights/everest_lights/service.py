"""Lighting daemon: paints the keyboard, follows keypresses, serves the window."""

from __future__ import annotations

import json
import os
import select
import socket
import struct
import threading
import time
from pathlib import Path

from .config import load, save
from .keymap import PAINTED_IDS, lights_for
from .protocol import Chassis, HidError, Keyboard, find_key_events

EVENT_STRUCT = struct.Struct("llHHi")
EV_KEY = 1
SOCKET_NAME = "everest-lights.sock"


def runtime_dir() -> Path:
    return Path(os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}")


def socket_path() -> Path:
    return runtime_dir() / SOCKET_NAME


def state_dir() -> Path:
    root = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(root) / "everest"


def log(message: str) -> None:
    line = time.strftime("%Y-%m-%d %H:%M:%S") + " " + message
    try:
        directory = state_dir()
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / "lights.log").open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        pass


def scale(rgb: list[int] | tuple[int, int, int], brightness: int) -> tuple[int, int, int]:
    factor = max(0, min(100, brightness)) / 100
    return tuple(max(0, min(255, int(channel * factor))) for channel in rgb[:3])


def mix(rest: tuple[int, int, int], pressed: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    amount = max(0.0, min(1.0, amount))
    return tuple(int(rest[i] + (pressed[i] - rest[i]) * amount) for i in range(3))


class Engine:
    def __init__(self):
        self.config = load()
        self.error = ""
        self.keyboard: Keyboard | None = None
        self.chassis: Chassis | None = None
        self.events: list[int] = []
        self.held: set[int] = set()
        self.fade_until: dict[int, float] = {}
        self.shown: dict[int, tuple[int, int, int]] | None = None
        self.full = True
        self.chassis_due = True
        self.flash_until = 0.0
        self.last_paint = 0.0
        self.next_open = 0.0
        self.lock = threading.Lock()
        self.wake = threading.Event()
        self.stop = False
        self._open_devices()

    def status(self) -> dict:
        with self.lock:
            return {
                "ok": self.error == "",
                "error": self.error,
                "config": self.config,
                "keyboard": getattr(self.keyboard, "path", None),
                "chassis": getattr(self.chassis, "path", None),
                "keys": len(self.events),
            }

    def _open_devices(self) -> None:
        notes: list[str] = []
        if self.keyboard is None:
            try:
                self.keyboard = Keyboard()
                self.full = True
                log(f"keyboard {self.keyboard.path}")
            except HidError as exc:
                notes.append(str(exc))
        if self.chassis is None:
            try:
                self.chassis = Chassis()
                self.chassis_due = True
                log(f"chassis {self.chassis.path}")
            except HidError as exc:
                notes.append(str(exc))
        if not self.events:
            for node in find_key_events():
                try:
                    self.events.append(os.open(node, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC))
                    log(f"keys {node}")
                except PermissionError:
                    notes.append(f"cannot read {node}")
        self.error = "; ".join(dict.fromkeys(notes))
        if self.error and self.error != getattr(self, "_logged_error", ""):
            log(self.error)
            self._logged_error = self.error

    def close(self) -> None:
        self.stop = True
        self.wake.set()
        if self.keyboard:
            self.keyboard.close()
        if self.chassis:
            self.chassis.close()
        for fd in self.events:
            os.close(fd)
        self.events.clear()

    def update(self, patch: dict) -> dict:
        with self.lock:
            merged = dict(self.config)
            merged.update(patch)
            self.config = save(merged)
            self.full = True
            self.chassis_due = True
        self.wake.set()
        return self.config

    def flash(self) -> None:
        with self.lock:
            self.flash_until = time.monotonic() + 0.45
            self.full = True
        self.wake.set()

    def desired(self, now: float) -> dict[int, tuple[int, int, int]]:
        config = self.config
        brightness = config["brightness"]
        if config["mode"] == "off":
            rest = (0, 0, 0)
            pressed = (0, 0, 0)
        else:
            rest = scale(config["base"], brightness)
            pressed = scale(config["press"], brightness)
        colors = {light_id: rest for light_id in PAINTED_IDS}
        if config["mode"] != "typing":
            if now < self.flash_until:
                colors = {light_id: pressed for light_id in PAINTED_IDS}
            return colors
        if now < self.flash_until:
            return {light_id: pressed for light_id in PAINTED_IDS}
        fade_ms = config["fade_ms"]
        for light_id in self.held:
            colors[light_id] = pressed
        expired = []
        for light_id, deadline in self.fade_until.items():
            if light_id in self.held:
                continue
            remaining = deadline - now
            if remaining <= 0:
                expired.append(light_id)
                continue
            colors[light_id] = mix(rest, pressed, remaining / (fade_ms / 1000))
        for light_id in expired:
            self.fade_until.pop(light_id, None)
        return colors

    def chassis_color(self) -> tuple[int, int, int] | None:
        config = self.config
        if not config["chassis"] or config["mode"] == "off":
            return (0, 0, 0) if self.chassis else None
        source = config["base"] if config["chassis_match"] else config["chassis_color"]
        return scale(source, config["brightness"])

    def tick(self) -> None:
        self._drain_keys()
        now = time.monotonic()
        with self.lock:
            colors = self.desired(now)
            restart = self.full
            paint = restart or colors != self.shown
            chassis_due = self.chassis_due
            chassis_rgb = self.chassis_color()
            power = self.config["power"] and self.config["mode"] != "off" and self.config["chassis"]
            self.full = False
            self.chassis_due = False
        if paint and self.keyboard and (restart or now - self.last_paint >= 0.04):
            try:
                self.keyboard.paint(colors, restart=restart)
                self.shown = colors
                self.last_paint = now
            except HidError as exc:
                self.error = str(exc)
                log(str(exc))
                self.shown = None
                with self.lock:
                    self.full = True
        if chassis_due and self.chassis and chassis_rgb is not None:
            try:
                self.chassis.paint(*chassis_rgb, power and chassis_rgb != (0, 0, 0))
            except HidError as exc:
                self.error = str(exc)
                log(str(exc))

    def _drain_keys(self) -> None:
        if not self.events:
            return
        readable, _, _ = select.select(self.events, [], [], 0)
        if not readable:
            return
        now = time.monotonic()
        changed = False
        with self.lock:
            fade = self.config["fade_ms"] / 1000
            typing = self.config["mode"] == "typing"
        for fd in readable:
            while True:
                try:
                    packet = os.read(fd, EVENT_STRUCT.size * 64)
                except BlockingIOError:
                    break
                except OSError:
                    break
                if not packet:
                    break
                count = len(packet) // EVENT_STRUCT.size
                for index in range(count):
                    _, _, kind, code, value = EVENT_STRUCT.unpack_from(packet, index * EVENT_STRUCT.size)
                    if kind != EV_KEY or not typing:
                        continue
                    lights = lights_for(code)
                    if not lights:
                        continue
                    with self.lock:
                        if value == 1:
                            for light_id in lights:
                                self.held.add(light_id)
                                self.fade_until.pop(light_id, None)
                            changed = True
                        elif value == 0:
                            for light_id in lights:
                                self.held.discard(light_id)
                                self.fade_until[light_id] = now + fade
                            changed = True
        if changed:
            self.wake.set()

    def serve(self, connection: socket.socket) -> None:
        try:
            chunks = []
            while True:
                piece = connection.recv(65536)
                if not piece:
                    break
                chunks.append(piece)
                if b"\n" in piece:
                    break
            raw = b"".join(chunks).split(b"\n", 1)[0]
            if not raw:
                return
            message = json.loads(raw.decode("utf-8"))
            command = message.get("cmd")
            if command == "get":
                reply = self.status()
            elif command == "set":
                config = self.update(message.get("config") or {})
                reply = {"ok": True, "config": config}
            elif command == "flash":
                self.flash()
                reply = {"ok": True}
            elif command == "off":
                self.update({"mode": "off"})
                reply = {"ok": True, "config": self.config}
            else:
                reply = {"ok": False, "error": "unknown command"}
            connection.sendall(json.dumps(reply).encode("utf-8") + b"\n")
        except (OSError, json.JSONDecodeError, UnicodeError) as exc:
            log(f"client: {exc}")
        finally:
            connection.close()

    def run(self) -> None:
        path = socket_path()
        if path.exists():
            path.unlink()
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(path))
        os.chmod(path, 0o600)
        server.listen(4)
        server.setblocking(False)
        log(f"listening on {path}")
        self.tick()
        while not self.stop:
            self.wake.wait(0.033)
            self.wake.clear()
            now = time.monotonic()
            if now >= self.next_open and (self.keyboard is None or self.chassis is None or not self.events):
                self.next_open = now + 2
                self._open_devices()
            while True:
                try:
                    connection, _ = server.accept()
                except BlockingIOError:
                    break
                threading.Thread(target=self.serve, args=(connection,), daemon=True).start()
            self.tick()
        server.close()
        try:
            path.unlink()
        except OSError:
            pass


def call(message: dict, timeout: float = 2.0) -> dict:
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(timeout)
    client.connect(str(socket_path()))
    client.sendall(json.dumps(message).encode("utf-8") + b"\n")
    data = b""
    while b"\n" not in data:
        piece = client.recv(65536)
        if not piece:
            break
        data += piece
    client.close()
    return json.loads(data.decode("utf-8"))


def main() -> None:
    engine = Engine()
    try:
        engine.run()
    finally:
        engine.close()
