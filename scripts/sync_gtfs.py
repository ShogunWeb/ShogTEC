#!/usr/bin/env python3
"""Download the latest TEC GTFS feed and regenerate TECmap's local data assets."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
GTFS_URL = (
    "https://api-management-discovery-production.azure-api.net"
    "/api/gtfs/feed/tec/static"
)
GTFS_REALTIME_PROTO_URL = (
    "https://raw.githubusercontent.com/google/transit/master/"
    "gtfs-realtime/proto/gtfs-realtime.proto"
)
REQUIRED_FILES = {
    "routes.txt",
    "stop_times.txt",
    "stops.txt",
    "trips.txt",
}
OPTIONAL_FILES = {
    "agency.txt",
    "calendar.txt",
    "calendar_dates.txt",
    "feed_info.txt",
    "frequencies.txt",
    "shapes.txt",
    "transfers.txt",
}
MANAGED_PATTERNS = (
    "routes.js",
    "stops_with_coords.js",
    "stop_times_*.js",
    "line_shapes_*.js",
)


def load_api_key(env_file: Path | None = None) -> str:
    api_key = os.environ.get("BMC_PARTNER_KEY") or os.environ.get("API_KEY")
    if api_key and api_key.strip():
        return api_key.strip()

    env_file = env_file or ROOT / "server" / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            name, separator, value = line.partition("=")
            if not separator:
                continue
            name = name.strip()
            if name.startswith("export "):
                name = name[7:].strip()
            if name not in {"BMC_PARTNER_KEY", "API_KEY"}:
                continue
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]
            if value:
                return value

    raise SystemExit(
        f"Set BMC_PARTNER_KEY or API_KEY in the environment or {env_file}."
    )


def download_gtfs(token: str, archive_path: Path) -> None:
    request = Request(
        GTFS_URL,
        headers={
            "bmc-partner-key": token,
            "Accept": "application/zip",
        },
    )
    try:
        with urlopen(request, timeout=120) as response, archive_path.open("wb") as target:
            shutil.copyfileobj(response, target)
    except HTTPError as error:
        raise RuntimeError(
            f"TEC GTFS download failed with HTTP {error.code}."
        ) from error


def download_realtime_proto(destination: Path) -> None:
    request = Request(GTFS_REALTIME_PROTO_URL)
    with urlopen(request, timeout=30) as response, destination.open("wb") as target:
        shutil.copyfileobj(response, target)
    if "FeedMessage" not in destination.read_text(encoding="utf-8"):
        raise ValueError("Downloaded GTFS-Realtime schema is invalid.")


def extract_gtfs_files(archive_path: Path, destination: Path) -> set[str]:
    destination.mkdir(parents=True, exist_ok=True)
    wanted_files = REQUIRED_FILES | OPTIONAL_FILES
    with zipfile.ZipFile(archive_path) as archive:
        members: dict[str, zipfile.ZipInfo] = {}
        for member in archive.infolist():
            filename = PurePosixPath(member.filename).name
            if filename not in wanted_files or member.is_dir():
                continue
            if filename in members:
                raise ValueError(f"GTFS archive contains duplicate {filename}.")
            members[filename] = member

        missing = REQUIRED_FILES - members.keys()
        if missing:
            raise ValueError(
                "GTFS archive is missing required files: "
                + ", ".join(sorted(missing))
            )

        for filename, member in members.items():
            with archive.open(member) as source, (destination / filename).open("wb") as target:
                shutil.copyfileobj(source, target)
            if (destination / filename).stat().st_size == 0:
                raise ValueError(f"GTFS archive contains an empty {filename}.")

    return set(members)


def generate_assets(staging_root: Path) -> None:
    shutil.copy2(ROOT / "convert_data.py", staging_root / "convert_data.py")
    staging_scripts = staging_root / "scripts"
    staging_scripts.mkdir()
    shutil.copy2(
        ROOT / "scripts" / "generate_line_shapes.py",
        staging_scripts / "generate_line_shapes.py",
    )

    subprocess.run(
        [sys.executable, "convert_data.py"],
        cwd=staging_root,
        check=True,
    )
    if (staging_root / "data" / "shapes.txt").is_file():
        subprocess.run(
            [sys.executable, "scripts/generate_line_shapes.py"],
            cwd=staging_root,
            check=True,
        )

    staged_data = staging_root / "data"
    if not list(staged_data.glob("stop_times_*.js")):
        raise RuntimeError(
            "No schedule chunks were generated; check that TEC trip IDs match "
            "the configured day-type and region filters."
        )


def install_assets(staged_data: Path) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    new_files = {path.name for path in staged_data.iterdir() if path.is_file()}

    for pattern in MANAGED_PATTERNS:
        for old_file in DATA_DIR.glob(pattern):
            if old_file.name not in new_files:
                old_file.unlink()

    for source in staged_data.iterdir():
        if not source.is_file():
            continue
        with tempfile.NamedTemporaryFile(
            dir=DATA_DIR, prefix=f".{source.name}.", delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)
        try:
            shutil.copy2(source, temporary_path)
            os.replace(temporary_path, DATA_DIR / source.name)
        finally:
            temporary_path.unlink(missing_ok=True)


def sync_gtfs() -> None:
    token = load_api_key()
    with tempfile.TemporaryDirectory(prefix="tecmap-gtfs-") as temporary:
        staging_root = Path(temporary)
        archive_path = staging_root / "tec-gtfs.zip"
        download_gtfs(token, archive_path)
        staging_data = staging_root / "data"
        found_files = extract_gtfs_files(archive_path, staging_data)
        download_realtime_proto(staging_data / "gtfs-realtime.proto")
        generate_assets(staging_root)
        install_assets(staging_data)

    print(
        f"TEC GTFS assets refreshed from {GTFS_URL} "
        f"({len(found_files)} source files)."
    )


if __name__ == "__main__":
    sync_gtfs()
