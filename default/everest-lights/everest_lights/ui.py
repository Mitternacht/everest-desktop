"""Everest Lights window."""

from __future__ import annotations

import subprocess

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, Gtk

from .config import DEFAULTS
from .service import call

MODES = ("typing", "solid", "off")
MODE_LABELS = ("Typing", "Solid", "Off")


def rgba_of(rgb: list[int]) -> Gdk.RGBA:
    color = Gdk.RGBA()
    color.red = rgb[0] / 255
    color.green = rgb[1] / 255
    color.blue = rgb[2] / 255
    color.alpha = 1
    return color


def rgb_of(color: Gdk.RGBA) -> list[int]:
    return [int(color.red * 255 + 0.5), int(color.green * 255 + 0.5), int(color.blue * 255 + 0.5)]


class LightsWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application):
        super().__init__(application=app, title="Everest Lights", default_width=460, default_height=640)
        self.set_title("Everest Lights")
        self._ready = False
        self._config = dict(DEFAULTS)

        header = Adw.HeaderBar()
        title = Adw.WindowTitle.new("Everest Lights", "Alienware x15 R2")
        header.set_title_widget(title)
        self.grant = Gtk.Button(label="Grant access")
        self.grant.add_css_class("suggested-action")
        self.grant.set_visible(False)
        self.grant.connect("clicked", self._grant)
        header.pack_start(self.grant)

        page = Adw.PreferencesPage()

        appearance = Adw.PreferencesGroup(
            title="Keyboard",
            description="Typing lights the key you press, then lets it settle.",
        )
        self.mode = Adw.ComboRow(title="Mode")
        self.mode.set_model(Gtk.StringList.new(list(MODE_LABELS)))
        appearance.add(self.mode)

        self.base = self._color_row("Resting color", "Color of keys that are sitting still")
        self.press = self._color_row("Pressed color", "Color of the key under your finger")
        appearance.add(self.base[0])
        appearance.add(self.press[0])

        self.fade = Adw.SpinRow.new_with_range(80, 1200, 20)
        self.fade.set_title("Settle time")
        self.fade.set_subtitle("Milliseconds a key takes to return")
        appearance.add(self.fade)

        self.brightness = Adw.SpinRow.new_with_range(5, 100, 5)
        self.brightness.set_title("Brightness")
        self.brightness.set_subtitle("Percent, for the keyboard and the chassis")
        appearance.add(self.brightness)

        flash_row = Adw.ActionRow(title="Preview", subtitle="Light every key for a moment")
        flash = Gtk.Button(label="Flash")
        flash.add_css_class("suggested-action")
        flash.connect("clicked", lambda *_: self._send({"cmd": "flash"}))
        flash_row.add_suffix(flash)
        appearance.add(flash_row)
        page.add(appearance)

        chassis = Adw.PreferencesGroup(title="Chassis", description="Logo, light bar, and power button.")
        self.chassis = Adw.SwitchRow(title="Chassis lights")
        self.match = Adw.SwitchRow(title="Match the keyboard", subtitle="Use the resting color on the chassis")
        self.chassis_color = self._color_row("Chassis color", "Used when it does not follow the keyboard")
        self.power = Adw.SwitchRow(title="Power button")
        chassis.add(self.chassis)
        chassis.add(self.match)
        chassis.add(self.chassis_color[0])
        chassis.add(self.power)
        page.add(chassis)

        state = Adw.PreferencesGroup(title="This machine")
        self.status = Adw.ActionRow(title="Connecting")
        state.add(self.status)
        page.add(state)

        view = Adw.ToolbarView()
        view.add_top_bar(header)
        view.set_content(page)
        self.set_content(view)

        self.mode.connect("notify::selected", lambda *_: self._push())
        self.base[1].connect("color-set", lambda *_: self._push())
        self.press[1].connect("color-set", lambda *_: self._push())
        self.chassis_color[1].connect("color-set", lambda *_: self._push())
        self.fade.connect("notify::value", lambda *_: self._push())
        self.brightness.connect("notify::value", lambda *_: self._push())
        self.chassis.connect("notify::active", lambda *_: self._push())
        self.match.connect("notify::active", lambda *_: self._push())
        self.power.connect("notify::active", lambda *_: self._push())

        self._load()
        GLib.timeout_add(1000, self._refresh_status)

    def _color_row(self, title: str, subtitle: str):
        row = Adw.ActionRow(title=title, subtitle=subtitle)
        button = Gtk.ColorButton()
        button.set_use_alpha(False)
        row.add_suffix(button)
        return row, button

    def _apply_form(self, config: dict) -> None:
        self._ready = False
        self._config = config
        self.mode.set_selected(MODES.index(config["mode"]))
        self.base[1].set_rgba(rgba_of(config["base"]))
        self.press[1].set_rgba(rgba_of(config["press"]))
        self.chassis_color[1].set_rgba(rgba_of(config["chassis_color"]))
        self.fade.set_value(config["fade_ms"])
        self.brightness.set_value(config["brightness"])
        self.chassis.set_active(config["chassis"])
        self.match.set_active(config["chassis_match"])
        self.power.set_active(config["power"])
        typing = config["mode"] == "typing"
        self.press[0].set_sensitive(typing)
        self.fade.set_sensitive(typing)
        self.chassis_color[0].set_sensitive(config["chassis"] and not config["chassis_match"])
        self._ready = True

    def _form_config(self) -> dict:
        selected = self.mode.get_selected()
        mode = MODES[selected] if 0 <= selected < len(MODES) else "typing"
        return {
            "mode": mode,
            "base": rgb_of(self.base[1].get_rgba()),
            "press": rgb_of(self.press[1].get_rgba()),
            "fade_ms": int(self.fade.get_value()),
            "brightness": int(self.brightness.get_value()),
            "chassis": self.chassis.get_active(),
            "chassis_match": self.match.get_active(),
            "chassis_color": rgb_of(self.chassis_color[1].get_rgba()),
            "power": self.power.get_active(),
        }

    def _push(self, *_args) -> None:
        if not self._ready:
            return
        config = self._form_config()
        self.press[0].set_sensitive(config["mode"] == "typing")
        self.fade.set_sensitive(config["mode"] == "typing")
        self.chassis_color[0].set_sensitive(config["chassis"] and not config["chassis_match"])
        self._send({"cmd": "set", "config": config})

    def _send(self, message: dict) -> None:
        try:
            reply = call(message)
        except OSError as exc:
            self.status.set_title("Lights service is not running")
            self.status.set_subtitle(str(exc))
            return
        if message.get("cmd") == "set" and reply.get("config"):
            self._config = reply["config"]

    def _load(self) -> None:
        try:
            reply = call({"cmd": "get"})
        except OSError as exc:
            self.status.set_title("Lights service is not running")
            self.status.set_subtitle(str(exc))
            self._apply_form(dict(DEFAULTS))
            return
        self._apply_form(reply.get("config") or dict(DEFAULTS))
        self._show_status(reply)

    def _refresh_status(self) -> bool:
        try:
            self._show_status(call({"cmd": "get"}))
        except OSError:
            self.status.set_title("Lights service is not running")
            self.status.set_subtitle("Start it again from the Lights app")
        return True

    def _show_status(self, reply: dict) -> None:
        parts = []
        if reply.get("keyboard"):
            parts.append("keyboard")
        if reply.get("chassis"):
            parts.append("chassis")
        if reply.get("keys"):
            parts.append("key events")
        title = "Connected" if parts else "Looking for the controllers"
        error = reply.get("error") or ""
        self.grant.set_visible(bool(error) and ("cannot open" in error or "cannot read" in error))
        self.status.set_title(title)
        self.status.set_subtitle(error or ", ".join(parts))

    def _grant(self, *_args) -> None:
        from .__main__ import LAUNCHER

        script = (
            f"sudo {LAUNCHER} install-system; "
            "status=$?; echo; "
            "if [ $status -eq 0 ]; then echo 'Access granted. The lights pick this up within a couple of seconds.'; "
            "else echo 'Access was not granted.'; fi; "
            "read -r -p 'Press enter to close. '"
        )
        subprocess.Popen(["foot", "-e", "bash", "-lc", script])
        self.status.set_title("Waiting for the password prompt")
        self.status.set_subtitle("A terminal is asking for your password")


class LightsApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.everest.Lights")

    def do_activate(self):
        window = self.props.active_window
        if window is None:
            window = LightsWindow(self)
        window.present()


def main() -> None:
    raise SystemExit(LightsApp().run(None))
