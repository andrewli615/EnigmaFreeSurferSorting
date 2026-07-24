import gzip
import tempfile
import unittest
from pathlib import Path

from sorter.scanner import Scanner
from tests.nifti_helpers import valid_nifti_bytes


class TestScanner(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.scanner = Scanner()

    def tearDown(self):
        self.temp_dir.cleanup()

    def create_file(self, relative_path):
        file_path = self.root / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(valid_nifti_bytes())
        return file_path

    def create_gz_file(self, relative_path):
        file_path = self.root / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(file_path, "wb") as compressed_file:
            compressed_file.write(valid_nifti_bytes())
        return file_path

    def test_finds_t1w_files_and_ignores_other_modalities(self):
        t1w = self.create_file("sub-01/anat/sub-01_T1w.nii")
        t1w_gz = self.create_gz_file("sub-02/anat/sub-02_T1w.nii.gz")
        self.create_file("sub-01/func/sub-01_task-rest_bold.nii")
        self.create_file("sub-01/anat/sub-01_FLAIR.nii")
        self.create_file("derivatives/sub-03/anat/sub-03_T1w.nii")

        result = self.scanner.scan(self.root)

        self.assertEqual(result["t1w_files"], [t1w.resolve(), t1w_gz.resolve()])
        self.assertEqual(len(result["unknown_files"]), 2)

    def test_accepts_plain_anat_folder_files_when_no_other_modality_token_exists(self):
        t1w = self.create_file("anat/ST1AAB0001.nii")

        result = self.scanner.scan(self.root)

        self.assertEqual(result["t1w_files"], [t1w.resolve()])

    def test_subject_id_containing_t1_does_not_make_functional_file_t1w(self):
        self.create_file("func/ST1AAB0001_resting.nii")

        result = self.scanner.scan(self.root)

        self.assertEqual(result["t1w_files"], [])
        self.assertEqual(len(result["unknown_files"]), 1)


if __name__ == "__main__":
    unittest.main()
