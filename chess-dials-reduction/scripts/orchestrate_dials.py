#!/usr/bin/env python3
"""
orchestrate_dials.py: Unified orchestrator for CHESS ID4B/QM2 DIALS data reduction.
Supports Stage 1 (Fast / Pilot: Import -> Mask -> Find Spots -> Index -> Bravais Evaluation)
and Stage 2 (Heavy Compute: Refine -> Integrate -> Symmetrize -> Scale -> Dual SHELX Export).

Author: Steven Gomez-Alvarado / CHESS Data Reduction Skills
"""

import argparse
import glob
import os
import shutil
import subprocess
import sys


def run_cmd(cmd, cwd=None, log_file=None):
    """Execute a shell command with real-time output and error handling."""
    print(f"\n[RUNNING]: {cmd}")
    if cwd:
        print(f"[WORKING DIR]: {cwd}")

    stdout_dest = subprocess.PIPE
    stderr_dest = subprocess.STDOUT

    process = subprocess.Popen(
        cmd,
        shell=True,
        cwd=cwd,
        stdout=stdout_dest,
        stderr=stderr_dest,
        universal_newlines=True,
        bufsize=1
    )

    log_handle = open(log_file, "a") if log_file else None

    output_lines = []
    for line in iter(process.stdout.readline, ""):
        print(line, end="")
        output_lines.append(line)
        if log_handle:
            log_handle.write(line)
            log_handle.flush()

    process.stdout.close()
    return_code = process.wait()
    if log_handle:
        log_handle.close()

    if return_code != 0:
        raise RuntimeError(f"Command failed with exit code {return_code}: {cmd}")

    return "".join(output_lines)


def stage_1(args):
    """Execute Stage 1: Import, Masking, Find Spots, Index, and Bravais Settings."""
    work_dir = os.path.abspath(args.work_dir)
    os.makedirs(work_dir, exist_ok=True)
    dials_env = f"source {args.dials_env}"

    print("=================================================================")
    print("=== DIALS Reduction Pipeline: Stage 1 (Interactive Verification) ===")
    print(f"Working Directory: {work_dir}")
    print("=================================================================")

    # 1. Discover raw scan folders / CBF files
    cbf_inputs = []
    if args.raw_dir:
        raw_dir = os.path.abspath(args.raw_dir)
        # Check if raw_dir has subdirectories (multiple scans) or direct CBFs
        subdirs = sorted([d for d in glob.glob(os.path.join(raw_dir, "*")) if os.path.isdir(d)])
        if subdirs:
            print(f"Found {len(subdirs)} scan directories in {raw_dir}:")
            for sd in subdirs:
                print(f"  - {os.path.basename(sd)}")
                cbf_inputs.append(f"{sd}/*.cbf")
        else:
            cbf_inputs.append(f"{raw_dir}/*.cbf")
    elif args.cbf_pattern:
        cbf_inputs = [args.cbf_pattern]
    else:
        raise ValueError("Must provide either --raw-dir or --cbf-pattern.")

    input_str = " ".join(cbf_inputs)

    # 1. dials.import
    import_cmd = f"{dials_env} && dials.import {input_str} geometry.goniometer.axes={args.goniometer_axes}"
    run_cmd(import_cmd, cwd=work_dir)

    # 2. Mask generation
    mask_file = os.path.join(work_dir, "pixels.mask")
    gen_mask_cmd = f"{dials_env} && dials.generate_mask imported.expt output.mask={mask_file}"
    run_cmd(gen_mask_cmd, cwd=work_dir)

    if args.edf_mask and os.path.exists(args.edf_mask):
        print(f"Combining with beamline calibration EDF mask: {args.edf_mask}")
        script_dir = os.path.dirname(os.path.abspath(__file__))
        combine_cmd = (
            f"{dials_env} && dials.python {os.path.join(script_dir, 'mask_to_dials.py')} "
            f"--edf {args.edf_mask} --out {mask_file} --combine-with {mask_file}"
        )
        run_cmd(combine_cmd, cwd=work_dir)

    # 3. Create or verify find_spots.phil
    phil_path = os.path.join(work_dir, "find_spots.phil")
    if not os.path.exists(phil_path):
        print(f"Writing default calibrated spotfinder PHIL: {phil_path}")
        with open(phil_path, "w") as f:
            f.write(f"""spotfinder {{
  threshold {{
    dispersion {{
      gain = {args.gain}
      global_threshold = {args.global_threshold}
    }}
  }}
}}
""")

    # 4. dials.find_spots
    find_spots_cmd = (
        f"{dials_env} && dials.find_spots {phil_path} imported.expt "
        f"mask={mask_file} spotfinder.filter.d_min={args.d_min}"
    )
    run_cmd(find_spots_cmd, cwd=work_dir)

    # 5. dials.index
    index_args = ["imported.expt", "strong.refl"]
    if args.unit_cell and args.space_group:
        index_args.append(f'indexing.known_symmetry.unit_cell="{args.unit_cell}"')
        index_args.append(f'indexing.known_symmetry.space_group="{args.space_group}"')
    index_cmd = f"{dials_env} && dials.index {' '.join(index_args)}"
    run_cmd(index_cmd, cwd=work_dir)

    # 6. dials.refine_bravais_settings
    bravais_cmd = f"{dials_env} && dials.refine_bravais_settings indexed.expt indexed.refl"
    run_cmd(bravais_cmd, cwd=work_dir)

    # 7. Evaluate Bravais settings using bravais_matcher.py
    script_dir = os.path.dirname(os.path.abspath(__file__))
    matcher_cmd = f"python3 {os.path.join(script_dir, 'bravais_matcher.py')} --log dials.refine_bravais_settings.log"
    if args.unit_cell:
        matcher_cmd += f' --target-cell "{args.unit_cell}"'
    if args.space_group:
        matcher_cmd += f' --target-lattice "{args.space_group}"'
    run_cmd(matcher_cmd, cwd=work_dir)

    print("\n=================================================================")
    print("=== Stage 1 Complete. Review Bravais settings above before Stage 2 ===")
    print("=================================================================\n")


def stage_2(args):
    """Execute Stage 2: Refine, Integrate, Symmetrize, Scale, and Dual Export."""
    work_dir = os.path.abspath(args.work_dir)
    dials_env = f"source {args.dials_env}"

    print("=================================================================")
    print("=== DIALS Reduction Pipeline: Stage 2 (Integration & Export) ===")
    print(f"Working Directory: {work_dir}")
    print("=================================================================")

    # 1. Re-indexing (if change of basis is required)
    refl_file = "indexed.refl"
    if args.cb_op and args.cb_op != "a,b,c":
        print(f"Applying change of basis operator: {args.cb_op}")
        reindex_cmd = f"{dials_env} && dials.reindex indexed.refl change_of_basis_op={args.cb_op} output.reflections=reindexed.refl"
        run_cmd(reindex_cmd, cwd=work_dir)
        refl_file = "reindexed.refl"

    # Select target experiment file
    bravais_expt = f"bravais_setting_{args.bravais_setting}.expt"
    if not os.path.exists(os.path.join(work_dir, bravais_expt)):
        raise FileNotFoundError(f"Experiment file {bravais_expt} not found in {work_dir}")

    # 2. dials.refine
    refine_cmd = f"{dials_env} && dials.refine {bravais_expt} {refl_file}"
    run_cmd(refine_cmd, cwd=work_dir)

    # 3. dials.integrate
    integrate_cmd = f"{dials_env} && dials.integrate refined.expt refined.refl nproc={args.nproc}"
    run_cmd(integrate_cmd, cwd=work_dir)

    # 4. dials.symmetry
    symm_cmd = f"{dials_env} && dials.symmetry integrated.expt integrated.refl"
    run_cmd(symm_cmd, cwd=work_dir)

    # 5. dials.scale
    scale_cmd = (
        f"{dials_env} && dials.scale symmetrized.expt symmetrized.refl "
        f"overwrite_existing_models=True absorption_level={args.absorption_level} anomalous={args.anomalous}"
    )
    run_cmd(scale_cmd, cwd=work_dir)

    # 6. Dual Export: for_refinement bundle
    refinement_dir = os.path.join(work_dir, "for_refinement")
    os.makedirs(refinement_dir, exist_ok=True)

    print(f"\nExporting refinement reflection files to: {refinement_dir}")

    # A. Unmerged SHELX (for Jana2020)
    unmerged_cmd = (
        f"{dials_env} && dials.export scaled.expt scaled.refl "
        f"format=shelx composition={args.composition} shelx.scale=False output.reflections=unmerged.hkl output.experiment=unmerged.ins"
    )
    run_cmd(unmerged_cmd, cwd=work_dir)
    shutil.move(os.path.join(work_dir, "unmerged.hkl"), os.path.join(refinement_dir, "unmerged.hkl"))
    shutil.move(os.path.join(work_dir, "unmerged.ins"), os.path.join(refinement_dir, "unmerged.ins"))

    # B. Merged SHELX (for Olex2 / SHELXL)
    merge_cmd = f"{dials_env} && dials.merge scaled.expt scaled.refl output.html=None"
    run_cmd(merge_cmd, cwd=work_dir)

    merged_export_cmd = (
        f"{dials_env} && dials.export merged.expt merged.refl "
        f"format=shelx composition={args.composition} shelx.scale=False output.reflections=merged.hkl output.experiment=merged.ins"
    )
    run_cmd(merged_export_cmd, cwd=work_dir)
    shutil.move(os.path.join(work_dir, "merged.hkl"), os.path.join(refinement_dir, "merged.hkl"))
    shutil.move(os.path.join(work_dir, "merged.ins"), os.path.join(refinement_dir, "merged.ins"))

    print("\n=================================================================")
    print("=== Stage 2 Complete! Refinement files ready in for_refinement/ ===")
    print(f"  Jana2020 Target: {os.path.join(refinement_dir, 'unmerged.ins')}, unmerged.hkl")
    print(f"  Olex2 Target:    {os.path.join(refinement_dir, 'merged.ins')}, merged.hkl")
    print("=================================================================\n")


def main():
    parser = argparse.ArgumentParser(description="Unified CHESS DIALS Data Reduction Orchestrator.")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # Common parameters
    common_args = argparse.ArgumentParser(add_help=False)
    common_args.add_argument("--work-dir", required=True, help="Working directory for data reduction")
    common_args.add_argument(
        "--dials-env",
        default="/nfs/chess/sw/dials_sgomezalvarado/dials_env.sh",
        help="Path to dials_env.sh activation script"
    )

    # Subcommand: stage1
    p1 = subparsers.add_parser("stage1", parents=[common_args], help="Run Stage 1: Import, Spotfinding, Index, Bravais")
    p1.add_argument("--raw-dir", help="Path to raw scans directory (e.g. .../raw6M/sample/mount/temp/)")
    p1.add_argument("--cbf-pattern", help="Direct CBF glob pattern (e.g. '/path/to/*.cbf')")
    p1.add_argument("--goniometer-axes", default="0,-1,0", help="Rotation axis in laboratory frame (default: 0,-1,0)")
    p1.add_argument("--edf-mask", help="Path to beamline calibration EDF mask (e.g. mask_trans.edf)")
    p1.add_argument("--gain", type=float, default=1.0, help="Spotfinder detector gain")
    p1.add_argument("--global-threshold", type=int, default=5000, help="Spotfinder global intensity threshold")
    p1.add_argument("--d-min", type=float, default=0.75, help="High-resolution spotfinder filter cut-off in Angstroms")
    p1.add_argument("--unit-cell", help="Target unit cell: 'a b c alpha beta gamma'")
    p1.add_argument("--space-group", help="Target space group symbol (e.g. P6322)")

    # Subcommand: stage2
    p2 = subparsers.add_parser("stage2", parents=[common_args], help="Run Stage 2: Refine, Integrate, Scale, Export")
    p2.add_argument("--bravais-setting", type=int, required=True, help="Chosen Bravais setting number (e.g. 12)")
    p2.add_argument("--cb-op", default="a,b,c", help="Change of basis operator (e.g. -c,a,-b+c)")
    p2.add_argument("--nproc", type=int, default=32, help="Number of CPU cores for parallel integration")
    p2.add_argument("--absorption-level", default="high", choices=["low", "medium", "high"], help="DIALS scale absorption correction")
    p2.add_argument("--anomalous", default="True", choices=["True", "False"], help="Preserve anomalous Bijvoet pairs")
    p2.add_argument("--composition", default="FeTe2", help="Chemical formula for SHELX SFAC/UNIT generation (e.g. K2Co2TeO6)")

    args = parser.parse_args()

    if args.subcommand == "stage1":
        stage_1(args)
    elif args.subcommand == "stage2":
        stage_2(args)


if __name__ == "__main__":
    main()
