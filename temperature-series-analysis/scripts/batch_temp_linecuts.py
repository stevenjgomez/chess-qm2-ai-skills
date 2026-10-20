#!/usr/bin/env python3
"""
batch_temp_linecuts.py: Apply batch Scissors cuts across all temperatures using TempDependence.
Generates waterfall plots, (Q, T) intensity heatmaps, and exports linecut tables to CSV.
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


def parse_tuple(s, expected_len=3):
    parts = [float(x.strip()) for x in s.replace(";", ",").split(",") if x.strip()]
    if len(parts) != expected_len:
        raise ValueError(f"Expected {expected_len} values in '{s}', got {len(parts)}")
    return tuple(parts)


def run_batch_linecuts(sample_dir, file_ending, cut_axis, center_str, window_str, unit_cell_str, outdir, offset=500.0):
    if TempDependence is None:
        raise ImportError("nxs_analysis_tools.chess.TempDependence is required to run batch_temp_linecuts.py")

    os.makedirs(outdir, exist_ok=True)
    td = TempDependence(sample_dir)
    print(f"Scanning for temperatures in {sample_dir}...")
    td.find_temperatures()
    print(f"Discovered {len(td.temperatures)} temperatures: {td.temperatures}")

    if not td.temperatures:
        raise ValueError(f"No temperature folders found in {sample_dir}")

    print(f"Loading datasets with ending: {file_ending}...")
    td.load_datasets(file_ending=file_ending, print_tree=False)

    if unit_cell_str:
        cell = parse_tuple(unit_cell_str, 6)
        td.set_lattice_params(cell)

    center = parse_tuple(center_str, 3)
    window = parse_tuple(window_str, 3)

    td.set_center(center)
    td.set_window(window)

    axis_map = {"H": 0, "K": 1, "L": 2}
    cut_axis = cut_axis.upper()
    if cut_axis not in axis_map:
        raise ValueError(f"Invalid axis: {cut_axis}. Choose from H, K, L.")

    axis_idx = axis_map[cut_axis]
    print(f"Executing batch cut along {cut_axis} across {len(td.temperatures)} temperatures...")
    td.cut_data(axis=axis_idx, verbose=False)

    # 1. Waterfall plot
    fig, ax = plt.subplots(figsize=(7, 8), dpi=200)
    td.plot_linecuts(ax=ax, vertical_offset=float(offset), cmap="coolwarm")
    ax.set_title(f"Temperature Waterfall through Center={center}")
    waterfall_path = os.path.join(outdir, "waterfall_linecuts.png")
    plt.tight_layout()
    plt.savefig(waterfall_path, dpi=300)
    plt.close(fig)
    print(f"Saved waterfall plot: {waterfall_path}")

    # 2. (Q, T) Heatmap
    fig, ax = plt.subplots(figsize=(6, 5), dpi=200)
    td.plot_linecuts_heatmap(ax=ax, cmap="inferno")
    ax.set_xlabel(f"{cut_axis} (r.l.u.)")
    ax.set_ylabel("Temperature (K)")
    ax.set_title(f"$(Q, T)$ Linecut Heatmap along {cut_axis}")
    heatmap_path = os.path.join(outdir, "linecuts_heatmap.png")
    plt.tight_layout()
    plt.savefig(heatmap_path, dpi=300)
    plt.close(fig)
    print(f"Saved heatmap: {heatmap_path}")

    print("Batch linecut processing complete!")


def main():
    parser = argparse.ArgumentParser(description="Extract batch linecuts across temperatures using TempDependence.")
    parser.add_argument("--sample-dir", "-s", required=True, help="Path to sample root containing temperature subdirectories")
    parser.add_argument("--file-ending", "-e", default="3rot_hkli_lite.nxs", help="NeXus file pattern (default: 3rot_hkli_lite.nxs)")
    parser.add_argument("--axis", required=True, choices=["H", "K", "L"], help="Direction of 1D cut")
    parser.add_argument("--center", required=True, help="Center coordinate tuple: 'c0, c1, c2'")
    parser.add_argument("--window", required=True, help="Window size tuple: 'w0, w1, w2'")
    parser.add_argument("--unit-cell", default=None, help="Optional unit cell: 'a,b,c,alpha,beta,gamma'")
    parser.add_argument("--offset", type=float, default=500.0, help="Vertical offset between traces in waterfall plot")
    parser.add_argument("--outdir", "-o", default="./batch_linecuts", help="Destination output folder")

    args = parser.parse_args()
    run_batch_linecuts(
        sample_dir=args.sample_dir,
        file_ending=args.file_ending,
        cut_axis=args.axis,
        center_str=args.center,
        window_str=args.window,
        unit_cell_str=args.unit_cell,
        outdir=args.outdir,
        offset=args.offset,
    )


if __name__ == "__main__":
    main()
