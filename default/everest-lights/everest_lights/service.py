"""Lighting daemon: paints the keyboard, follows keypresses, serves the window."""

from __future__ import annotations

import fcntl
import json
import os
import re
import select
import socket
import struct
import subprocess
import threading
import time
from pathlib import Path

from .config import load, save
from .keymap import CAPS_LIGHTS, MIC_MUTE_LIGHTS, PAINTED_IDS, SPEAKER_MUTE_LIGHTS, lights_for
from .protocol import Chassis, HidError, Keyboard, find_key_events

EVENT_STRUCT = struct.Struct("llHHi")
EV_KEY = 1
LED_CAPSL = 1
# EVIOCGLED(8): the LED bits the compositor last set on this keyboard.
EVIOCGLED = (2 << 30) | (8 << 16) | (ord("E") << 8) | 0x19
SOCKET_NAME = "everest-lights.sock"
SYN_DROPPED = 3
# Resend every light this often; the firmware can drop or revert a color.
FULL_REPAINT_S = 2.0
AUDIO_EVENT = re.compile(r"Event 'change' on (sink|source|server)\b(?!-)")
# Muted audio keys show full white, like Dell's own mute lamp, at any brightness.
MUTED_WHITE = (255, 255, 255)


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


def _caps_on(fd: int) -> bool:
    buf = bytearray(8)
    try:
        fcntl.ioctl(fd, EVIOCGLED, buf, True)
    except OSError:
        return False
    return bool(buf[0] >> LED_CAPSL & 1)


def _audio_muted() -> tuple[bool | None, bool | None]:
    """None when pactl could not answer, so a hiccup never reads as unmuted."""

    def muted(args: list[str]) -> bool | None:
        try:
            text = subprocess.check_output(args, text=True, timeout=1)
        except (OSError, subprocess.SubprocessError):
            return None
        return "yes" in text.lower()

    return (
        muted(["pactl", "get-sink-mute", "@DEFAULT_SINK@"]),
        muted(["pactl", "get-source-mute", "@DEFAULT_SOURCE@"]),
    )


class Engine:
    def __init__(self):
        self.config = load()
        self.error = ""
        self.keyboard: Keyboard | None = None
        self.chassis: Chassis | None = None
        self.events: list[int] = []
        self.caps_on = False
        self.speaker_muted = False
        self.mic_muted = False
        self.audio_thread: threading.Thread | None = None
        self.audio_proc: subprocess.Popen | None = None
        self.held: set[int] = set()
        self.fade_until: dict[int, float] = {}
        self.shown: dict[int, tuple[int, int, int]] | None = None
        # restart re-enters custom mode (startup, suspend, a reopened keyboard);
        # repaint only resends every light (settings changes, the periodic refresh).
        self.restart = True
        self.repaint = False
        self.last_full = 0.0
        self.slept = 0.0
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
                self.restart = True
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
        if self.audio_proc:
            self.audio_proc.kill()
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
            if merged.get("mode") != self.config.get("mode"):
                self.held.clear()
                self.fade_until.clear()
            self.config = save(merged)
            self.repaint = True
            self.chassis_due = True
        self.wake.set()
        return self.config

    def flash(self) -> None:
        with self.lock:
            self.flash_until = time.monotonic() + 0.45
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
        if config["mode"] == "off":
            return colors
        if config["mode"] != "typing":
            if now < self.flash_until:
                colors = {light_id: pressed for light_id in PAINTED_IDS}
            else:
                self._apply_indicators(colors, rest, pressed, MUTED_WHITE)
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
        self._apply_indicators(colors, rest, pressed, MUTED_WHITE)
        return colors

    def _apply_indicators(self, colors: dict[int, tuple[int, int, int]], rest, pressed, muted) -> None:
        """Caps, mute, and mic stay lit only while that state is actually on."""
        if self.caps_on:
            for light_id in CAPS_LIGHTS:
                colors[light_id] = pressed
        for light_id in SPEAKER_MUTE_LIGHTS:
            colors[light_id] = muted if self.speaker_muted else rest
        for light_id in MIC_MUTE_LIGHTS:
            colors[light_id] = muted if self.mic_muted else rest

    def _refresh_caps(self) -> None:
        """Hyprland owns the lock LEDs. Follow them, never write them."""
        if not self.events:
            return
        caps = _caps_on(self.events[0])
        self.caps_on = caps

    def chassis_color(self) -> tuple[int, int, int] | None:
        config = self.config
        if not config["chassis"] or config["mode"] == "off":
            return (0, 0, 0) if self.chassis else None
        source = config["base"] if config["chassis_match"] else config["chassis_color"]
        return scale(source, config["brightness"])

    def _woke_from_sleep(self) -> bool:
        """The keyboard forgets custom mode across suspend; monotonic time skips it."""
        slept = time.clock_gettime(time.CLOCK_BOOTTIME) - time.monotonic()
        woke = slept - self.slept > 1
        self.slept = slept
        return woke

    def tick(self) -> None:
        self._drain_keys()
        now = time.monotonic()
        with self.lock:
            if self._woke_from_sleep():
                self.restart = True
            self._refresh_caps()
            colors = self.desired(now)
            restart = self.restart
            full = restart or self.repaint or self.shown is None or now - self.last_full >= FULL_REPAINT_S
            paint = full or colors != self.shown
            chassis_due = self.chassis_due
            chassis_rgb = self.chassis_color()
            power = self.config["power"] and self.config["mode"] != "off" and self.config["chassis"]
        if paint and self.keyboard and (restart or now - self.last_paint >= 0.04):
            if full:
                changes = colors
            else:
                changes = {light_id: rgb for light_id, rgb in colors.items() if self.shown.get(light_id) != rgb}
            try:
                self.keyboard.paint(changes, restart=restart)
            except HidError as exc:
                self._lost_keyboard(exc, now)
            else:
                with self.lock:
                    self.shown = colors
                    self.restart = self.repaint = False
                    if full:
                        self.last_full = now
                self.last_paint = now
        if chassis_due and self.chassis and chassis_rgb is not None:
            try:
                self.chassis.paint(*chassis_rgb, power and chassis_rgb != (0, 0, 0))
            except HidError as exc:
                self.error = str(exc)
                log(str(exc))
                self.chassis.close()
                self.chassis = None
                self.next_open = now + 1
            else:
                with self.lock:
                    self.chassis_due = False

    def _lost_keyboard(self, exc: HidError, now: float) -> None:
        """Drop the handle; run() reopens it, so a replugged keyboard comes back."""
        self.error = str(exc)
        log(str(exc))
        self.keyboard.close()
        self.keyboard = None
        self.next_open = now + 1
        with self.lock:
            self.shown = None
            self.restart = True

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
                except OSError as exc:
                    # The node went away (replug, resume); run() reopens it.
                    log(f"keys: {exc}")
                    os.close(fd)
                    self.events.remove(fd)
                    break
                if not packet:
                    break
                count = len(packet) // EVENT_STRUCT.size
                for index in range(count):
                    _, _, kind, code, value = EVENT_STRUCT.unpack_from(packet, index * EVENT_STRUCT.size)
                    if kind == 0 and code == SYN_DROPPED:
                        # Releases were lost; nothing may stay stuck lit.
                        with self.lock:
                            self.held.clear()
                        changed = True
                        continue
                    if kind != EV_KEY or (value == 1 and not typing):
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

    def _check_audio(self) -> None:
        speaker, mic = _audio_muted()
        with self.lock:
            speaker = self.speaker_muted if speaker is None else speaker
            mic = self.mic_muted if mic is None else mic
            if (speaker, mic) == (self.speaker_muted, self.mic_muted):
                return
            self.speaker_muted = speaker
            self.mic_muted = mic
        log(f"audio lights speaker={'muted' if speaker else 'on'} mic={'muted' if mic else 'on'}")
        self.wake.set()

    def _watch_audio(self) -> None:
        """Follow the default sink and source mute through pactl subscribe."""
        backoff = 1.0
        while not self.stop:
            try:
                watcher = subprocess.Popen(
                    ["pactl", "subscribe"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                )
            except OSError as exc:
                log(f"pactl subscribe: {exc}")
                time.sleep(5)
                continue
            self.audio_proc = watcher
            started = time.monotonic()
            # Subscribed first, then read, so no change slips in between.
            self._check_audio()
            for line in watcher.stdout:
                if self.stop:
                    break
                if AUDIO_EVENT.match(line):
                    self._check_audio()
            watcher.kill()
            watcher.wait()
            # pactl exits at once while PipeWire is down; do not spin on it.
            backoff = min(backoff * 2, 30.0) if time.monotonic() - started < 2 else 1.0
            time.sleep(backoff)

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
        self.audio_thread = threading.Thread(target=self._watch_audio, name="audio-mute", daemon=True)
        self.audio_thread.start()
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
