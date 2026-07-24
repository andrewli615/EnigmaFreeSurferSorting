#!/bin/bash

#SBATCH --job-name=prepare_fs_batches
#SBATCH --account=st-sfrangou-1
#SBATCH --time=00:30:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --mail-type=BEGIN,END,FAIL
#SBATCH --output=prepare_fs_batches_output_%j.txt
#SBATCH --error=prepare_fs_batches_error_%j.txt

set -euo pipefail

# Step 2 of the workflow:
#   - enter FS_ChineseEthnoracial
#   - process each direct batch folder inside it
#   - move top-level .nii files into rawdata when needed
#   - write batch-specific Step 1, 3, 4, and 5 PBS files
#
# This script does not sort raw source datasets. Use jobs/submit_sort.sh for
# the first sorting step.

WORK_DIR="${WORK_DIR:-/scratch/ss-vbrain-1/ali152}"
cd "$WORK_DIR"

PROJECT_DIR="${PROJECT_DIR:-${WORK_DIR}/EnigmaFreeSurferSorting}"
PROJECT_NAME="${PROJECT_NAME:-FS_ChineseEthnoracial}"
BATCH_ROOT="${BATCH_ROOT:-${WORK_DIR}/${PROJECT_NAME}}"
EMAIL="${EMAIL:-ali152@student.ubc.ca}"

# false = preview only and write/move nothing
# true = move files into rawdata and overwrite Step 1/3/4/5 PBS files
APPLY_CHANGES="${APPLY_CHANGES:-false}"

PYTHON_MODULE="${PYTHON_MODULE:-python/3.12.7}"
if command -v module >/dev/null 2>&1; then
    module load "$PYTHON_MODULE"
fi

python3 --version

if [ ! -d "$PROJECT_DIR" ]; then
    echo "Project folder does not exist: $PROJECT_DIR"
    exit 1
fi

if [ ! -d "$BATCH_ROOT" ]; then
    echo "Batch root does not exist: $BATCH_ROOT"
    exit 1
fi

PREPARE_COMMAND=(
    python3 "${PROJECT_DIR}/scripts/setup_chinese_ethnoracial_batches.py"
    --root "$BATCH_ROOT"
    --email "$EMAIL"
)

if [ "$APPLY_CHANGES" = "true" ]; then
    PREPARE_COMMAND+=(--apply)
fi

"${PREPARE_COMMAND[@]}"
