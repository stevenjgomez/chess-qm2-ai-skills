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

Features:
- Dual exposure extraction engine: reads count time from NeXus wrapper files (entry/logs/T)
  and parses raw SPEC data files (#C Temperature Setpoint at, #S, #T).
- Modal exposure filtering: automatically excludes scans with disparate exposure times
  (e.g. parent orientation scans or test runs) that would distort clustering statistics.
- Pre-validation of incomplete stubs: verifies transform.nxs exists and has non-zero size,
  preventing broken NXlink reads.
- Formatted pre-compilation audit table detailing candidate status and parameters.
- Strict data safety enforcement: existing .nxs files will NOT be overwritten unless --force is given.

Target Environment:
  Host: Interactive CPU Node (via qrsh -q interactive.q -l mem_free=350G from lnx201)
        or non-interactive batch job (via qsub with SGE wrapper)
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


def find_spec_file(sample_dir):
    """
    Attempt to auto-discover the SPEC data file associated with this sample directory.
    Supports standard CHESS hierarchy:
      sample_dir: /nfs/chess/id4baux/{cycle}/{experiment}/nxrefine/{sample}/{subsample}
      raw SPEC:   /nfs/chess/id4b/{cycle}/{experiment}/{sample}
    """
    norm_path = os.path.abspath(sample_dir)
    if "id4baux" not in norm_path:
        return None

    raw_base = norm_path.replace("id4baux", "id4b")
    parts = raw_base.split(os.sep)
    try:
        id4b_idx = parts.index("id4b")
        if len(parts) >= id4b_idx + 3:
            exp_raw_dir = os.sep + os.path.join(*parts[: id4b_idx + 3])
            if os.path.isdir(exp_raw_dir):
                remaining = parts[id4b_idx + 3 :]
                # Test each token in the path hierarchy
                for candidate in remaining:
                    if candidate in ("nxrefine", "processed_old_way"):
                        continue
                    spec_candidate = os.path.join(exp_raw_dir, candidate)
                    if os.path.isfile(spec_candidate):
                        return spec_candidate
                # Secondary fuzzy match against files in the experiment raw folder
                for f in os.listdir(exp_raw_dir):
                    f_path = os.path.join(exp_raw_dir, f)
                    if os.path.isfile(f_path):
                        for c in remaining:
                            if c.lower() == f.lower() or f.lower() in c.lower():
                                return f_path
    except (ValueError, IndexError, OSError):
        pass
    return None


def parse_spec_file(spec_path):
    """
    Parse a SPEC file to extract scan numbers, exposure times (#T),
    and temperature setpoints.
    Returns: dict mapping temperature (float/int) -> list of dicts:
      {'scan': int, 'time': float, 'cmd': str}
    """
    if not spec_path or not os.path.isfile(spec_path):
        return {}

    temp_map = {}
    current_temp = None
    current_scan = None
    current_cmd = None

    try:
        with open(spec_path, "r", errors="ignore") as f:
            for line in f:
                line_str = line.strip()
                if "Temperature Setpoint at" in line_str:
                    m = re.search(r"Temperature Setpoint at\s+([\d.]+)", line_str)
                    if m:
                        val = float(m.group(1))
                        current_temp = int(val) if val.is_integer() else val
                elif line_str.startswith("#S"):
                    parts = line_str.split(None, 2)
                    if len(parts) >= 2:
                        try:
                            current_scan = int(parts[1])
                            current_cmd = parts[2] if len(parts) > 2 else ""
                        except ValueError:
                            current_scan = None
                elif line_str.startswith("#T") and current_temp is not None:
                    parts = line_str.split()
                    if len(parts) >= 2:
                        try:
                            t_val = float(parts[1])
                            if current_temp not in temp_map:
                                temp_map[current_temp] = []
                            temp_map[current_temp].append({
                                "scan": current_scan,
                                "time": t_val,
                                "cmd": current_cmd or "",
                            })
                        except ValueError:
                            pass
    except OSError as e:
        print(f"Warning: Could not read SPEC file '{spec_path}': {e}", file=sys.stderr)

    return temp_map


def extract_nexus_exposure(wrapper_path):
    """
    Extract count time (#T) and scan command from NXRefine wrapper file via h5py.
    Returns: (exposure_time, frame_time, command_str) or (None, None, None).
    """
    try:
        import h5py
        with h5py.File(wrapper_path, "r") as f:
            entries = [k for k in f.keys() if k.startswith("f")]
            if not entries:
                entries = list(f.keys())
            for e in entries:
                if not isinstance(f[e], h5py.Group):
                    continue
                exp_t = None
                frame_t = None
                cmd_str = None

                if "logs/T" in f[e]:
                    exp_t = float(f[e]["logs/T"][()])
                if "logs/command" in f[e]:
                    cmd_val = f[e]["logs/command"][()]
                    cmd_str = cmd_val.decode("utf-8") if isinstance(cmd_val, bytes) else str(cmd_val)
                    m = re.search(r"flyscan\s+\S+\s+[\d.]+\s+[\d.]+\s+\d+\s+([\d.]+)", cmd_str)
                    if m:
                        try:
                            frame_t = float(m.group(1))
                        except ValueError:
                            pass
                if "instrument/detector/frame_time" in f[e]:
                    det_ft = float(f[e]["instrument/detector/frame_time"][()])
                    if frame_t is None:
                        frame_t = det_ft

                if exp_t is not None or frame_t is not None:
                    return exp_t, frame_t, cmd_str
    except Exception:
        pass
    return None, None, None


def calculate_modal_exposure(exposure_dict, tolerance=0.01):
    """
    Calculate the statistical mode (most common value) among positive exposure times,
    grouping values within relative tolerance (default 1%).
    Returns: (modal_value, count, total_valid)
    """
    valid_exposures = [v for v in exposure_dict.values() if v is not None and v > 0]
    if not valid_exposures:
        return None, 0, 0

    clusters = []  # list of (representative_val, [values])
    for val in valid_exposures:
        matched = False
        for rep, group in clusters:
            if abs(val - rep) / max(rep, 1e-6) <= tolerance:
                group.append(val)
                matched = True
                break
        if not matched:
            clusters.append((val, [val]))

    clusters.sort(key=lambda c: len(c[1]), reverse=True)
    modal_rep = clusters[0][0]
    modal_count = len(clusters[0][1])
    return modal_rep, modal_count, len(valid_exposures)


def audit_and_filter_candidates(
    sample_dir,
    format_type,
    file_ending=None,
    include_temps=None,
    exclude_temps=None,
    spec_path=None,
    allow_mixed_exposures=False,
    exposure_tolerance=0.01,
):
    """
    Perform pre-validation and exposure audit across all candidate temperature datasets.
    Validates that:
    1. Transform/count files exist and are non-empty (>0 bytes).
    2. Datasets adhere to the modal exposure time (unless allow_mixed_exposures=True).

    Returns:
      retained_temps: list of validated temperatures to load
      audit_records: list of dicts for summary printing
    """
    candidates = {}  # temp -> dict of metadata
    pattern_nx = re.compile(r".*?_(\d+(?:[p.]\d+)?)\.nxs$")

    # Parse SPEC file if available
    spec_data = parse_spec_file(spec_path) if spec_path else {}

    if format_type == "nxrefine":
        for item in os.listdir(sample_dir):
            item_path = os.path.join(sample_dir, item)
            if os.path.isfile(item_path):
                m = pattern_nx.match(item)
                if m:
                    token = m.group(1).replace("p", ".")
                    try:
                        val = float(token)
                        t = int(val) if val.is_integer() else val
                    except ValueError:
                        continue

                    # Check transform.nxs existence and size
                    folder_str = str(t)
                    transform_path = os.path.join(sample_dir, folder_str, "transform.nxs")
                    has_transform = os.path.isfile(transform_path) and os.path.getsize(transform_path) > 0
                    t_size_gb = (
                        os.path.getsize(transform_path) / (1024**3)
                        if has_transform
                        else 0.0
                    )

                    # Extract exposure
                    exp_t, frame_t, cmd = extract_nexus_exposure(item_path)
                    if exp_t is None and t in spec_data:
                        exp_t = spec_data[t][-1]["time"]
                        cmd = spec_data[t][-1]["cmd"]

                    candidates[t] = {
                        "type": "nxrefine",
                        "wrapper": item,
                        "valid_stub": has_transform,
                        "size_gb": t_size_gb,
                        "exposure_t": exp_t,
                        "frame_t": frame_t,
                        "cmd": cmd,
                    }

    elif format_type == "chess":
        for item in os.listdir(sample_dir):
            item_path = os.path.join(sample_dir, item)
            if os.path.isdir(item_path):
                token = item.replace("p", ".")
                try:
                    val = float(token)
                    t = int(val) if val.is_integer() else val
                except ValueError:
                    continue

                # Search for target file ending
                target_file = None
                size_gb = 0.0
                try:
                    for f in os.listdir(item_path):
                        if f.endswith(file_ending):
                            fp = os.path.join(item_path, f)
                            if os.path.isfile(fp) and os.path.getsize(fp) > 0:
                                target_file = f
                                size_gb = os.path.getsize(fp) / (1024**3)
                                break
                except OSError:
                    pass

                exp_t = None
                cmd = None
                if t in spec_data:
                    exp_t = spec_data[t][-1]["time"]
                    cmd = spec_data[t][-1]["cmd"]

                candidates[t] = {
                    "type": "chess",
                    "wrapper": target_file,
                    "valid_stub": target_file is not None,
                    "size_gb": size_gb,
                    "exposure_t": exp_t,
                    "frame_t": None,
                    "cmd": cmd,
                }

    sorted_temps = sorted(candidates.keys(), key=float)

    # Compute modal exposure among valid candidate stubs
    valid_exposures = {
        t: info["exposure_t"]
        for t, info in candidates.items()
        if info["valid_stub"] and info["exposure_t"] is not None
    }
    modal_exp, modal_cnt, total_cnt = calculate_modal_exposure(
        valid_exposures, tolerance=exposure_tolerance
    )

    audit_records = []
    retained_temps = []

    for t in sorted_temps:
        info = candidates[t]
        status = "INCLUDED"
        details = "Ready for compilation"

        # 1. User manual inclusion/exclusion filters
        if include_temps is not None and t not in include_temps:
            status = "EXCLUDED"
            details = "Omitted by --temperatures filter"
        elif exclude_temps is not None and t in exclude_temps:
            status = "EXCLUDED"
            details = "Explicitly excluded via --exclude-temperatures"
        # 2. Stub validity
        elif not info["valid_stub"]:
            status = "SKIPPED"
            details = (
                "Incomplete stub: missing/empty transform.nxs"
                if info["type"] == "nxrefine"
                else f"Missing {file_ending}"
            )
        # 3. Exposure time check
        elif modal_exp is not None and info["exposure_t"] is not None:
            rel_diff = abs(info["exposure_t"] - modal_exp) / max(modal_exp, 1e-6)
            if rel_diff > exposure_tolerance:
                if not allow_mixed_exposures:
                    status = "EXCLUDED"
                    details = f"Exposure mismatch ({info['exposure_t']:.1f} s vs modal {modal_exp:.1f} s)"
                else:
                    details = f"Exposure mismatch permitted via --allow-mixed-exposures ({info['exposure_t']:.1f} s)"

        if status == "INCLUDED":
            retained_temps.append(t)

        audit_records.append({
            "temp": t,
            "status": status,
            "size_gb": info["size_gb"],
            "exposure_t": info["exposure_t"],
            "details": details,
        })

    return retained_temps, audit_records, modal_exp


def print_audit_table(audit_records, modal_exp, sample_dir):
    """Print a structured ASCII summary table of candidate datasets."""
    print("\n" + "=" * 92)
    print(" [XTEC Prep] Dataset Pre-Validation & Exposure Audit")
    print(f" Sample Directory: {sample_dir}")
    if modal_exp is not None:
        print(f" Modal Exposure Time Detected: {modal_exp:.2f} s")
    else:
        print(" Modal Exposure Time: Not determined (insufficient metadata)")
    print("=" * 92)
    print(
        f" {'Temp (K)':>8} | {'Status':^10} | {'Volume Size':^13} | {'Count Time (s)':^14} | {'Details'}"
    )
    print("-" * 92)

    n_inc = 0
    n_skip = 0
    n_exc = 0

    for r in audit_records:
        t_str = f"{r['temp']} K"
        stat_str = f"[{r['status']}]"
        size_str = f"{r['size_gb']:.2f} GB" if r["size_gb"] > 0 else "--"
        exp_str = f"{r['exposure_t']:.1f} s" if r["exposure_t"] is not None else "--"

        if r["status"] == "INCLUDED":
            n_inc += 1
        elif r["status"] == "SKIPPED":
            n_skip += 1
        else:
            n_exc += 1

        print(
            f" {t_str:>8} | {stat_str:<10} | {size_str:>13} | {exp_str:>14} | {r['details']}"
        )

    print("=" * 92)
    print(
        f" Audit Summary: Total: {len(audit_records)} | Included: {n_inc} | Excluded: {n_exc} | Skipped Stubs: {n_skip}"
    )
    print("=" * 92 + "\n")


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
        "--spec-file",
        default=None,
        help="Path to the SPEC data file. Auto-discovered under /nfs/chess/id4b/ if omitted.",
    )
    parser.add_argument(
        "--allow-mixed-exposures",
        action="store_true",
        help="Disable automatic exclusion of runs with exposure times deviating from the modal value.",
    )
    parser.add_argument(
        "--exposure-tolerance",
        type=float,
        default=0.01,
        help="Relative tolerance for exposure time matching (default: 0.01 = 1%%).",
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
        print(f"Error: No temperature datasets found in {sample_dir}", file=sys.stderr)
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

    # Locate SPEC file (explicit or auto-discovered)
    spec_file = args.spec_file
    if spec_file is None:
        spec_file = find_spec_file(sample_dir)
        if spec_file:
            print(f"[XTEC Prep] Auto-discovered SPEC data file: '{spec_file}'")
    else:
        print(f"[XTEC Prep] Using specified SPEC data file: '{spec_file}'")

    # Perform pre-validation and exposure audit
    print("[XTEC Prep] Performing stub pre-validation and exposure time audit...")
    retained_temps, audit_records, modal_exp = audit_and_filter_candidates(
        sample_dir=sample_dir,
        format_type=format_type,
        file_ending=file_ending,
        include_temps=include_temps,
        exclude_temps=exclude_temps,
        spec_path=spec_file,
        allow_mixed_exposures=args.allow_mixed_exposures,
        exposure_tolerance=args.exposure_tolerance,
    )

    # Print the formatted audit table
    print_audit_table(audit_records, modal_exp, sample_dir)

    if len(retained_temps) < 2:
        print(
            f"Error: XTEC requires at least 2 valid temperature points with uniform exposure for clustering.\n"
            f"Only {len(retained_temps)} dataset(s) met criteria: {retained_temps}.\n"
            "If mixed exposures are intentional, pass --allow-mixed-exposures.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Load validated datasets into TempDependence
    print(f"[XTEC Prep] Loading {len(retained_temps)} validated temperature datasets...")
    if format_type == "chess":
        td.load_datasets(
            temperatures=retained_temps,
            file_ending=file_ending,
            print_tree=False,
        )
    else:
        td.load_datasets(
            temperatures=retained_temps,
            use_nxlink=True,
            print_tree=False,
        )

    loaded_temps = list(td.datasets.keys())
    print(f"[XTEC Prep] Successfully loaded {len(loaded_temps)} datasets: {loaded_temps} K")

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
    print(f" Output File    : {output_path} ({file_size_mb:.2f} MB)")
    print(f" Signal Shape   : {sig_shape} [T, Q1, Q2, Q3]")
    print(f" Coordinate Axes: {axis_names}")
    print(f" Temperatures   : {len(loaded_temps)} points ({min(loaded_temps)} K -> {max(loaded_temps)} K)")
    if modal_exp is not None:
        print(f" Exposure Time  : {modal_exp:.2f} s uniform")
    print(" Ready for GPU execution on lnx4428.")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
