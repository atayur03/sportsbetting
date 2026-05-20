"""Minimal S3 file transfer API.

Public API:
- `write(file, path)`: upload a local file to an S3 path/key.
- `read(file, path)`: download an S3 path/key into a local file.
"""

from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def read(file: str | Path, path: str) -> str:
    """Download `path` from S3 into local `file` and return the local path."""
    local_file = Path(file)
    bucket, key = _bucket_and_key(path)
    local_file.parent.mkdir(parents=True, exist_ok=True)
    _s3_client().download_file(bucket, key, str(local_file))
    return str(local_file)


def write(file: str | Path, path: str) -> str:
    """Upload local `file` to S3 `path` and return the S3 URI."""
    local_file = Path(file)
    if not local_file.exists():
        raise FileNotFoundError(f"File not found: {local_file}")
    bucket, key = _bucket_and_key(path)
    _s3_client().upload_file(str(local_file), bucket, key)
    return f"s3://{bucket}/{key}"


def list_keys(prefix: str) -> list[str]:
    """Return S3 keys under `prefix`.

    This is intentionally kept in the AWS module so callers do not create S3
    clients directly.
    """
    bucket, key_prefix = _bucket_and_key(prefix)
    client = _s3_client()
    keys: list[str] = []
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=key_prefix):
        keys.extend(item["Key"] for item in page.get("Contents", []))
    return keys


def _load_env_file(path: Path = PROJECT_ROOT / ".env") -> None:
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


def _region() -> str:
    _load_env_file()
    return os.getenv("AWS_REGION") or os.getenv("CDK_DEFAULT_REGION") or "us-east-1"


def _s3_client():
    try:
        import boto3
    except ImportError as exc:
        raise ImportError("Install boto3 to use S3 helpers: pip install -r aws/requirements.txt") from exc
    return boto3.client("s3", region_name=_region())


def _cloudformation_client():
    try:
        import boto3
    except ImportError as exc:
        raise ImportError("Install boto3 to use S3 helpers: pip install -r aws/requirements.txt") from exc
    return boto3.client("cloudformation", region_name=_region())


def _default_bucket() -> str:
    _load_env_file()
    bucket = os.getenv("SPORTSBETTING_S3_BUCKET", "").strip()
    if bucket:
        return bucket

    stack_name = os.getenv("SPORTSBETTING_STACK_NAME", "SportsBettingStack")
    try:
        response = _cloudformation_client().describe_stacks(StackName=stack_name)
    except Exception:
        return ""
    stacks = response.get("Stacks") or []
    outputs = (stacks[0] if stacks else {}).get("Outputs") or []
    for output in outputs:
        if output.get("OutputKey") == "BucketName":
            return str(output.get("OutputValue") or "")
    return ""


def _bucket_and_key(path: str) -> tuple[str, str]:
    clean_path = path.strip()
    if clean_path.startswith("s3://"):
        without_scheme = clean_path.removeprefix("s3://")
        bucket, _, key = without_scheme.partition("/")
        if not bucket or not key:
            raise ValueError("S3 path must look like s3://bucket/key")
        return bucket, key

    bucket = _default_bucket()
    if not bucket:
        raise ValueError("Set SPORTSBETTING_S3_BUCKET or deploy SportsBettingStack with a BucketName output.")
    return bucket, clean_path.lstrip("/")


__all__ = ["read", "write"]
