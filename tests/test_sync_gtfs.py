import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.sync_gtfs import REQUIRED_FILES, extract_gtfs_files
from scripts.update_gtfs import main as update_gtfs


class ExtractGtfsFilesTests(unittest.TestCase):
    def test_extracts_required_files_from_nested_gtfs_archive(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive_path = root / "gtfs.zip"
            destination = root / "data"

            with zipfile.ZipFile(archive_path, "w") as archive:
                for filename in REQUIRED_FILES:
                    archive.writestr(f"feed/{filename}", f"{filename}\n")

            found = extract_gtfs_files(archive_path, destination)

            self.assertEqual(found, REQUIRED_FILES)
            for filename in REQUIRED_FILES:
                self.assertEqual(
                    (destination / filename).read_text(encoding="utf-8"),
                    f"{filename}\n",
                )

    def test_rejects_archive_missing_required_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive_path = root / "gtfs.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("feed/stops.txt", "stop_id,stop_name\n")

            with self.assertRaisesRegex(ValueError, "missing required files"):
                extract_gtfs_files(archive_path, root / "data")

    def test_rejects_duplicate_gtfs_filenames(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive_path = root / "gtfs.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("feed-a/stops.txt", "stop_id,stop_name\n")
                archive.writestr("feed-b/stops.txt", "stop_id,stop_name\n")
                for filename in REQUIRED_FILES - {"stops.txt"}:
                    archive.writestr(f"feed/{filename}", f"{filename}\n")

            with self.assertRaisesRegex(ValueError, "duplicate stops.txt"):
                extract_gtfs_files(archive_path, root / "data")


class UpdateGtfsTests(unittest.TestCase):
    def test_reads_key_from_external_env_file_and_passes_it_to_sync(self):
        with tempfile.TemporaryDirectory() as temporary:
            env_file = Path(temporary) / "secrets.env"
            env_file.write_text("BMC_PARTNER_KEY='test-key'\n", encoding="utf-8")

            with (
                patch.dict(
                    "os.environ",
                    {"BMC_PARTNER_KEY": "", "API_KEY": ""},
                    clear=False,
                ),
                patch(
                    "scripts.update_gtfs.subprocess.run",
                    return_value=SimpleNamespace(returncode=0),
                ) as run,
            ):
                result = update_gtfs(["--env-file", str(env_file)])

            self.assertEqual(result, 0)
            self.assertEqual(run.call_args.kwargs["env"]["BMC_PARTNER_KEY"], "test-key")
            self.assertEqual(
                run.call_args.kwargs["cwd"],
                Path(__file__).resolve().parents[1],
            )

    def test_reads_env_file_from_local_config_when_no_argument_is_given(self):
        with tempfile.TemporaryDirectory() as temporary:
            config_file = Path(temporary) / "update_gtfs.config.json"
            env_file = Path(temporary) / "private.env"
            config_file.write_text(
                f'{{"env_file": "{env_file}"}}',
                encoding="utf-8",
            )
            env_file.write_text("BMC_PARTNER_KEY=config-key\n", encoding="utf-8")

            with (
                patch.dict(
                    "os.environ",
                    {"BMC_PARTNER_KEY": "", "API_KEY": ""},
                    clear=False,
                ),
                patch("scripts.update_gtfs.CONFIG_FILE", config_file),
                patch(
                    "scripts.update_gtfs.subprocess.run",
                    return_value=SimpleNamespace(returncode=0),
                ) as run,
            ):
                result = update_gtfs([])

            self.assertEqual(result, 0)
            self.assertEqual(
                run.call_args.kwargs["env"]["BMC_PARTNER_KEY"],
                "config-key",
            )


if __name__ == "__main__":
    unittest.main()
