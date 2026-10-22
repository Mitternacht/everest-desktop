"""Static formats/schema checks; does not pretend to validate a running desktop."""
import json
from pathlib import Path
import re
import tomllib
import hashlib
import struct

root = Path(__file__).resolve().parents[1]
bar = json.loads((root / "config/shell-bar.json").read_text())
assert bar["id"] == "omarchy.bar" and bar["position"] == "top"
ids = [item["id"] for section in bar["layout"].values() for item in section]
assert len(ids) == len(set(ids))
assert all(name.startswith("omarchy.") for name in ids)
required = {"background", "foreground", "accent", "selection", "muted", "dark_background",
            "darker_background", "lighter_background", "dark_foreground",
            "light_foreground", "bright_foreground", "red", "yellow", "green",
            "cyan", "blue", "magenta", "bright_red", "bright_yellow", "bright_green",
            "bright_cyan", "bright_blue", "bright_magenta"}
for mode in ("dawn", "dusk"):
    theme = root / "themes" / ("everest-" + mode)
    palette = tomllib.loads((theme / "colors.toml").read_text())
    assert required <= palette.keys()
    assert palette["mode"] == ("light" if mode == "dawn" else "dark")
    assert all(re.fullmatch("#[0-9a-fA-F]{6}", palette[key]) for key in required)
    for path in theme.glob("shell.*.toml"):
        tomllib.loads(path.read_text())
    dock = json.loads((theme / "everest-dock.json").read_text())
    assert all(dock[key] == palette[key] for key in dock)
    photo = root / "assets" / (mode + ".jpg")
    data = photo.read_bytes()
    assert data.startswith(b"\xff\xd8\xff")
    position = 2
    while position < len(data):
        assert data[position] == 0xff
        while data[position] == 0xff:
            position += 1
        marker = data[position]
        position += 1
        length = struct.unpack(">H", data[position:position + 2])[0]
        if marker in (0xc0, 0xc1, 0xc2):
            height, width = struct.unpack(">HH", data[position + 3:position + 7])
            assert (width, height) == (3840, 2160)
            break
        position += length
    else:
        raise AssertionError("No JPEG frame dimensions found")
    lock = json.loads((root / "assets/wallpapers.lock.json").read_text())["photos"][mode]
    assert hashlib.sha256(data).hexdigest() == lock["sha256"]
plugin = json.loads((root / "plugins/everest.typography/manifest.json").read_text())
assert plugin["id"] == "everest.typography" and plugin["kinds"] == ["service"]
print("JSON, TOML, bundled photographs, plugin manifest, and theme schemas passed.")
