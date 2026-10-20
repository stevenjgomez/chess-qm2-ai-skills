---
name: reciprocal-space-animation
description: >-
  Generate high-quality dynamic animations (GIF, MP4) of 3D reciprocal space X-ray
  and neutron diffraction datasets (NeXus/HDF5). Use when generating volumetric axis
  scans (scrolling through L, H, or K slices), animating temperature-series evolution
  across phase transitions, managing headless rendering memory leaks, or exporting
  animated figures for presentations and reports.
---

# Reciprocal Space Animation Skill (`reciprocal-space-animation`)

This skill provides operational standards, memory management protocols, and copy-paste-ready recipes for animating 3D reciprocal space volumes and temperature series into GIF or MP4 media using `matplotlib.animation` or `imageio`.

---

## 1. Golden Rules of Animation Generation

1. **Memory Leak Prevention (`gc.collect()` & Frame Re-use)**:
   Generating a 50–200 frame animation can rapidly consume gigabytes of memory if new `Figure` or `Axes` objects are instantiated per frame.
   - **Mandatory Pattern**: Instantiate `fig, ax, im` **once**, and update `im.set_data(...)` and text labels dynamically in the animation loop.
   - Explicitly call `plt.close(fig)` and `gc.collect()` immediately after saving.
2. **Lazy Slice Extraction**:
   Do not load the entire 3D volume into an eager 3D NumPy array prior to animation. Read each 2D slice hyperslab lazily inside the generator:
   ```python
   # Reads only the current 2D plane from disk per frame:
   slice_data = np.asarray(data[:, :, l_val].nxsignal.nxdata, dtype=np.float32)
   ```
3. **Fixed Global Normalization Across All Frames**:
   Dynamic re-normalization per frame causes distracting intensity flickering.
   - Sample 3–5 representative slices (e.g. at 10%, 50%, and 90% of the volume) to establish global `vmin` and `vmax` bounds *before* starting the animation.
4. **Clean Headless Backends**:
   Always set `matplotlib.use("Agg")` prior to importing `pyplot`.
5. **Animation Media Optimization**:
   - For **Markdown / Web / Artifacts**: Export animated GIFs using `Pillow` writer with `fps = 10 - 15` and `dpi = 120 - 150`.
   - For **Presentations / Large Datasets**: Export MP4 using `ffmpeg` writer with `bitrate = 1800`.

---

## 2. Recipes

### Recipe 1: Volume Axis Scanning (Scrolling along $L$)

```python
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from matplotlib.animation import FuncAnimation, PillowWriter
import numpy as np
import nexusformat.nexus as nx
import gc

def animate_l_scan(nxs_path, out_gif, fps=12, stride=2):
    nx.nxsetmemory(20000)
    root = nx.nxload(nxs_path)
    data = root.entry.data

    # Coordinate array along L (axis 2 in Legacy CHESS [H, K, L])
    l_coords = np.asarray(data.nxaxes[2].nxdata)[::stride]
    h_axis = np.asarray(data.nxaxes[0].nxdata)
    k_axis = np.asarray(data.nxaxes[1].nxdata)

    # 1. Establish robust global vmin and vmax from sample slices
    sample_indices = [len(l_coords) // 4, len(l_coords) // 2, 3 * len(l_coords) // 4]
    sample_slices = [np.asarray(data[:, :, l_coords[idx]].nxsignal.nxdata, dtype=np.float32) for idx in sample_indices]
    pos = np.concatenate([s[s > 0] for s in sample_slices])
    vmin = max(1.0, float(np.nanpercentile(pos, 5)))
    vmax = float(np.nanpercentile(pos, 99.8))

    # 2. Setup figure once
    fig, ax = plt.subplots(figsize=(6, 5), dpi=140)
    
    # Initialize with first frame
    initial_slice = np.asarray(data[:, :, l_coords[0]].nxsignal.nxdata, dtype=np.float32)
    im = ax.imshow(
        initial_slice.T,
        origin="lower",
        extent=[h_axis[0], h_axis[-1], k_axis[0], k_axis[-1]],
        norm=LogNorm(vmin=vmin, vmax=vmax),
        cmap="viridis",
        aspect=1.0,
    )
    ax.set_xlabel(r"$H$ (r.l.u.)")
    ax.set_ylabel(r"$K$ (r.l.u.)")
    title_text = ax.set_title(f"$(HKL)$ Volume Scan: $L = {l_coords[0]:.2f}$ r.l.u.")
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Intensity (counts)")

    # 3. Update function
    def update(frame_idx):
        l_val = l_coords[frame_idx]
        slice_2d = np.asarray(data[:, :, l_val].nxsignal.nxdata, dtype=np.float32)
        im.set_data(slice_2d.T)
        title_text.set_text(f"$(HKL)$ Volume Scan: $L = {l_val:.2f}$ r.l.u.")
        return [im, title_text]

    # 4. Render and export
    anim = FuncAnimation(fig, update, frames=len(l_coords), blit=True)
    writer = PillowWriter(fps=fps)
    anim.save(out_gif, writer=writer)
    plt.close(fig)
    gc.collect()
    print(f"Exported volume scan animation: {out_gif}")
```

---

### Recipe 2: Temperature Series Evolution Animation

```python
import os
import glob
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from matplotlib.animation import FuncAnimation, PillowWriter
import numpy as np
import nexusformat.nexus as nx
import gc

def animate_temp_series(temp_files_dict, out_gif, plane="HK", coord=0.0, fps=5):
    """
    temp_files_dict: dict mapping float(temperature_K) -> file_path
    plane: 'HK', 'HL', or 'KL'
    """
    sorted_temps = sorted(temp_files_dict.keys())
    
    # Pre-load coordinate arrays and measure global intensity bounds
    roots = {t: nx.nxload(temp_files_dict[t]) for t in sorted_temps}
    
    sample_slices = []
    for t in sorted_temps[::max(1, len(sorted_temps) // 3)]:
        data = roots[t].entry.data
        sample_slices.append(np.asarray(data[:, :, coord].nxsignal.nxdata, dtype=np.float32))
    pos = np.concatenate([s[s > 0] for s in sample_slices])
    vmin = max(1.0, float(np.nanpercentile(pos, 5)))
    vmax = float(np.nanpercentile(pos, 99.8))

    # Initialize plot
    fig, ax = plt.subplots(figsize=(6, 5), dpi=140)
    data0 = roots[sorted_temps[0]].entry.data
    slice0 = np.asarray(data0[:, :, coord].nxsignal.nxdata, dtype=np.float32)
    h_axis = np.asarray(data0.nxaxes[0].nxdata)
    k_axis = np.asarray(data0.nxaxes[1].nxdata)

    im = ax.imshow(
        slice0.T,
        origin="lower",
        extent=[h_axis[0], h_axis[-1], k_axis[0], k_axis[-1]],
        norm=LogNorm(vmin=vmin, vmax=vmax),
        cmap="viridis",
        aspect=1.0,
    )
    ax.set_xlabel(r"$H$ (r.l.u.)")
    ax.set_ylabel(r"$K$ (r.l.u.)")
    title_text = ax.set_title(f"Temperature Evolution: $T = {sorted_temps[0]:.1f}$ K")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="Intensity (counts)")

    def update(frame_idx):
        t = sorted_temps[frame_idx]
        s = np.asarray(roots[t].entry.data[:, :, coord].nxsignal.nxdata, dtype=np.float32)
        im.set_data(s.T)
        title_text.set_text(f"Temperature Evolution: $T = {t:.1f}$ K")
        return [im, title_text]

    anim = FuncAnimation(fig, update, frames=len(sorted_temps), blit=True)
    anim.save(out_gif, writer=PillowWriter(fps=fps))
    plt.close(fig)
    gc.collect()
    print(f"Exported temperature evolution animation: {out_gif}")
```

---

## 3. Standalone CLI Reference Scripts

This skill includes standalone CLI tools in [`scripts/`](./scripts/):

1. **`animate_volume.py`**:
   ```bash
   python scripts/animate_volume.py --nxs path/to/volume.nxs --axis L --stride 2 --fps 12 --output scroll_L.gif
   ```
2. **`animate_temp_series.py`**:
   ```bash
   python scripts/animate_temp_series.py --dir path/to/sample_dir --file-pattern "*hkli*.nxs" --plane HK --coord 0.0 --output temp_evolution.gif
   ```

---

## 4. Sister Skills & Integration

- For **Static 2D Slices & 3-Panel Summaries**: Consult [`reciprocal-space-plotting`](../reciprocal-space-plotting/SKILL.md).
- For **1D Linecuts with Scissors**: Consult [`reciprocal-space-linecuts`](../reciprocal-space-linecuts/SKILL.md).
- For **Batch Temperature Operations**: Consult [`temperature-series-analysis`](../temperature-series-analysis/SKILL.md).
