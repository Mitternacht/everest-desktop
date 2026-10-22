"""Static formats/schema checks; does not pretend to validate a running desktop."""
import json
from pathlib import Path
import re
import tomllib
import xml.etree.ElementTree as ET

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
    svg = ET.parse(root / "assets" / (mode + ".svg")).getroot()
    assert svg.attrib["viewBox"] == "0 0 2560 1440"
print("JSON, TOML, original SVG assets, and theme schemas passed.")
