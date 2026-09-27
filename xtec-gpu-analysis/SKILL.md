---
name: xtec-gpu-analysis
description: >-
  Execute and analyze X-ray and neutron scattering temperature-series datasets using
  GPU-accelerated X-ray Temperature Clustering (XTEC-GPU) with PyTorch and torchgmm.
  Enforces CLASSE/CHESS remote cluster node etiquette, distinguishing between regular
  CPU nodes (e.g. lnx308) and dedicated CUDA GPU nodes (e.g. lnx4428), non-interactive SSH
  execution, discrete reciprocal-space Q-map visualization, and automated Markdown reporting.
---

# XTEC-GPU Analysis & Cluster Execution Skill

This skill provides operational procedures, node separation rules, environment configurations, and visualization standards for running GPU-accelerated X-ray Temperature Clustering (`XTEC-GPU`) on CHESS/CLASSE computing infrastructure.

---

## 1. Remote Cluster Node Topology & Etiquette

Always strictly distinguish between the three classes of machines:

| Node Role | Host | Purpose & Hardware | Execution Rule |
| :--- | :--- | :--- | :--- |
| **Login Node** | `lnx201` | Shell management, file editing, git, job dispatch. **No GPU.** | **NEVER run compute**, heavy data loading, or model training here. |
| **Regular CPU Node** | `lnx308` | Regular data reduction, `nxs_analysis_tools`, 3D rotations, PDF compilation. | Use for CPU-bound "usual scripts". Python: `/nfs/chess/sw/anaconda3_sgomezalvarado_nightly/bin/python`. |
| **CUDA GPU Node** | `lnx4428` | Heavy ML/clustering, PyTorch, `torchgmm`, GPU preprocessing. **NVIDIA Titan RTX (24 GB VRAM).** | **Exclusively use for XTEC-GPU workflows.** Python: `/nfs/chess/sw/qm2_XTEC312/bin/python`. |

*Detailed reference:* [Cluster Topology & Execution Guide](./references/cluster_topology.md)

---

## 2. Python Environments & Execution Pattern

- **Do NOT use** `/nfs/chess/sw/qm2_XTEC/bin/python` (Python 3.9, which crashes on PEP 604 type unions `X | Y`).
- **Always use** the dedicated CUDA environment:
  ```bash
  PYTHON="/nfs/chess/sw/qm2_XTEC312/bin/python"
  ```
- **Remote Execution Command**:
  Execute remotely from `lnx201` via non-interactive SSH with `BatchMode=yes`:
  ```bash
  ssh -o BatchMode=yes lnx4428 "PYTHONPATH=/path/to/XTEC-GPU/src /nfs/chess/sw/qm2_XTEC312/bin/python <script>.py"
  ```
- **Agent Sandbox Rule**: Always specify `BypassSandbox: true` when running SSH commands to remote compute nodes.
- **Grid Engine Note**: `qstat -F cuda_free` reports $\le 0$ on `lnx4428` due to load sensor issues; direct SSH execution is approved and avoids queue deadlocks.

---

## 3. End-to-End XTEC Workflow Pipeline

1. **Preprocessing**:
   - `Mask_Zeros`: Filters dead pixels / detector gaps.
   - `Threshold_Background`: KL-divergence background thresholding isolates peaks and fluctuation regions from noise.
   - `Peak_averaging`: Identifies connected Bragg peaks in reciprocal space for mode `s`.
2. **Model Selection (BIC Sweeps)**:
   - Sweep cluster count $k \in [2, 14]$ for candidate modes:
     - **Mode `d`** (`xtec-d`): Direct voxel clustering via GPU GMM (`torchgmm`).
     - **Mode `s`** (`xtec-s`): Peak-averaged clustering mapped back to voxel space.
   - Select winner based on BIC minimum and knee analysis.
3. **Clustering & Deterministic Ordering**:
   - Train Gaussian Mixture Model using `kmeans++` initialization.
   - Sort clusters deterministically by low-temperature intensity so Cluster 1 is always the highest-intensity low-$T$ feature (superlattice/order parameter).

*Detailed reference:* [XTEC Workflow Guide](./references/xtec_workflow.md)

---

## 4. Visualization & Reporting Standards

1. **Reciprocal-Space Q-Map**:
   - **Discrete Colors**: Use `matplotlib.colors.ListedColormap` with qualitative palettes (`tab10` / `tab20`). Never use continuous colormaps like `viridis`.
   - **White/Transparent Background**: Initialized with `np.nan` and `cmap.set_bad(color="white", alpha=0.0)`. Unclustered/background voxels must render pure white or transparent.
   - **Discrete Colorbar**: Centered ticks matching cluster IDs $1, 2, \dots, K$ (`BoundaryNorm` with bins $[0.5, 1.5, \dots, K+0.5]$).
   - **Calibrated Axes**: Inherit physical reciprocal lattice coordinates ($H, K$ in r.l.u.) and slice title (e.g. $L = 0.50$).
2. **Trajectory & Intensity Plots**:
   - **Palette Synchronization**: Exactly match the discrete colors used in the Q-map.
   - **Legend Positioning**: Place legends outside the plot area (`bbox_to_anchor=(1.02, 1), loc="upper left"`) so curves are never obscured.
3. **Automated Markdown Reporting (`report.md`)**:
   - **Absolute Image Paths**: Always use absolute paths (e.g. `![Q-map](/home/sgomezalvarado/...)`) because reports symlinked at workspace roots break when using relative paths.
   - **Cross-Referenced Tables**: Map 1-indexed plot labels (`Cluster 1` to `Cluster K`) to 0-indexed HDF5 datasets in `results.h5`.
