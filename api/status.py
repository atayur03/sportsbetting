"""Status data API backed by the project AWS module."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aws import read  # noqa: E402


STATUS_JSON_KEY = "public/data/trade-status.json"
CACHE_TTL_SECONDS = 30
_cached_payload: dict[str, Any] | None = None
_cached_at = 0.0


def load_env_file(path: Path = PROJECT_ROOT / ".env") -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_status_payload() -> dict:
    global _cached_at, _cached_payload

    load_env_file()
    now = time.monotonic()
    if _cached_payload is not None and now - _cached_at < CACHE_TTL_SECONDS:
        return _cached_payload

    missing_env = [
        name
        for name in ("AWS_REGION", "SPORTSBETTING_S3_BUCKET")
        if not os.getenv(name)
    ]
    if missing_env:
        raise RuntimeError(f"Missing required API env values: {', '.join(missing_env)}")

    with tempfile.TemporaryDirectory() as temp_dir:
        local_file = Path(temp_dir) / "trade-status.json"
        try:
            read(local_file, STATUS_JSON_KEY)
        except Exception as exc:
            raise RuntimeError(
                f"S3 status JSON not found or not readable at {STATUS_JSON_KEY}. "
                "Run `cd website && npm run export-status`, then "
                "`python -c \"from aws import write; print(write('website/public/data/trade-status.json', "
                "'public/data/trade-status.json'))\"`."
            ) from exc
        _cached_payload = json.loads(local_file.read_text(encoding="utf-8"))
        _cached_at = now
        return _cached_payload


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        try:
            payload = load_status_payload()
        except Exception as exc:
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(exc)}).encode("utf-8"))
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))


if __name__ == "__main__":
    print(json.dumps(load_status_payload()))
