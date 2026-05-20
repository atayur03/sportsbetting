"""Internal helpers for S3-backed project files."""

from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Any

from aws.helpers.s3_storage import read, write
from aws.helpers.s3_storage import _bucket_and_key, _s3_client


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def cache_root() -> Path:
    configured = os.getenv("SPORTSBETTING_S3_CACHE_DIR")
    if configured:
        return Path(configured)
    if os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
        return Path("/tmp/.s3_cache")
    return PROJECT_ROOT / ".s3_cache"


def managed_s3_key(path: Path) -> str | None:
    """Return the S3 key for a project-managed artifact path."""
    try:
        relative_path = path.resolve().relative_to(PROJECT_ROOT)
    except ValueError:
        relative_path = path

    parts = relative_path.parts
    relative = relative_path.as_posix()

    if relative == "kalshi/trading/data/real_trade_log.csv":
        return "private/kalshi/trading/real_trade_log.csv"
    if relative == "kalshi/trading/data/fill_history.csv":
        return "private/kalshi/trading/fill_history.csv"
    if relative.startswith("execution/data/simulations/kalshi/"):
        return f"private/execution/simulations/kalshi/{relative_path.name}"
    if len(parts) == 3 and parts[:2] == ("execution", "data") and relative_path.name.startswith("trade_status"):
        return f"private/execution/status/{relative_path.name}"
    if relative.startswith("website/public/data/"):
        return f"public/data/{relative_path.name}"
    return None


def cache_path_for_key(key: str) -> Path:
    return cache_root() / key


def local_storage_path(path: Path) -> Path:
    key = managed_s3_key(path)
    if key is None:
        return path
    return cache_path_for_key(key)


def destination(path: Path) -> str:
    key = managed_s3_key(path)
    if key is None:
        return str(path)
    return key


def require_s3_for_managed_paths(paths: list[Path]) -> None:
    """Fail fast if S3-backed project paths cannot use the configured client."""
    keys = [key for path in paths if (key := managed_s3_key(path))]
    if not keys:
        return
    _s3_client()
    for key in keys:
        _bucket_and_key(key)


def read_if_exists(path: Path) -> Path | None:
    """Return a readable local path for `path`, downloading from S3 when managed."""
    key = managed_s3_key(path)
    if key is None:
        return path if path.exists() else None

    cache_path = cache_path_for_key(key)
    try:
        read(cache_path, key)
        return cache_path
    except Exception as exc:
        if not _is_missing_s3_object(exc):
            raise
        if path.exists():
            return path
        return None


def exists(path: Path) -> bool:
    return read_if_exists(path) is not None


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    local_path = read_if_exists(path)
    if local_path is None:
        raise FileNotFoundError(f"CSV not found: {path}")
    with local_path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def read_csv_rows_if_exists(path: Path) -> list[dict[str, str]]:
    local_path = read_if_exists(path)
    if local_path is None:
        return []
    with local_path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def write_csv_rows(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> str:
    local_path = local_storage_path(path)
    local_path.parent.mkdir(parents=True, exist_ok=True)
    with local_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

    key = managed_s3_key(path)
    if key is None:
        return str(local_path)
    return write(local_path, key)


def append_csv_row(path: Path, row: dict[str, Any], columns: list[str]) -> str:
    local_path = read_if_exists(path) or local_storage_path(path)
    local_path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = local_path.exists()
    with local_path.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)

    key = managed_s3_key(path)
    if key is None:
        return str(local_path)
    return write(local_path, key)


def _is_missing_s3_object(exc: Exception) -> bool:
    response = getattr(exc, "response", {}) or {}
    error = response.get("Error", {}) if isinstance(response, dict) else {}
    code = str(error.get("Code") or "")
    return code in {"404", "NoSuchKey", "NotFound"}
