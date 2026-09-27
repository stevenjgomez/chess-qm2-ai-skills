#!/usr/bin/env python
"""
Diagnostic Cross-Section Visualizer for Reciprocal Space NeXus Volumes.
Extracts central 2D slices (HK, HL, KL planes) from 1rot_hkli.nxs or 3rot_hkli.nxs
and visualizes them using nxs_analysis_tools.plot_slice() with true crystallographic
skew angles (e.g. 60° for hexagonal in-plane HK).

Automatically re-executes inside /nfs/chess/sw/anaconda3_sgomezalvarado_nightly/bin/python
if launched from another environment (e.g. anaconda3_jpcr).
"""

import sys
import os

# Ensure execution in dedicated nightly environment where nxs_analysis_tools is installed
NIGHTLY_PYTHON = "/nfs/chess/sw/anaconda3_sgomezalvarado_nightly/bin/python"
if sys.executable != NIGHTLY_PYTHON and os.path.exists(NIGHTLY_PYTHON):
    os.execv(NIGHTLY_PYTHON, [NIGHTLY_PYTHON] + sys.argv)

import argparse
import numpy as np

# Ensure headless plotting
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from nexusformat.nexus import nxload, NXdata, NXfield, nxsetmemory
from nxs_analysis_tools import plot_slice


def compute_reciprocal_angles(unit_cell_str):
    """
    Compute reciprocal lattice angles alpha*, beta*, gamma* from real-space cell:
    a, b, c, alpha, beta, gamma.
    """
    try:
        parts = [float(x.strip()) for x in unit_cell_str.split(",")]
        a, b, c, alpha, beta, gamma = parts
        ar = np.radians(alpha)
        br = np.radians(beta)
        gr = np.radians(gamma)
        
        cos_as = np.clip((np.cos(br) * np.cos(gr) - np.cos(ar)) / (np.sin(br) * np.sin(gr)), -1.0, 1.0)
        cos_bs = np.clip((np.cos(ar) * np.cos(gr) - np.cos(br)) / (np.sin(ar) * np.sin(gr)), -1.0, 1.0)
        cos_gs = np.clip((np.cos(ar) * np.cos(br) - np.cos(gr)) / (np.sin(ar) * np.sin(br)), -1.0, 1.0)
        
        alpha_star = float(np.degrees(np.arccos(cos_as)))
        beta_star = float(np.degrees(np.arccos(cos_bs)))
        gamma_star = float(np.degrees(np.arccos(cos_gs)))
        return alpha_star, beta_star, gamma_star
    except Exception as e:
        print(f"Warning: Failed to parse unit cell '{unit_cell_str}' ({e}). Defaulting to orthogonal angles (90°).")
        return 90.0, 90.0, 90.0


def extract_slice(counts, coord_array, axis_idx, thickness=0.05):
    """
    Extract a 2D slice by averaging over a narrow slice around zero along the specified axis.
    """
    mask = np.abs(coord_array) <= thickness
    if not np.any(mask):
        idx = int(np.argmin(np.abs(coord_array)))
        if axis_idx == 0:
            return counts[idx, :, :]
        elif axis_idx == 1:
            return counts[:, idx, :]
        else:
            return counts[:, :, idx]
    else:
        return np.nanmean(np.take(counts, np.where(mask)[0], axis=axis_idx), axis=axis_idx)


def main():
    parser = argparse.ArgumentParser(description="Cross-Section Slicer for NeXus HKL Reciprocal Volumes using plot_slice()")
    parser.add_argument("--nxs-file", required=True, help="Path to 1rot_hkli.nxs or 3rot_hkli.nxs")
    parser.add_argument("--outdir", default=None, help="Output directory for PNGs (defaults to nxs file dir)")
    parser.add_argument("--unit-cell", default=None, help="Real-space unit cell string 'a,b,c,alpha,beta,gamma'")
    parser.add_argument("--thickness", type=float, default=0.05, help="Integration slice half-width in r.l.u.")
    parser.add_argument("--hlim", type=float, default=None, help="In-plane H axis limit +/-")
    parser.add_argument("--klim", type=float, default=None, help="In-plane K axis limit +/-")
    parser.add_argument("--llim", type=float, default=None, help="Out-of-plane L axis limit +/-")
    parser.add_argument("--vmin", type=float, default=None, help="Colorbar lower cutoff")
    parser.add_argument("--vmax", type=float, default=None, help="Colorbar upper cutoff")
    parser.add_argument("--cmap", default="turbo", help="Colormap name (default 'turbo')")

    args = parser.parse_args()

    nxs_path = os.path.abspath(args.nxs_file)
    if not os.path.exists(nxs_path):
        raise FileNotFoundError(f"File not found: {nxs_path}")

    outdir = args.outdir or os.path.dirname(nxs_path)
    os.makedirs(outdir, exist_ok=True)

    # Resolve unit cell parameters
    unit_cell_str = args.unit_cell
    if not unit_cell_str:
        unitcell_txt = os.path.join(os.path.dirname(nxs_path), "unitcell.txt")
        if os.path.exists(unitcell_txt):
            with open(unitcell_txt, "r") as f:
                unit_cell_str = f.read().strip()
                print(f"Loaded unit cell from {unitcell_txt}: {unit_cell_str}")

    alpha_star, beta_star, gamma_star = 90.0, 90.0, 90.0
    if unit_cell_str:
        alpha_star, beta_star, gamma_star = compute_reciprocal_angles(unit_cell_str)
    print(f"Reciprocal angles: alpha*={alpha_star:.1f}°, beta*={beta_star:.1f}°, gamma*={gamma_star:.1f}°")

    print(f"Loading reciprocal space volume: {nxs_path}")
    nxsetmemory(100000)
    nx_obj = nxload(nxs_path)

    data_entry = nx_obj.entry.data
    H_field = data_entry.H
    K_field = data_entry.K
    L_field = data_entry.L
    H = np.asarray(H_field.nxdata)
    K = np.asarray(K_field.nxdata)
    L = np.asarray(L_field.nxdata)
    counts = data_entry.counts.nxdata

    print(f"Volume loaded. Dimensions: H={len(H)}, K={len(K)}, L={len(L)}")

    h_bounds = (-args.hlim, args.hlim) if args.hlim is not None else None
    k_bounds = (-args.klim, args.klim) if args.klim is not None else None
    l_bounds = (-args.llim, args.llim) if args.llim is not None else None

    # Extract 2D slices
    hk_slice = extract_slice(counts, L, axis_idx=2, thickness=args.thickness)
    hl_slice = extract_slice(counts, K, axis_idx=1, thickness=args.thickness)
    kl_slice = extract_slice(counts, H, axis_idx=0, thickness=args.thickness)

    # Wrap in 2D NXdata structures for plot_slice()
    nx_hk = NXdata(NXfield(hk_slice, name="counts"), (H_field, K_field))
    nx_hl = NXdata(NXfield(hl_slice, name="counts"), (H_field, L_field))
    nx_kl = NXdata(NXfield(kl_slice, name="counts"), (K_field, L_field))

    # Automatic contrast scaling across positive counts
    all_positive = np.concatenate([
        hk_slice[hk_slice > 0].ravel(),
        hl_slice[hl_slice > 0].ravel(),
        kl_slice[kl_slice > 0].ravel()
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

    # 1. HK Plane with skew_angle = gamma_star (e.g. 60° for hexagonal)
    hk_out = os.path.join(outdir, "slice_HK.png")
    fig, ax = plt.subplots(figsize=(6, 5), dpi=200)
    plot_slice(
        nx_hk,
        skew_angle=gamma_star,
        ax=ax,
        logscale=True,
        vmin=c_min,
        vmax=c_max,
        xlim=h_bounds,
        ylim=k_bounds,
        title=f"HK Plane (L = 0, skew={gamma_star:.0f}°)",
        cmap=args.cmap,
        cbar=True
    )
    fig.savefig(hk_out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved slice to {hk_out}")

    # 2. HL Plane with skew_angle = beta_star (90°)
    hl_out = os.path.join(outdir, "slice_HL.png")
    fig, ax = plt.subplots(figsize=(6, 5), dpi=200)
    plot_slice(
        nx_hl,
        skew_angle=beta_star,
        ax=ax,
        logscale=True,
        vmin=c_min,
        vmax=c_max,
        xlim=h_bounds,
        ylim=l_bounds,
        title="HL Plane (K = 0)",
        cmap=args.cmap,
        cbar=True
    )
    fig.savefig(hl_out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved slice to {hl_out}")

    # 3. KL Plane with skew_angle = alpha_star (90°)
    kl_out = os.path.join(outdir, "slice_KL.png")
    fig, ax = plt.subplots(figsize=(6, 5), dpi=200)
    plot_slice(
        nx_kl,
        skew_angle=alpha_star,
        ax=ax,
        logscale=True,
        vmin=c_min,
        vmax=c_max,
        xlim=k_bounds,
        ylim=l_bounds,
        title="KL Plane (H = 0)",
        cmap=args.cmap,
        cbar=True
    )
    fig.savefig(kl_out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved slice to {kl_out}")

    # 4. Composite 3-panel Summary Plot
    summary_out = os.path.join(outdir, "slices_summary.png")
    summary_fig, axes = plt.subplots(1, 3, figsize=(18, 5), dpi=200)

    plot_slice(nx_hk, skew_angle=gamma_star, ax=axes[0], logscale=True, vmin=c_min, vmax=c_max,
               xlim=h_bounds, ylim=k_bounds, title=f"HK Plane (skew={gamma_star:.0f}°)", cmap=args.cmap, cbar=False)
    plot_slice(nx_hl, skew_angle=beta_star, ax=axes[1], logscale=True, vmin=c_min, vmax=c_max,
               xlim=h_bounds, ylim=l_bounds, title="HL Plane", cmap=args.cmap, cbar=False)
    im_last = plot_slice(nx_kl, skew_angle=alpha_star, ax=axes[2], logscale=True, vmin=c_min, vmax=c_max,
                         xlim=k_bounds, ylim=l_bounds, title="KL Plane", cmap=args.cmap, cbar=False)

    summary_fig.subplots_adjust(right=0.88, wspace=0.3)
    cbar_ax = summary_fig.add_axes([0.90, 0.20, 0.015, 0.60])
    cbar = summary_fig.colorbar(im_last, cax=cbar_ax)
    cbar.set_label("Intensity (counts)", rotation=270, labelpad=15)

    summary_fig.savefig(summary_out, dpi=300, bbox_inches="tight")
    plt.close(summary_fig)
    print(f"Saved 3-panel summary plot to {summary_out}")


if __name__ == "__main__":
    main()
