import gzip
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from main import main
from tests.nifti_helpers import valid_nifti_bytes


class TestMain(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.input_folder = self.root / "input"
        self.output_folder = self.root / "output"
        self.input_folder.mkdir()

    def tearDown(self):
        self.temp_dir.cleanup()

    def create_file(self, relative_path):
        file_path = self.input_folder / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(valid_nifti_bytes())
        return file_path

    def create_gz_file(self, relative_path):
        file_path = self.input_folder / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(file_path, "wb") as compressed_file:
            compressed_file.write(valid_nifti_bytes())
        return file_path

    def test_preview_does_not_create_output(self):
        self.create_file("sub-01/anat/sub-01_T1w.nii")
        arguments = [
            "main.py",
            "--input-folder",
            str(self.input_folder),
            "--output-folder",
            str(self.output_folder),
            "--location-name",
            "STRADL",
        ]

        output = StringIO()
        with patch("sys.argv", arguments), redirect_stdout(output):
            exit_code = main()

        self.assertEqual(exit_code, 0)
        self.assertIn("PREVIEW ONLY: T1W SORTING", output.getvalue())
        self.assertFalse(self.output_folder.exists())

    def test_apply_writes_batches_report_and_removes_marker_after_success(self):
        self.create_file("sub-01/anat/sub-01_T1w.nii")
        self.create_gz_file("sub-02/anat/sub-02_T1w.nii.gz")
        arguments = [
            "main.py",
            "--input-folder",
            str(self.input_folder),
            "--output-folder",
            str(self.output_folder),
            "--location-name",
            "NIMH",
            "--subjects-per-batch",
            "1",
            "--apply",
        ]

        with patch("sys.argv", arguments), redirect_stdout(StringIO()):
            exit_code = main()

        self.assertEqual(exit_code, 0)
        self.assertTrue((self.output_folder / "NIMH_1/sub-01_T1w.nii").exists())
        self.assertTrue((self.output_folder / "NIMH_2/sub-02_T1w.nii").exists())
        self.assertFalse((self.output_folder / ".NIMH.INCOMPLETE").exists())
        self.assertIn(
            "FINAL STATUS: VALID",
            (self.output_folder / "NIMH_sorting_report.txt").read_text(),
        )

    def test_apply_returns_failure_and_keeps_marker_for_corrupt_input(self):
        corrupt = self.input_folder / "sub-01/anat/sub-01_T1w.nii"
        corrupt.parent.mkdir(parents=True)
        corrupt.touch()
        arguments = [
            "main.py",
            "--input-folder",
            str(self.input_folder),
            "--output-folder",
            str(self.output_folder),
            "--location-name",
            "bad",
            "--apply",
        ]

        with patch("sys.argv", arguments), redirect_stdout(StringIO()):
            exit_code = main()

        self.assertEqual(exit_code, 1)
        self.assertTrue((self.output_folder / ".bad.INCOMPLETE").exists())
        self.assertIn(
            str(corrupt),
            (self.output_folder / "bad_sorting_report.txt").read_text(),
        )


if __name__ == "__main__":
    unittest.main()

