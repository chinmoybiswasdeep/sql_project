"""Download the public MIMIC-IV Clinical Database Demo (v2.2) with checksum verification.

The demo is openly licensed (ODbL) and requires no PhysioNet credentialing.
The full MIMIC-IV dataset is *not* downloaded by this script: it requires a
credentialed PhysioNet account, CITI training and a signed data use agreement.

Usage:
    python -m ingestion.download_demo [--dest data/raw] [--force]
"""

from __future__ import annotations

import argparse
import hashlib
import urllib.request
from pathlib import Path

from config.settings import DEMO_BASE_URL, get_settings, load_source_contract
from ingestion.logging_utils import get_logger

log = get_logger("ingestion.download")


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while block := fh.read(chunk):
            digest.update(block)
    return digest.hexdigest()


def fetch_checksums() -> dict[str, str]:
    with urllib.request.urlopen(f"{DEMO_BASE_URL}/SHA256SUMS.txt", timeout=60) as resp:
        text = resp.read().decode()
    sums: dict[str, str] = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 2:
            sums[parts[1]] = parts[0]
    return sums


def download(dest: Path, force: bool = False) -> list[Path]:
    contract = load_source_contract()
    wanted = ["LICENSE.txt"] + [t["file"] for t in contract["tables"].values()]
    checksums = fetch_checksums()
    fetched: list[Path] = []
    for rel in wanted:
        target = dest / rel
        expected = checksums.get(rel)
        if expected is None:
            raise RuntimeError(f"{rel} is not listed in the demo SHA256SUMS; contract out of date?")
        if target.exists() and not force and sha256_file(target) == expected:
            log.info("already present, checksum ok", extra={"file": rel})
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".part")
        log.info("downloading", extra={"file": rel})
        urllib.request.urlretrieve(f"{DEMO_BASE_URL}/{rel}", tmp)
        actual = sha256_file(tmp)
        if actual != expected:
            tmp.unlink(missing_ok=True)
            raise RuntimeError(f"checksum mismatch for {rel}: expected {expected}, got {actual}")
        tmp.replace(target)
        fetched.append(target)
        log.info("verified", extra={"file": rel, "sha256": actual})
    return fetched


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dest", type=Path, default=get_settings().demo_dir)
    parser.add_argument("--force", action="store_true", help="re-download even if checksums match")
    args = parser.parse_args()
    files = download(args.dest, args.force)
    log.info("demo download complete", extra={"new_files": len(files), "dest": str(args.dest)})


if __name__ == "__main__":
    main()
