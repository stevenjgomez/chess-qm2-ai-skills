#!/usr/bin/env python3
"""
temp_order_parameter.py: Multi-temperature peak fitting and order parameter curve generation.
Uses nxs_analysis_tools.chess.TempDependence and lmfit models.
"""

import os
import sys
import argparse
import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    from nxs_analysis_tools.chess import TempDependence
except ImportError:
    TempDependence = None

try:
    from lmfit.models import GaussianModel, LinearModel, LorentzianModel
except ImportError:
    GaussianModel = None


def parse_tuple(s, expected_len=3):
    parts = [float(x.strip()) for x in s.replace(";", ",").split(",") if x.strip()]
    if len(parts) != expected_len:
        raise ValueError(f"Expected {expected_len} values in '{s}', got {len(parts)}")
    return tuple(parts)


def run_order_parameter_fit(sample_dir, file_ending, cut_axis, center_str, window_str, param_name, out_png, model_type="gaussian"):
    if TempDependence is None:
        raise ImportError("nxs_analysis_tools.chess.TempDependence is required to run temp_order_parameter.py")
    if GaussianModel is None:
        raise ImportError("lmfit is required for peak fitting. Please execute in an environment with lmfit installed.")

    td = TempDependence(sample_dir)
    td.find_temperatures()
    if not td.temperatures:
        raise ValueError(f"No temperatures found in {sample_dir}")

    td.load_datasets(file_ending=file_ending, print_tree=False)

    center = parse_tuple(center_str, 3)
    window = parse_tuple(window_str, 3)
    td.set_center(center)
    td.set_window(window)

    axis_map = {"H": 0, "K": 1, "L": 2}
    cut_axis = cut_axis.upper()
    axis_idx = axis_map[cut_axis]

    print(f"Cutting data along {cut_axis} through center {center}...")
    td.cut_data(axis=axis_idx, verbose=False)

    print(f"Configuring {model_type} model + linear background...")
    if model_type.lower() == "lorentzian":
        peak = LorentzianModel(prefix="peak_")
    else:
        peak = GaussianModel(prefix="peak_")
    bg = LinearModel(prefix="bg_")
    model = peak + bg

    td.set_model_components(model)
    td.guess()
    print("Fitting peak across all temperatures...")
    td.fit(verbose=False)

    # Plot order parameter
    fig, ax = plt.subplots(figsize=(6, 4.5), dpi=200)
    td.plot_order_parameter(param_name=param_name, ax=ax, marker="o", color="crimson")
    ax.set_xlabel("Temperature (K)", fontsize=11)
    ax.set_ylabel(f"Fitted {param_name.capitalize()}", fontsize=11)
    ax.set_title(f"Order Parameter: {param_name} vs Temperature\nCenter={center}", fontsize=11)
    ax.grid(True, linestyle="--", alpha=0.5)

    os.makedirs(os.path.dirname(os.path.abspath(out_png)), exist_ok=True)
    plt.tight_layout()
    plt.savefig(out_png, dpi=300)
    plt.close(fig)
    print(f"Saved order parameter figure: {out_png}")


def main():
    parser = argparse.ArgumentParser(description="Fit reflection across temperatures and extract order parameter.")
    parser.add_argument("--sample-dir", "-s", required=True, help="Path to sample root containing temperature subdirectories")
    parser.add_argument("--file-ending", "-e", default="3rot_hkli_lite.nxs", help="NeXus file pattern (default: 3rot_hkli_lite.nxs)")
    parser.add_argument("--axis", required=True, choices=["H", "K", "L"], help="Direction of 1D cut")
    parser.add_argument("--center", required=True, help="Center coordinate tuple: 'c0, c1, c2'")
    parser.add_argument("--window", required=True, help="Window size tuple: 'w0, w1, w2'")
    parser.add_argument("--param", default="peakheight", choices=["peakheight", "area", "sigma", "center"], help="Fit parameter to plot (default: peakheight)")
    parser.add_argument("--model", default="gaussian", choices=["gaussian", "lorentzian"], help="Peak model function")
    parser.add_argument("--output", "-o", required=True, help="Output PNG path")

    args = parser.parse_args()
    run_order_parameter_fit(
        sample_dir=args.sample_dir,
        file_ending=args.file_ending,
        cut_axis=args.axis,
        center_str=args.center,
        window_str=args.window,
        param_name=args.param,
        out_png=args.output,
        model_type=args.model,
    )


if __name__ == "__main__":
    main()
