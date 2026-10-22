"""Materialize selected photo assets on a GitHub runner, never on the authoring host."""
import hashlib
import json
import os
from pathlib import Path
import urllib.request

if os.environ.get("GITHUB_ACTIONS") != "true":
    raise SystemExit("Run the Prepare wallpapers GitHub Actions workflow instead.")

root = Path(__file__).resolve().parents[1]
photos = json.loads((root / "assets/photos.json").read_text())
lock = {"license": "https://www.pexels.com/license/", "photos": {}}
for name, photo in photos.items():
    request = urllib.request.Request(photo["url"], headers={"User-Agent": "EverestDesktop/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read(20 * 1024 * 1024 + 1)
    if not 20_000 < len(data) <= 20 * 1024 * 1024 or not data.startswith(b"\xff\xd8\xff"):
        raise SystemExit("Invalid or oversized JPEG response for " + name)
    (root / "assets" / (name + ".jpg")).write_bytes(data)
    lock["photos"][name] = {"id": photo["id"], "sha256": hashlib.sha256(data).hexdigest(),
                             "bytes": len(data), "width": 3840, "height": 2160}
(root / "assets/wallpapers.lock.json").write_text(json.dumps(lock, indent=2) + "\n")
