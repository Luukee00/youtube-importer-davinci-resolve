"""Small Windows CLI client for the Resolve Lua proof of concept."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import tempfile
import time
import uuid
from datetime import datetime, timezone

PREFS_DIR = Path(os.environ.get("APPDATA", "")) / "Blackmagic Design/DaVinci Resolve/Support/Fusion/Profiles"
STATE_DIR = Path.home() / ".ytresolve-importer"
PREFS_TABLE = "RossiYouTubeImporter"
LOG_FILE = STATE_DIR / "bridge_debug.log"


def log_event(event: str, **details: object) -> None:
    record = {"time_utc": datetime.now(timezone.utc).isoformat(), "event": event, **details}
    with LOG_FILE.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")


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
    for key in ("Response", "Status", "Session"):
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
    log_event("request", id=request_id, action=action, path=str(media_path.resolve()) if media_path else None)
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
            log_event("response", **response[1])
            return response[1]
        time.sleep(0.1)
    status = read_status()
    log_event("timeout", id=request_id, status=status)
    detail = f" Bridge status: {status}." if status else " No startup status was saved."
    raise TimeoutError("No reply from Resolve." + detail + " Restart Resolve, run the bridge once, then retry.")


def main() -> int:
    parser = argparse.ArgumentParser(description="DaVinci Resolve Free Lua bridge proof of concept")
    parser.add_argument("--ping", action="store_true", help="check the in-Resolve bridge")
    parser.add_argument("--file", type=Path, help="local media file to import and append")
    parser.add_argument("--timeout", type=float, default=20)
    args = parser.parse_args()
    if not args.ping and args.file is None:
        parser.error("choose --ping or --file")
    if args.file is not None and not args.file.is_file():
        parser.error(f"media file does not exist: {args.file}")
    try:
        result = send("ping" if args.ping else "import_append", args.file, args.timeout)
    except Exception as exc:
        print(f"Bridge error: {exc}")
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
