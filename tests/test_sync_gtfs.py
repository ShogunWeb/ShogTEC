import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.sync_gtfs import REQUIRED_FILES, extract_gtfs_files


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


if __name__ == "__main__":
    unittest.main()
