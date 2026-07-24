from pathlib import Path


class Scanner:
    """Find T1-weighted NIfTI files without changing the input dataset."""

    IGNORE_FOLDERS = {
        "excluded",
        "exclude",
        "derivatives",
        "sourcedata",
        "__pycache__",
        ".git",
    }

    NON_T1W_TOKENS = {
        "bold",
        "dwi",
        "fieldmap",
        "fmap",
        "flair",
        "func",
        "pdw",
        "sbref",
        "t2",
        "t2w",
    }

    T1W_NAME_TOKENS = {
        "t1weighted",
        "mprage",
        "mp-rage",
        "spgr",
        "irspgr",
        "bravo",
    }

    def scan(self, root_path):
        root = Path(root_path).expanduser().resolve()

        if not root.exists():
            raise FileNotFoundError(f"Folder does not exist: {root}")
        if not root.is_dir():
            raise NotADirectoryError(f"Path is not a folder: {root}")

        t1w_files = []
        unknown_files = []

        for file_path in root.rglob("*"):
            if not file_path.is_file():
                continue
            if self._inside_skipped_folder(file_path):
                continue
            if not self._is_nifti(file_path):
                continue

            if self._is_t1w(file_path):
                t1w_files.append(file_path)
            else:
                unknown_files.append(file_path)

        return {
            "root": root,
            "t1w_files": sorted(t1w_files),
            "unknown_files": sorted(unknown_files),
        }

    def _is_t1w(self, file_path):
        stem = self._nifti_stem(file_path).lower()
        parts = {part.lower() for part in Path(file_path).parts}

        if self._bids_suffix(file_path) == "t1w":
            return True

        if (
            any(token in stem for token in self.NON_T1W_TOKENS)
            or parts.intersection(self.NON_T1W_TOKENS)
        ):
            return False

        if self._contains_t1_label(stem):
            return True

        if any(token in stem for token in self.T1W_NAME_TOKENS):
            return True

        return "anat" in parts

    def _is_nifti(self, file_path):
        name = Path(file_path).name.lower()
        return name.endswith(".nii") or name.endswith(".nii.gz")

    def _nifti_stem(self, file_path):
        name = Path(file_path).name
        for suffix in (".nii.gz", ".nii"):
            if name.lower().endswith(suffix):
                return name[:-len(suffix)]
        return Path(name).stem

    def _bids_suffix(self, file_path):
        return self._nifti_stem(file_path).split("_")[-1].lower()

    def _contains_t1_label(self, stem):
        labels = ("t1", "t1w")
        separators = {"_", "-", "."}

        for label in labels:
            start = 0
            while True:
                position = stem.find(label, start)
                if position == -1:
                    break

                before = stem[position - 1] if position > 0 else ""
                after_position = position + len(label)
                after = stem[after_position] if after_position < len(stem) else ""

                before_ok = position == 0 or before in separators
                after_ok = after_position == len(stem) or after in separators

                if before_ok and after_ok:
                    return True

                start = position + 1

        return False

    def _inside_skipped_folder(self, file_path):
        return any(parent.name.lower() in self.IGNORE_FOLDERS for parent in file_path.parents)
