from pathlib import Path
import re
import shutil

from sorter.integrity import IntegrityError, atomic_copy, atomic_unzip
from sorter.renamer import Renamer
from sorter.safety import (
    ensure_free_space,
    estimate_required_bytes,
    validate_location_name,
)


class Organizer:
    """Copy selected T1w NIfTI files into numeric location batches."""

    T1W_VARIANT_ENTITIES = frozenset({
        "den",
        "desc",
        "echo",
        "flip",
        "hemi",
        "inv",
        "label",
        "mt",
        "part",
        "proc",
        "rec",
        "res",
        "space",
    })

    def __init__(self):
        self.renamer = Renamer()

    def plan(self, scan_result, output_path, location_name="location1", subjects_per_batch=30, copy_files_path=None):
        validate_location_name(location_name)
        if subjects_per_batch <= 0:
            raise ValueError("subjects_per_batch must be greater than 0")

        input_root = Path(scan_result["root"]).expanduser().resolve()
        output_root = Path(output_path).expanduser().resolve()

        if output_root == input_root or input_root in output_root.parents:
            raise ValueError(
                "Output folder cannot be inside the input dataset folder. "
                "Choose a separate output location to avoid recursively sorting generated files."
            )

        selected_records, unselected_records, multiple_subjects = self._select_t1w_records(
            scan_result["t1w_files"]
        )
        operations = self._build_operations(
            selected_records,
            output_root,
            location_name,
            subjects_per_batch,
        )
        copy_files = [op["source"] for op in operations if op["action"] == "copy"]
        unzip_files = [op["source"] for op in operations if op["action"] == "unzip"]

        return {
            "input_root": input_root,
            "output_root": output_root,
            "operations": operations,
            "batch_folders": sorted({op["batch_folder"] for op in operations}),
            "selected_t1w_files": [record["file"] for record in selected_records],
            "unselected_t1w_files": [record["file"] for record in unselected_records],
            "multiple_t1w_subjects": sorted(multiple_subjects, key=self._natural_key),
            "unknown_files": sorted(scan_result.get("unknown_files", [])),
            "copy_files": copy_files,
            "unzip_files": unzip_files,
            "expected_output_files": [op["destination"] for op in operations],
            "required_bytes": estimate_required_bytes(copy_files, unzip_files),
            "copy_files_path": copy_files_path,
        }

    def organize(self, scan_result, output_path, location_name="location1", subjects_per_batch=30, copy_files_path=None):
        plan = self.plan(
            scan_result,
            output_path,
            location_name=location_name,
            subjects_per_batch=subjects_per_batch,
            copy_files_path=copy_files_path,
        )
        output_root = plan["output_root"]
        output_root.mkdir(parents=True, exist_ok=True)
        ensure_free_space(output_root, plan["required_bytes"])

        copied_t1w_files = []
        processing_errors = []
        prepared_batch_folders = set()
        updated_operations = []

        for operation in plan["operations"]:
            batch_folder = operation["batch_folder"]
            try:
                if batch_folder not in prepared_batch_folders:
                    batch_folder.mkdir(parents=True, exist_ok=True)
                    if copy_files_path is not None:
                        self._copy_batch_support_files(copy_files_path, batch_folder)
                    prepared_batch_folders.add(batch_folder)

                destination = self._safe_output_path(operation["destination"])
                copied_file = self._copy_or_unzip(operation["source"], destination)
                copied_t1w_files.append(copied_file)
                updated_operations.append({**operation, "destination": copied_file})
            except (IntegrityError, OSError, EOFError, ValueError) as error:
                processing_errors.append({
                    "subject_id": operation["subject_id"],
                    "session": operation["session"],
                    "source": operation["source"],
                    "destination": operation["destination"],
                    "error_type": type(error).__name__,
                    "error": str(error),
                })
                updated_operations.append(operation)

        expected_output_files = [
            operation.get("destination")
            for operation in updated_operations
            if operation.get("destination") is not None
        ]

        return {
            **plan,
            "operations": updated_operations,
            "batch_folders": sorted(prepared_batch_folders),
            "copied_t1w_files": copied_t1w_files,
            "processing_errors": processing_errors,
            "expected_output_files": expected_output_files,
        }

    def _select_t1w_records(self, t1w_files):
        subjects = {}

        for file_path in sorted(Path(file_path).resolve() for file_path in t1w_files):
            subject_id = self.renamer.extract_subject_id(file_path)
            session = self.renamer.extract_session_id(file_path)
            record = {
                "file": file_path,
                "subject_id": subject_id,
                "session": session,
            }
            subjects.setdefault(subject_id, {}).setdefault(session, []).append(record)

        selected_records = []
        unselected_records = []
        multiple_subjects = []

        for subject_id in sorted(subjects, key=self._natural_key):
            sessions = subjects[subject_id]
            first_session = sorted(sessions, key=self._session_rank)[0]
            candidates = sorted(sessions[first_session], key=self._t1w_rank)
            all_records = [
                record
                for session_records in sessions.values()
                for record in session_records
            ]

            selected_records.append(candidates[0])
            unselected_records.extend(
                record for record in all_records if record["file"] != candidates[0]["file"]
            )

            if len(all_records) > 1:
                multiple_subjects.append(subject_id)

        return selected_records, sorted(unselected_records, key=lambda record: record["file"]), multiple_subjects

    def _build_operations(self, selected_records, output_root, location_name, subjects_per_batch):
        planned_destinations = set()
        operations = []

        for index, record in enumerate(selected_records):
            batch_number = (index // subjects_per_batch) + 1
            batch_folder = output_root / f"{location_name}_{batch_number}"
            destination = batch_folder / self.renamer.t1w_name(
                record["subject_id"],
                record["session"],
            )
            destination = self._planned_unique_output_path(destination, planned_destinations)
            planned_destinations.add(destination)

            operations.append({
                "subject_id": record["subject_id"],
                "session": record["session"],
                "source": record["file"],
                "destination": destination,
                "batch_folder": batch_folder,
                "action": "unzip" if record["file"].name.lower().endswith(".nii.gz") else "copy",
            })

        return operations

    def _copy_or_unzip(self, input_file, output_file):
        input_file = Path(input_file)
        output_file = Path(output_file)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        if input_file.name.lower().endswith(".nii.gz"):
            if output_file.name.lower().endswith(".gz"):
                output_file = output_file.with_suffix("")
            atomic_unzip(input_file, output_file)
            return output_file

        atomic_copy(input_file, output_file, validate_as_nifti=True)
        return output_file

    def _copy_batch_support_files(self, copy_files_path, batch_folder):
        copy_files_folder = Path(copy_files_path).expanduser().resolve()

        if not copy_files_folder.exists():
            raise FileNotFoundError(f"Copy files folder does not exist: {copy_files_folder}")
        if not copy_files_folder.is_dir():
            raise NotADirectoryError(f"Copy files path is not a folder: {copy_files_folder}")

        for item in copy_files_folder.iterdir():
            destination = batch_folder / item.name
            if destination.exists():
                continue
            if item.is_dir():
                shutil.copytree(item, destination)
            else:
                shutil.copy2(item, destination)

    def _planned_unique_output_path(self, output_file, planned_destinations):
        output_file = Path(output_file)
        if output_file not in planned_destinations and not output_file.exists():
            return output_file

        counter = 2
        while True:
            candidate = output_file.with_name(
                f"{output_file.stem}_duplicate-{counter}{output_file.suffix}"
            )
            if candidate not in planned_destinations and not candidate.exists():
                return candidate
            counter += 1

    def _safe_output_path(self, output_file):
        output_file = Path(output_file)
        if not output_file.exists():
            return output_file

        counter = 2
        while True:
            candidate = output_file.with_name(
                f"{output_file.stem}_duplicate-{counter}{output_file.suffix}"
            )
            if not candidate.exists():
                return candidate
            counter += 1

    def _t1w_rank(self, record):
        file_path = record["file"]
        entities = self.renamer.bids_entities(file_path)
        optional_entities = [
            key for key in entities if key not in {"sub", "ses", "run", "trial"}
        ]
        variant_entities = [
            key for key in optional_entities if key in self.T1W_VARIANT_ENTITIES
        ]

        return (
            self._run_priority(entities),
            len(variant_entities),
            len(optional_entities),
            1 if file_path.name.lower().endswith(".nii.gz") else 0,
            len(file_path.name),
            self._natural_key(file_path.name),
        )

    def _run_priority(self, entities):
        run_value = entities.get("run", entities.get("trial"))

        if run_value is not None and run_value.lstrip("0") == "1":
            return 0
        if run_value is None:
            return 1
        return 2

    def _session_rank(self, session):
        if session is None:
            return (0, ())
        return (1, self._natural_key(session))

    def _natural_key(self, value):
        return tuple(
            int(part) if part.isdigit() else part.lower()
            for part in re.split(r"(\d+)", str(value))
        )

