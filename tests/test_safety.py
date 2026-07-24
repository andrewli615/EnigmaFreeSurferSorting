import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sorter.safety import ensure_free_space, safe_output_child, validate_location_name


class TestSafety(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_safe_output_child_stays_below_output_root(self):
        child = safe_output_child(self.output_root, "location1")

        self.assertEqual(child.parent, self.output_root.resolve())

    def test_location_name_rejects_path_traversal(self):
        with self.assertRaises(ValueError):
            validate_location_name("../escaped")

    def test_free_space_check_rejects_insufficient_space(self):
        disk_usage = type("DiskUsage", (), {"free": 100})()

        with patch("sorter.safety.shutil.disk_usage", return_value=disk_usage):
            with self.assertRaises(OSError):
                ensure_free_space(self.output_root, required_bytes=101)


if __name__ == "__main__":
    unittest.main()

