#!/usr/bin/env python
"""
Diagnostic Cross-Section Visualizer for Reciprocal Space NeXus Volumes.
Extracts central 2D orthogonal slices (HK, HL, KL planes) from 1rot_hkli.nxs or 3rot_hkli.nxs
and generates publication-quality figures with logarithmic intensity colormaps.
Compatible with /nfs/chess/sw/anaconda3_jpcr/ without modifications.
"""

import os
import sys
import argparse
import numpy as np

# Ensure headless plotting
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm

from nexusformat.nexus import nxload, nxsetmemory


def extract_slice_and_extent(H, K, L, counts, plane, thickness=0.05):
    """
    Extract a 2D slice around zero for the perpendicular axis.
    thickness: integration half-width in r.l.u.
    """
    if plane == "HK":
        l_mask = np.abs(L) <= thickness
        if not np.any(l_mask):
            l_idx = np.argmin(np.abs(L))
            slice_data = counts[:, :, l_idx]
        else:
            slice_data = np.nanmean(counts[:, :, l_mask], axis=2)
        extent = [H[0], H[-1], K[0], K[-1]]
        xlabel, ylabel = "H (r.l.u.)", "K (r.l.u.)"
        title = f"HK Plane (L = 0 +/- {thickness} r.l.u.)"
        display_data = slice_data.T

    elif plane == "HL":
        k_mask = np.abs(K) <= thickness
        if not np.any(k_mask):
            k_idx = np.argmin(np.abs(K))
            slice_data = counts[:, k_idx, :]
        else:
            slice_data = np.nanmean(counts[:, k_mask, :], axis=1)
        extent = [H[0], H[-1], L[0], L[-1]]
        xlabel, ylabel = "H (r.l.u.)", "L (r.l.u.)"
        title = f"HL Plane (K = 0 +/- {thickness} r.l.u.)"
        display_data = slice_data.T

    elif plane == "KL":
        h_mask = np.abs(H) <= thickness
        if not np.any(h_mask):
            h_idx = np.argmin(np.abs(H))
            slice_data = counts[h_idx, :, :]
        else:
            slice_data = np.nanmean(counts[h_mask, :, :], axis=0)
        extent = [K[0], K[-1], L[0], L[-1]]
        xlabel, ylabel = "K (r.l.u.)", "L (r.l.u.)"
        title = f"KL Plane (H = 0 +/- {thickness} r.l.u.)"
        display_data = slice_data.T

    else:
        raise ValueError(f"Unknown plane: {plane}")

    return display_data, extent, xlabel, ylabel, title


def plot_and_save_slice(display_data, extent, xlabel, ylabel, title, outpath, vmin=None, vmax=None, xlim=None, ylim=None):
    fig, ax = plt.subplots(figsize=(6, 5), dpi=200)

    positive_counts = display_data[display_data > 0]
    if len(positive_counts) == 0:
        c_min, c_max = 1.0, 10.0
    else:
        c_min = float(np.percentile(positive_counts, 5))
        c_max = float(np.percentile(positive_counts, 99.8))
        if c_min <= 0:
            c_min = 1.0
        if c_max <= c_min:
            c_max = c_min * 10.0

    if vmin is not None:
        c_min = vmin
    if vmax is not None:
        c_max = vmax

    norm = LogNorm(vmin=c_min, vmax=c_max)
    im = ax.imshow(
        display_data,
        origin="lower",
        extent=extent,
        aspect="equal",
        cmap="turbo",
        norm=norm,
        interpolation="nearest"
    )

    if xlim is not None:
        ax.set_xlim(xlim)
    if ylim is not None:
        ax.set_ylim(ylim)

    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Intensity (counts)", rotation=270, labelpad=15)

    ax.set_xlabel(xlabel, fontsize=11)
    ax.set_ylabel(ylabel, fontsize=11)
    ax.set_title(title, fontsize=12, pad=10)
    ax.grid(color="gray", linestyle="--", linewidth=0.5, alpha=0.5)

    fig.tight_layout()
    fig.savefig(outpath, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved slice to {outpath}")


def main():
    parser = argparse.ArgumentParser(description="Cross-Section Slicer for NeXus HKL Reciprocal Volumes")
    parser.add_argument("--nxs-file", required=True, help="Path to 1rot_hkli.nxs or 3rot_hkli.nxs")
    parser.add_argument("--outdir", default=None, help="Output directory for PNGs (defaults to nxs file dir)")
    parser.add_argument("--thickness", type=float, default=0.05, help="Integration slice half-width in r.l.u.")
    parser.add_argument("--hlim", type=float, default=None, help="In-plane H axis limit +/- (default None = full extent)")
    parser.add_argument("--klim", type=float, default=None, help="In-plane K axis limit +/- (default None = full extent)")
    parser.add_argument("--llim", type=float, default=None, help="Out-of-plane L axis limit +/- (default None = full extent)")
    parser.add_argument("--vmin", type=float, default=None, help="Colorbar lower cutoff")
    parser.add_argument("--vmax", type=float, default=None, help="Colorbar upper cutoff")

    args = parser.parse_args()

    nxs_path = os.path.abspath(args.nxs_file)
    if not os.path.exists(nxs_path):
        raise FileNotFoundError(f"File not found: {nxs_path}")

    outdir = args.outdir or os.path.dirname(nxs_path)
    os.makedirs(outdir, exist_ok=True)

    print(f"Loading reciprocal space volume: {nxs_path}")
    nxsetmemory(100000)
    nx_obj = nxload(nxs_path)

    data_entry = nx_obj.entry.data
    H = np.asarray(data_entry.H.nxdata)
    K = np.asarray(data_entry.K.nxdata)
    L = np.asarray(data_entry.L.nxdata)
    counts = data_entry.counts.nxdata

    print(f"Volume loaded. Dimensions: H={len(H)}, K={len(K)}, L={len(L)}")

    h_bounds = (-args.hlim, args.hlim) if args.hlim is not None else None
    k_bounds = (-args.klim, args.klim) if args.klim is not None else None
    l_bounds = (-args.llim, args.llim) if args.llim is not None else None

    # 1. HK Plane
    hk_data, hk_ext, hk_x, hk_y, hk_title = extract_slice_and_extent(H, K, L, counts, "HK", args.thickness)
    hk_out = os.path.join(outdir, "slice_HK.png")
    plot_and_save_slice(hk_data, hk_ext, hk_x, hk_y, hk_title, hk_out, args.vmin, args.vmax, xlim=h_bounds, ylim=k_bounds)

    # 2. HL Plane
    hl_data, hl_ext, hl_x, hl_y, hl_title = extract_slice_and_extent(H, K, L, counts, "HL", args.thickness)
    hl_out = os.path.join(outdir, "slice_HL.png")
    plot_and_save_slice(hl_data, hl_ext, hl_x, hl_y, hl_title, hl_out, args.vmin, args.vmax, xlim=h_bounds, ylim=l_bounds)

    # 3. KL Plane
    kl_data, kl_ext, kl_x, kl_y, kl_title = extract_slice_and_extent(H, K, L, counts, "KL", args.thickness)
    kl_out = os.path.join(outdir, "slice_KL.png")
    plot_and_save_slice(kl_data, kl_ext, kl_x, kl_y, kl_title, kl_out, args.vmin, args.vmax, xlim=k_bounds, ylim=l_bounds)

    # 4. Composite 3-panel Summary Plot
    summary_fig, axes = plt.subplots(1, 3, figsize=(16, 5), dpi=200)

    all_positive = np.concatenate([
        hk_data[hk_data > 0].ravel(),
        hl_data[hl_data > 0].ravel(),
        kl_data[kl_data > 0].ravel()
    ])
    if len(all_positive) > 0:
        c_min = float(np.percentile(all_positive, 5))
        c_max = float(np.percentile(all_positive, 99.8))
        if c_min <= 0:
            c_min = 1.0
        if c_max <= c_min:
            c_max = c_min * 10.0
    else:
        c_min, c_max = 1.0, 10.0

    if args.vmin is not None:
        c_min = args.vmin
    if args.vmax is not None:
        c_max = args.vmax

    norm = LogNorm(vmin=c_min, vmax=c_max)

    panels = [
        (axes[0], hk_data, hk_ext, hk_x, hk_y, "HK Plane (L=0)", h_bounds, k_bounds),
        (axes[1], hl_data, hl_ext, hl_x, hl_y, "HL Plane (K=0)", h_bounds, l_bounds),
        (axes[2], kl_data, kl_ext, kl_x, kl_y, "KL Plane (H=0)", k_bounds, l_bounds)
    ]

    for ax, data_slice, ext, xl, yl, tit, x_b, y_b in panels:
        im = ax.imshow(data_slice, origin="lower", extent=ext, aspect="equal", cmap="turbo", norm=norm)
        if x_b:
            ax.set_xlim(x_b)
        if y_b:
            ax.set_ylim(y_b)
        ax.set_xlabel(xl, fontsize=10)
        ax.set_ylabel(yl, fontsize=10)
        ax.set_title(tit, fontsize=11)
        ax.grid(color="gray", linestyle="--", linewidth=0.5, alpha=0.5)

    summary_fig.subplots_adjust(right=0.88, wspace=0.3)
    cbar_ax = summary_fig.add_axes([0.90, 0.20, 0.015, 0.60])
    cbar = summary_fig.colorbar(im, cax=cbar_ax)
    cbar.set_label("Intensity (counts)", rotation=270, labelpad=15)

    summary_out = os.path.join(outdir, "slices_summary.png")
    summary_fig.savefig(summary_out, dpi=300, bbox_inches="tight")
    plt.close(summary_fig)
    print(f"Saved 3-panel summary plot to {summary_out}")


if __name__ == "__main__":
    main()
