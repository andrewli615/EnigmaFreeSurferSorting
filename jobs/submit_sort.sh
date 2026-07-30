#!/bin/bash

#SBATCH --job-name=sort_t1w_
#SBATCH --account=st-sfrangou-1
#SBATCH --time=02:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=5
#SBATCH --mem=32G
#SBATCH --mail-type=BEGIN,END,FAIL
#SBATCH --output=sort_t1w_output_%j.txt
#SBATCH --error=sort_t1w_error_%j.txt

set -euo pipefail

# Configure these values before submitting, or export them in the shell.
WORK_DIR="${WORK_DIR:-CHANGE}"
cd "$WORK_DIR"

PROJECT_DIR="${PROJECT_DIR:-${WORK_DIR}/EnigmaFreeSurferSorting}"

GCC_MODULE="${GCC_MODULE:-gcc/7.5.0}"
PYTHON_MODULE="${PYTHON_MODULE:-python/3.12.7}"
if command -v module >/dev/null 2>&1; then
    module load "$GCC_MODULE"
    module load "$PYTHON_MODULE"
fi

python3 --version

LOCATION_NAME="${LOCATION_NAME:-CHANGE}"
SUBJECTS_PER_BATCH="${SUBJECTS_PER_BATCH:-30}"
APPLY_CHANGES="${APPLY_CHANGES:-CHANGE}"

BASE_DIR="${BASE_DIR:-$WORK_DIR}"
COPY_FILES_FOLDER="${COPY_FILES_FOLDER:-${BASE_DIR}/Copy_Files}"
INPUT_FOLDER="${INPUT_FOLDER:-${BASE_DIR}/${LOCATION_NAME}}"
OUTPUT_FOLDER="${OUTPUT_FOLDER:-${BASE_DIR}}"

if [ ! -d "$INPUT_FOLDER" ]; then
    echo "Input folder does not exist: $INPUT_FOLDER"
    exit 1
fi

SORT_COMMAND=(
    python3 "${PROJECT_DIR}/main.py"
    --input-folder "$INPUT_FOLDER"
    --output-folder "$OUTPUT_FOLDER"
    --location-name "$LOCATION_NAME"
    --subjects-per-batch "$SUBJECTS_PER_BATCH"
)

if [ -d "$COPY_FILES_FOLDER" ]; then
    SORT_COMMAND+=(--copy-files-path "$COPY_FILES_FOLDER")
fi

if [ "$APPLY_CHANGES" = "true" ]; then
    SORT_COMMAND+=(--apply)
fi

"${SORT_COMMAND[@]}"
