#!/usr/bin/env python
"""
Master Orchestration Script for CHESS Legacy Data Reduction.
Drives headless frame stacking, orientation matrix solving, 1-rot verification slicing,
and full batch distributed reduction across CLASSE CPU compute nodes.
Compatible with /nfs/chess/sw/anaconda3_jpcr/ without modifications.
"""

import os
import sys
import argparse
import subprocess
import json
import shutil
from datetime import datetime

# Add local scripts directory to sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import pipeline_tracker


PYTHON_EXEC = "/nfs/chess/sw/anaconda3_jpcr/bin/python"
NIGHTLY_PYTHON = "/nfs/chess/sw/anaconda3_sgomezalvarado_nightly/bin/python"
VIS_PYTHON = NIGHTLY_PYTHON if os.path.exists(NIGHTLY_PYTHON) else PYTHON_EXEC
DEFAULT_CODEBASE = os.environ.get(
    "CHESS_LEGACY_CODEBASE",
    os.path.expanduser("~/Documents/automate_legacy_workflow/StevenGomezAlvarado_Codebase")
)


def run_cmd(cmd_list, description):
    print(f"\n>>> [RUNNING] {description}", flush=True)
    print(f"Command: {' '.join(cmd_list)}", flush=True)
    proc = subprocess.Popen(
        cmd_list,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    output_lines = []
    for line in iter(proc.stdout.readline, ''):
        print(line, end='', flush=True)
        output_lines.append(line)
    proc.stdout.close()
    returncode = proc.wait()
    if returncode != 0:
        raise RuntimeError(f"Step '{description}' failed with exit code {returncode}")
    return ''.join(output_lines)


def discover_paths(cycle, experiment, sample, sample_id):
    raw_root = f"/nfs/chess/id4b/{cycle}/{experiment}/raw6M/{sample}/{sample_id}"
    processed_root = f"/nfs/chess/id4baux/{cycle}/{experiment}/processed_old_way/{sample}/{sample_id}"
    spec_file = f"/nfs/chess/id4b/{cycle}/{experiment}/{sample}"
    calib_dir = f"/nfs/chess/id4baux/{cycle}/{experiment}/calibrations"
    return raw_root, processed_root, spec_file, calib_dir


def get_sorted_temperatures(raw_root):
    if not os.path.exists(raw_root):
        raise FileNotFoundError(f"Raw directory does not exist: {raw_root}")
    temp_dirs = [d for d in os.listdir(raw_root) if os.path.isdir(os.path.join(raw_root, d))]
    num_dirs = [d for d in temp_dirs if d.isdigit()]
    num_dirs.sort(key=lambda x: int(x))
    return num_dirs


def get_rotation_scan_folders(raw_temp_dir):
    scans = [s for s in os.listdir(raw_temp_dir) if os.path.isdir(os.path.join(raw_temp_dir, s))]
    scans.sort()
    return scans


def run_fastpath(args):
    """
    Execute single rotation 1 stack at warmest temperature, solve ORM, run 1rot HKL, and slice.
    """
    raw_root, processed_root, spec_file, calib_dir = discover_paths(
        args.cycle, args.experiment, args.sample, args.sample_id
    )

    if not os.path.exists(spec_file):
        raise FileNotFoundError(f"SPEC file not found: {spec_file}")
    if not os.path.exists(args.calib_file):
        raise FileNotFoundError(f"Calibration (.poni) not found: {args.calib_file}")
    if not os.path.exists(args.mask_file):
        raise FileNotFoundError(f"Mask (.edf) not found: {args.mask_file}")

    temperatures = get_sorted_temperatures(raw_root)
    if not temperatures:
        raise RuntimeError(f"No temperature folders found in {raw_root}")

    warmest_temp = temperatures[-1]
    print(f"\n=======================================================")
    print(f"FAST-PATH VERIFICATION RUN: Sample {args.sample_id}")
    print(f"Detected {len(temperatures)} temperatures: {temperatures}")
    print(f"Warmest temperature selected for orientation: {warmest_temp} K")
    print(f"=======================================================\n")

    # Initialize tracker
    pipeline_tracker.init_sample(
        sample_root=processed_root,
        sample_name=args.sample,
        sample_id=args.sample_id,
        cycle=args.cycle,
        experiment=args.experiment,
        spec_file=spec_file,
        calib_file=args.calib_file,
        mask_file=args.mask_file,
        unit_cell=args.unit_cell
    )

    raw_temp_dir = os.path.join(raw_root, warmest_temp)
    proc_temp_dir = os.path.join(processed_root, warmest_temp)
    os.makedirs(proc_temp_dir, exist_ok=True)

    scan_folders = get_rotation_scan_folders(raw_temp_dir)
    if not scan_folders:
        raise RuntimeError(f"No scan folders in {raw_temp_dir}")
    if len(scan_folders) > 3:
        raise RuntimeError(
            f"Anomalous scan count: found {len(scan_folders)} scans in {raw_temp_dir} ({scan_folders}). "
            f"Expected either 1 or 3 rotations. User clarification required before proceeding."
        )
    print(f"Detected {len(scan_folders)} rotation scan(s) in {raw_temp_dir}: {scan_folders}")
    rot1_scan = scan_folders[0]
    scan_num = rot1_scan.split("_")[-1]

    # Step 1: Stack Rotation 1
    stack1_file = os.path.join(proc_temp_dir, "stack1.nxs")
    if not os.path.exists(stack1_file) or args.force_stack:
        pipeline_tracker.update_temp_step(processed_root, warmest_temp, "stacking", "RUNNING")
        stacker_script = os.path.join(args.codebase, "stack_em_all.py")
        raw_scan_path = os.path.join(raw_temp_dir, rot1_scan) + "/"
        proc_out_path = proc_temp_dir + "/"

        cmd_stack = [
            PYTHON_EXEC, "-u", stacker_script,
            spec_file, args.calib_file, args.mask_file,
            args.sample, str(int(scan_num)), str(warmest_temp),
            raw_scan_path, proc_out_path
        ]
        run_cmd(cmd_stack, f"Stacking Rotation 1 ({rot1_scan}) at {warmest_temp}K")
        pipeline_tracker.update_temp_step(processed_root, warmest_temp, "stacking", "COMPLETED", {"stacked": [1]})
    else:
        print(f"Stack 1 already exists at {stack1_file}. Skipping stacking.")

    # Step 2: Headless ORM Solver
    orm_script = os.path.join(SCRIPT_DIR, "orm_solver.py")
    orm_target = os.path.join(proc_temp_dir, "ormatrix_auto.nxs")
    if not os.path.exists(orm_target) or args.force_orm:
        cmd_orm = [
            PYTHON_EXEC, "-u", orm_script,
            "--projectdir", proc_temp_dir,
            "--unitcell", args.unit_cell,
            "--codebase", args.codebase
        ]
        run_cmd(cmd_orm, f"Headless Orientation Matrix Solving at {warmest_temp}K")
        clean_temp_val = float(str(warmest_temp).replace("p", "."))
        clean_temp = int(clean_temp_val) if clean_temp_val.is_integer() else clean_temp_val
        pipeline_tracker.record_orientation_result(
            processed_root, clean_temp, orm_target, None, verified=False
        )
    else:
        print(f"Orientation matrix already exists at {orm_target}. Skipping solver.")

    # Step 3: 1-Rotation HKL Reciprocal Space Conversion
    hkl1_file = os.path.join(proc_temp_dir, "1rot_hkli.nxs")
    if not os.path.exists(hkl1_file) or args.force_hkl:
        pipeline_tracker.update_temp_step(processed_root, warmest_temp, "hkl_1rot", "RUNNING")
        conv_script = os.path.join(args.codebase, "Pil6M_HKLConv_3D_2022_1rot.py")
        cmd_conv = [
            PYTHON_EXEC, "-u", conv_script,
            proc_temp_dir + "/", proc_temp_dir + "/",
            str(args.hlim), str(args.hstep),
            str(args.klim), str(args.kstep),
            str(args.llim), str(args.lstep)
        ]
        run_cmd(cmd_conv, f"1-Rotation HKL Conversion at {warmest_temp}K")
        pipeline_tracker.update_temp_step(processed_root, warmest_temp, "hkl_1rot", "COMPLETED")
    else:
        print(f"1-rotation volume already exists at {hkl1_file}. Skipping conversion.")

    # Step 4: Cross-Sectional Diagnostic Visualization
    vis_script = os.path.join(SCRIPT_DIR, "slice_visualizer.py")
    cmd_vis = [
        VIS_PYTHON, "-u", vis_script,
        "--nxs-file", hkl1_file,
        "--outdir", proc_temp_dir,
        "--hlim", str(args.hlim),
        "--klim", str(args.klim),
        "--llim", str(args.llim)
    ]
    run_cmd(cmd_vis, f"Generating Diagnostic Slices at {warmest_temp}K")

    print("\n=======================================================")
    print("FAST-PATH VERIFICATION RUN COMPLETE")
    print(f"Diagnostic Slices: {proc_temp_dir}/slices_summary.png")
    print(f"State: AWAITING USER VERIFICATION")
    print("=======================================================\n")
    pipeline_tracker.print_summary(processed_root)


def process_temperature(temp_str, args, raw_root, processed_root, spec_file, orm_source):
    """Process a single temperature dataset: stacking, copying verified ORM, HKL conversion, and slicing."""
    raw_temp_dir = os.path.join(raw_root, str(temp_str))
    proc_temp_dir = os.path.join(processed_root, str(temp_str))
    os.makedirs(proc_temp_dir, exist_ok=True)

    scan_folders = get_rotation_scan_folders(raw_temp_dir)
    if not scan_folders:
        print(f"Warning: No scan folders found in {raw_temp_dir}. Skipping.")
        return
    if len(scan_folders) > 3:
        raise RuntimeError(
            f"Anomalous scan count: found {len(scan_folders)} scans in {raw_temp_dir} ({scan_folders}). "
            f"Expected either 1 or 3 rotations. User clarification required before proceeding."
        )

    print(f"\n=======================================================")
    print(f"Processing Temperature: {temp_str} K ({len(scan_folders)} rotation scan(s))")
    print(f"=======================================================")

    # Ensure orientation matrix exists
    dest_orm = os.path.join(proc_temp_dir, "ormatrix_auto.nxs")
    if orm_source and os.path.exists(orm_source) and not os.path.exists(dest_orm):
        shutil.copy2(orm_source, dest_orm)
        print(f"Copied verified orientation matrix to {dest_orm}")
        npy_source = orm_source + ".npy"
        if os.path.exists(npy_source):
            shutil.copy2(npy_source, dest_orm + ".npy")

    unitcell_txt = os.path.join(proc_temp_dir, "unitcell.txt")
    if not os.path.exists(unitcell_txt):
        with open(unitcell_txt, "w") as f:
            f.write(f"{args.unit_cell}\n")

    # Stacking
    stacker_script = os.path.join(args.codebase, "stack_em_all.py")
    stacked_indices = []
    for rot_idx, scan_folder in enumerate(scan_folders, start=1):
        stack_file = os.path.join(proc_temp_dir, f"stack{rot_idx}.nxs")
        if not os.path.exists(stack_file) or args.force_stack:
            pipeline_tracker.update_temp_step(processed_root, temp_str, "stacking", "RUNNING")
            raw_scan_path = os.path.join(raw_temp_dir, scan_folder) + "/"
            proc_out_path = proc_temp_dir + "/"
            scan_num = scan_folder.split("_")[-1]
            cmd_stack = [
                PYTHON_EXEC, "-u", stacker_script,
                spec_file, args.calib_file, args.mask_file,
                args.sample, str(int(scan_num)), str(temp_str),
                raw_scan_path, proc_out_path
            ]
            run_cmd(cmd_stack, f"Stacking Rotation {rot_idx} ({scan_folder}) at {temp_str}K")
            stacked_indices.append(rot_idx)
        else:
            print(f"Stack {rot_idx} already exists at {stack_file}. Skipping stacking.")
            stacked_indices.append(rot_idx)
    pipeline_tracker.update_temp_step(processed_root, temp_str, "stacking", "COMPLETED", {"stacked": stacked_indices})

    # Reciprocal Space Conversion
    if len(scan_folders) == 1:
        hkl_file = os.path.join(proc_temp_dir, "1rot_hkli.nxs")
        step_name = "hkl_1rot"
        conv_script = os.path.join(args.codebase, "Pil6M_HKLConv_3D_2022_1rot.py")
    else:
        hkl_file = os.path.join(proc_temp_dir, "3rot_hkli.nxs")
        step_name = "hkl_3rot"
        conv_script = os.path.join(args.codebase, "Pil6M_HKLConv_3D_2022_3rot.py")

    if not os.path.exists(hkl_file) or args.force_hkl:
        pipeline_tracker.update_temp_step(processed_root, temp_str, step_name, "RUNNING")
        cmd_conv = [
            PYTHON_EXEC, "-u", conv_script,
            proc_temp_dir + "/", proc_temp_dir + "/",
            str(args.hlim), str(args.hstep),
            str(args.klim), str(args.kstep),
            str(args.llim), str(args.lstep)
        ]
        run_cmd(cmd_conv, f"{'1-Rotation' if len(scan_folders)==1 else '3-Rotation'} HKL Conversion at {temp_str}K")
        pipeline_tracker.update_temp_step(processed_root, temp_str, step_name, "COMPLETED")
    else:
        print(f"HKL reciprocal volume already exists at {hkl_file}. Skipping conversion.")

    # Cross-Sectional Diagnostic Visualization
    vis_script = os.path.join(SCRIPT_DIR, "slice_visualizer.py")
    cmd_vis = [
        VIS_PYTHON, "-u", vis_script,
        "--nxs-file", hkl_file,
        "--outdir", proc_temp_dir,
        "--hlim", str(args.hlim),
        "--klim", str(args.klim),
        "--llim", str(args.llim)
    ]
    run_cmd(cmd_vis, f"Generating Diagnostic Slices at {temp_str}K")


def run_batch(args):
    """Execute batch reduction across all sorted temperatures."""
    raw_root, processed_root, spec_file, _ = discover_paths(
        args.cycle, args.experiment, args.sample, args.sample_id
    )
    temperatures = get_sorted_temperatures(raw_root)
    ref_temp = str(args.ref_temp)
    orm_source = os.path.join(processed_root, ref_temp, "ormatrix_auto.nxs")
    if not os.path.exists(orm_source):
        raise FileNotFoundError(f"Reference orientation matrix not found at {orm_source}. Run fastpath first!")

    print(f"\n=======================================================")
    print(f"BATCH REDUCTION RUN: Sample {args.sample_id}")
    print(f"Total temperatures ({len(temperatures)}): {temperatures}")
    print(f"Using verified orientation matrix: {orm_source}")
    print(f"Grid limits: H=[-{args.hlim}, {args.hlim}], K=[-{args.klim}, {args.klim}], L=[-{args.llim}, {args.llim}]")
    print(f"=======================================================\n")

    for temp in temperatures:
        process_temperature(temp, args, raw_root, processed_root, spec_file, orm_source)

    print("\n=======================================================")
    print("ALL TEMPERATURES PROCESSED SUCCESSFULLY")
    print("=======================================================")
    pipeline_tracker.print_summary(processed_root)


def run_single(args):
    """Execute reduction for a single specified temperature."""
    if not args.temperature:
        raise ValueError("--temperature must be specified when mode is 'single'")
    raw_root, processed_root, spec_file, _ = discover_paths(
        args.cycle, args.experiment, args.sample, args.sample_id
    )
    ref_temp = str(args.ref_temp)
    orm_source = os.path.join(processed_root, ref_temp, "ormatrix_auto.nxs")
    if not os.path.exists(orm_source):
        raise FileNotFoundError(f"Reference orientation matrix not found at {orm_source}")
    process_temperature(str(args.temperature), args, raw_root, processed_root, spec_file, orm_source)
    pipeline_tracker.print_summary(processed_root)


def main():
    parser = argparse.ArgumentParser(description="Master CHESS Legacy Pipeline Orchestrator")
    parser.add_argument("--mode", choices=["fastpath", "batch", "single"], default="fastpath",
                        help="Execution mode: fastpath (reference T only), batch (all temperatures), or single (one T)")
    parser.add_argument("--temperature", default=None, help="Target temperature for single mode")
    parser.add_argument("--ref-temp", default="281", help="Reference temperature where ORM was verified")
    parser.add_argument("--cycle", default="2026-2", help="CHESS cycle (e.g. 2026-2)")
    parser.add_argument("--experiment", default="gomez-al-4850-a", help="Experiment name")
    parser.add_argument("--sample", required=True, help="Sample name (e.g. FeTe2)")
    parser.add_argument("--sample-id", required=True, help="Sample ID (e.g. FeTe2-5A)")
    parser.add_argument("--calib-file", required=True, help="Full path to .poni calibration file")
    parser.add_argument("--mask-file", required=True, help="Full path to .edf mask file")
    parser.add_argument("--unit-cell", required=True, help="Unit cell 'a,b,c,al,be,ga' or path to unitcell.txt/.cif")
    parser.add_argument("--codebase", default=DEFAULT_CODEBASE, help="Path to legacy codebase")

    # Grid limits (defaults reflect standard full-energy CHESS QM2 beamline range; override per experiment/energy)
    parser.add_argument("--hlim", type=float, default=5.1, help="Max H limit (default 5.1)")
    parser.add_argument("--hstep", type=float, default=0.01, help="H step size (default 0.01)")
    parser.add_argument("--klim", type=float, default=5.1, help="Max K limit (default 5.1)")
    parser.add_argument("--kstep", type=float, default=0.01, help="K step size (default 0.01)")
    parser.add_argument("--llim", type=float, default=9.1, help="Max L limit (default 9.1)")
    parser.add_argument("--lstep", type=float, default=0.02, help="L step size (default 0.02)")

    # Flags
    parser.add_argument("--force-stack", action="store_true", help="Re-run stacking even if stack1.nxs exists")
    parser.add_argument("--force-orm", action="store_true", help="Re-run ORM solver even if ormatrix_auto.nxs exists")
    parser.add_argument("--force-hkl", action="store_true", help="Re-run HKL conversion even if 1rot_hkli.nxs exists")

    args = parser.parse_args()

    if args.mode == "fastpath":
        run_fastpath(args)
    elif args.mode == "batch":
        run_batch(args)
    elif args.mode == "single":
        run_single(args)


if __name__ == "__main__":
    main()
