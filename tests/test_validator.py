import tempfile
import unittest
from pathlib import Path

from sorter.validator import Validator
from tests.nifti_helpers import valid_nifti_bytes


class TestValidator(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_folder = Path(self.temp_dir.name)
        self.validator = Validator()

    def tearDown(self):
        self.temp_dir.cleanup()

    def create_file(self, relative_path, content=b"data"):
        file_path = self.output_folder / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        if file_path.name.endswith(".nii"):
            content = valid_nifti_bytes(content)
        file_path.write_bytes(content)
        return file_path

    def test_validates_expected_t1w_files(self):
        first = self.create_file("STRADL_1/sub-01_T1w.nii")
        second = self.create_file("STRADL_1/sub-02_T1w.nii")

        result = self.validator.validate_batches(
            [self.output_folder / "STRADL_1"],
            [first, second],
            files_per_batch=2,
        )

        self.assertEqual(result["batches_checked"], 1)
        self.assertEqual(result["nifti_files_checked"], 2)
        self.assertEqual(result["missing_expected_files"], [])
        self.assertEqual(result["corrupt_files"], [])
        self.assertEqual(result["oversized_batches"], [])

    def test_reports_corrupt_and_partial_files(self):
        corrupt = self.output_folder / "STRADL_1/sub-01_T1w.nii"
        corrupt.parent.mkdir(parents=True)
        corrupt.touch()
        partial = self.create_file("STRADL_1/.sub-02_T1w.nii.partial-test", b"partial")

        result = self.validator.validate_batches(
            [self.output_folder / "STRADL_1"],
            [corrupt],
        )

        self.assertEqual(result["corrupt_files"][0]["path"], corrupt.resolve())
        self.assertEqual(result["partial_files"], [partial.resolve()])

    def test_reports_oversized_batches(self):
        files = [
            self.create_file(f"STRADL_1/sub-{index:02d}_T1w.nii")
            for index in range(3)
        ]

        result = self.validator.validate_batches(
            [self.output_folder / "STRADL_1"],
            files,
            files_per_batch=2,
        )

        self.assertEqual(len(result["oversized_batches"]), 1)
        self.assertEqual(result["oversized_batches"][0]["file_count"], 3)


if __name__ == "__main__":
    unittest.main()

