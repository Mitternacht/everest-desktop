#!/usr/bin/env python3
"""App grouping and window shelf using Hyprland's public IPC. No key remapping."""
import argparse
import json
import re
import subprocess

SHELF = "special:everest-minimized"


def query(name):
    return json.loads(subprocess.check_output(["hyprctl", "-j", name], text=True, timeout=3))


def dispatch(name, argument=None):
    command = ["hyprctl", "dispatch", name]
    if argument is not None:
        command.append(argument)
    subprocess.run(command, check=True, capture_output=True, timeout=3)


def app_id(window):
    return (window.get("initialClass") or window.get("class") or window.get("address", "")).casefold()


def normal(window):
    return window.get("mapped", True) and not window.get("hidden", False) and window.get("workspace", {}).get("id", 0) > 0


def choose(command, clients, active):
    visible = [window for window in clients if normal(window)]
    backward = command.startswith("previous")
    if command.endswith("app"):
        groups = {}
        for window in visible:
            groups.setdefault(app_id(window), []).append(window)
        names = sorted(groups)
        if not names:
            return None
        current = app_id(active)
        if current in names:
            index = (names.index(current) + (-1 if backward else 1)) % len(names)
        else:
            index = -1 if backward else 0
        return min(groups[names[index]], key=lambda w: w.get("focusHistoryID", 999999))
    windows = sorted([w for w in visible if app_id(w) == app_id(active)],
                     key=lambda w: w["address"])
    if not windows:
        return None
    addresses = [w["address"] for w in windows]
    index = addresses.index(active["address"]) if active.get("address") in addresses else -1
    return windows[(index + (-1 if backward else 1)) % len(windows)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["next-app", "previous-app", "next-window",
                                          "previous-window", "minimize", "restore"])
    args = parser.parse_args()
    clients = query("clients")
    active = query("activewindow")
    if args.command == "minimize":
        if active and normal(active):
            dispatch("movetoworkspacesilent", SHELF + ",address:" + active["address"])
        return
    if args.command == "restore":
        shelf = [w for w in clients if w.get("workspace", {}).get("name") == SHELF]
        if not shelf:
            return
        workspace = query("activeworkspace").get("id")
        if not isinstance(workspace, int) or workspace <= 0:
            raise RuntimeError("Focus an ordinary workspace before restoring a window.")
        target = min(shelf, key=lambda w: w.get("focusHistoryID", 999999))
        dispatch("movetoworkspace", str(workspace) + ",address:" + target["address"])
    else:
        target = choose(args.command, clients, active)
        if target is None:
            return
    address = target["address"]
    if not re.fullmatch(r"0x[0-9a-fA-F]+", address):
        raise RuntimeError("Unexpected Hyprland window address")
    dispatch("focuswindow", "address:" + address)
    dispatch("bringactivetotop")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as error:
        raise SystemExit("Everest: " + str(error))
