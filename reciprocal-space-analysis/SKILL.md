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

## 2. Remote Cluster Etiquette & Automated Reporting

1. **Node Separation**:
   - **Login node (`lnx201`)**: Text editing, job management, lightweight git operations.
   - **Compute node (`lnx308`)**: All heavy array manipulations, 3D rotations, batch rendering, and LaTeX compilation. Python: `/nfs/chess/sw/anaconda3_sgomezalvarado_nightly/bin/python`.
2. **Headless Execution**:
   - Always invoke `matplotlib.use("Agg")` before importing `matplotlib.pyplot`.
3. **Automated LaTeX Summaries**:
   - Automatically compile generated figures into PDF reports using `/usr/bin/pdflatex -interaction=nonstopmode <file>.tex`.
4. **Strict Data Safety: NEVER Delete Any `.nxs` Files**:
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
  nx.nxsetmemory(20000)  # 20 GB
  ```

### 3.2 Array Axes vs. Reciprocal Space Planes
With `use_nxlink=True`, NXRefine datasets preserve native C-contiguous axes:
`data.nxaxes == ['Ql', 'Qk', 'Qh']` (shape `(N_l, N_k, N_h)`).
- **Physical Planes require fixing the perpendicular axis**:
  - **$HK$ Plane**: Hold $L$ ($Q_l$) constant (e.g. $L = 0.0$). Free axes are $H, K$.
    $\rightarrow$ **Slice Axis 0**: `data[0.0, :, :]`
  - **$HL$ Plane**: Hold $K$ ($Q_k$) constant (e.g. $K = 0.0$). Free axes are $H, L$.
    $\rightarrow$ **Slice Axis 1**: `data[:, 0.0, :]`
  - **$KL$ Plane**: Hold $H$ ($Q_h$) constant (e.g. $H = 0.0$). Free axes are $K, L$.
    $\rightarrow$ **Slice Axis 2**: `data[:, :, 0.0]`
- > [!WARNING]
  > Fixing $H = 0.0$ ($Q_h = 0.0$) eliminates $H$ and yields the **$KL$ plane**, NOT the $HK$ plane!

### 3.3 Float vs. Integer Indexing
`nexusformat.nexus.NXdata` strictly distinguishes between integer and float indices:
- **Integer index** (`data[:, 0, :]`): Selects the **0th array element** along that axis (e.g. minimum bound $K = -3.0$).
- **Float index** (`data[:, 0.0, :]`): Queries the **physical reciprocal space coordinate** ($K = 0.0$).
- **Rule**: Always use float literals (`0.0`, `1.5`) when selecting reciprocal cuts.

### 3.4 Scissors & Linecut Coordinates
`Scissors.cut_data()` maps coordinates positionally to `data.nxaxes`. Under `use_nxlink=True`, `center` and `window` tuples must follow $(L, K, H)$ order:
```python
# center and window ordered as (L, K, H):
scissors.cut_data(center=(0.0, 0.0, -0.5), window=(0.2, 0.2, 0.25))
```

### 3.5 Temperature Series Discovery & Normalization
- Temperature keys can appear as integers (`15`), floats (`15.5`), or filesystem string notation (`'15p5'`).
- `TempDict` provides transparent polymorphic access:
  ```python
  td.datasets[15.5] == td.datasets['15.5'] == td.datasets['15p5']
  ```
- **Discovery**: Always discover temperatures dynamically using `sample.find_temperatures()`.
- **Loading**: Use `sample.load_datasets(temperatures=[...])`.

### 3.6 Colormaps, LogNorm & Lattice Skew
- In `plot_slice(..., logscale=True)`, set `vmin > 0` (e.g. `vmin=1, vmax=1e4`) to avoid `LogNorm` errors on zero or negative masked counts.
- For non-orthogonal / hexagonal systems (`@angles = [60.0, 90.0, 90.0]`), set `skew_angle=60` in `plot_slice` to correctly project the reciprocal lattice geometry.

---

*Detailed cluster reference:* [Cluster Execution Guide](./references/cluster_execution.md)
