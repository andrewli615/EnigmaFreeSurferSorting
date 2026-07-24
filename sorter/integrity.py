from pathlib import Path
import gzip
import hashlib
import math
import os
import shutil
import struct
import uuid


#
# This exception represents a copy, unzip, checksum, or file validation failure.
#
class IntegrityError(Exception):
    pass


#
# Calculate and return the SHA-256 checksum for one file.
#
# Args:
#   file_path: File that should be read
#
# Return:
#   Lowercase SHA-256 checksum string
#
def sha256(file_path):
    digest = hashlib.sha256()
    with open(file_path, "rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


#
# Validate that a NIfTI file is readable, non-empty, and structurally complete.
#
# Args:
#   file_path: NIfTI file that should be validated
#   compressed: Optional override indicating whether the file contains gzip data
#
# Return:
#   None when valid, or a detailed error string when invalid
#
def validate_nifti(file_path, compressed=None):
    file_path = Path(file_path)
    if compressed is None:
        compressed = file_path.name.lower().endswith(".nii.gz")

    try:
        if file_path.stat().st_size == 0:
            return "file is empty"

        if compressed:
            with gzip.open(file_path, "rb") as source:
                header = source.read(544)
                total_size = len(header)
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    total_size += len(chunk)
        else:
            with open(file_path, "rb") as source:
                header = source.read(544)
            total_size = file_path.stat().st_size
    except (OSError, EOFError) as error:
        return f"file cannot be read: {error}"

    if len(header) < 4:
        return f"NIfTI data is too small ({len(header)} uncompressed bytes)"

    little_endian = struct.unpack("<I", header[:4])[0]
    big_endian = struct.unpack(">I", header[:4])[0]
    header_size = little_endian if little_endian in {348, 540} else big_endian
    minimum_size = 352 if header_size == 348 else 544 if header_size == 540 else None

    if minimum_size is None:
        return "invalid NIfTI header: sizeof_hdr is not 348 or 540"

    if len(header) < minimum_size:
        return f"NIfTI data is too small ({len(header)} uncompressed bytes)"

    if header_size == 348:
        endian = "<" if little_endian == 348 else ">"
        dimensions = struct.unpack(f"{endian}8h", header[40:56])
        dimension_count = dimensions[0]
        bitpix = struct.unpack(f"{endian}h", header[72:74])[0]
        vox_offset = struct.unpack(f"{endian}f", header[108:112])[0]

        if dimension_count < 1 or dimension_count > 7:
            return f"invalid NIfTI dimensions: dim[0]={dimension_count}"

        image_dimensions = dimensions[1:dimension_count + 1]
        if any(dimension <= 0 for dimension in image_dimensions):
            return f"invalid NIfTI dimensions: {image_dimensions}"

        if bitpix <= 0:
            return f"invalid NIfTI bitpix value: {bitpix}"

        voxel_count = math.prod(image_dimensions)
        expected_size = max(352, math.ceil(vox_offset)) + math.ceil(
            voxel_count * bitpix / 8
        )
        if total_size < expected_size:
            return (
                f"NIfTI data is truncated: expected at least {expected_size} "
                f"bytes, found {total_size}"
            )

    return None


#
# Copy one file through a temporary path and verify its checksum before finalizing.
#
# Args:
#   source_file: Existing input file
#   destination_file: Final output file path
#   validate_as_nifti: Whether the source and copied file must pass NIfTI validation
#
# Return:
#   Dictionary containing the source, destination, checksum, and final size
#
def atomic_copy(source_file, destination_file, validate_as_nifti=False):
    source_file = Path(source_file)
    destination_file = Path(destination_file)

    if validate_as_nifti:
        source_error = validate_nifti(source_file)
        if source_error:
            raise IntegrityError(f"source is invalid: {source_error}")

    destination_file.parent.mkdir(parents=True, exist_ok=True)
    partial_file = _partial_path(destination_file)

    try:
        shutil.copy2(source_file, partial_file)
        _flush_file(partial_file)

        source_hash = sha256(source_file)
        destination_hash = sha256(partial_file)
        if source_hash != destination_hash:
            raise IntegrityError(
                f"checksum mismatch: source={source_hash}, copied={destination_hash}"
            )

        if validate_as_nifti:
            copied_error = validate_nifti(
                partial_file,
                compressed=source_file.name.lower().endswith(".nii.gz"),
            )
            if copied_error:
                raise IntegrityError(f"copied file is invalid: {copied_error}")

        os.replace(partial_file, destination_file)
        if sha256(destination_file) != destination_hash:
            destination_file.unlink(missing_ok=True)
            raise IntegrityError("checksum mismatch after finalizing copied file")
        return {
            "source": source_file,
            "destination": destination_file,
            "sha256": destination_hash,
            "size": destination_file.stat().st_size,
        }
    except Exception:
        partial_file.unlink(missing_ok=True)
        raise


#
# Unzip one compressed NIfTI through a temporary path and verify the result.
#
# Args:
#   source_file: Existing compressed NIfTI file
#   destination_file: Final uncompressed NIfTI output path
#
# Return:
#   Dictionary containing the source, destination, checksum, and final size
#
def atomic_unzip(source_file, destination_file):
    source_file = Path(source_file)
    destination_file = Path(destination_file)

    source_error = validate_nifti(source_file)
    if source_error:
        raise IntegrityError(f"compressed source is invalid: {source_error}")

    destination_file.parent.mkdir(parents=True, exist_ok=True)
    partial_file = _partial_path(destination_file)
    source_digest = hashlib.sha256()

    try:
        with gzip.open(source_file, "rb") as source:
            with open(partial_file, "wb") as destination:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    source_digest.update(chunk)
                    destination.write(chunk)
                destination.flush()
                os.fsync(destination.fileno())

        output_hash = sha256(partial_file)
        if source_digest.hexdigest() != output_hash:
            raise IntegrityError(
                "checksum mismatch between decompressed source and output"
            )

        output_error = validate_nifti(partial_file, compressed=False)
        if output_error:
            raise IntegrityError(f"unzipped file is invalid: {output_error}")

        os.replace(partial_file, destination_file)
        if sha256(destination_file) != output_hash:
            destination_file.unlink(missing_ok=True)
            raise IntegrityError("checksum mismatch after finalizing unzipped file")
        return {
            "source": source_file,
            "destination": destination_file,
            "sha256": output_hash,
            "size": destination_file.stat().st_size,
        }
    except Exception:
        partial_file.unlink(missing_ok=True)
        raise


#
# Return a unique hidden temporary path beside the final destination file.
#
def _partial_path(destination_file):
    return destination_file.with_name(
        f".{destination_file.name}.partial-{uuid.uuid4().hex}"
    )


#
# Ask the operating system to flush a completed temporary file to storage.
#
def _flush_file(file_path):
    with open(file_path, "rb") as copied_file:
        os.fsync(copied_file.fileno())
