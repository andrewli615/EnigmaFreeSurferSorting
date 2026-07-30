#!/usr/bin/env python3
import argparse
import shutil
from pathlib import Path


STEP1_NAME = "step1_run_reconAll_task.pbs"
STEP3_NAME = "step3_QC_task.pbs"
STEP4_NAME = "step4_extract_thicknessareavolume.pbs"
STEP5_NAME = "step5_run_Schaefer1000_task.pbs"


def main():
    args = parse_arguments()
    root = resolve_root(args)

    if not root.exists():
        raise FileNotFoundError(f"Root folder does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Root path is not a folder: {root}")

    batches = sorted(folder for folder in root.iterdir() if folder.is_dir())

    if not batches:
        print(f"No batch folders were found under {root}")
        return 1

    for batch_folder in batches:
        prepare_batch(batch_folder, args.email, args.apply)

    if not args.apply:
        print("\nPreview only. Run again with --apply to move files and write PBS scripts.")

    return 0


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Normalize FS_ChineseEthnoracial batches and write batch-specific PBS files."
    )
    parser.add_argument(
        "--root",
        default=None,
        help="Folder containing batch folders. Overrides --base-dir and --project-name.",
    )
    parser.add_argument(
        "--base-dir",
        default="/scratch/ss-vbrain-1/ali152",
        help="Base scratch folder containing the project folder.",
    )
    parser.add_argument(
        "--project-name",
        default="FS_ChineseEthnoracial",
        help="Project folder name below --base-dir.",
    )
    parser.add_argument(
        "--email",
        default="ali152@student.ubc.ca",
        help="Email used in PBS notifications.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually move top-level .nii files into rawdata and overwrite PBS scripts.",
    )
    return parser.parse_args()


def resolve_root(args):
    if args.root is not None:
        return Path(args.root).expanduser().resolve()

    return (Path(args.base_dir).expanduser() / args.project_name).resolve()


def prepare_batch(batch_folder, email, apply_changes):
    rawdata = batch_folder / "rawdata"
    top_level_nii = sorted(batch_folder.glob("*.nii"))

    print(f"\n{batch_folder.name}")
    if top_level_nii:
        print(f"  move {len(top_level_nii)} top-level .nii files into {rawdata}")
        if apply_changes:
            rawdata.mkdir(exist_ok=True)
            move_into_rawdata(top_level_nii, rawdata)
    elif rawdata.is_dir():
        print("  rawdata folder already exists; leaving imaging files in place")
    else:
        print("  warning: no top-level .nii files and no rawdata folder found")
        if apply_changes:
            rawdata.mkdir(exist_ok=True)

    subject_count = count_nifti_files(rawdata if rawdata.exists() else batch_folder)
    print(f"  T1w .nii files in rawdata: {subject_count}")
    if subject_count > 30:
        print("  warning: this batch has more than 30 .nii files")

    scripts = {
        STEP1_NAME: step1_script(batch_folder, email, subject_count),
        STEP3_NAME: step3_script(batch_folder, email),
        STEP4_NAME: step4_script(batch_folder, email),
        STEP5_NAME: step5_script(batch_folder, email),
    }

    for filename, content in scripts.items():
        path = batch_folder / filename
        print(f"  write {path.name}")
        if apply_changes:
            path.write_text(content)


def move_into_rawdata(files, rawdata):
    for source in files:
        destination = rawdata / source.name
        if destination.exists():
            raise FileExistsError(f"Destination already exists: {destination}")
        shutil.move(str(source), str(destination))


def count_nifti_files(rawdata):
    if not rawdata.exists():
        return 0
    return len(sorted(rawdata.glob("*.nii")))


def step1_script(batch_folder, email, subject_count):
    location = batch_folder.name
    jobs = max(1, subject_count)
    rawdata = batch_folder / "rawdata"
    fsoutput = batch_folder / "FSoutput"
    output_log = batch_folder / "Step1Output.txt"
    error_log = batch_folder / "Step1Error.txt"
    return f"""#!/bin/bash

#PBS -l walltime=10:00:00,select=1:ncpus=32:mem=100gb
#PBS -N {location}_step1_FST
#PBS -A st-sfrangou-1
#PBS -m abe
#PBS -M {email}
#PBS -o {output_log}
#PBS -e {error_log}

export FREESURFER_HOME=/arc/project/st-sfrangou-1/software/freesurfer
source "$FREESURFER_HOME/SetUpFreeSurfer.sh"

export SUBJECTS_DIR={fsoutput}
mkdir -p "$SUBJECTS_DIR"

cd {rawdata}
module load intel-oneapi-compilers/2023.1.0
module load parallel
ls *.nii | parallel --jobs {jobs} 'recon-all -s {{.}} -i {{}} -all'
"""


def step3_script(batch_folder, email):
    location = batch_folder.name
    rawdata = batch_folder / "rawdata"
    fsoutput = batch_folder / "FSoutput"
    output_log = batch_folder / "Step3_Output.txt"
    error_log = batch_folder / "Step3_Error.txt"
    return f"""#!/bin/bash

#PBS -l walltime=03:00:00,select=1:ncpus=32:mem=100gb
#PBS -N {location}_step3
#PBS -A st-sfrangou-1
#PBS -m abe
#PBS -M {email}
#PBS -o {output_log}
#PBS -e {error_log}

export FREESURFER_HOME=/arc/project/st-sfrangou-1/software/freesurfer
source "$FREESURFER_HOME/SetUpFreeSurfer.sh"
module load gcc/9.4.0

datafolder={rawdata}
cd "$datafolder"
cd ..
parentfolder=$(pwd)

fsoutput_folder={fsoutput}

cd "$parentfolder"
mkdir -p FSoutput_QC_step2_internal
cd "$fsoutput_folder"
module load matlab/R2019b
cp /arc/project/st-sfrangou-1/software/ENIGMA_Cortical_QC_2.0/createQC_PNGimages_ryg.m createQC_PNGimages.m
matlab -nodisplay -r createQC_PNGimages
rm createQC_PNGimages.m
cd "$parentfolder/FSoutput_QC_step2_internal"
chmod 777 /arc/project/st-sfrangou-1/software/ENIGMA_Cortical_QC_2.0/make_ENIGMA_QC_webpage.sh
/arc/project/st-sfrangou-1/software/ENIGMA_Cortical_QC_2.0/make_ENIGMA_QC_webpage.sh "$parentfolder/FSoutput_QC_step2_internal/"

cd "$parentfolder"
mkdir -p FSoutput_QC_step3_external
cd "$fsoutput_folder"
cp /arc/project/st-sfrangou-1/software/freesurfer_statsurf_display-individual/QCstep3_run_me_ryg.m QCstep3_run_me.m
matlab -nodisplay -r QCstep3_run_me
rm QCstep3_run_me.m
cd "$parentfolder/FSoutput_QC_step3_external"
chmod 777 /arc/project/st-sfrangou-1/software/freesurfer_statsurf_display-individual/make_ENIGMA_QC_webpage_ryg.sh
/arc/project/st-sfrangou-1/software/freesurfer_statsurf_display-individual/make_ENIGMA_QC_webpage_ryg.sh "$parentfolder/FSoutput_QC_step3_external/"

cd "$parentfolder"
mkdir -p FSoutput_QC_step4_subcortical
cd "$fsoutput_folder"
cp /arc/project/st-sfrangou-1/software/ENIGMA-Wrapper-Scripts-master/enigma_wrapscripts/Matlab/QCstep4_run_me_ryg.m QCstep4_run_me.m
matlab -nodisplay -nodesktop -nosplash < QCstep4_run_me.m
rm QCstep4_run_me.m
cd "$parentfolder/FSoutput_QC_step4_subcortical"
chmod 777 /arc/project/st-sfrangou-1/software/ENIGMA-Wrapper-Scripts-master/enigma_wrapscripts/Matlab/make_subcortical_ENIGMA_QC_webpage_ryg.sh
/arc/project/st-sfrangou-1/software/ENIGMA-Wrapper-Scripts-master/enigma_wrapscripts/Matlab/make_subcortical_ENIGMA_QC_webpage_ryg.sh "$parentfolder/FSoutput_QC_step4_subcortical/"
"""


def step4_script(batch_folder, email):
    location = batch_folder.name
    fsoutput = batch_folder / "FSoutput"
    tav = batch_folder / "TAV"
    output_log = batch_folder / "Step4_Output.txt"
    error_log = batch_folder / "Step4_Error.txt"
    return f"""#!/bin/bash

#PBS -l walltime=02:00:00,select=1:ncpus=4:mem=16gb
#PBS -N {location}_step4_FreeSurfer_Tool
#PBS -A st-sfrangou-1
#PBS -m abe
#PBS -M {email}
#PBS -o {output_log}
#PBS -e {error_log}

export FREESURFER_HOME=/arc/project/st-sfrangou-1/software/freesurfer
source "$FREESURFER_HOME/SetUpFreeSurfer.sh"
module load gcc/9.4.0

export SUBJECTS_DIR={fsoutput}

mkdir -p {tav}
cd {tav}

SUBJECT_LIST=$(find "$SUBJECTS_DIR" -mindepth 1 -maxdepth 1 -type d \\
  -name "sub-*_*" ! -name "fsaverage" -exec basename {{}} \\;)

echo "$SUBJECT_LIST"
echo "$SUBJECT_LIST" | wc -w

aparcstats2table --subjects $SUBJECT_LIST --hemi lh --parc aparc --meas area --tablefile data_area_lh_aparc.txt
aparcstats2table --subjects $SUBJECT_LIST --hemi rh --parc aparc --meas area --tablefile data_area_rh_aparc.txt
aparcstats2table --subjects $SUBJECT_LIST --hemi lh --parc aparc --meas thickness --tablefile data_thickness_lh_aparc.txt
aparcstats2table --subjects $SUBJECT_LIST --hemi rh --parc aparc --meas thickness --tablefile data_thickness_rh_aparc.txt
asegstats2table --subjects $SUBJECT_LIST --meas volume --tablefile data_aseg_stats.txt
"""


def step5_script(batch_folder, email):
    location = batch_folder.name
    fsoutput = batch_folder / "FSoutput"
    output_log = batch_folder / "Step5_Output_Schaefer1000.txt"
    error_log = batch_folder / "Step5_Error_Schaefer1000.txt"
    return f"""#!/bin/bash

#PBS -l walltime=5:00:00,select=1:ncpus=32:mem=100gb
#PBS -N {location}_Schaefer1000
#PBS -A st-sfrangou-1
#PBS -m abe
#PBS -M {email}
#PBS -o {output_log}
#PBS -e {error_log}

export FREESURFER_HOME=/arc/project/st-sfrangou-1/software/freesurfer
source "$FREESURFER_HOME/SetUpFreeSurfer.sh"

export SUBJECTS_DIR={fsoutput}

LH_ANNOT="$FREESURFER_HOME/subjects/fsaverage/label/lh.Schaefer2018_1000Parcels_7Networks_order.annot"
RH_ANNOT="$FREESURFER_HOME/subjects/fsaverage/label/rh.Schaefer2018_1000Parcels_7Networks_order.annot"

if [ ! -f "$LH_ANNOT" ] || [ ! -f "$RH_ANNOT" ]; then
    echo "Missing Schaefer1000 annot files in $FREESURFER_HOME/subjects/fsaverage/label"
    exit 1
fi

SUBJECT_LIST=$(find "$SUBJECTS_DIR" -mindepth 1 -maxdepth 1 -type d \\
  -name "sub-*_*" ! -name "fsaverage" -exec basename {{}} \\;)

for sub in $SUBJECT_LIST
do
  mri_surf2surf --hemi lh \\
    --srcsubject fsaverage \\
    --trgsubject "$sub" \\
    --sval-annot "$LH_ANNOT" \\
    --tval "$SUBJECTS_DIR/$sub/label/lh.Schaefer2018_1000Parcels_7Networks_order.annot"

  mri_surf2surf --hemi rh \\
    --srcsubject fsaverage \\
    --trgsubject "$sub" \\
    --sval-annot "$RH_ANNOT" \\
    --tval "$SUBJECTS_DIR/$sub/label/rh.Schaefer2018_1000Parcels_7Networks_order.annot"

  mris_anatomical_stats \\
    -a "$SUBJECTS_DIR/$sub/label/lh.Schaefer2018_1000Parcels_7Networks_order.annot" \\
    -b -f "$SUBJECTS_DIR/$sub/stats/lh.Schaefer1000.stats" "$sub" lh

  mris_anatomical_stats \\
    -a "$SUBJECTS_DIR/$sub/label/rh.Schaefer2018_1000Parcels_7Networks_order.annot" \\
    -b -f "$SUBJECTS_DIR/$sub/stats/rh.Schaefer1000.stats" "$sub" rh
done

cd "$SUBJECTS_DIR"

aparcstats2table --hemi lh --subjects $SUBJECT_LIST --parc Schaefer1000 --meas area --tablefile lh.Schaefer1000.area.txt
aparcstats2table --hemi rh --subjects $SUBJECT_LIST --parc Schaefer1000 --meas area --tablefile rh.Schaefer1000.area.txt
aparcstats2table --hemi lh --subjects $SUBJECT_LIST --parc Schaefer1000 --meas thickness --tablefile lh.Schaefer1000.thickness.txt
aparcstats2table --hemi rh --subjects $SUBJECT_LIST --parc Schaefer1000 --meas thickness --tablefile rh.Schaefer1000.thickness.txt
"""


if __name__ == "__main__":
    raise SystemExit(main())
