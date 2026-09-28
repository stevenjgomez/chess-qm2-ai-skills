---
name: reciprocal-space-analysis
description: >-
  Analyze, reconstruct, index, align, and compare 3D reciprocal space X-ray
  and neutron diffraction datasets (NeXus/HDF5) using nxs_analysis_tools.
  Use when processing synchrotron reciprocal space volumes, performing hexagonal
  or non-orthogonal lattice transformations, overlaying reflections under skew
  projections, comparing multi-dataset linecuts and animations, or executing
  heavy data pipelines on remote compute clusters.
---

# 3D Reciprocal Space Analysis & Visualization Skill

This skill provides comprehensive guidelines, mathematical formulas, and operational best practices for analyzing, indexing, comparing, and visualizing 3D reciprocal space diffraction datasets (e.g., from CHESS ID4B/QM2 beamlines or similar synchrotron/neutron facilities) using `nxs_analysis_tools`.

---

## 1. Upstream AI Skills & Dynamic Documentation Links

The canonical, authoritative reference skills for `nxs_analysis_tools` and general reciprocal space data analysis are hosted on GitHub in the [`nxs_analysis_tools`](https://github.com/stevenjgomez/nxs_analysis_tools) repository on the `main` branch. Always consult these dynamic upstream resources for the latest schema updates and analysis workflows:

- **NeXus & CHESS Data Formats Skill**:
  [`https://github.com/stevenjgomez/nxs_analysis_tools/blob/main/.agents/skills/nexus-chess-formats/SKILL.md`](https://github.com/stevenjgomez/nxs_analysis_tools/blob/main/.agents/skills/nexus-chess-formats/SKILL.md)
  *(Covers file layouts, lazy vs. eager HDF5 loading, plane vs. axis slicing, temperature normalization, and 4D XTEC export.)*
- **Notebook Tutorials Workflow Skill**:
  [`https://github.com/stevenjgomez/nxs_analysis_tools/blob/main/.agents/skills/notebook-tutorials/SKILL.md`](https://github.com/stevenjgomez/nxs_analysis_tools/blob/main/.agents/skills/notebook-tutorials/SKILL.md)
  *(Covers safe programmatic editing with `nbformat`, built-in Pooch datasets, Sphinx/myst-nb execution, and headless testing.)*
- **Repository Guidelines & Rules**:
  [`https://github.com/stevenjgomez/nxs_analysis_tools/blob/main/GEMINI.md`](https://github.com/stevenjgomez/nxs_analysis_tools/blob/main/GEMINI.md)
  *(Covers testing conventions, git branching from `main`, commit trailers, and release workflows.)*
- **Official Documentation**:
  [`https://nxs-analysis-tools.readthedocs.io/en/stable/`](https://nxs-analysis-tools.readthedocs.io/en/stable/)

---

## 2. Remote Cluster Etiquette & Execution Modes

Per [`GEMINI.md`](../GEMINI.md), all remote Python and Conda environments on CLASSE are **strictly read-only / immutable**. Never run `pip install` or modify environment configurations.

1. **Compute Nodes vs. Login Node**:
   - **Login node (`lnx201`)**: Text editing, job submission, git operations, and lightweight monitoring only. Computing, array manipulation, or figure rendering on `lnx201` is strictly forbidden.
   - **Interactive Analysis Sessions (Mandatory `qrsh` for Humans)**:
     Downstream reciprocal space data analysis using `nxs_analysis_tools` (generating 2D slices with `plot_slice()`, 1D linecuts with `Scissors`, order parameter calculations, skew transformations, and LaTeX summary report compilation) must follow the cluster interactive protocol:
     1. Login to `lnx201.classe.cornell.edu`
     2. Request an interactive shell allocation:
        ```bash
        qrsh -q interactive.q -l mem_free=350G
        ```
     3. Execute analysis using `/nfs/chess/sw/anaconda3_sgomezalvarado_nightly/bin/python`. Do not SSH directly into nodes like `lnx308`.
   - **Automated / Agentic Sessions (Mandatory `qsub` Batch Submission)**:
     In unattended automated sessions over SSH, `qrsh` prompts for Kerberos passwords (`Password for <user>@CLASSE.CORNELL.EDU:`), causing unattended scripts to hang. Automated agents must submit short-lived SGE batch wrappers via `qsub` (200 GB RAM, AVX2 pool) and stream stdout/stderr via `tail -f <log>`.
2. **Data Reduction vs. Data Analysis Execution Policy**:
   - **Raw Data Reduction Pipeline** (stacking raw CBF frames, ORM basinhopping solving, 3D reciprocal conversion): Heavy, long-running ($>30$ minutes), memory-intensive ($>100\text{ GB}$). Must be submitted via Grid Engine:
     ```bash
     qsub -q 'all.q@lnx307*,all.q@lnx311*,all.q@lnx312*,all.q@lnx313*' -l mem_free=200G -pe sge_pe 32 <job>.sh
     ```
   - **Downstream Data Analysis** (`nxs_analysis_tools`): Fast, operates on already-converted volumes with lazy loading ($O(1)$ RAM). Executed inside interactive `qrsh` sessions or short batch jobs.
3. **Mandatory "Show-Before-Submit" Verification Gate**:
   - Prior to executing `qsub <job_script>.sh` for any task, the assistant MUST present the complete script text to the user, highlighting queue targets, memory requests, slot allocations, environment path, and CLI invocation. The user must provide confirmation before the job is submitted.
4. **Headless Execution**:
   - Always invoke `matplotlib.use("Agg")` before importing `matplotlib.pyplot`.
5. **Automated LaTeX Summaries**:
   - Automatically compile generated figures into PDF reports using `/usr/bin/pdflatex -interaction=nonstopmode <file>.tex`.
6. **Strict Data Safety: NEVER Delete Any `.nxs` Files**:
   - > [!CAUTION]
   - > **Mandatory Data Protection Policy**: Under no circumstances should the agent or user delete, remove (`os.remove`, `rm`), or overwrite any `.nxs` files (`transform.nxs`, `*hkli*.nxs`, `stack*.nxs`, etc.). Re-runs and transformations must always generate newly suffixed files (`_1.nxs`, `_2.nxs`) rather than removing prior datasets.

---

## 3. Core Data Analysis Principles (`nxs_analysis_tools`)

### 3.1 Lazy Loading Mechanics in `nexusformat`
- **Avoid Out-of-Memory (OOM) Errors**: `nexusformat.nexus.nxload(path)` traverses the file structure without loading underlying arrays into RAM ($O(1)$ memory).
- **The `.nxdata` Trap**: Accessing `.nxdata` forces an **eager read** of the entire 1–2+ GB volume per temperature into memory. **Never access `.nxdata` directly on full volumes.**
- **Hyperslab Slicing**: Slicing with `data[slice_obj]` reads *only* the requested 2D or 1D hyperslab directly from disk via HDF5 chunking.
- **NXRefine Datasets**: Always load with `use_nxlink=True` (default in `load_transform` and `load_datasets`) so that `root.entry.transform` retains the `NXlink` pointer. Setting `use_nxlink=False` forces an eager `.nxdata.transpose(2, 1, 0)`.
- **Legacy CHESS Datasets**: Datasets loaded via `load_data()` return `g.entry.data` and are natively lazy.
- **NeXus Slab Limit**: Raise the memory limit upon import:
  ```python
  import nexusformat.nexus as nx
  nx.nxsetmemory(20000)  # 20 GB (sufficient for 2D slicing/linecuts; use 100000 for 3D reconstruction)
  ```

### 3.2 Array Axes vs. Reciprocal Space Planes: Format Comparison
A reciprocal lattice plane is defined by **fixing the coordinate perpendicular to the plane**:
- **$HK$ Plane**: Hold $L$ ($Q_l$) constant. Free axes are $H, K$.
- **$HL$ Plane**: Hold $K$ ($Q_k$) constant. Free axes are $H, L$.
- **$KL$ Plane**: Hold $H$ ($Q_h$) constant. Free axes are $K, L$.

Because NXRefine and Legacy CHESS data structures use different axis ordering conventions, slice axes and `Scissors` coordinate orders differ:

| Format | Dataset Axes | $HK$ Slice ($L=\text{const}$) | $HL$ Slice ($K=\text{const}$) | $KL$ Slice ($H=\text{const}$) | `Scissors` Tuple Order |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **NXRefine** (`use_nxlink=True`) | `['Ql', 'Qk', 'Qh']` (shape `(N_l, N_k, N_h)`) | Axis 0 (`data[0.0, :, :]`) | Axis 1 (`data[:, 0.0, :]`) | Axis 2 (`data[:, :, 0.0]`) | `(L, K, H)` |
| **Legacy CHESS** (`hkli.nxs`) | `['H', 'K', 'L']` (shape `(N_h, N_k, N_l)`) | Axis 2 (`data[:, :, 0.0]`) | Axis 1 (`data[:, 0.0, :]`) | Axis 0 (`data[0.0, :, :]`) | `(H, K, L)` |

> [!WARNING]
> In NXRefine, fixing Axis 2 ($Q_h = 0.0$) eliminates $H$ and yields the **$KL$ plane**, NOT the $HK$ plane! Conversely, in Legacy CHESS, fixing Axis 0 ($H = 0.0$) eliminates $H$ and yields the **$KL$ plane**. Always check `data.nxaxes` before slicing!
>
> **Pipeline Architecture Detection**: Samples are structured as `{sample_name}/{sample_id}/`. Always inspect the specific sample leaf `/nfs/chess/id4baux/{cycle}/{experiment}/{pipeline}/{sample_name}/{sample_id}/`. A material (e.g. `FeTe2/`) can exist under *both* `nxrefine/` and `processed_old_way/` if different sample mounts were reduced with different workflows.

### 3.3 Float vs. Integer Indexing
`nexusformat.nexus.NXdata` strictly distinguishes between integer and float indices:
- **Integer index** (`data[:, 0, :]`): Selects the **0th array element** along that axis (e.g. minimum bound $K = -3.0$).
- **Float index** (`data[:, 0.0, :]`): Queries the **physical reciprocal space coordinate** ($K = 0.0$).
- **Rule**: Always use float literals (`0.0`, `1.5`) when selecting reciprocal cuts.

### 3.4 Scissors & Linecut Coordinates
`Scissors.cut_data()` maps coordinates positionally to `data.nxaxes`:
- **For NXRefine** (`['Ql', 'Qk', 'Qh']`), `center` and `window` tuples must follow **$(L, K, H)$** order:
  ```python
  # center and window ordered as (L, K, H):
  scissors.cut_data(center=(0.0, 0.0, -0.5), window=(0.2, 0.2, 0.25))
  ```
- **For Legacy CHESS** (`['H', 'K', 'L']`), `center` and `window` tuples must follow **$(H, K, L)$** order:
  ```python
  # center and window ordered as (H, K, L):
  scissors.cut_data(center=(-0.5, 0.0, 0.0), window=(0.25, 0.2, 0.2))
  ```

### 3.5 Temperature Series Discovery & Normalization
- Temperature keys can appear as integers (`15`), floats (`15.5`), or filesystem string notation (`'15p5'`).
- `TempDict` provides transparent polymorphic access:
  ```python
  td.datasets[15.5] == td.datasets['15.5'] == td.datasets['15p5']
  ```
- **Discovery**: Always discover temperatures dynamically using `sample.find_temperatures()`.
- **Loading**: Use `sample.load_datasets(temperatures=[...])`.

### 3.6 Colormaps, LogNorm & True Physical Aspect Ratio Calibration
- **LogNorm Cutoffs**: In `plot_slice(..., logscale=True)`, set `vmin > 0` (e.g. `vmin=1, vmax=1e4`) to avoid `LogNorm` errors on zero or negative masked counts.
- **Lattice Skew**: For non-orthogonal / hexagonal systems (`@angles = [60.0, 90.0, 90.0]`), set `skew_angle=gamma_star` (e.g. `skew_angle=60`) in `plot_slice` to project true reciprocal lattice parallelogram geometry.
- **Physical Aspect Ratio Calibration (`reciprocal_lattice_params`)**:
  - `plot_slice()` automatically sets `ax.set(aspect=np.cos(shear_angle))` (which equals $\sin(\theta_{\text{skew}})$) to correct for shear distortion assuming equal physical reciprocal lengths ($v_X^* = v_Y^*$).
  - When reciprocal lattice vectors differ in physical length ($a^* \ne b^*$ or along out-of-plane cuts $(HL), (KL)$ where $c^* \ne a^*, b^*$), calculate reciprocal lattice parameters using `reciprocal_lattice_params(lattice_params)`:
    ```python
    from nxs_analysis_tools.datareduction import reciprocal_lattice_params

    a_star, b_star, c_star, alpha_star, beta_star, gamma_star = reciprocal_lattice_params(
        (a, b, c, alpha, beta, gamma)
    )
    ```
  - Apply the physical aspect ratio calibration immediately after calling `plot_slice()`:
    $$\boxed{A_{\text{final}} = \frac{v_Y^*}{v_X^*} \times \text{ax.get\_aspect()}}$$
    ```python
    # HK Plane (X=H, Y=K):
    plot_slice(nx_hk, skew_angle=gamma_star, ax=ax_hk, ...)
    ax_hk.set_aspect(ax_hk.get_aspect() * (b_star / a_star))

    # HL Plane (X=H, Y=L):
    plot_slice(nx_hl, skew_angle=beta_star, ax=ax_hl, ...)
    ax_hl.set_aspect(ax_hl.get_aspect() * (c_star / a_star))

    # KL Plane (X=K, Y=L):
    plot_slice(nx_kl, skew_angle=alpha_star, ax=ax_kl, ...)
    ax_kl.set_aspect(ax_kl.get_aspect() * (c_star / b_star))
    ```
  - This ensures that $1\text{ \AA}^{-1}$ occupies the exact same screen pixel length in every physical direction, preserving circular diffuse scattering rings and preventing elongation along the $L$ axis.

---

## 4. Beamline Lifecycle Integration & Sister Skills

$$\text{Raw CBFs} \xrightarrow{\text{chess-legacy-reduction}} \text{3D Volumes} \xrightarrow{\text{reciprocal-space-analysis}} \text{Diagnostic Slicing} \xrightarrow{\text{xtec-gpu-analysis}} \text{4D Phase Clustering}$$

- **Upstream Data Reduction**: For converting raw Pilatus CBF detector frames into 3D NeXus reciprocal space volumes (`1rot_hkli.nxs`, `3rot_hkli.nxs`), consult the [`chess-legacy-reduction`](../chess-legacy-reduction/SKILL.md) skill.
- **Downstream Phase Clustering**: For clustering temperature-series reciprocal space datasets with GPU acceleration (PyTorch / `torchgmm`), consult the [`xtec-gpu-analysis`](../xtec-gpu-analysis/SKILL.md) skill.
- **Cluster Execution Details**: See the [Cluster Execution Guide](./references/cluster_execution.md) for interactive `qrsh` sessions, headless matplotlib, and memory management.
