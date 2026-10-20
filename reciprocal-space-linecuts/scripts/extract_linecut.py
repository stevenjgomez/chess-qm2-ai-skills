#!/usr/bin/env python3
"""
extract_linecut.py: Standalone 1D reciprocal space linecut extractor and plotter.
Uses nxs_analysis_tools.Scissors or fallback HDF5 hyperslab integration.
"""

import os
import sys
import argparse
import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    import nexusformat.nexus as nx
except ImportError:
    nx = None

try:
    from nxs_analysis_tools.datareduction import Scissors
except ImportError:
    Scissors = None


def parse_tuple(s, expected_len=3):
    parts = [float(x.strip()) for x in s.replace(";", ",").split(",") if x.strip()]
    if len(parts) != expected_len:
        raise ValueError(f"Expected {expected_len} values in '{s}', got {len(parts)}")
    return tuple(parts)


def extract_linecut(nxs_path, cut_axis, center_str, window_str, out_png, out_csv=None):
    if nx is None:
        raise ImportError("nexusformat is required to run extract_linecut.py")

    nx.nxsetmemory(20000)
    root = nx.nxload(nxs_path)
    if hasattr(root, "entry") and hasattr(root.entry, "data"):
        data = root.entry.data
    elif hasattr(root, "entry") and hasattr(root.entry, "transform"):
        data = root.entry.transform
    else:
        raise ValueError(f"Could not find valid NXdata in {nxs_path}")

    cut_axis = cut_axis.upper()
    axes = [ax.nxname for ax in data.nxaxes]
    is_nxrefine = ("Ql" in axes or "ql" in [a.lower() for a in axes])

    center = parse_tuple(center_str, 3)
    window = parse_tuple(window_str, 3)

    if is_nxrefine:
        axis_map = {"L": 0, "K": 1, "H": 2}
    else:
        axis_map = {"H": 0, "K": 1, "L": 2}

    if cut_axis not in axis_map:
        raise ValueError(f"Invalid cut axis: {cut_axis}. Choose from H, K, L.")

    axis_idx = axis_map[cut_axis]

    if Scissors is not None:
        scissors = Scissors(data)
        linecut = scissors.cut_data(center=center, window=window, axis=axis_idx)
        q_vals = np.asarray(linecut.nxaxes[0].nxdata)
        intensity = np.asarray(linecut.nxsignal.nxdata, dtype=np.float32)
    else:
        # Fallback manual slice integration
        print("Note: Scissors not available; falling back to manual hyperslab integration.")
        c0, c1, c2 = center
        w0, w1, w2 = window
        # Get axis grids
        ax0 = np.asarray(data.nxaxes[0].nxdata)
        ax1 = np.asarray(data.nxaxes[1].nxdata)
        ax2 = np.asarray(data.nxaxes[2].nxdata)
        
        # Determine ranges
        m0 = np.abs(ax0 - c0) <= (w0 / 2.0)
        m1 = np.abs(ax1 - c1) <= (w1 / 2.0)
        m2 = np.abs(ax2 - c2) <= (w2 / 2.0)
        
        counts_3d = np.asarray(data.nxsignal.nxdata, dtype=np.float32)
        if axis_idx == 0:
            q_vals = ax0[m0]
            intensity = np.nanmean(counts_3d[m0, :, :][:, m1, :][:, :, m2], axis=(1, 2))
        elif axis_idx == 1:
            q_vals = ax1[m1]
            intensity = np.nanmean(counts_3d[:, m1, :][m0, :, :][:, :, m2], axis=(0, 2))
        else:
            q_vals = ax2[m2]
            intensity = np.nanmean(counts_3d[:, :, m2][m0, :, :][:, m1, :], axis=(0, 1))

    # Save CSV if requested
    if out_csv:
        os.makedirs(os.path.dirname(os.path.abspath(out_csv)), exist_ok=True)
        table = np.column_stack([q_vals, intensity])
        np.savetxt(out_csv, table, delimiter=",", header=f"{cut_axis}_rlu,intensity", comments="")
        print(f"Saved linecut CSV: {out_csv}")

    # Plot
    fig, ax = plt.subplots(figsize=(6, 4), dpi=200)
    ax.plot(q_vals, intensity, "o-", color="royalblue", markersize=3, lw=1.2, label=f"Cut along {cut_axis}")
    ax.set_xlabel(f"{cut_axis} (r.l.u.)", fontsize=11)
    ax.set_ylabel("Integrated Intensity (counts)", fontsize=11)
    ax.set_title(f"1D Linecut along {cut_axis}\nCenter={center}, Window={window}", fontsize=11)
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend()

    os.makedirs(os.path.dirname(os.path.abspath(out_png)), exist_ok=True)
    plt.tight_layout()
    plt.savefig(out_png, dpi=300)
    plt.close(fig)
    print(f"Saved linecut plot: {out_png}")


def main():
    parser = argparse.ArgumentParser(description="Extract and plot 1D reciprocal space linecut using Scissors.")
    parser.add_argument("--nxs", required=True, help="Path to NeXus volume (.nxs)")
    parser.add_argument("--axis", required=True, choices=["H", "K", "L"], help="Direction of 1D cut")
    parser.add_argument("--center", required=True, help="Center coordinate tuple: 'c0, c1, c2'")
    parser.add_argument("--window", required=True, help="Window size tuple: 'w0, w1, w2'")
    parser.add_argument("--output", "-o", required=True, help="Output PNG path")
    parser.add_argument("--csv", default=None, help="Optional output CSV path")

    args = parser.parse_args()
    extract_linecut(
        nxs_path=args.nxs,
        cut_axis=args.axis,
        center_str=args.center,
        window_str=args.window,
        out_png=args.output,
        out_csv=args.csv,
    )


if __name__ == "__main__":
    main()
