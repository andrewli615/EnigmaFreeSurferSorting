import argparse
import sys
from pathlib import Path

from sorter.validator import Validator


def main():
    args = parse_arguments()
    validator = Validator()
    output_folder = Path(args.output_folder).expanduser().resolve()
    result = validator.validate_nifti_tree(
        output_folder,
        files_per_batch=args.subjects_per_batch,
    )
    has_errors = validation_has_errors(result)

    report_path = output_folder / args.report_name
    write_report(report_path, result, has_errors)
    print(f"Validation report: {report_path}")
    print("Final status:", "FAILED" if has_errors else "VALID")
    return 1 if has_errors else 0


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Read-only validation of an existing T1w sorter output folder."
    )
    parser.add_argument("--output-folder", required=True)
    parser.add_argument(
        "--subjects-per-batch",
        type=int,
        default=30,
        help="Maximum T1w files expected in each numeric batch folder.",
    )
    parser.add_argument(
        "--report-name",
        default="standalone_validation_report.txt",
        help="Report filename written inside the output folder.",
    )
    return parser.parse_args()


def write_report(report_path, result, has_errors):
    with open(report_path, "w") as report:
        report.write("===== STANDALONE T1W OUTPUT VALIDATION =====\n")
        report.write(f"Batches checked: {result['batches_checked']}\n")
        report.write(f"NIfTI files checked: {result['nifti_files_checked']}\n")
        report.write(f"Missing expected files: {len(result['missing_expected_files'])}\n")
        report.write(f"Corrupt NIfTI files: {len(result['corrupt_files'])}\n")
        report.write(f"Partial files: {len(result['partial_files'])}\n")
        report.write(f"Incomplete run markers: {len(result['incomplete_files'])}\n")
        report.write(f"Duplicate files: {len(result['duplicate_files'])}\n")
        report.write(f"Compressed output files: {len(result['compressed_output_files'])}\n")
        report.write(f"Unexpected NIfTI files: {len(result['unexpected_nifti_files'])}\n")
        report.write(f"Oversized batches: {len(result['oversized_batches'])}\n")
        report.write(f"FINAL STATUS: {'FAILED' if has_errors else 'VALID'}\n")

        for heading, key in [
            ("Partial files", "partial_files"),
            ("Incomplete run markers", "incomplete_files"),
            ("Duplicate files", "duplicate_files"),
            ("Compressed output files", "compressed_output_files"),
            ("Unexpected NIfTI files", "unexpected_nifti_files"),
        ]:
            if result[key]:
                report.write(f"\n{heading}:\n")
                for item in result[key]:
                    report.write(f"  - {item}\n")

        if result["oversized_batches"]:
            report.write("\nOversized batches:\n")
            for record in result["oversized_batches"]:
                report.write(
                    f"  - {record['batch_folder']}: "
                    f"{record['file_count']} files, limit {record['limit']}\n"
                )

        if result["corrupt_files"]:
            report.write("\nCorrupt NIfTI files:\n")
            for record in result["corrupt_files"]:
                report.write(f"  - {record['path']}: {record['error']}\n")


def validation_has_errors(result):
    return any([
        result["missing_expected_files"],
        result["corrupt_files"],
        result["partial_files"],
        result["incomplete_files"],
        result["duplicate_files"],
        result["compressed_output_files"],
        result["unexpected_nifti_files"],
        result["oversized_batches"],
    ])


if __name__ == "__main__":
    sys.exit(main())

