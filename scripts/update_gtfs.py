#!/usr/bin/env python3
"""Load the Belgian Mobility key from an env file and run the GTFS sync."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

if __package__:
    from scripts.sync_gtfs import ROOT, load_api_key
else:
    from sync_gtfs import ROOT, load_api_key

CONFIG_FILE = ROOT / "scripts" / "update_gtfs.config.json"


def resolve_env_file(parser: argparse.ArgumentParser, requested: Path | None) -> Path:
    if requested is not None:
        env_file = requested.expanduser()
        return env_file if env_file.is_absolute() else Path.cwd() / env_file

    if not CONFIG_FILE.is_file():
        return ROOT / "server" / ".env"

    try:
        config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        parser.error(f"Cannot read {CONFIG_FILE}: {error}")

    if (
        not isinstance(config, dict)
        or not isinstance(config.get("env_file"), str)
        or not config["env_file"].strip()
    ):
        parser.error(f"{CONFIG_FILE} must contain an 'env_file' path.")

    env_file = Path(config["env_file"]).expanduser()
    if not env_file.is_absolute():
        env_file = ROOT / env_file
    return env_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file",
        type=Path,
        help="Override the env file path from scripts/update_gtfs.config.json",
    )
    args = parser.parse_args(argv)
    env_file = resolve_env_file(parser, args.env_file)

    try:
        api_key = load_api_key(env_file)
    except SystemExit as error:
        parser.error(str(error))

    child_env = os.environ.copy()
    child_env["BMC_PARTNER_KEY"] = api_key
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "sync_gtfs.py")],
        cwd=ROOT,
        env=child_env,
        check=False,
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
