#!/usr/bin/env python3
"""
animate_volume.py: Fast, memory-safe reciprocal space volume scan animator.
Generates an animated GIF or MP4 scrolling along a designated reciprocal axis (H, K, or L).
"""

import os
import sys
import argparse
import numpy as np
import gc

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from matplotlib.animation import FuncAnimation, PillowWriter

try:
    import nexusformat.nexus as nx
except ImportError:
    nx = None


def animate_volume(nxs_path, axis_name, out_path, fps=12, stride=2, vmin=None, vmax=None, cmap="viridis"):
    if nx is None:
        raise ImportError("nexusformat is required to run animate_volume.py")

    nx.nxsetmemory(20000)
    root = nx.nxload(nxs_path)
    if hasattr(root, "entry") and hasattr(root.entry, "data"):
        data = root.entry.data
    elif hasattr(root, "entry") and hasattr(root.entry, "transform"):
        data = root.entry.transform
    else:
        raise ValueError(f"Could not find valid NXdata in {nxs_path}")

    axis_name = axis_name.upper()
    axes = [ax.nxname for ax in data.nxaxes]
    is_nxrefine = ("Ql" in axes or "ql" in [a.lower() for a in axes])

    # Map axis to index
    if is_nxrefine:
        axis_map = {"L": 0, "K": 1, "H": 2}
    else:
        axis_map = {"H": 0, "K": 1, "L": 2}

    if axis_name not in axis_map:
        raise ValueError(f"Invalid axis: {axis_name}. Choose from H, K, L.")

    scan_idx = axis_map[axis_name]
    coord_arr = np.asarray(data.nxaxes[scan_idx].nxdata)[::max(1, int(stride))]
    n_frames = len(coord_arr)
    print(f"Generating animation along {axis_name} across {n_frames} frames (stride={stride})...")

    # Determine free 2D axes
    free_indices = [i for i in range(3) if i != scan_idx]
    x_name = data.nxaxes[free_indices[0]].nxname
    y_name = data.nxaxes[free_indices[1]].nxname
    x_coords = np.asarray(data.nxaxes[free_indices[0]].nxdata)
    y_coords = np.asarray(data.nxaxes[free_indices[1]].nxdata)

    # Establish global vmin/vmax across sample slices
    sample_sub = [coord_arr[i] for i in range(0, n_frames, max(1, n_frames // 4))]
    sample_slices = []
    for c in sample_sub:
        if scan_idx == 0:
            s = np.asarray(data[c, :, :].nxsignal.nxdata, dtype=np.float32)
        elif scan_idx == 1:
            s = np.asarray(data[:, c, :].nxsignal.nxdata, dtype=np.float32)
        else:
            s = np.asarray(data[:, :, c].nxsignal.nxdata, dtype=np.float32)
        sample_slices.append(s)
    
    pos = np.concatenate([s[s > 0] for s in sample_slices])
    if len(pos) == 0:
        pos = np.array([1.0, 10.0], dtype=np.float32)
    _vmin = float(vmin) if vmin is not None else max(1.0, float(np.nanpercentile(pos, 5)))
    _vmax = float(vmax) if vmax is not None else float(np.nanpercentile(pos, 99.8))

    # Initialize plot
    fig, ax = plt.subplots(figsize=(6, 5), dpi=140)
    if scan_idx == 0:
        init_s = np.asarray(data[coord_arr[0], :, :].nxsignal.nxdata, dtype=np.float32)
    elif scan_idx == 1:
        init_s = np.asarray(data[:, coord_arr[0], :].nxsignal.nxdata, dtype=np.float32)
    else:
        init_s = np.asarray(data[:, :, coord_arr[0]].nxsignal.nxdata, dtype=np.float32)

    im = ax.imshow(
        init_s.T,
        origin="lower",
        extent=[x_coords[0], x_coords[-1], y_coords[0], y_coords[-1]],
        norm=LogNorm(vmin=_vmin, vmax=_vmax),
        cmap=cmap,
        aspect=1.0,
    )
    ax.set_xlabel(f"{x_name} (r.l.u.)", fontsize=11)
    ax.set_ylabel(f"{y_name} (r.l.u.)", fontsize=11)
    title_text = ax.set_title(f"Volume Scan along {axis_name}: {coord_arr[0]:.2f} r.l.u.", fontsize=12)
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Intensity (counts)", fontsize=10)

    def update(frame_idx):
        c = coord_arr[frame_idx]
        if scan_idx == 0:
            s_2d = np.asarray(data[c, :, :].nxsignal.nxdata, dtype=np.float32)
        elif scan_idx == 1:
            s_2d = np.asarray(data[:, c, :].nxsignal.nxdata, dtype=np.float32)
        else:
            s_2d = np.asarray(data[:, :, c].nxsignal.nxdata, dtype=np.float32)
        im.set_data(s_2d.T)
        title_text.set_text(f"Volume Scan along {axis_name}: {c:.2f} r.l.u.")
        return [im, title_text]

    anim = FuncAnimation(fig, update, frames=n_frames, blit=True)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    writer = PillowWriter(fps=fps)
    anim.save(out_path, writer=writer)
    plt.close(fig)
    gc.collect()
    print(f"Exported volume scan animation: {out_path}")


def main():
    parser = argparse.ArgumentParser(description="Animate scrolling through reciprocal space volume.")
    parser.add_argument("--nxs", required=True, help="Path to 3D NeXus reciprocal volume (.nxs)")
    parser.add_argument("--axis", default="L", choices=["H", "K", "L"], help="Axis to scan (default: L)")
    parser.add_argument("--output", "-o", required=True, help="Destination GIF or MP4 path")
    parser.add_argument("--stride", type=int, default=2, help="Frame stride along scan axis (default: 2)")
    parser.add_argument("--fps", type=int, default=12, help="Animation playback speed (fps)")
    parser.add_argument("--vmin", type=float, default=None, help="LogNorm minimum intensity")
    parser.add_argument("--vmax", type=float, default=None, help="LogNorm maximum intensity")
    parser.add_argument("--cmap", default="viridis", help="Colormap (default: viridis)")

    args = parser.parse_args()
    animate_volume(
        nxs_path=args.nxs,
        axis_name=args.axis,
        out_path=args.output,
        fps=args.fps,
        stride=args.stride,
        vmin=args.vmin,
        vmax=args.vmax,
        cmap=args.cmap,
    )


if __name__ == "__main__":
    main()
