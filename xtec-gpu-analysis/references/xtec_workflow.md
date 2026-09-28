# XTEC-GPU Pipeline & Visualization Standards

This reference guide documents the end-to-end X-ray Temperature Clustering (XTEC-GPU) pipeline, 4D dataset compilation via `to_xtec()`, command-line interface, discrete visualization rules, and report formatting.

---

## 1. Pipeline Overview

XTEC automates the discovery of phase transitions, charge density waves (CDWs), and order parameters in large reciprocal-space temperature series without human bias.

```text
[3D NeXus Series across Temperatures]
                 │
                 ▼
  [Phase 0: 4D Dataset Compilation (Interactive CPU qrsh)]
  ├── TempDependence.find_temperatures()
  ├── TempDependence.load_datasets() (auto-detect NXRefine vs CHESS)
  └── TempDependence.to_xtec() -> xtec_data.nxs
                 │
                 ▼
      [Phase 1: Preprocessing (GPU via qsub -l cuda_free=1)]
      ├── Mask_Zeros (filter dead pixels)
      └── Threshold_Background (KL-divergence cutoff)
                 │
                 ▼
      [Phase 2: Model Selection (GPU via qsub -l cuda_free=1)]
      ├── BIC Sweep (k = 2 ... 14) Mode 'd' (Direct Voxel GMM)
      ├── BIC Sweep (k = 2 ... 14) Mode 's' (Peak-Averaged GMM)
      └── Knee / Minimum BIC Determination
                 │
                 ▼
      [Phase 3: Clustering & Reordering (GPU via qsub -l cuda_free=1)]
      ├── GMM Training (torchgmm, kmeans++ seed)
      └── Deterministic Reordering (descending low-T intensity)
                 │
                 ▼
      [Phase 4: Visualization & Reporting]
      ├── Discrete Reciprocal-Space Q-Map (pure white background)
      ├── Synchronized Trajectories & Average Intensities
      └── Comprehensive Markdown Report (absolute image paths)
```

---

## 2. Phase 0: Compiling 4D Datasets via `to_xtec()`

XTEC-GPU algorithms require a 4D `NXdata` structure:
- **Axis 0**: Temperature (`Te` in K).
- **Axes 1–3**: Spatial reciprocal lattice coordinates (`Qh, Qk, Ql` or `H, K, L`).

### 2.1 Automated Helper Script (`scripts/generate_xtec_input.py`)

Run the bundled utility in an interactive session (`qrsh -q interactive.q -l mem_free=350G` from `lnx201`):

```bash
# Auto-detects format (NXRefine or Legacy CHESS) and writes xtec_data.nxs
/nfs/chess/sw/anaconda3_sgomezalvarado_nightly/bin/python \
  $HOME/.gemini/config/skills/xtec-gpu-analysis/scripts/generate_xtec_input.py \
  --sample-dir /path/to/sample \
  --output /path/to/sample/xtec_data.nxs
```

#### CLI Flags:
- `--sample-dir` / `-s`: Root directory of sample containing temperature files or subdirectories.
- `--output` / `-o`: Destination `.nxs` file (defaults to `<sample-dir>/xtec_data.nxs`).
- `--file-ending` / `-e`: Explicit pattern for legacy CHESS (e.g. `1rot_hkli.nxs`, `3rot_hkli.nxs`).
- `--temperatures` / `-t`: Filter specific temperatures (e.g. `--temperatures "111,116,281"`).
- `--exclude-temperatures` / `-x`: Exclude anomalous temperatures.
- `--force` / `-f`: Overwrite existing output file (disabled by default for data safety).

### 2.2 Programmatic Usage in Python

#### A. NXRefine Datasets
Top-level `*_<temp>.nxs` files pointing via `NXlink` to `<temp>/transform.nxs`:
```python
from nxs_analysis_tools.chess import TempDependence

td = TempDependence("/path/to/sample_dir")
td.find_temperatures()
# Pre-validates candidate folders and loads via lazy NXlinks
td.load_datasets(use_nxlink=True, print_tree=False)
td.to_xtec(filepath="/path/to/sample_dir/xtec_data.nxs", overwrite=False)
```

#### B. Legacy CHESS Datasets
Subdirectories named `<temp>/` containing `*1rot_hkli.nxs` or `*3rot_hkli.nxs`:
```python
from nxs_analysis_tools.chess import TempDependence

td = TempDependence("/path/to/sample_dir")
td.find_temperatures()
# Auto-detects legacy CHESS folders and matches specified file ending
td.load_datasets(file_ending="1rot_hkli.nxs", print_tree=False)
td.to_xtec(filepath="/path/to/sample_dir/xtec_data.nxs", overwrite=False)
```

### 2.3 Verifying the Generated NeXus File

Inspect the compiled file using `nexusformat`:
```python
import nexusformat.nexus as nx

root = nx.nxload("/path/to/sample_dir/xtec_data.nxs")
data = root['entry']['data']

print("Signal shape:", data.nxsignal.shape)  # e.g. (15, 201, 201, 151) -> (T, Qh, Qk, Ql)
print("Axes:", [ax.nxname for ax in data.nxaxes])  # ['Te', 'Qh', 'Qk', 'Ql']
print("Temperatures (K):", data['Te'].nxdata)
```

---

## 3. Autonomous GPU Batch Execution (`qsub -l cuda_free=1`)

Once `xtec_data.nxs` is available, submit the autonomous clustering job to the Grid Engine GPU queue on `lnx4428`:

```bash
qsub -l cuda_free=1 example_job_scripts/xtec-gpu-clustering.sh
```

### 3.1 Autonomous Pipeline Inside the SGE Job
To avoid holding and releasing GPU allocations or requiring manual human intervention between model selection and clustering, the job script executes an integrated sequence:

```bash
# 1. BIC model selection sweep with streamed preprocessing
/nfs/chess/sw/qm2_XTEC312/bin/xtec-gpu bic-d data.nxs \
  -o results/bic_d/ \
  --streamed-preprocess \
  --min-nc 2 \
  --max-nc 14

# 2. Autonomous k* determination (locating global minimum of the BIC curve)
BEST_K=$(/nfs/chess/sw/qm2_XTEC312/bin/python -c "
import h5py, numpy as np
with h5py.File('results/bic_d/bic_xtec_d.h5', 'r') as f:
    ks = f['n_clusters'][...].astype(int)
    bics = f['bic_scores'][...].astype(float)
best_k = int(ks[np.argmin(bics)])
print(best_k)
")

# 3. Final GMM clustering using optimal k* with deterministic reordering
/nfs/chess/sw/qm2_XTEC312/bin/xtec-gpu xtec-d data.nxs \
  -o results/xtec_d_k${BEST_K}/ \
  --streamed-preprocess \
  -n ${BEST_K} \
  --rescale mean \
  --reorder-clusters
```

### 3.2 Standalone CLI Subcommands
When executing individual stages or testing specific parameters:

```bash
# Standalone BIC sweep (Mode d)
/nfs/chess/sw/qm2_XTEC312/bin/xtec-gpu bic-d data.nxs -o bic_d/ --streamed-preprocess --min-nc 2 --max-nc 14

# Standalone BIC sweep (Mode s with peak averaging)
/nfs/chess/sw/qm2_XTEC312/bin/xtec-gpu bic-s data.nxs -o bic_s/ --streamed-preprocess --min-nc 2 --max-nc 14

# Standalone direct clustering (Mode d) with known k
/nfs/chess/sw/qm2_XTEC312/bin/xtec-gpu xtec-d data.nxs -o results/ --streamed-preprocess -n 4 --rescale mean --reorder-clusters

# Standalone peak-averaged clustering (Mode s) with known k
/nfs/chess/sw/qm2_XTEC312/bin/xtec-gpu xtec-s data.nxs -o results/ --streamed-preprocess -n 4 --reorder-clusters
```

---

## 4. Visualization Standards

### 4.1 Reciprocal-Space Q-Map (`qmap.png`)

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

### 4.2 Temperature Trajectories (`trajectories.png`)

- **Color Synchronization**: The color of Cluster $k$ in the trajectory plot must match Cluster $k$ in the Q-map.
- **Legend Layout**: When $k > 5$, anchor the legend outside the axes:
  ```python
  ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left")
  ```

---

## 5. Report Integrity & Absolute Image Linking

When maintaining `report.md`:
- **Never use relative image links** (e.g. `./workflow_runs/...`), because reports symlinked at the workspace root or viewed in separate tools will break.
- **Always use absolute paths**:
  ```markdown
  ![Reciprocal Space Q-Map](/path/to/results/xtec_d/qmap.png)
  ```
- **Map Indices**: Provide a clear table cross-referencing 1-indexed plot labels (`Cluster 1` to `Cluster K`) with 0-indexed HDF5 datasets in `results.h5`.

---

## 6. Mandatory Data Safety Policy

> [!CAUTION]
> **NEVER delete any `.nxs` files**. If a file already exists, reuse it or use non-destructive suffixing (`xtec_data_1.nxs`). Never issue `rm` or `os.remove` on any `.nxs` file.
