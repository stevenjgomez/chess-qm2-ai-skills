#!/usr/bin/env python3
"""
animate_temp_series.py: Fast, memory-safe temperature-series animator.
Discovers reciprocal space volumes across temperatures and renders a smooth evolution GIF or MP4.
"""

import os
import sys
import re
import glob
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


def extract_temp_from_path(p):
    """Attempt to parse temperature in Kelvin from file or directory name."""
    dirname = os.path.basename(os.path.dirname(os.path.abspath(p)))
    fname = os.path.basename(p)
    for text in (dirname, fname):
        m = re.search(r'(\d+p\d+|\d+\.\d+|\d+)k?', text, re.IGNORECASE)
        if m:
            val_str = m.group(1).replace('p', '.')
            try:
                return float(val_str)
            except ValueError:
                pass
    return None


def animate_temp_series(files, plane, coord, out_path, fps=5, vmin=None, vmax=None, cmap="viridis"):
    if nx is None:
        raise ImportError("nexusformat is required to run animate_temp_series.py")

    nx.nxsetmemory(20000)
    
    # Map temperatures to file paths
    temp_map = {}
    for f in files:
        t = extract_temp_from_path(f)
        if t is not None:
            temp_map[t] = f

    if not temp_map:
        raise ValueError(f"Could not parse temperatures from provided files: {files}")

    sorted_temps = sorted(temp_map.keys())
    print(f"Found {len(sorted_temps)} temperature volumes from {sorted_temps[0]} K to {sorted_temps[-1]} K.")

    # Determine slice indexing
    plane = plane.upper()
    coord = float(coord)

    # Sample slices to determine global vmin/vmax
    sample_indices = [0, len(sorted_temps) // 2, -1]
    sample_slices = []
    roots = {}
    for idx in sample_indices:
        t = sorted_temps[idx]
        r = nx.nxload(temp_map[t])
        roots[t] = r
        d = r.entry.data if hasattr(r.entry, "data") else r.entry.transform
        if plane == "HK":
            s = np.asarray(d[:, :, coord].nxsignal.nxdata, dtype=np.float32)
        elif plane == "HL":
            s = np.asarray(d[:, coord, :].nxsignal.nxdata, dtype=np.float32)
        else:
            s = np.asarray(d[coord, :, :].nxsignal.nxdata, dtype=np.float32)
        sample_slices.append(s)

    pos = np.concatenate([s[s > 0] for s in sample_slices])
    if len(pos) == 0:
        pos = np.array([1.0, 10.0], dtype=np.float32)
    _vmin = float(vmin) if vmin is not None else max(1.0, float(np.nanpercentile(pos, 5)))
    _vmax = float(vmax) if vmax is not None else float(np.nanpercentile(pos, 99.8))

    # Setup initial plot
    fig, ax = plt.subplots(figsize=(6, 5), dpi=140)
    t0 = sorted_temps[0]
    r0 = roots.get(t0) or nx.nxload(temp_map[t0])
    d0 = r0.entry.data if hasattr(r0.entry, "data") else r0.entry.transform
    
    if plane == "HK":
        slice0 = np.asarray(d0[:, :, coord].nxsignal.nxdata, dtype=np.float32)
        x_coords = np.asarray(d0.nxaxes[0].nxdata)
        y_coords = np.asarray(d0.nxaxes[1].nxdata)
        x_label, y_label = r"$H$ (r.l.u.)", r"$K$ (r.l.u.)"
    elif plane == "HL":
        slice0 = np.asarray(d0[:, coord, :].nxsignal.nxdata, dtype=np.float32)
        x_coords = np.asarray(d0.nxaxes[0].nxdata)
        y_coords = np.asarray(d0.nxaxes[2].nxdata)
        x_label, y_label = r"$H$ (r.l.u.)", r"$L$ (r.l.u.)"
    else:
        slice0 = np.asarray(d0[coord, :, :].nxsignal.nxdata, dtype=np.float32)
        x_coords = np.asarray(d0.nxaxes[1].nxdata)
        y_coords = np.asarray(d0.nxaxes[2].nxdata)
        x_label, y_label = r"$K$ (r.l.u.)", r"$L$ (r.l.u.)"

    im = ax.imshow(
        slice0.T,
        origin="lower",
        extent=[x_coords[0], x_coords[-1], y_coords[0], y_coords[-1]],
        norm=LogNorm(vmin=_vmin, vmax=_vmax),
        cmap=cmap,
        aspect=1.0,
    )
    ax.set_xlabel(x_label, fontsize=11)
    ax.set_ylabel(y_label, fontsize=11)
    title_text = ax.set_title(f"Temperature Evolution: $T = {t0:.1f}$ K ({plane} at {coord:g})", fontsize=12)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="Intensity (counts)")

    def update(frame_idx):
        t = sorted_temps[frame_idx]
        r = nx.nxload(temp_map[t])
        d = r.entry.data if hasattr(r.entry, "data") else r.entry.transform
        if plane == "HK":
            s_2d = np.asarray(d[:, :, coord].nxsignal.nxdata, dtype=np.float32)
        elif plane == "HL":
            s_2d = np.asarray(d[:, coord, :].nxsignal.nxdata, dtype=np.float32)
        else:
            s_2d = np.asarray(d[coord, :, :].nxsignal.nxdata, dtype=np.float32)
        im.set_data(s_2d.T)
        title_text.set_text(f"Temperature Evolution: $T = {t:.1f}$ K ({plane} at {coord:g})")
        return [im, title_text]

    anim = FuncAnimation(fig, update, frames=len(sorted_temps), blit=True)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    writer = PillowWriter(fps=fps)
    anim.save(out_path, writer=writer)
    plt.close(fig)
    gc.collect()
    print(f"Exported temperature evolution animation: {out_path}")


def main():
    parser = argparse.ArgumentParser(description="Animate temperature series evolution of reciprocal space slice.")
    parser.add_argument("--pattern", required=True, help="Glob pattern for temperature NeXus volumes (e.g. 'FeGeSb_*/3rot*.nxs')")
    parser.add_argument("--plane", default="HK", choices=["HK", "HL", "KL"], help="Reciprocal plane (default: HK)")
    parser.add_argument("--coord", type=float, default=0.0, help="Perpendicular coordinate (e.g. 0.0)")
    parser.add_argument("--output", "-o", required=True, help="Destination GIF or MP4 path")
    parser.add_argument("--fps", type=int, default=5, help="Animation speed (fps, default: 5)")
    parser.add_argument("--cmap", default="viridis", help="Colormap (default: viridis)")

    args = parser.parse_args()
    files = sorted(glob.glob(args.pattern))
    if not files:
        print(f"No files matched pattern: {args.pattern}")
        sys.exit(1)

    animate_temp_series(
        files=files,
        plane=args.plane,
        coord=args.coord,
        out_path=args.output,
        fps=args.fps,
        cmap=args.cmap,
    )


if __name__ == "__main__":
    main()
