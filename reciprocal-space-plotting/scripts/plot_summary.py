#!/usr/bin/env python3
"""
plot_summary.py: Fast, standalone 3-panel orthogonal summary generator (HK, HL, KL).
Loads 3D NeXus reciprocal volume lazily and generates publication-ready side-by-side diagnostic figures.
"""

import os
import sys
import math
import argparse
import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from matplotlib.ticker import MultipleLocator

try:
    import nexusformat.nexus as nx
except ImportError:
    nx = None


def reciprocal_lattice_params(a, b, c, alpha, beta, gamma):
    al_rad = math.radians(alpha)
    be_rad = math.radians(beta)
    ga_rad = math.radians(gamma)
    cos_al = math.cos(al_rad)
    cos_be = math.cos(be_rad)
    cos_ga = math.cos(ga_rad)
    sin_al = math.sin(al_rad)
    sin_be = math.sin(be_rad)
    sin_ga = math.sin(ga_rad)
    vol = a * b * c * math.sqrt(
        max(0.0, 1.0 - cos_al**2 - cos_be**2 - cos_ga**2 + 2.0 * cos_al * cos_be * cos_ga)
    )
    if vol <= 0.0:
        return 1.0, 1.0, 1.0
    return (b * c * sin_al) / vol, (a * c * sin_be) / vol, (a * b * sin_ga) / vol


def parse_unit_cell(cell_str):
    if not cell_str:
        return 5.0, 5.0, 5.0, 90.0, 90.0, 90.0
    parts = [float(x.strip()) for x in cell_str.replace(";", ",").split(",") if x.strip()]
    if len(parts) == 6:
        return tuple(parts)
    return 5.0, 5.0, 5.0, 90.0, 90.0, 90.0


def generate_3panel_summary(nxs_path, output_png, h_val=0.0, k_val=0.0, l_val=0.0, unit_cell=None, cmap="viridis"):
    if nx is None:
        raise ImportError("nexusformat is required to run plot_summary.py")

    nx.nxsetmemory(20000)
    root = nx.nxload(nxs_path)
    if hasattr(root, "entry") and hasattr(root.entry, "data"):
        data = root.entry.data
    elif hasattr(root, "entry") and hasattr(root.entry, "transform"):
        data = root.entry.transform
    else:
        raise ValueError(f"Could not find valid NXdata in {nxs_path}")

    # Determine axis conventions
    axes = [ax.nxname for ax in data.nxaxes]
    is_nxrefine = ("Ql" in axes or "ql" in [a.lower() for a in axes])

    if is_nxrefine:
        # NXRefine order: [Ql, Qk, Qh]
        slice_hk = data[float(l_val), :, :]
        slice_hl = data[:, float(k_val), :]
        slice_kl = data[:, :, float(h_val)]
        h_arr = np.asarray(slice_hk.nxaxes[1].nxdata)
        k_arr = np.asarray(slice_hk.nxaxes[0].nxdata)
        l_arr = np.asarray(slice_hl.nxaxes[0].nxdata)
        img_hk = np.asarray(slice_hk.nxsignal.nxdata, dtype=np.float32)
        img_hl = np.asarray(slice_hl.nxsignal.nxdata, dtype=np.float32)
        img_kl = np.asarray(slice_kl.nxsignal.nxdata, dtype=np.float32)
    else:
        # Legacy CHESS order: [H, K, L]
        slice_hk = data[:, :, float(l_val)]
        slice_hl = data[:, float(k_val), :]
        slice_kl = data[float(h_val), :, :]
        h_arr = np.asarray(slice_hk.nxaxes[0].nxdata)
        k_arr = np.asarray(slice_hk.nxaxes[1].nxdata)
        l_arr = np.asarray(slice_hl.nxaxes[1].nxdata)
        img_hk = np.asarray(slice_hk.nxsignal.nxdata, dtype=np.float32).T
        img_hl = np.asarray(slice_hl.nxsignal.nxdata, dtype=np.float32).T
        img_kl = np.asarray(slice_kl.nxsignal.nxdata, dtype=np.float32).T

    # Reciprocal aspect ratios
    a, b, c, al, be, ga = parse_unit_cell(unit_cell)
    a_s, b_s, c_s = reciprocal_lattice_params(a, b, c, al, be, ga)

    # Dynamic vmin/vmax
    all_pos = np.concatenate([img_hk[img_hk > 0], img_hl[img_hl > 0], img_kl[img_kl > 0]])
    if len(all_pos) == 0:
        all_pos = np.array([1.0, 10.0], dtype=np.float32)
    vmin = max(1.0, float(np.nanpercentile(all_pos, 5)))
    vmax = float(np.nanpercentile(all_pos, 99.8))
    norm = LogNorm(vmin=vmin, vmax=vmax)

    fig, axes = plt.subplots(1, 3, figsize=(15, 5), dpi=200)

    # 1. HK Plane (X=H, Y=K)
    im0 = axes[0].imshow(img_hk, origin="lower", extent=[h_arr[0], h_arr[-1], k_arr[0], k_arr[-1]],
                         norm=norm, cmap=cmap, aspect=(b_s / a_s))
    axes[0].set_xlabel(r"$H$ (r.l.u.)", fontsize=11)
    axes[0].set_ylabel(r"$K$ (r.l.u.)", fontsize=11)
    axes[0].set_title(f"$(HK{l_val:g})$ Plane", fontsize=12)

    # 2. HL Plane (X=H, Y=L)
    axes[1].imshow(img_hl, origin="lower", extent=[h_arr[0], h_arr[-1], l_arr[0], l_arr[-1]],
                   norm=norm, cmap=cmap, aspect=(c_s / a_s))
    axes[1].set_xlabel(r"$H$ (r.l.u.)", fontsize=11)
    axes[1].set_ylabel(r"$L$ (r.l.u.)", fontsize=11)
    axes[1].set_title(f"$(H{k_val:g}L)$ Plane", fontsize=12)

    # 3. KL Plane (X=K, Y=L)
    axes[2].imshow(img_kl, origin="lower", extent=[k_arr[0], k_arr[-1], l_arr[0], l_arr[-1]],
                   norm=norm, cmap=cmap, aspect=(c_s / b_s))
    axes[2].set_xlabel(r"$K$ (r.l.u.)", fontsize=11)
    axes[2].set_ylabel(r"$L$ (r.l.u.)", fontsize=11)
    axes[2].set_title(f"$({h_val:g}KL)$ Plane", fontsize=12)

    for ax in axes:
        ax.xaxis.set_major_locator(MultipleLocator(2))
        ax.xaxis.set_minor_locator(MultipleLocator(1))
        ax.yaxis.set_major_locator(MultipleLocator(2))
        ax.yaxis.set_minor_locator(MultipleLocator(1))
        ax.tick_params(direction="in", top=True, right=True, which="both")

    fig.subplots_adjust(right=0.90, wspace=0.25)
    cbar_ax = fig.add_axes([0.92, 0.15, 0.015, 0.70])
    cbar = fig.colorbar(im0, cax=cbar_ax)
    cbar.set_label("Intensity (counts)", fontsize=10)

    os.makedirs(os.path.dirname(os.path.abspath(output_png)), exist_ok=True)
    plt.savefig(output_png, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved 3-panel summary plot: {output_png}")


def main():
    parser = argparse.ArgumentParser(description="Generate 3-panel orthogonal reciprocal space summary (HK, HL, KL).")
    parser.add_argument("--nxs", required=True, help="Path to 3D NeXus reciprocal volume (.nxs)")
    parser.add_argument("--output", "-o", required=True, help="Output PNG path")
    parser.add_argument("--h", type=float, default=0.0, help="H coordinate for KL plane cut")
    parser.add_argument("--k", type=float, default=0.0, help="K coordinate for HL plane cut")
    parser.add_argument("--l", type=float, default=0.0, help="L coordinate for HK plane cut")
    parser.add_argument("--unit-cell", default=None, help="Unit cell: 'a,b,c,alpha,beta,gamma'")
    parser.add_argument("--cmap", default="viridis", help="Colormap (default: viridis)")

    args = parser.parse_args()
    generate_3panel_summary(
        nxs_path=args.nxs,
        output_png=args.output,
        h_val=args.h,
        k_val=args.k,
        l_val=args.l,
        unit_cell=args.unit_cell,
        cmap=args.cmap,
    )


if __name__ == "__main__":
    main()
