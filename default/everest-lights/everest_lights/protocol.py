"""AlienFX APIv5 (keyboard) and APIv4 (chassis) over hidraw.

The keyboard is Darfon 0d62:babc, feature report 0xCC, 64 bytes.
The chassis is Alienware AW-ELC 187c:0550, output report id 0, 34 bytes.
hid-generic stays bound. Nothing here detaches the kernel driver.
"""

from __future__ import annotations

import fcntl
import glob
import os
import time

KEYBOARD_VID = "0D62"
KEYBOARD_PID = "BABC"
CHASSIS_VID = "187C"
CHASSIS_PID = "0550"

FEATURE_LEN = 64
FEATURE_ID = 0xCC
OUTPUT_LEN = 34

# Awake power-button states: AC, charging, battery.
POWER_STATES = (0x5C, 0x5D, 0x5F)
POWER_LIGHT_ID = 2
CHASSIS_LIGHT_IDS = tuple(range(16))


def _ioc(direction: int, nr: int, size: int) -> int:
    return (direction << 30) | (size << 16) | (ord("H") << 8) | nr


def _set_feature_ioc(size: int) -> int:
    return _ioc(3, 0x06, size)


def feature_report(payload: bytes) -> bytes:
    if 1 + len(payload) > FEATURE_LEN:
        raise ValueError(f"feature payload is {len(payload)} bytes")
    buf = bytearray(FEATURE_LEN)
    buf[0] = FEATURE_ID
    buf[1 : 1 + len(payload)] = payload
    return bytes(buf)


def color_set_payloads(items: list[tuple[int, int, int, int]]) -> list[bytes]:
    """Pack (light_id, r, g, b) into ColorSet payloads, 15 keys each."""
    payloads: list[bytes] = []
    for start in range(0, len(items), 15):
        data = bytearray((0x8C, 0x02, 0x00))
        for light_id, red, green, blue in items[start : start + 15]:
            data += bytes(((light_id + 1) & 0xFF, red & 0xFF, green & 0xFF, blue & 0xFF))
        payloads.append(bytes(data))
    return payloads


def output_report(payload: bytes, mods: list[tuple[int, bytes]] | None = None) -> bytes:
    buf = bytearray(OUTPUT_LEN)
    buf[1 : 1 + len(payload)] = payload
    if mods:
        for offset, values in mods:
            buf[offset : offset + len(values)] = values
    return bytes(buf)


def _hidraw_nodes():
    for path in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
        yield path


def _uevent(path: str) -> str:
    try:
        return open(os.path.join(path, "device", "uevent"), encoding="utf-8", errors="replace").read().upper()
    except OSError:
        return ""


def find_keyboard() -> str | None:
    for path in _hidraw_nodes():
        uevent = _uevent(path)
        if KEYBOARD_VID not in uevent or KEYBOARD_PID not in uevent:
            continue
        try:
            descriptor = open(os.path.join(path, "device", "report_descriptor"), "rb").read()
        except OSError:
            continue
        if b"\x09\xcc" in descriptor and b"\x85\xcc" in descriptor:
            return "/dev/" + os.path.basename(path)
    return None


def find_chassis() -> str | None:
    for path in _hidraw_nodes():
        uevent = _uevent(path)
        if CHASSIS_VID in uevent and CHASSIS_PID in uevent:
            return "/dev/" + os.path.basename(path)
    return None


def find_key_events() -> list[str]:
    """Event nodes for the Darfon keyboard, including its consumer-control keys."""
    found: list[str] = []
    for node in sorted(glob.glob("/sys/class/input/event*")):
        current = os.path.realpath(os.path.join(node, "device"))
        matched = False
        for _ in range(12):
            vendor = os.path.join(current, "idVendor")
            product = os.path.join(current, "idProduct")
            if os.path.isfile(vendor) and os.path.isfile(product):
                try:
                    vid = open(vendor, encoding="utf-8").read().strip().upper()
                    pid = open(product, encoding="utf-8").read().strip().upper()
                except OSError:
                    break
                matched = vid == KEYBOARD_VID and pid == KEYBOARD_PID
                break
            parent = os.path.dirname(current)
            if parent == current:
                break
            current = parent
        if matched:
            found.append("/dev/input/" + os.path.basename(node))
    return found


class HidError(OSError):
    pass


class Keyboard:
    def __init__(self, path: str | None = None):
        self.path = path or find_keyboard()
        if not self.path:
            raise HidError("Darfon keyboard 0d62:babc not found")
        try:
            self.fd = os.open(self.path, os.O_RDWR | os.O_CLOEXEC)
        except PermissionError as exc:
            raise HidError(f"cannot open {self.path}") from exc
        self.ready = False

    def close(self) -> None:
        fd = getattr(self, "fd", None)
        if fd is not None:
            os.close(fd)
            self.fd = None

    def _feature(self, payload: bytes) -> None:
        buf = bytearray(feature_report(payload))
        try:
            fcntl.ioctl(self.fd, _set_feature_ioc(FEATURE_LEN), buf, True)
        except OSError as exc:
            raise HidError(exc.errno, f"keyboard feature report failed: {exc}") from exc

    def reset(self) -> None:
        self._feature(bytes((0x94,)))

    def set_brightness(self, level: int) -> None:
        """Hardware dimmer under every key color; Fn+F7 changes it too.

        Level 0 blanked an m16 R2 keyboard until reboot, so it is never sent.
        """
        self._feature(bytes((0x83, 0x38, 0x9C, max(1, min(255, level)))))

    def enter_custom_mode(self) -> None:
        """Leave the firmware animation and accept per-key colors."""
        self.reset()
        self._feature(bytes((0x80, 0x01, 0xFE, 0x00, 0x00, 0x01, 0x01, 0x01)))
        self._feature(bytes((0x8B, 0x01, 0xFF)))
        # Packets sent in the first 20-50 ms after this are dropped, and the
        # first color packet carries ids 0-29: Esc, the F row and the audio keys.
        time.sleep(0.1)
        # Full hardware level; the app's brightness scales colors instead.
        self.set_brightness(255)
        self.ready = True

    def paint(self, colors: dict[int, tuple[int, int, int]], restart: bool = False) -> None:
        if restart or not self.ready:
            self.enter_custom_mode()
        items = [(light_id, rgb[0], rgb[1], rgb[2]) for light_id, rgb in sorted(colors.items())]
        for payload in color_set_payloads(items):
            self._feature(payload)
            # Loop after every packet, as Zeecka's measured m15 R7 code does.
            self._feature(bytes((0x8C, 0x13)))


class Chassis:
    def __init__(self, path: str | None = None):
        self.path = path or find_chassis()
        if not self.path:
            raise HidError("AW-ELC chassis 187c:0550 not found")
        try:
            self.fd = os.open(self.path, os.O_RDWR | os.O_CLOEXEC)
        except PermissionError as exc:
            raise HidError(f"cannot open {self.path}") from exc

    def close(self) -> None:
        fd = getattr(self, "fd", None)
        if fd is not None:
            os.close(fd)
            self.fd = None

    def _out(self, payload: bytes, mods: list[tuple[int, bytes]] | None = None) -> None:
        report = output_report(payload, mods)
        try:
            written = os.write(self.fd, report)
        except OSError as exc:
            raise HidError(f"chassis report failed: {exc}") from exc
        if written != len(report):
            raise HidError(f"chassis report wrote {written} of {len(report)} bytes")
        time.sleep(0.006)

    def paint(self, red: int, green: int, blue: int, power: bool) -> None:
        ids = bytes(CHASSIS_LIGHT_IDS)
        self._out(bytes((0x03, 0x21, 0x00, 0x03, 0x00, 0xFF)), [(4, bytes((4,)))])
        self._out(bytes((0x03, 0x21, 0x00, 0x03, 0x00, 0xFF)), [(4, bytes((1,)))])
        self._out(
            bytes((0x03, 0x27)),
            [(3, bytes((red, green, blue, 0, len(ids))) + ids)],
        )
        self._out(bytes((0x03, 0x21, 0x00, 0x03, 0x00, 0xFF)))
        if power:
            self._paint_power(red, green, blue)

    def _paint_power(self, red: int, green: int, blue: int) -> None:
        control = bytes((0x03, 0x21, 0x00, 0x03, 0x00, 0xFF))
        for state in POWER_STATES:
            self._out(bytes((0x03, 0x22)), [(4, bytes((4, 0, state)))])
            self._out(bytes((0x03, 0x22)), [(4, bytes((1, 0, state)))])
            self._out(bytes((0x03, 0x23, 0x01, 0x00, 0x01)), [(6, bytes((POWER_LIGHT_ID,)))])
            self._out(
                bytes((0x03, 0x24, 0x00, 0x07, 0xD0, 0x00, 0xFA)),
                [(3, bytes((0, 0, 0xD0, 0, 0xFA, red, green, blue)))],
            )
            self._out(bytes((0x03, 0x22)), [(4, bytes((2, 0, state)))])
        self._out(control, [(4, bytes((5,)))])
