#!/usr/bin/env python3
"""
plot_slice.py: Fast, standalone 2D reciprocal space slice generator.
Loads 3D NeXus reciprocal space datasets lazily and saves high-resolution 2D cross-sections.

Supports:
  - Planes: HK (L=const), HL (K=const), KL (H=const)
  - Native format auto-detection: Legacy CHESS ([H, K, L]) vs NXRefine ([Ql, Qk, Qh])
  - Aspect ratio calibration via unit cell parameters
  - Headless execution with LogNorm and integer ticks
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

try:
    import h5py
except ImportError:
    h5py = None


def reciprocal_lattice_params(a, b, c, alpha, beta, gamma):
    """Calculate reciprocal lattice lengths and angles."""
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
        return 1.0, 1.0, 1.0, 90.0, 90.0, 90.0
    
    a_star = (b * c * sin_al) / vol
    b_star = (a * c * sin_be) / vol
    c_star = (a * b * sin_ga) / vol
    return a_star, b_star, c_star, 90.0, 90.0, 90.0


def parse_unit_cell(cell_str):
    if not cell_str:
        return 5.0, 5.0, 5.0, 90.0, 90.0, 90.0
    parts = [float(x.strip()) for x in cell_str.replace(";", ",").split(",") if x.strip()]
    if len(parts) == 6:
        return tuple(parts)
    return 5.0, 5.0, 5.0, 90.0, 90.0, 90.0


def plot_single_slice(nxs_path, plane, coord, output_png, unit_cell=None, vmin=None, vmax=None, cmap="viridis"):
    if nx is None:
        raise ImportError("nexusformat is required to run plot_slice.py")
    
    nx.nxsetmemory(20000)
    root = nx.nxload(nxs_path)
    
    if hasattr(root, "entry") and hasattr(root.entry, "data"):
        data = root.entry.data
    elif hasattr(root, "entry") and hasattr(root.entry, "transform"):
        data = root.entry.transform
    else:
        raise ValueError(f"Could not find valid NXdata under entry.data or entry.transform in {nxs_path}")
    
    plane = plane.upper()
    coord = float(coord)
    
    # Check axes
    axes = [ax.nxname for ax in data.nxaxes]
    is_nxrefine = ("Ql" in axes or "ql" in [a.lower() for a in axes])
    
    if is_nxrefine:
        # NXRefine order: [Ql, Qk, Qh] -> indices 0, 1, 2
        if plane == "HK":
            slice_nx = data[coord, :, :]
            x_label, y_label = r"$Q_h$ (r.l.u.)", r"$Q_k$ (r.l.u.)"
            h_idx, v_idx = 2, 1
        elif plane == "HL":
            slice_nx = data[:, coord, :]
            x_label, y_label = r"$Q_h$ (r.l.u.)", r"$Q_l$ (r.l.u.)"
            h_idx, v_idx = 2, 0
        elif plane == "KL":
            slice_nx = data[:, :, coord]
            x_label, y_label = r"$Q_k$ (r.l.u.)", r"$Q_l$ (r.l.u.)"
            h_idx, v_idx = 1, 0
        else:
            raise ValueError(f"Unknown plane: {plane}")
    else:
        # Legacy CHESS order: [H, K, L] -> indices 0, 1, 2
        if plane == "HK":
            slice_nx = data[:, :, coord]
            x_label, y_label = r"$H$ (r.l.u.)", r"$K$ (r.l.u.)"
            h_idx, v_idx = 0, 1
        elif plane == "HL":
            slice_nx = data[:, coord, :]
            x_label, y_label = r"$H$ (r.l.u.)", r"$L$ (r.l.u.)"
            h_idx, v_idx = 0, 2
        elif plane == "KL":
            slice_nx = data[coord, :, :]
            x_label, y_label = r"$K$ (r.l.u.)", r"$L$ (r.l.u.)"
            h_idx, v_idx = 1, 2
        else:
            raise ValueError(f"Unknown plane: {plane}")

    counts = np.asarray(slice_nx.nxsignal.nxdata, dtype=np.float32)
    x_axis = np.asarray(slice_nx.nxaxes[0].nxdata)
    y_axis = np.asarray(slice_nx.nxaxes[1].nxdata)
    
    # Determine physical aspect ratio
    a, b, c, al, be, ga = parse_unit_cell(unit_cell)
    a_s, b_s, c_s, _, _, _ = reciprocal_lattice_params(a, b, c, al, be, ga)
    
    aspect = 1.0
    if plane == "HK":
        aspect = b_s / a_s
    elif plane == "HL":
        aspect = c_s / a_s
    elif plane == "KL":
        aspect = c_s / b_s

    # Normalization
    pos = counts[counts > 0]
    if len(pos) == 0:
        pos = np.array([1.0, 10.0], dtype=np.float32)
    _vmin = float(vmin) if vmin is not None else max(1.0, float(np.nanpercentile(pos, 5)))
    _vmax = float(vmax) if vmax is not None else float(np.nanpercentile(pos, 99.8))
    if _vmax <= _vmin:
        _vmax = _vmin * 10.0

    fig, ax = plt.subplots(figsize=(6, 5), dpi=200)
    im = ax.imshow(
        counts.T,
        origin="lower",
        extent=[x_axis[0], x_axis[-1], y_axis[0], y_axis[-1]],
        norm=LogNorm(vmin=_vmin, vmax=_vmax),
        cmap=cmap,
        aspect=aspect,
    )
    
    ax.xaxis.set_major_locator(MultipleLocator(2))
    ax.xaxis.set_minor_locator(MultipleLocator(1))
    ax.yaxis.set_major_locator(MultipleLocator(2))
    ax.yaxis.set_minor_locator(MultipleLocator(1))
    ax.tick_params(direction="in", top=True, right=True, which="both")
    
    ax.set_xlabel(x_label, fontsize=11)
    ax.set_ylabel(y_label, fontsize=11)
    ax.set_title(f"{plane} Slice at coordinate {coord:g}", fontsize=12)
    
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Intensity (counts)", fontsize=10)
    
    os.makedirs(os.path.dirname(os.path.abspath(output_png)), exist_ok=True)
    plt.tight_layout()
    plt.savefig(output_png, dpi=300)
    plt.close(fig)
    print(f"Saved reciprocal slice: {output_png}")


def main():
    parser = argparse.ArgumentParser(description="Generate 2D reciprocal space cross-section from NeXus volume.")
    parser.add_argument("--nxs", required=True, help="Path to 3D NeXus reciprocal volume (.nxs)")
    parser.add_argument("--plane", default="HK", choices=["HK", "HL", "KL"], help="Reciprocal plane to cut")
    parser.add_argument("--coord", type=float, default=0.0, help="Perpendicular coordinate value (e.g. 0.0)")
    parser.add_argument("--output", "-o", required=True, help="Output PNG path")
    parser.add_argument("--unit-cell", default=None, help="Unit cell string: 'a,b,c,alpha,beta,gamma'")
    parser.add_argument("--vmin", type=float, default=None, help="LogNorm minimum intensity")
    parser.add_argument("--vmax", type=float, default=None, help="LogNorm maximum intensity")
    parser.add_argument("--cmap", default="viridis", help="Colormap (default: viridis)")
    
    args = parser.parse_args()
    plot_single_slice(
        nxs_path=args.nxs,
        plane=args.plane,
        coord=args.coord,
        output_png=args.output,
        unit_cell=args.unit_cell,
        vmin=args.vmin,
        vmax=args.vmax,
        cmap=args.cmap,
    )


if __name__ == "__main__":
    main()
