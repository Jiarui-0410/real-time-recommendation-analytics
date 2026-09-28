from __future__ import annotations

import argparse
import hashlib
import mimetypes
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def upload_directory(directory: Path, bucket: str, prefix: str) -> int:
    import boto3

    client = boto3.client("s3")
    count = 0
    for path in sorted(directory.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(directory).as_posix()
        key = "/".join(part for part in (prefix.strip("/"), relative) if part)
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        client.upload_file(
            str(path),
            bucket,
            key,
            ExtraArgs={"ContentType": content_type, "Metadata": {"sha256": sha256(path)}},
        )
        count += 1
        print(f"s3://{bucket}/{key}")
    return count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Upload model/data artifacts to S3")
    parser.add_argument("directory", type=Path)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--prefix", default="models/current")
    args = parser.parse_args(argv)
    if not args.directory.is_dir():
        parser.error(f"not a directory: {args.directory}")
    count = upload_directory(args.directory, args.bucket, args.prefix)
    print(f"uploaded {count} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

