"""Local IPC client used by the Windows app to talk to DaVinci Resolve."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import tempfile
import time
import uuid

PREFS_DIR = Path(os.environ.get("APPDATA", "")) / "Blackmagic Design/DaVinci Resolve/Support/Fusion/Profiles"
STATE_DIR = Path.home() / ".ytresolve-importer"
PREFS_TABLE = "RossiYouTubeImporter"


def lua_string(value: str) -> str:
    """Encode UTF-8 bytes as decimal Lua escapes; no source text can escape the string."""
    return '"' + "".join(f"\\{b:03d}" for b in value.encode("utf-8")) + '"'


def newest_prefs() -> Path:
    candidates = list(PREFS_DIR.glob("*/Fusion.prefs"))
    if not candidates:
        raise RuntimeError(f"Fusion.prefs not found under {PREFS_DIR}")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def read_importer_prefs() -> dict[str, str]:
    """Read fields from the nested RossiYouTubeImporter table in Fusion.prefs."""
    text = newest_prefs().read_text(encoding="utf-8", errors="replace")
    blocks = re.findall(
        rf"(?m)^[ \t]*{PREFS_TABLE}\s*=\s*\{{\r?\n([\s\S]*?)^[ \t]*\}}",
        text,
    )
    if not blocks:
        return {}
    block = blocks[-1]
    fields: dict[str, str] = {}
    for key in ("Response", "Status"):
        matches = re.findall(rf'(?m)^[ \t]*{key}\s*=\s*"([^"\r\n]*)"', block)
        if matches:
            fields[key] = matches[-1]
    return fields


def read_response() -> tuple[str, dict] | None:
    raw = read_importer_prefs().get("Response")
    if not raw or ":" not in raw:
        return None
    request_id, hex_payload = raw.split(":", 1)
    try:
        return request_id, json.loads(bytes.fromhex(hex_payload).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def read_status() -> str | None:
    try:
        return read_importer_prefs().get("Status")
    except OSError:
        return None


def send(action: str, media_path: Path | None = None, timeout: float = 20) -> dict:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    request_id = uuid.uuid4().hex
    fields = [f"id={lua_string(request_id)}", f"action={lua_string(action)}"]
    if media_path is not None:
        fields.append(f"path={lua_string(str(media_path.resolve()))}")
    payload = "return {" + ",".join(fields) + "}\n"
    destination = STATE_DIR / "request.lua"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=STATE_DIR,
                                     prefix="request-", suffix=".tmp", delete=False) as stream:
        stream.write(payload)
        temporary = Path(stream.name)
    deadline = time.monotonic() + timeout
    while True:
        try:
            os.replace(temporary, destination)
            break
        except PermissionError:
            if time.monotonic() >= deadline:
                temporary.unlink(missing_ok=True)
                raise RuntimeError("Resolve is still reading the request file; timed out")
            time.sleep(0.05)

    while time.monotonic() < deadline:
        response = read_response()
        if response and response[0] == request_id:
            return response[1]
        time.sleep(0.1)
    status = read_status()
    detail = f" Bridge status: {status}." if status else " No startup status was saved."
    raise TimeoutError("No reply from Resolve." + detail + " Restart Resolve, run the bridge once, then retry.")
