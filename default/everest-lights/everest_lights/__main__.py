"""Launch the lights window, the background service, or a one-time hardware check."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from .protocol import find_chassis, find_keyboard, find_key_events
from .service import call, main as serve

REPO = Path(__file__).resolve().parents[3]
LAUNCHER = Path(__file__).resolve().parents[1] / "everest-lights"
RULES = REPO / "default" / "udev" / "alienware-lights.rules"
ICON = REPO / "applications" / "icons" / "everest-lights.svg"


def _session_env() -> dict[str, str]:
    env = os.environ.copy()
    runtime = env.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    env.setdefault("XDG_RUNTIME_DIR", runtime)
    if "WAYLAND_DISPLAY" not in env:
        for name in ("wayland-1", "wayland-0"):
            if (Path(runtime) / name).exists():
                env["WAYLAND_DISPLAY"] = name
                break
    return env


def _can_open(path: str | None) -> bool:
    if not path:
        return False
    try:
        fd = os.open(path, os.O_RDWR | os.O_CLOEXEC)
    except OSError:
        return False
    os.close(fd)
    return True


def install_system() -> None:
    if os.geteuid() != 0:
        raise SystemExit("install-system must run as root")
    if not RULES.is_file():
        raise SystemExit(f"missing udev rules: {RULES}")
    destination = Path("/etc/udev/rules.d/71-alienware-lights.rules")
    destination.write_text(RULES.read_text(encoding="utf-8"), encoding="utf-8")
    os.chmod(destination, 0o644)
    subprocess.check_call(["udevadm", "control", "--reload"])
    subprocess.check_call(["udevadm", "trigger", "--subsystem-match=hidraw"])
    subprocess.check_call(["udevadm", "trigger", "--subsystem-match=input"])
    print(f"installed {destination}")


def install_user() -> None:
    env = _session_env()
    unit_dir = Path.home() / ".config" / "systemd" / "user"
    unit_dir.mkdir(parents=True, exist_ok=True)
    unit = unit_dir / "everest-lights.service"
    unit.write_text(
        "\n".join(
            [
                "[Unit]",
                "Description=Everest Alienware lighting",
                "After=graphical-session.target",
                "PartOf=graphical-session.target",
                "",
                "[Service]",
                "Type=simple",
                f"ExecStart={LAUNCHER} daemon",
                "Restart=on-failure",
                "RestartSec=2",
                "",
                "[Install]",
                "WantedBy=graphical-session.target",
                "",
            ]
        ),
        encoding="utf-8",
    )
    desktop_dir = Path.home() / ".local" / "share" / "applications"
    desktop_dir.mkdir(parents=True, exist_ok=True)
    installed = Path.home() / ".local" / "bin" / "everest-lights"
    desktop = desktop_dir / "everest-lights.desktop"
    desktop.write_text(
        "\n".join(
            [
                "[Desktop Entry]",
                "Name=Everest Lights",
                "Comment=Alienware keyboard and chassis lighting",
                f"Exec={installed}",
                "Icon=everest-lights",
                "Terminal=false",
                "Type=Application",
                "Categories=Settings;HardwareSettings;",
                "StartupNotify=true",
                "StartupWMClass=com.everest.Lights",
                "",
            ]
        ),
        encoding="utf-8",
    )
    icon_dir = Path.home() / ".local" / "share" / "icons" / "hicolor" / "scalable" / "apps"
    icon_dir.mkdir(parents=True, exist_ok=True)
    if ICON.is_file():
        (icon_dir / "everest-lights.svg").write_text(ICON.read_text(encoding="utf-8"), encoding="utf-8")
    subprocess.run(["update-desktop-database", str(desktop_dir)], check=False, env=env)
    subprocess.run(
        ["gtk4-update-icon-cache", "-f", "-t", str(Path.home() / ".local" / "share" / "icons" / "hicolor")],
        check=False,
        env=env,
    )
    bindir = Path.home() / ".local" / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    link = bindir / "everest-lights"
    if link.is_symlink() or link.exists():
        link.unlink()
    link.symlink_to(LAUNCHER)
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=False, env=env)
    subprocess.run(["systemctl", "--user", "enable", "--now", "everest-lights.service"], check=False, env=env)


def ensure_access() -> None:
    if _can_open(find_keyboard()) and _can_open(find_chassis()):
        return
    if os.geteuid() == 0:
        install_system()
        return
    print("Asking for permission to let your user reach the lighting controllers.")
    subprocess.check_call(["pkexec", str(LAUNCHER), "install-system"])


def ensure_daemon() -> None:
    try:
        call({"cmd": "get"}, timeout=0.4)
        return
    except OSError:
        pass
    env = _session_env()
    subprocess.Popen(
        [str(LAUNCHER), "daemon"],
        env=env,
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(40):
        try:
            call({"cmd": "get"}, timeout=0.2)
            return
        except OSError:
            time.sleep(0.05)
    raise SystemExit("The lights service did not start. See ~/.local/state/everest/lights.log")


def probe() -> None:
    """Paint a known pattern. Used to confirm the controllers answer."""
    from .keymap import PAINTED_IDS
    from .protocol import Chassis, Keyboard

    keyboard = Keyboard()
    chassis = Chassis()
    try:
        blue = {light_id: (18, 72, 120) for light_id in PAINTED_IDS}
        for light_id in (43, 62, 63, 64):
            blue[light_id] = (240, 193, 74)
        keyboard.paint(blue)
        chassis.paint(18, 72, 120, True)
        print(f"keyboard {keyboard.path}")
        print(f"chassis {chassis.path}")
        print(f"events {', '.join(find_key_events()) or 'none'}")
        time.sleep(1.2)
    finally:
        keyboard.close()
        chassis.close()


def main(argv: list[str] | None = None) -> None:
    command = (argv if argv is not None else sys.argv[1:])[:1]
    command = command[0] if command else "open"
    if command in ("open", ""):
        ensure_daemon()
        from .ui import main as ui_main

        ui_main()
        return
    if command == "daemon":
        serve()
        return
    if command == "setup":
        ensure_access()
        install_user()
        ensure_daemon()
        print("Lights are installed. Open them with everest-lights, or from the app grid.")
        return
    if command == "install-system":
        install_system()
        return
    if command == "off":
        ensure_daemon()
        print(call({"cmd": "off"}))
        return
    if command == "probe":
        probe()
        return
    if command == "check":
        keyboard = find_keyboard()
        chassis = find_chassis()
        print(f"keyboard {keyboard or 'missing'} writable={_can_open(keyboard)}")
        print(f"chassis {chassis or 'missing'} writable={_can_open(chassis)}")
        print(f"events {', '.join(find_key_events()) or 'none'}")
        return
    raise SystemExit(f"Unknown command {command}. Use open, setup, off, or check.")


if __name__ == "__main__":
    main()
