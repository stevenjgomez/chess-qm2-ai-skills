#!/usr/bin/env python3
"""
generate_xtec_input.py - Automated 4D NeXus Input Generation for XTEC-GPU

Compiles a temperature series of 3D reciprocal-space datasets (NeXus format)
into a single 4D NXdata group with temperature along Axis 0 (e.g. 'Te' in K)
and reciprocal lattice coordinates along Axes 1-3 (e.g. Qh, Qk, Ql or H, K, L).

Supports both:
1. NXRefine datasets: Top-level '*_<temp>.nxs' wrapper files linked to '<temp>/transform.nxs'.
2. Legacy CHESS datasets: Subdirectories named '<temp>/' containing '*1rot_hkli.nxs',
   '*3rot_hkli.nxs', or '*hkli.nxs'.

Strictly enforces CLASSE data protection policies: existing .nxs files will NOT
be overwritten unless explicitly commanded with --force.

Target Environment:
  Host: Interactive CPU Node (via qrsh -q interactive.q -l mem_free=350G from lnx201)
  Python: /nfs/chess/sw/anaconda3_sgomezalvarado_nightly/bin/python
"""

import argparse
import os
import re
import sys
import numpy as np


def detect_legacy_file_ending(sample_dir):
    """
    Auto-detect the most appropriate file ending pattern for legacy CHESS datasets.
    Prioritizes 3-rotation reconstructions, then 1-rotation, then generic hkli/transform.
    Handles automatic integer suffixing (e.g. 1rot_hkli_1.nxs, 3rot_hkli_2.nxs)
    by selecting the highest suffix present.
    """
    pattern = re.compile(r".*?(3rot_hkli|1rot_hkli|hkli|transform)(?:_(\d+))?\.nxs$")
    priority = {"3rot_hkli": 3, "1rot_hkli": 2, "hkli": 1, "transform": 0}
    found_matches = []

    for item in os.listdir(sample_dir):
        item_path = os.path.join(sample_dir, item)
        if os.path.isdir(item_path):
            try:
                for f in os.listdir(item_path):
                    m = pattern.match(f)
                    if m:
                        rtype = m.group(1)
                        suffix_str = m.group(2)
                        suffix_int = int(suffix_str) if suffix_str is not None else 0
                        ending = f"{rtype}_{suffix_str}.nxs" if suffix_str is not None else f"{rtype}.nxs"
                        found_matches.append((priority[rtype], suffix_int, ending))
            except OSError:
                continue

    if not found_matches:
        return "hkli.nxs"

    # Sort descending by priority, then suffix number
    found_matches.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return found_matches[0][2]


def parse_temperature_list(temp_str):
    """Parse comma- or space-separated temperature string into a list of floats/ints."""
    if not temp_str:
        return None
    raw_tokens = re.split(r"[,\s]+", temp_str.strip())
    temps = []
    for token in raw_tokens:
        if not token:
            continue
        token_clean = token.replace("p", ".")
        try:
            val = float(token_clean)
            temps.append(int(val) if val.is_integer() else val)
        except ValueError:
            print(f"Warning: Could not parse '{token}' as a valid temperature. Skipping.")
    return temps if temps else None


def main():
    parser = argparse.ArgumentParser(
        description="Compile a temperature series of 3D reciprocal-space volumes into a 4D XTEC input NeXus file."
    )
    parser.add_argument(
        "--sample-dir",
        "-s",
        required=True,
        help="Path to the sample directory containing temperature datasets.",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output .nxs filepath. Defaults to '<sample-dir>/xtec_data.nxs'.",
    )
    parser.add_argument(
        "--file-ending",
        "-e",
        default=None,
        help="File ending pattern for legacy CHESS folders (e.g. '1rot_hkli.nxs', '3rot_hkli.nxs'). Auto-detected if omitted.",
    )
    parser.add_argument(
        "--temperatures",
        "-t",
        default=None,
        help="Comma- or space-separated list of temperatures to include (e.g. '111,116,281' or '100 200 300').",
    )
    parser.add_argument(
        "--exclude-temperatures",
        "-x",
        default=None,
        help="Comma- or space-separated list of temperatures to exclude.",
    )
    parser.add_argument(
        "--temp-axis",
        default="Te",
        help="Axis name for the temperature dimension (default: 'Te').",
    )
    parser.add_argument(
        "--temp-units",
        default="K",
        help="Units attribute for the temperature axis (default: 'K').",
    )
    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Allow overwriting output file if it already exists (use with caution).",
    )

    args = parser.parse_args()

    sample_dir = os.path.abspath(args.sample_dir)
    if not os.path.isdir(sample_dir):
        print(f"Error: Sample directory not found: {sample_dir}", file=sys.stderr)
        sys.exit(1)

    output_path = args.output
    if output_path is None:
        output_path = os.path.join(sample_dir, "xtec_data.nxs")
    output_path = os.path.abspath(output_path)

    # Enforce data protection policy
    if os.path.exists(output_path) and not args.force:
        print(
            f"Error: Output file already exists: {output_path}\n"
            "By CLASSE data safety policy, existing .nxs files will not be overwritten automatically.\n"
            "To proceed, specify a distinct output path with -o or pass --force if an explicit re-creation is required.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Import nxs_analysis_tools
    try:
        from nxs_analysis_tools.chess import TempDependence
        import nexusformat.nexus as nx
    except ImportError as e:
        print(
            f"Error importing nxs_analysis_tools or nexusformat: {e}\n"
            "Ensure you are running in '/nfs/chess/sw/anaconda3_sgomezalvarado_nightly/bin/python'.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Initialize TempDependence
    print(f"[XTEC Prep] Initializing TempDependence for sample: {sample_dir}")
    td = TempDependence(sample_dir)
    td.find_temperatures()

    if not td.temperatures:
        print(f"Error: No valid temperature datasets found in {sample_dir}", file=sys.stderr)
        sys.exit(1)

    include_temps = parse_temperature_list(args.temperatures)
    exclude_temps = parse_temperature_list(args.exclude_temperatures)

    # Resolve format type
    file_ending = args.file_ending
    format_type = td._detect_format()
    print(f"[XTEC Prep] Detected dataset layout format: '{format_type}'")

    if format_type == "chess":
        if file_ending is None:
            file_ending = detect_legacy_file_ending(sample_dir)
            print(f"[XTEC Prep] Auto-detected legacy file ending pattern: '{file_ending}'")
        else:
            print(f"[XTEC Prep] Using specified legacy file ending pattern: '{file_ending}'")

    # Load datasets
    print("[XTEC Prep] Loading temperature datasets (pre-validating completeness)...")
    if format_type == "chess":
        td.load_datasets(
            temperatures=include_temps,
            exclude_temperatures=exclude_temps,
            file_ending=file_ending,
            print_tree=False,
        )
    else:
        td.load_datasets(
            temperatures=include_temps,
            exclude_temperatures=exclude_temps,
            use_nxlink=True,
            print_tree=False,
        )

    valid_temps = list(td.datasets.keys())
    if len(valid_temps) < 2:
        print(
            f"Error: XTEC requires at least 2 temperature points for clustering. Found {len(valid_temps)}: {valid_temps}",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"[XTEC Prep] Successfully loaded {len(valid_temps)} datasets: {valid_temps} K")

    # Export to XTEC format via to_xtec
    print(f"[XTEC Prep] Compiling 4D NXdata volume and writing to: {output_path}")
    xtec_data = td.to_xtec(
        filepath=output_path,
        temp_axis_name=args.temp_axis,
        temp_units=args.temp_units,
        overwrite=args.force,
    )

    # Verification
    if not os.path.isfile(output_path):
        print(f"Error: Expected output file was not created: {output_path}", file=sys.stderr)
        sys.exit(1)

    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    sig_shape = xtec_data.nxsignal.shape
    axis_names = [ax.nxname for ax in xtec_data.nxaxes]

    print("\n" + "=" * 60)
    print(" [XTEC Prep] 4D NeXus Dataset Successfully Generated!")
    print("=" * 60)
    print(f" Output File : {output_path} ({file_size_mb:.2f} MB)")
    print(f" Signal Shape: {sig_shape} [T, Q1, Q2, Q3]")
    print(f" Coordinate Axes: {axis_names}")
    print(f" Temperatures: {len(valid_temps)} points ({min(valid_temps)} K -> {max(valid_temps)} K)")
    print(" Ready for GPU execution on lnx4428.")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
