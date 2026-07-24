from pathlib import Path

from sorter.integrity import validate_nifti


class Validator:
    """Validate T1w batch folders without changing output files."""

    def validate_batches(self, batch_folders, expected_output_files=(), files_per_batch=30):
        if files_per_batch <= 0:
            raise ValueError("files_per_batch must be greater than 0")

        output_roots = self._normalize_output_paths(batch_folders)
        expected_files = {Path(file_path).expanduser().resolve() for file_path in expected_output_files}

        missing_expected_files = sorted(
            file_path for file_path in expected_files if not file_path.exists()
        )
        corrupt_files = []
        duplicate_files = []
        compressed_output_files = []
        unexpected_nifti_files = []
        oversized_batches = []
        all_nifti_files = set()

        for output_root in output_roots:
            nifti_files = self._find_nifti_files(output_root)
            all_nifti_files.update(nifti_files)
            expected_in_batch = [
                file_path for file_path in expected_files if output_root == file_path.parent.resolve()
            ]

            if len(expected_in_batch) > files_per_batch:
                oversized_batches.append({
                    "batch_folder": output_root,
                    "file_count": len(expected_in_batch),
                    "limit": files_per_batch,
                })

            for file_path in nifti_files:
                if file_path.name.lower().endswith(".nii.gz"):
                    compressed_output_files.append(file_path)
                if "duplicate-" in file_path.name:
                    duplicate_files.append(file_path)
                if expected_files and file_path not in expected_files:
                    unexpected_nifti_files.append(file_path)

        files_to_validate = expected_files if expected_files else all_nifti_files
        for file_path in sorted(files_to_validate):
            if not file_path.exists() or not self._is_nifti(file_path):
                continue
            error = validate_nifti(file_path)
            if error:
                corrupt_files.append({"path": file_path, "error": error})

        partial_files = []
        incomplete_files = []
        for output_root in output_roots:
            partial_files.extend(self._find_partial_files(output_root))
            incomplete_files.extend(self._find_incomplete_files(output_root))

        return {
            "batches_checked": len(output_roots),
            "nifti_files_checked": len(expected_files) if expected_files else sum(
                len(self._find_nifti_files(output_root)) for output_root in output_roots
            ),
            "missing_expected_files": missing_expected_files,
            "corrupt_files": sorted(corrupt_files, key=lambda record: str(record["path"])),
            "partial_files": sorted(partial_files),
            "incomplete_files": sorted(incomplete_files),
            "duplicate_files": sorted(duplicate_files),
            "compressed_output_files": sorted(compressed_output_files),
            "unexpected_nifti_files": sorted(unexpected_nifti_files),
            "oversized_batches": sorted(
                oversized_batches,
                key=lambda record: str(record["batch_folder"]),
            ),
        }

    def validate_nifti_tree(self, output_root, files_per_batch=30):
        output_root = Path(output_root).expanduser().resolve()
        self._normalize_output_paths(output_root)
        batch_folders = sorted(
            folder for folder in output_root.iterdir() if folder.is_dir()
        )

        if not batch_folders:
            batch_folders = [output_root]

        return self.validate_batches(batch_folders, files_per_batch=files_per_batch)

    def _normalize_output_paths(self, output_path):
        if isinstance(output_path, list):
            output_roots = output_path
        elif isinstance(output_path, tuple):
            output_roots = list(output_path)
        else:
            output_roots = [output_path]

        normalized_roots = []

        for root in output_roots:
            root = Path(root).expanduser().resolve()
            if not root.exists():
                raise FileNotFoundError(f"Output folder does not exist: {root}")
            if not root.is_dir():
                raise NotADirectoryError(f"Output path is not a folder: {root}")
            normalized_roots.append(root)

        return normalized_roots

    def _find_nifti_files(self, folder_path):
        return sorted(
            file_path.resolve()
            for file_path in Path(folder_path).rglob("*")
            if file_path.is_file() and self._is_nifti(file_path)
        )

    def _is_nifti(self, file_path):
        name = Path(file_path).name.lower()
        return name.endswith(".nii") or name.endswith(".nii.gz")

    def _find_partial_files(self, output_root):
        return sorted(
            file_path.resolve()
            for file_path in Path(output_root).rglob("*")
            if file_path.is_file() and ".partial-" in file_path.name
        )

    def _find_incomplete_files(self, output_root):
        return sorted(
            file_path.resolve()
            for file_path in Path(output_root).rglob("*")
            if file_path.is_file() and file_path.name == ".INCOMPLETE"
        )
