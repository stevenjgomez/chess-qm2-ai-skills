#!/usr/bin/env python
"""
Diagnostic Cross-Section Visualizer for Reciprocal Space NeXus Volumes.
Extracts central 2D slices (HK, HL, KL planes) from 1rot_hkli.nxs or 3rot_hkli.nxs
and visualizes them using nxs_analysis_tools.plot_slice() with true crystallographic
skew angles (e.g. 60° for hexagonal in-plane HK) and true physical reciprocal
lattice aspect ratios (b*/a*, c*/a*, c*/b*).

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

from matplotlib.ticker import MultipleLocator
from matplotlib.collections import LineCollection

from nexusformat.nexus import nxload, NXdata, NXfield, nxsetmemory
from nxs_analysis_tools import plot_slice, reciprocal_lattice_params


def get_nice_integer_step(span, target_num=8):
    """Pick a clean integer tick interval producing approximately target_num divisions."""
    candidates = [1, 2, 4, 5, 6, 8, 10, 12, 15, 20, 24, 25, 30, 50, 100]
    best_step = 1
    best_diff = float('inf')
    for c in candidates:
        n = span / c
        diff = abs(n - target_num)
        if diff < best_diff:
            best_diff = diff
            best_step = c
    return best_step


def apply_grid_and_ticks(ax, quadmesh, x_bounds, y_bounds, x_major=None, y_major=None, grid_step=None, grid_color="gray", grid_alpha=0.5):
    """
    Apply integer-aligned major/minor ticks and skew-aligned grid lines to a plot_slice() axis.

    Formatting requirements:
    1. Major ticks: placed strictly on integers (MultipleLocator), dynamically choosing a step
       yielding ~6-10 intervals across the axis so labels never overlap.
    2. Minor ticks: integer-aligned (step 1 for step <= 6, step 2 for step <= 20, else 5).
    3. Grid lines: rendered via LineCollection transformed by quadmesh.get_transform() so that
       lines of constant reciprocal lattice coordinates strictly reflect the crystallographic skew_angle.
       Grid lines default to spacing matching major ticks (or custom grid_step).
    """
    xmin, xmax = x_bounds
    ymin, ymax = y_bounds

    x_span = xmax - xmin
    y_span = ymax - ymin

    if x_major is None:
        x_major = get_nice_integer_step(x_span, target_num=8)
    if y_major is None:
        y_major = get_nice_integer_step(y_span, target_num=8)

    # 1. Ticks: Major on integers, Minor integer-aligned
    ax.xaxis.set_major_locator(MultipleLocator(x_major))
    x_minor = 1 if x_major <= 6 else (2 if x_major <= 20 else 5)
    ax.xaxis.set_minor_locator(MultipleLocator(x_minor))

    ax.yaxis.set_major_locator(MultipleLocator(y_major))
    y_minor = 1 if y_major <= 6 else (2 if y_major <= 20 else 5)
    ax.yaxis.set_minor_locator(MultipleLocator(y_minor))

    ax.tick_params(direction='in', top=True, right=True, which='both')

    # 2. Skew-aligned grid lines in reciprocal data coordinates
    trans = quadmesh.get_transform()

    hx_step = grid_step if grid_step is not None else x_major
    ky_step = grid_step if grid_step is not None else y_major

    h_start = int(np.ceil(xmin / hx_step)) * hx_step
    h_ints = np.arange(h_start, int(np.floor(xmax)) + 1, hx_step)
    k_start = int(np.ceil(ymin / ky_step)) * ky_step
    k_ints = np.arange(k_start, int(np.floor(ymax)) + 1, ky_step)

    h_lines = [[(h, ymin), (h, ymax)] for h in h_ints]
    k_lines = [[(xmin, k), (xmax, k)] for k in k_ints]

    lc = LineCollection(
        h_lines + k_lines,
        transform=trans,
        colors=grid_color,
        linestyles='--',
        linewidths=0.5,
        alpha=grid_alpha,
        zorder=2
    )
    ax.add_collection(lc)


def get_reciprocal_parameters(unit_cell_str):
    """
    Compute reciprocal lattice vector lengths (a*, b*, c*) in Å⁻¹
    and reciprocal angles (alpha*, beta*, gamma*) in degrees from real-space cell string:
    'a, b, c, alpha, beta, gamma'.
    """
    try:
        parts = [float(x.strip()) for x in unit_cell_str.split(",")]
        a_star, b_star, c_star, alpha_star, beta_star, gamma_star = reciprocal_lattice_params(tuple(parts))
        return float(a_star), float(b_star), float(c_star), float(alpha_star), float(beta_star), float(gamma_star)
    except Exception as e:
        print(f"Warning: Failed to compute reciprocal parameters from unit cell '{unit_cell_str}' ({e}). Defaulting to isotropic 90°.")
        return 1.0, 1.0, 1.0, 90.0, 90.0, 90.0


def extract_lazy_slice(counts_field, coord_array, axis_idx, center=0.0, thickness=0.05):
    """
    Extract a 2D slice from an NXfield/HDF5 dataset lazily by indexing only the required hyperslab.
    Avoids reading the entire 3D volume into memory.
    """
    mask = np.abs(coord_array - center) <= thickness
    indices = np.where(mask)[0]
    if len(indices) == 0:
        indices = np.array([int(np.argmin(np.abs(coord_array - center)))])

    min_i, max_i = int(indices[0]), int(indices[-1])
    slice_span = slice(min_i, max_i + 1)
    rel_indices = indices - min_i

    if axis_idx == 0:
        slab = counts_field[slice_span, :, :].nxdata
        return np.nanmean(np.take(slab, rel_indices, axis=0), axis=0) if len(indices) > 1 else slab[0, :, :]
    elif axis_idx == 1:
        slab = counts_field[:, slice_span, :].nxdata
        return np.nanmean(np.take(slab, rel_indices, axis=1), axis=1) if len(indices) > 1 else slab[:, 0, :]
    else:
        slab = counts_field[:, :, slice_span].nxdata
        return np.nanmean(np.take(slab, rel_indices, axis=2), axis=2) if len(indices) > 1 else slab[:, :, 0]


def main():
    parser = argparse.ArgumentParser(description="Cross-Section Slicer for NeXus HKL Reciprocal Volumes using plot_slice()")
    parser.add_argument("--nxs-file", required=True, help="Path to 1rot_hkli.nxs or 3rot_hkli.nxs")
    parser.add_argument("--outdir", default=None, help="Output directory for PNGs (defaults to nxs file dir)")
    parser.add_argument("--unit-cell", default=None, help="Real-space unit cell string 'a,b,c,alpha,beta,gamma'")
    parser.add_argument("--thickness", type=float, default=0.05, help="Integration slice half-width in r.l.u.")
    parser.add_argument("--h-center", type=float, default=0.0, help="Center H coordinate for KL slice (default: 0.0)")
    parser.add_argument("--k-center", type=float, default=0.0, help="Center K coordinate for HL slice (default: 0.0)")
    parser.add_argument("--l-center", type=float, default=0.0, help="Center L coordinate for HK slice (default: 0.0)")
    parser.add_argument("--hlim", type=float, default=None, help="In-plane H axis limit +/-")
    parser.add_argument("--klim", type=float, default=None, help="In-plane K axis limit +/-")
    parser.add_argument("--llim", type=float, default=None, help="Out-of-plane L axis limit +/-")
    parser.add_argument("--vmin", type=float, default=None, help="Colorbar lower cutoff")
    parser.add_argument("--vmax", type=float, default=None, help="Colorbar upper cutoff")
    parser.add_argument("--cmap", default="turbo", help="Colormap name (default 'turbo')")
    parser.add_argument("--major-step", type=int, default=None, help="Integer step for major axis ticks (auto-scaled by default)")
    parser.add_argument("--grid-step", type=int, default=None, help="Integer step for reciprocal grid lines (matches major ticks by default)")
    parser.add_argument("--grid-color", default="gray", help="Grid line color (default 'gray')")
    parser.add_argument("--grid-alpha", type=float, default=0.5, help="Grid line alpha (default 0.5)")
    parser.add_argument("--no-grid", action="store_true", help="Disable grid lines")

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

    a_star, b_star, c_star, alpha_star, beta_star, gamma_star = 1.0, 1.0, 1.0, 90.0, 90.0, 90.0
    if unit_cell_str:
        a_star, b_star, c_star, alpha_star, beta_star, gamma_star = get_reciprocal_parameters(unit_cell_str)
    print(f"Reciprocal lengths: a*={a_star:.4f} Å⁻¹, b*={b_star:.4f} Å⁻¹, c*={c_star:.4f} Å⁻¹")
    print(f"Reciprocal angles : alpha*={alpha_star:.1f}°, beta*={beta_star:.1f}°, gamma*={gamma_star:.1f}°")
    print(f"Physical aspect corrections: b*/a*={b_star/a_star:.4f} (HK), c*/a*={c_star/a_star:.4f} (HL), c*/b*={c_star/b_star:.4f} (KL)")

    print(f"Loading reciprocal space volume (lazy structure): {nxs_path}")
    nxsetmemory(100000)
    nx_obj = nxload(nxs_path)

    data_entry = nx_obj.entry.data
    H_field = data_entry.H
    K_field = data_entry.K
    L_field = data_entry.L
    H = np.asarray(H_field.nxdata)
    K = np.asarray(K_field.nxdata)
    L = np.asarray(L_field.nxdata)
    counts_field = data_entry.counts

    print(f"Volume linked. Dimensions: H={len(H)}, K={len(K)}, L={len(L)}")

    h_bounds = (-args.hlim, args.hlim) if args.hlim is not None else (float(np.min(H)), float(np.max(H)))
    k_bounds = (-args.klim, args.klim) if args.klim is not None else (float(np.min(K)), float(np.max(K)))
    l_bounds = (-args.llim, args.llim) if args.llim is not None else (float(np.min(L)), float(np.max(L)))

    # Extract 2D slices lazily from HDF5
    hk_slice = extract_lazy_slice(counts_field, L, axis_idx=2, center=args.l_center, thickness=args.thickness)
    hl_slice = extract_lazy_slice(counts_field, K, axis_idx=1, center=args.k_center, thickness=args.thickness)
    kl_slice = extract_lazy_slice(counts_field, H, axis_idx=0, center=args.h_center, thickness=args.thickness)

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
    p_hk = plot_slice(
        nx_hk,
        skew_angle=gamma_star,
        ax=ax,
        logscale=True,
        vmin=c_min,
        vmax=c_max,
        xlim=h_bounds,
        ylim=k_bounds,
        title=f"HK Plane (L = {args.l_center:g}, skew={gamma_star:.0f}°)",
        cmap=args.cmap,
        cbar=True
    )
    # Apply physical reciprocal aspect ratio correction
    ax.set_aspect(ax.get_aspect() * (b_star / a_star))
    if not args.no_grid:
        apply_grid_and_ticks(ax, p_hk, h_bounds, k_bounds, x_major=args.major_step, y_major=args.major_step,
                             grid_step=args.grid_step, grid_color=args.grid_color, grid_alpha=args.grid_alpha)
    fig.savefig(hk_out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved slice to {hk_out}")

    # 2. HL Plane with skew_angle = beta_star (90°)
    hl_out = os.path.join(outdir, "slice_HL.png")
    fig, ax = plt.subplots(figsize=(6, 5), dpi=200)
    p_hl = plot_slice(
        nx_hl,
        skew_angle=beta_star,
        ax=ax,
        logscale=True,
        vmin=c_min,
        vmax=c_max,
        xlim=h_bounds,
        ylim=l_bounds,
        title=f"HL Plane (K = {args.k_center:g}, skew={beta_star:.0f}°)" if beta_star != 90.0 else f"HL Plane (K = {args.k_center:g})",
        cmap=args.cmap,
        cbar=True
    )
    # Apply physical reciprocal aspect ratio correction
    ax.set_aspect(ax.get_aspect() * (c_star / a_star))
    if not args.no_grid:
        apply_grid_and_ticks(ax, p_hl, h_bounds, l_bounds, x_major=args.major_step, y_major=None,
                             grid_step=args.grid_step, grid_color=args.grid_color, grid_alpha=args.grid_alpha)
    fig.savefig(hl_out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved slice to {hl_out}")

    # 3. KL Plane with skew_angle = alpha_star (90°)
    kl_out = os.path.join(outdir, "slice_KL.png")
    fig, ax = plt.subplots(figsize=(6, 5), dpi=200)
    p_kl = plot_slice(
        nx_kl,
        skew_angle=alpha_star,
        ax=ax,
        logscale=True,
        vmin=c_min,
        vmax=c_max,
        xlim=k_bounds,
        ylim=l_bounds,
        title=f"KL Plane (H = {args.h_center:g}, skew={alpha_star:.0f}°)" if alpha_star != 90.0 else f"KL Plane (H = {args.h_center:g})",
        cmap=args.cmap,
        cbar=True
    )
    # Apply physical reciprocal aspect ratio correction
    ax.set_aspect(ax.get_aspect() * (c_star / b_star))
    if not args.no_grid:
        apply_grid_and_ticks(ax, p_kl, k_bounds, l_bounds, x_major=args.major_step, y_major=None,
                             grid_step=args.grid_step, grid_color=args.grid_color, grid_alpha=args.grid_alpha)
    fig.savefig(kl_out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved slice to {kl_out}")

    # 4. Composite 3-panel Summary Plot
    summary_out = os.path.join(outdir, "slices_summary.png")
    summary_fig, axes = plt.subplots(1, 3, figsize=(18, 5), dpi=200)

    p0 = plot_slice(nx_hk, skew_angle=gamma_star, ax=axes[0], logscale=True, vmin=c_min, vmax=c_max,
                    xlim=h_bounds, ylim=k_bounds, title=f"HK (L={args.l_center:g}, skew={gamma_star:.0f}°)", cmap=args.cmap, cbar=False)
    axes[0].set_aspect(axes[0].get_aspect() * (b_star / a_star))
    if not args.no_grid:
        apply_grid_and_ticks(axes[0], p0, h_bounds, k_bounds, x_major=args.major_step, y_major=args.major_step,
                             grid_step=args.grid_step, grid_color=args.grid_color, grid_alpha=args.grid_alpha)

    p1 = plot_slice(nx_hl, skew_angle=beta_star, ax=axes[1], logscale=True, vmin=c_min, vmax=c_max,
                    xlim=h_bounds, ylim=l_bounds, title=f"HL (K={args.k_center:g}, skew={beta_star:.0f}°)" if beta_star != 90.0 else f"HL (K={args.k_center:g})",
                    cmap=args.cmap, cbar=False)
    axes[1].set_aspect(axes[1].get_aspect() * (c_star / a_star))
    if not args.no_grid:
        apply_grid_and_ticks(axes[1], p1, h_bounds, l_bounds, x_major=args.major_step, y_major=None,
                             grid_step=args.grid_step, grid_color=args.grid_color, grid_alpha=args.grid_alpha)

    im_last = plot_slice(nx_kl, skew_angle=alpha_star, ax=axes[2], logscale=True, vmin=c_min, vmax=c_max,
                         xlim=k_bounds, ylim=l_bounds, title=f"KL (H={args.h_center:g}, skew={alpha_star:.0f}°)" if alpha_star != 90.0 else f"KL (H={args.h_center:g})",
                         cmap=args.cmap, cbar=False)
    axes[2].set_aspect(axes[2].get_aspect() * (c_star / b_star))
    if not args.no_grid:
        apply_grid_and_ticks(axes[2], im_last, k_bounds, l_bounds, x_major=args.major_step, y_major=None,
                             grid_step=args.grid_step, grid_color=args.grid_color, grid_alpha=args.grid_alpha)

    summary_fig.subplots_adjust(right=0.88, wspace=0.3)
    cbar_ax = summary_fig.add_axes([0.90, 0.20, 0.015, 0.60])
    cbar = summary_fig.colorbar(im_last, cax=cbar_ax)
    cbar.set_label("Intensity (counts)", rotation=270, labelpad=15)

    summary_fig.savefig(summary_out, dpi=300, bbox_inches="tight")
    plt.close(summary_fig)
    print(f"Saved 3-panel summary plot to {summary_out}")


if __name__ == "__main__":
    main()
