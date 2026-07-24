# EnigmaFreeSurferSorting

Prepares T1-weighted NIfTI files for ENIGMA FreeSurfer processing.

The sorter follows the same preview/apply pattern as the ENIGMA HALFpipe sorter:
preview first, review the planned paths, then run the same command with
`--apply` to write files.

Output is written into numeric location batches:

```text
<output-folder>/<location-name>_1/
<output-folder>/<location-name>_2/
```

Each batch contains up to 30 selected T1w `.nii` files by default. Source
`.nii.gz` files are unzipped into `.nii` outputs, and the original input files
are never moved, deleted, or changed.

## Usage

Preview:

```bash
python3 main.py \
  --input-folder /path/to/input \
  --output-folder /path/to/output \
  --location-name Vancouver_Healthy
```

Apply the reviewed preview:

```bash
python3 main.py \
  --input-folder /path/to/input \
  --output-folder /path/to/output \
  --location-name Vancouver_Healthy \
  --apply
```

Use a different batch size if needed:

```bash
python3 main.py \
  --input-folder /path/to/input \
  --output-folder /path/to/output \
  --location-name Vancouver_Healthy \
  --subjects-per-batch 30 \
  --apply
```

## Selection Rules

The scanner accepts `.nii` and `.nii.gz` files that look like T1w anatomical
images, including BIDS names ending in `_T1w`, common raw T1 labels, and plain
files inside `anat` folders when no other modality token is present.

When more than one T1w file is found for one subject, the sorter keeps one file
and reports the others. Selection prefers:

1. The earliest session.
2. An explicit `run-1`, `run-01`, `trial-1`, or `trial-01`.
3. Fewer reconstruction or variant entities such as `rec-*`, `desc-*`, or
   `proc-*`.
4. Uncompressed `.nii` over `.nii.gz` when all other ranking is tied.

Output files are named like:

```text
sub-<subject>_T1w.nii
sub-<subject>_ses-<session>_T1w.nii
```

## Data Safety

During an `--apply` run:

- Files are first written to hidden `.partial-*` paths.
- Copies are SHA-256 checksum verified before becoming final output files.
- Compressed inputs are fully decompressed and validated.
- NIfTI files must be non-empty and structurally valid.
- Available filesystem space is checked before writing.
- A hidden `.LOCATION.INCOMPLETE` marker remains until validation succeeds.
- Failures are reported while later files continue whenever possible.

Reports are written to:

```text
<output-folder>/<location-name>_sorting_report.txt
```

The report ends with `FINAL STATUS: VALID` or `FINAL STATUS: FAILED`.

## Sockeye Workflow

There are two separate Slurm steps.

### Step A: Sort T1w Files

This step scans a raw source dataset and creates numeric batches containing up
to 30 T1w `.nii` files. It does not create FreeSurfer PBS files.

```bash
export WORK_DIR=/scratch/YOUR_ACCOUNT/YOUR_USER
export PROJECT_DIR=$WORK_DIR/EnigmaFreeSurferSorting
export INPUT_FOLDER=$WORK_DIR/NIMH_Healthy
export OUTPUT_FOLDER=$WORK_DIR
export LOCATION_NAME=NIMH_Healthy
export APPLY_CHANGES=false

sbatch --account=YOUR_ACCOUNT jobs/submit_sort.sh
```

Review the preview output first. Then rerun with:

```bash
export APPLY_CHANGES=true
sbatch --account=YOUR_ACCOUNT jobs/submit_sort.sh
```

### Step B: Prepare FreeSurfer Batch Folders

This step is separate from file sorting. It enters a folder such as
`FS_ChineseEthnoracial`, processes every direct batch folder inside it, moves
top-level `.nii` files into `rawdata/` when needed, creates no imaging copies,
and writes batch-specific FreeSurfer Step 1, 3, 4, and 5 PBS files.

Preview:

```bash
export WORK_DIR=/scratch/ss-vbrain-1/ali152
export PROJECT_DIR=$WORK_DIR/EnigmaFreeSurferSorting
export PROJECT_NAME=FS_ChineseEthnoracial
export BATCH_ROOT=$WORK_DIR/$PROJECT_NAME
export EMAIL=ali152@student.ubc.ca
export APPLY_CHANGES=false

sbatch jobs/submit_prepare_freesurfer_batches.sh
```

Apply after reviewing the preview:

```bash
export APPLY_CHANGES=true
sbatch jobs/submit_prepare_freesurfer_batches.sh
```

Each direct folder under `BATCH_ROOT` becomes its own reference name. For
example, `FS_ChineseEthnoracial/SLIM_2` receives job names and paths containing
`SLIM_2`, creates/uses `SLIM_2/rawdata`, writes FreeSurfer output to
`SLIM_2/FSoutput`, and sets Step 1 `parallel --jobs` to the number of `.nii`
files in `SLIM_2/rawdata`.

## Validate Existing Output

```bash
python3 validate_output.py \
  --output-folder /path/to/output \
  --subjects-per-batch 30
```

## Build Deployment Package

```bash
bash jobs/build_deployment.sh
```
