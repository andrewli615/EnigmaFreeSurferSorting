import re
from pathlib import Path


class Renamer:
    """Build stable output names for selected T1w images."""

    SAFE_LABEL = re.compile(r"[^A-Za-z0-9_-]+")

    def t1w_name(self, subject_id, session=None):
        subject = self._clean_entity(subject_id, "sub")
        name = f"sub-{subject}"

        if session is not None:
            name += f"_ses-{self._clean_entity(session, 'ses')}"

        return f"{name}_T1w.nii"

    def extract_subject_id(self, file_path):
        entities = self.bids_entities(file_path)
        if entities.get("sub"):
            return entities["sub"]

        folder_subject = self.path_entity(file_path, "sub")
        if folder_subject:
            return folder_subject

        stem = self.nifti_stem(file_path)
        scan_labels = [
            "_t1_defaced",
            "_t1w",
            "_t1",
            "-t1w",
            "-t1",
            "_mprage",
            "-mprage",
            "_spgr",
            "-spgr",
            "_anat",
            "-anat",
        ]
        lowercase_stem = stem.lower()
        positions = [
            lowercase_stem.find(label)
            for label in scan_labels
            if lowercase_stem.find(label) != -1
        ]

        if positions:
            return stem[:min(positions)]
        return stem

    def extract_session_id(self, file_path):
        entities = self.bids_entities(file_path)
        return entities.get("ses") or self.path_entity(file_path, "ses")

    def bids_entities(self, file_path):
        entities = {}

        for part in self.nifti_stem(file_path).split("_"):
            if "-" not in part:
                continue
            key, value = part.split("-", 1)
            entities[key.lower()] = value

        return entities

    def path_entity(self, file_path, entity):
        prefix = f"{entity}-"

        for parent in Path(file_path).parents:
            if parent.name.lower().startswith(prefix):
                return parent.name[len(prefix):]

        return None

    def nifti_stem(self, file_path):
        name = Path(file_path).name

        for suffix in (".nii.gz", ".nii"):
            if name.lower().endswith(suffix):
                return name[:-len(suffix)]

        return Path(name).stem

    def _clean_entity(self, value, prefix):
        label = str(value)
        if label.lower().startswith(f"{prefix}-"):
            label = label[len(prefix) + 1:]

        label = self.SAFE_LABEL.sub("_", label).strip("_")
        return label or "unknown"

