import argparse
import sys
from pathlib import Path

from sorter.organizer import Organizer
from sorter.scanner import Scanner
from sorter.safety import (
    create_incomplete_marker,
    remove_incomplete_marker,
    safe_output_child,
    validate_location_name,
)
from sorter.validator import Validator


def main():
    args = parse_arguments()
    validate_location_name(args.location_name)

    scanner = Scanner()
    organizer = Organizer()
    validator = Validator()

    scan_result = scanner.scan(args.input_folder)

    if not args.apply:
        plan = organizer.plan(
            scan_result,
            args.output_folder,
            args.location_name,
            subjects_per_batch=args.subjects_per_batch,
            copy_files_path=args.copy_files_path,
        )
        print_plan(plan, args.copy_files_path)
        return 0

    incomplete_marker = create_incomplete_marker(
        safe_output_child(args.output_folder, f".{args.location_name}.INCOMPLETE")
    )
    organize_result = organizer.organize(
        scan_result,
        args.output_folder,
        args.location_name,
        subjects_per_batch=args.subjects_per_batch,
        copy_files_path=args.copy_files_path,
    )
    validation_result = validator.validate_batches(
        organize_result["batch_folders"],
        organize_result["expected_output_files"],
        files_per_batch=args.subjects_per_batch,
    )

    print_summary(scan_result, organize_result, validation_result)
    write_summary_report(
        args.output_folder,
        args.location_name,
        scan_result,
        organize_result,
        validation_result,
    )

    if has_errors(organize_result, validation_result):
        return 1

    remove_incomplete_marker(incomplete_marker)
    return 0


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Prepare T1w NIfTI files for ENIGMA FreeSurfer processing."
    )
    parser.add_argument(
        "--input-folder",
        required=True,
        help="Path to the dataset folder that should be scanned.",
    )
    parser.add_argument(
        "--output-folder",
        required=True,
        help="Path to the folder where sorted batch folders should be written.",
    )
    parser.add_argument(
        "--location-name",
        required=True,
        help="Name used for output batch folders, such as location1 or STRADL.",
    )
    parser.add_argument(
        "--subjects-per-batch",
        type=int,
        default=30,
        help="Number of T1w files per batch folder. Default is 30.",
    )
    parser.add_argument(
        "--copy-files-path",
        default=None,
        help="Optional folder containing support files to copy into each batch folder.",
    )
    parser.add_argument(
        "--dataset-type",
        choices=["auto", "raw", "bids"],
        default="auto",
        help="Accepted for compatibility. All inputs use the T1w-only pathway.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write files after reviewing preview mode. Without this flag, nothing is changed.",
    )

    return parser.parse_args()


def print_plan(plan, copy_files_path):
    print("##########PREVIEW ONLY: T1W SORTING##########")
    print("No files have been changed.")
    print(f"T1w files selected: {len(plan['operations'])}")
    print(f"Batch folders to create: {len(plan['batch_folders'])}")

    for operation in plan["operations"]:
        print(f"\n{operation['subject_id']}:")
        print(f" - {operation['action']}: {operation['source']} -> {operation['destination']}")

    print(f"\nOther T1w files excluded after subject/session selection: {len(plan['unselected_t1w_files'])}")
    for file_path in plan["unselected_t1w_files"]:
        print(f" - {file_path}")

    print(f"Other NIfTI files ignored: {len(plan['unknown_files'])}")
    for file_path in plan["unknown_files"]:
        print(f" - {file_path}")

    if copy_files_path:
        support_root = Path(copy_files_path).expanduser().resolve()
        if not support_root.exists():
            raise FileNotFoundError(f"Copy files folder does not exist: {support_root}")
        if not support_root.is_dir():
            raise NotADirectoryError(f"Copy files path is not a folder: {support_root}")

        print(f"\nSupport items copied into each numeric batch from: {support_root}")
        for item in sorted(support_root.iterdir()):
            print(f" - copy support item: {item}")

    print("\nRun again with --apply to perform these operations.")


def print_summary(scan_result, organize_result, validation_result):
    print("\n##########SCAN SUMMARY##########")
    print("T1w NIfTI files found:", len(scan_result["t1w_files"]))
    print("Other NIfTI files ignored:", len(scan_result["unknown_files"]))

    print("\n##########ORGANIZER SUMMARY##########")
    print("T1w files copied:", len(organize_result["copied_t1w_files"]))
    print("Batch folders created:", len(organize_result["batch_folders"]))
    print("Subjects with multiple T1w files:", len(organize_result["multiple_t1w_subjects"]))
    print("Excluded T1w files:", len(organize_result["unselected_t1w_files"]))
    print("Processing errors:", len(organize_result["processing_errors"]))

    print("\n##########VALIDATION SUMMARY##########")
    print("Batches checked:", validation_result["batches_checked"])
    print("T1w files checked:", validation_result["nifti_files_checked"])
    print("Missing expected files:", len(validation_result["missing_expected_files"]))
    print("Corrupt output files:", len(validation_result["corrupt_files"]))
    print("Partial output files:", len(validation_result["partial_files"]))
    print("Oversized batches:", len(validation_result["oversized_batches"]))
    print("Final status:", "FAILED" if has_errors(organize_result, validation_result) else "VALID")

    for batch_folder in organize_result["batch_folders"]:
        print("Batch folder:", batch_folder)

    for error in organize_result["processing_errors"]:
        print(
            "Processing error:",
            error["source"],
            "->",
            error["destination"],
            f"{error['error_type']}: {error['error']}",
        )

    for record in validation_result["corrupt_files"]:
        print("Corrupt output file:", record["path"], record["error"])


def write_summary_report(output_folder, location_name, scan_result, organize_result, validation_result):
    report_path = Path(output_folder) / f"{location_name}_sorting_report.txt"

    with open(report_path, "w") as report:
        report.write("##########SCAN SUMMARY##########\n")
        report.write(f"T1w NIfTI files found: {len(scan_result['t1w_files'])}\n")
        report.write(f"Other NIfTI files ignored: {len(scan_result['unknown_files'])}\n\n")

        report.write("##########ORGANIZER SUMMARY##########\n")
        report.write(f"T1w files copied: {len(organize_result['copied_t1w_files'])}\n")
        report.write(f"Batch folders created: {len(organize_result['batch_folders'])}\n")
        report.write(f"Subjects with multiple T1w files: {len(organize_result['multiple_t1w_subjects'])}\n")
        report.write(f"Excluded T1w files: {len(organize_result['unselected_t1w_files'])}\n")
        report.write(f"Processing errors: {len(organize_result['processing_errors'])}\n\n")

        report.write("##########VALIDATION SUMMARY##########\n")
        report.write(f"Batches checked: {validation_result['batches_checked']}\n")
        report.write(f"T1w files checked: {validation_result['nifti_files_checked']}\n")
        report.write(f"Missing expected files: {len(validation_result['missing_expected_files'])}\n")
        report.write(f"Corrupt output files: {len(validation_result['corrupt_files'])}\n")
        report.write(f"Partial output files: {len(validation_result['partial_files'])}\n")
        report.write(f"Incomplete run markers: {len(validation_result['incomplete_files'])}\n")
        report.write(f"Duplicate output files: {len(validation_result['duplicate_files'])}\n")
        report.write(f"Compressed output files: {len(validation_result['compressed_output_files'])}\n")
        report.write(f"Unexpected NIfTI files: {len(validation_result['unexpected_nifti_files'])}\n")
        report.write(f"Oversized batches: {len(validation_result['oversized_batches'])}\n")
        report.write(
            f"FINAL STATUS: {'FAILED' if has_errors(organize_result, validation_result) else 'VALID'}\n"
        )

        if organize_result["multiple_t1w_subjects"]:
            report.write("\nSubjects with multiple T1w files:\n")
            for subject_id in organize_result["multiple_t1w_subjects"]:
                report.write(f"  - {subject_id}\n")

        if organize_result["unselected_t1w_files"]:
            report.write("\nExcluded T1w files:\n")
            for file_path in organize_result["unselected_t1w_files"]:
                report.write(f"  - {file_path}\n")

        if scan_result["unknown_files"]:
            report.write("\nIgnored non-T1w NIfTI files:\n")
            for file_path in scan_result["unknown_files"]:
                report.write(f"  - {file_path}\n")

        if organize_result["processing_errors"]:
            report.write("\nProcessing errors:\n")
            for error in organize_result["processing_errors"]:
                report.write(f"  - Source: {error['source']}\n")
                report.write(f"    Destination: {error['destination']}\n")
                report.write(f"    Error: {error['error_type']}: {error['error']}\n")

        for heading, key in [
            ("Missing expected files", "missing_expected_files"),
            ("Partial output files", "partial_files"),
            ("Incomplete run markers", "incomplete_files"),
            ("Duplicate output files", "duplicate_files"),
            ("Compressed output files", "compressed_output_files"),
            ("Unexpected NIfTI files", "unexpected_nifti_files"),
        ]:
            if validation_result[key]:
                report.write(f"\n{heading}:\n")
                for item in validation_result[key]:
                    report.write(f"  - {item}\n")

        if validation_result["oversized_batches"]:
            report.write("\nOversized batches:\n")
            for record in validation_result["oversized_batches"]:
                report.write(
                    f"  - {record['batch_folder']}: "
                    f"{record['file_count']} files, limit {record['limit']}\n"
                )

        if validation_result["corrupt_files"]:
            report.write("\nCorrupt output files:\n")
            for record in validation_result["corrupt_files"]:
                report.write(f"  - {record['path']}: {record['error']}\n")


def has_errors(organize_result, validation_result):
    return any([
        not organize_result.get("copied_t1w_files"),
        organize_result.get("processing_errors"),
        validation_result.get("missing_expected_files"),
        validation_result.get("corrupt_files"),
        validation_result.get("partial_files"),
        validation_result.get("incomplete_files"),
        validation_result.get("duplicate_files"),
        validation_result.get("compressed_output_files"),
        validation_result.get("unexpected_nifti_files"),
        validation_result.get("oversized_batches"),
    ])


if __name__ == "__main__":
    sys.exit(main())

