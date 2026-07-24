from pathlib import Path
import os
import re
import shutil
import struct


#
# Location names become folder and report names, so only safe filename
# characters are accepted.
#
SAFE_LOCATION_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


#
# Validate a user-provided location name before it is used in an output path.
#
def validate_location_name(location_name):
    if not isinstance(location_name, str) or not SAFE_LOCATION_NAME.fullmatch(location_name):
        raise ValueError(
            "location_name must start with a letter or number and contain only "
            "letters, numbers, underscores, and hyphens"
        )

    return location_name


#
# Resolve a child output path and prove that it remains below its output root.
#
def safe_output_child(output_root, child_name):
    output_root = Path(output_root).expanduser().resolve()
    child_path = (output_root / child_name).resolve()

    if child_path.parent != output_root and output_root not in child_path.parents:
        raise ValueError(f"Output path escapes the output folder: {child_path}")

    return child_path


#
# Estimate the uncompressed byte count from a gzip trailer without writing it.
#
# Gzip stores this count modulo 2^32, so the compressed size is also used as a
# conservative lower bound for unusually large files.
#
def gzip_uncompressed_size(file_path):
    file_path = Path(file_path)
    compressed_size = file_path.stat().st_size

    with open(file_path, "rb") as source:
        if source.read(2) != b"\x1f\x8b" or compressed_size < 4:
            return compressed_size * 5
        source.seek(-4, os.SEEK_END)
        trailer_size = struct.unpack("<I", source.read(4))[0]

    return max(trailer_size, compressed_size * 5)


#
# Estimate output bytes from files that will be copied and files that will be
# unzipped.
#
def estimate_required_bytes(copy_files=(), unzip_files=()):
    required_bytes = sum(Path(file_path).stat().st_size for file_path in copy_files)

    for file_path in unzip_files:
        required_bytes += gzip_uncompressed_size(file_path)

    return required_bytes


#
# Ensure the destination filesystem has the estimated space plus a safety
# reserve before an apply run begins.
#
def ensure_free_space(destination, required_bytes):
    destination = Path(destination).expanduser().resolve()
    existing_parent = destination

    while not existing_parent.exists():
        existing_parent = existing_parent.parent

    free_bytes = shutil.disk_usage(existing_parent).free
    reserve_bytes = max(1024 ** 3, required_bytes // 10)
    minimum_free_bytes = required_bytes + reserve_bytes

    if free_bytes < minimum_free_bytes:
        raise OSError(
            "Insufficient free space before sorting: "
            f"need at least {minimum_free_bytes} bytes including reserve, "
            f"but only {free_bytes} bytes are available at {existing_parent}"
        )


#
# Create and flush a marker showing that an output run has not completed
# validation successfully.
#
def create_incomplete_marker(marker_path):
    marker_path = Path(marker_path)
    marker_path.parent.mkdir(parents=True, exist_ok=True)

    with open(marker_path, "w") as marker:
        marker.write(
            "This sorter output is incomplete or has not passed validation. "
            "Do not use it for FreeSurfer processing.\n"
        )
        marker.flush()
        os.fsync(marker.fileno())

    return marker_path


#
# Remove an incomplete marker only after the complete output validates.
#
def remove_incomplete_marker(marker_path):
    Path(marker_path).unlink(missing_ok=True)
