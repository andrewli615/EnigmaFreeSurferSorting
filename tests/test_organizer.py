import gzip
import tempfile
import unittest
from pathlib import Path

from sorter.organizer import Organizer
from sorter.scanner import Scanner
from tests.nifti_helpers import valid_nifti_bytes


class TestOrganizer(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.input_folder = self.root / "input"
        self.output_folder = self.root / "output"
        self.input_folder.mkdir()
        self.scanner = Scanner()
        self.organizer = Organizer()

    def tearDown(self):
        self.temp_dir.cleanup()

    def create_file(self, relative_path, payload=b"data"):
        file_path = self.input_folder / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(valid_nifti_bytes(payload))
        return file_path

    def create_gz_file(self, relative_path, payload=b"data"):
        file_path = self.input_folder / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(file_path, "wb") as compressed_file:
            compressed_file.write(valid_nifti_bytes(payload))
        return file_path

    def test_batches_t1w_files_directly_into_location_folders(self):
        for index in range(5):
            self.create_file(f"sub-{index:02d}/anat/sub-{index:02d}_T1w.nii", f"{index}".encode())

        scan_result = self.scanner.scan(self.input_folder)
        result = self.organizer.organize(
            scan_result,
            self.output_folder,
            "STRADL",
            subjects_per_batch=2,
        )

        self.assertEqual(len(result["copied_t1w_files"]), 5)
        self.assertTrue((self.output_folder / "STRADL_1/sub-00_T1w.nii").exists())
        self.assertTrue((self.output_folder / "STRADL_2/sub-02_T1w.nii").exists())
        self.assertTrue((self.output_folder / "STRADL_3/sub-04_T1w.nii").exists())
        self.assertEqual(len(list((self.output_folder / "STRADL_1").glob("*.nii"))), 2)
        self.assertEqual(len(list((self.output_folder / "STRADL_2").glob("*.nii"))), 2)
        self.assertEqual(len(list((self.output_folder / "STRADL_3").glob("*.nii"))), 1)

    def test_unzips_gz_sources_to_nii_outputs_without_touching_input(self):
        source = self.create_gz_file("sub-01/anat/sub-01_T1w.nii.gz", b"compressed t1")

        scan_result = self.scanner.scan(self.input_folder)
        result = self.organizer.organize(scan_result, self.output_folder, "NIMH")

        destination = self.output_folder / "NIMH_1/sub-01_T1w.nii"
        self.assertEqual(result["processing_errors"], [])
        self.assertTrue(destination.exists())
        self.assertFalse((self.output_folder / "NIMH_1/sub-01_T1w.nii.gz").exists())
        self.assertTrue(source.exists())
        self.assertEqual(list(self.input_folder.rglob("*.nii")), [])

    def test_selects_one_preferred_t1w_per_subject_and_reports_exclusions(self):
        selected = self.create_file("sub-01/anat/sub-01_T1w.nii", b"base")
        self.create_file("sub-01/anat/sub-01_rec-corrected_T1w.nii", b"variant")
        self.create_file("sub-01/ses-02/anat/sub-01_ses-02_T1w.nii", b"later")

        scan_result = self.scanner.scan(self.input_folder)
        plan = self.organizer.plan(scan_result, self.output_folder, "example")

        self.assertEqual(plan["selected_t1w_files"], [selected.resolve()])
        self.assertEqual(len(plan["unselected_t1w_files"]), 2)
        self.assertEqual(plan["multiple_t1w_subjects"], ["01"])

    def test_refuses_output_inside_input_dataset(self):
        self.create_file("sub-01/anat/sub-01_T1w.nii")
        scan_result = self.scanner.scan(self.input_folder)

        with self.assertRaises(ValueError):
            self.organizer.plan(scan_result, self.input_folder / "sorted", "example")


if __name__ == "__main__":
    unittest.main()

