#!/usr/bin/env python3
"""Assemble the portable zip from a PyInstaller build (Task 8.4).

Run on Windows AFTER `pyinstaller packaging/jarvis.spec`:

    python scripts/build_portable.py --version 1.0.0

Produces:
    dist-installer/JARVIS-portable-v1.0.0.zip
    dist-installer/SHA256SUMS.txt   (installer + portable zip hashes)

Fails with a clear message if dist/JARVIS does not exist (i.e. the
PyInstaller step was skipped). Never tested on real Windows yet — the
first real run is the v1.0.0 tag build (docs/PACKAGING.md).
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_portable(version: str) -> str:
    dist_dir = os.path.join(REPO, "dist", "JARVIS")
    if not os.path.isdir(dist_dir):
        print("ERROR: dist/JARVIS not found.", file=sys.stderr)
        print("Run first:  pyinstaller packaging/jarvis.spec", file=sys.stderr)
        raise SystemExit(2)
    out_dir = os.path.join(REPO, "dist-installer")
    os.makedirs(out_dir, exist_ok=True)
    zip_path = os.path.join(out_dir, f"JARVIS-portable-v{version}.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(dist_dir):
            for name in sorted(files):
                full = os.path.join(root, name)
                arc = os.path.relpath(full, dist_dir)
                zf.write(full, os.path.join("JARVIS", arc))
    print(f"wrote {zip_path}")
    return zip_path


def write_checksums(version: str, extra_files: list[str]) -> str:
    out_dir = os.path.join(REPO, "dist-installer")
    os.makedirs(out_dir, exist_ok=True)
    sums_path = os.path.join(out_dir, "SHA256SUMS.txt")
    lines = []
    for path in extra_files:
        if os.path.exists(path):
            digest = sha256_file(path)
            lines.append(f"{digest}  {os.path.basename(path)}")
            print(f"{digest}  {os.path.basename(path)}")
    with open(sums_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"wrote {sums_path}")
    return sums_path


def main() -> int:
    ap = argparse.ArgumentParser(description="build the portable zip")
    ap.add_argument("--version", required=True, help="e.g. 1.0.0")
    ap.add_argument(
        "--extra", action="append", default=[], help="extra file to checksum (repeatable)"
    )
    args = ap.parse_args()
    zip_path = build_portable(args.version)
    write_checksums(args.version, [zip_path, *args.extra])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
