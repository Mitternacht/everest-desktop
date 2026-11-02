"""Saved lighting preferences."""

from __future__ import annotations

import json
import os
from pathlib import Path

MODES = ("typing", "solid", "off")

DEFAULTS = {
    "mode": "typing",
    "base": [27, 79, 114],
    "press": [240, 193, 74],
    "fade_ms": 380,
    "brightness": 85,
    "chassis": True,
    "chassis_match": True,
    "chassis_color": [27, 79, 114],
    "power": True,
}


def config_path() -> Path:
    root = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(root) / "everest" / "lights.json"


def clamp_rgb(value) -> list[int]:
    if not isinstance(value, (list, tuple)) or len(value) < 3:
        return [0, 0, 0]
    return [max(0, min(255, int(part))) for part in value[:3]]


def normalize(raw: dict | None) -> dict:
    data = dict(DEFAULTS)
    if isinstance(raw, dict):
        data.update(raw)
    if data.get("mode") not in MODES:
        data["mode"] = DEFAULTS["mode"]
    data["base"] = clamp_rgb(data.get("base"))
    data["press"] = clamp_rgb(data.get("press"))
    data["chassis_color"] = clamp_rgb(data.get("chassis_color"))
    try:
        data["fade_ms"] = max(40, min(2000, int(data.get("fade_ms", 380))))
    except (TypeError, ValueError):
        data["fade_ms"] = 380
    try:
        data["brightness"] = max(0, min(100, int(data.get("brightness", 85))))
    except (TypeError, ValueError):
        data["brightness"] = 85
    data["chassis"] = bool(data.get("chassis", True))
    data["chassis_match"] = bool(data.get("chassis_match", True))
    data["power"] = bool(data.get("power", True))
    return data


def load() -> dict:
    path = config_path()
    try:
        return normalize(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        return normalize(None)


def save(config: dict) -> dict:
    config = normalize(config)
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return config
