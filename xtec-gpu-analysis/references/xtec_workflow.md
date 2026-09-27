# XTEC-GPU Pipeline & Visualization Standards

This reference guide documents the end-to-end X-ray Temperature Clustering (XTEC-GPU) pipeline, command-line interface, discrete visualization rules, and report formatting.

---

## 1. Pipeline Overview

XTEC automates the discovery of phase transitions, charge density waves (CDWs), and order parameters in large reciprocal-space temperature series without human bias.

```text
[3D NeXus Temperature Series (I(Q, T))]
                 │
                 ▼
     [1. Preprocessing (GPU)]
     ├── Mask_Zeros (filter dead pixels)
     └── Threshold_Background (KL-divergence cutoff)
                 │
                 ▼
       [2. Model Selection]
       ├── BIC Sweep (k = 2 ... 14) Mode 'd' (Direct Voxel GMM)
       ├── BIC Sweep (k = 2 ... 14) Mode 's' (Peak-Averaged GMM)
       └── Knee / Minimum BIC Determination
                 │
                 ▼
       [3. Clustering & Reordering]
       ├── GMM Training (torchgmm, kmeans++ seed)
       └── Deterministic Reordering (descending low-T intensity)
                 │
                 ▼
       [4. Visualization & Reporting]
       ├── Discrete Reciprocal-Space Q-Map (white background)
       ├── Synchronized Trajectories & Average Intensities
       └── Comprehensive Markdown Report (absolute image paths)
```

---

## 2. CLI Usage (`xtec-gpu`)

The package provides terminal-driven subcommands mirroring the NeXpy plugin:

```bash
# 1. Direct voxel clustering (Mode d)
PYTHONPATH=src /nfs/chess/sw/qm2_XTEC312/bin/xtec-gpu xtec-d data.nxs -o results/ -n 13 --rescale mean

# 2. Peak-averaged clustering (Mode s)
PYTHONPATH=src /nfs/chess/sw/qm2_XTEC312/bin/xtec-gpu xtec-s data.nxs -o results/ -n 13

# 3. BIC sweeps for model selection
PYTHONPATH=src /nfs/chess/sw/qm2_XTEC312/bin/xtec-gpu bic-d data.nxs -o bic_d/ --min-nc 2 --max-nc 14
PYTHONPATH=src /nfs/chess/sw/qm2_XTEC312/bin/xtec-gpu bic-s data.nxs -o bic_s/ --min-nc 2 --max-nc 14
```

---

## 3. Visualization Standards

### 3.1 Reciprocal-Space Q-Map (`qmap.png`)

- **Palette**: Discrete qualitative colormap. Never use continuous colormaps like `viridis`, `plasma`, or `jet`.
- **Background**: Pixels not assigned to any cluster (or below threshold) must be rendered **pure white or transparent**.
  ```python
  import matplotlib.colors as mcolors
  import numpy as np

  cluster_colors = _get_cluster_colors(nc)
  cmap = mcolors.ListedColormap(cluster_colors)
  cmap.set_bad(color="white", alpha=0.0)

  boundaries = np.arange(0.5, nc + 1.5, 1.0)
  norm = mcolors.BoundaryNorm(boundaries, cmap.N)

  # cluster_image is initialized to np.nan
  im = ax.imshow(slice_2d, origin="lower", cmap=cmap, norm=norm, extent=extent)
  cbar = plt.colorbar(im, ax=ax, ticks=np.arange(1, nc + 1), label="Cluster ID")
  cbar.ax.set_yticklabels([str(k) for k in range(1, nc + 1)])
  ```
- **Physical Extent**: Always pass `extent=[H_min, H_max, K_min, K_max]` and label axes with reciprocal lattice units (e.g. `H (r.l.u.)`, `K (r.l.u.)`) and slice level (e.g. `L = 0.50`).

### 3.2 Temperature Trajectories (`trajectories.png`)

- **Color Synchronization**: The color of Cluster $k$ in the trajectory plot must match Cluster $k$ in the Q-map.
- **Legend Layout**: When $k > 5$, anchor the legend outside the axes:
  ```python
  ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left")
  ```

---

## 4. Re-Plotting Existing Outputs

When visualization styles are updated, existing `results.h5` files can be re-rendered without re-running the heavy GMM EM training loop using `scripts/replot_figures.py`.

```python
import h5py
from xtec_gpu.xtec_cli import _plot_qmap, _plot_trajectories, _plot_avg_intensities

with h5py.File("results.h5", "r") as f:
    cluster_assigns = f["cluster_assignments"][:]
    pixel_assigns = f["pixel_assignments"][:]
    Data_ind = f["data_indices"][:]
    cluster_means = f["cluster_means"][:]
    cluster_covs = f["cluster_covariances"][:]
    Data_thresh = f["data_thresholded"][:]

nc = len(cluster_means)
_plot_qmap(data, Data_ind, pixel_assigns, nc, output_dir)
_plot_trajectories(data, cluster_means, cluster_covs, nc, "mean", output_dir)
_plot_avg_intensities(data, Data_thresh, cluster_assigns, nc, output_dir)
```

---

## 5. Report Integrity & Absolute Image Linking

When maintaining `report.md`:
- **Never use relative image links** (e.g. `./workflow_runs/...`), because reports symlinked at the workspace root or viewed in separate tools will break.
- **Always use absolute paths**:
  ```markdown
  ![Reciprocal Space Q-Map](/home/sgomezalvarado/XTEC_CUDA/benchmark_test/workflow_runs/srn0_benchmark/final_run/xtec_d/qmap.png)
  ```
- **Map Indices**: Provide a clear table cross-referencing 1-indexed plot labels (`Cluster 1` to `Cluster K`) with 0-indexed HDF5 datasets in `results.h5`.
