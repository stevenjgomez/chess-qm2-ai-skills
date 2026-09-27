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

## 1. Remote Cluster Etiquette & Automated Reporting

1. **Node Separation**:
   - **Login node (`lnx201`)**: Text editing, job management, lightweight git operations.
   - **Compute node (`lnx308`)**: All heavy array manipulations, 3D rotations, batch rendering, and LaTeX compilation. Python: `/nfs/chess/sw/anaconda3_sgomezalvarado_nightly/bin/python`.
2. **Headless Execution**:
   - Always invoke `matplotlib.use("Agg")` before importing `matplotlib.pyplot`.
3. **Automated LaTeX Summaries**:
   - Automatically compile generated figures into PDF reports using `/usr/bin/pdflatex -interaction=nonstopmode <file>.tex`.

---

## 2. Working with `nxs_analysis_tools`

1. **Documentation & Release Notes Priority**:
   - Rather than inspecting raw source code, consult the GitHub PR notes, release summaries, and ReadTheDocs site (`https://github.com/stevenjgomez/nxs_analysis_tools.git`, branch `main`).
2. **NeXus Memory Limits (`nxsetmemory`)**:
   - By default `nexusformat` enforces a 2,000 MB memory slab limit (`NX_MEMORY=2000`). For large 3D reciprocal space volumes, raise this immediately upon import:
     ```python
     import nexusformat.nexus as nx
     nx.nxsetmemory(20000)  # Allocate up to 20,000 MB
     ```
3. **Transform Volume Indexing & Slicing**:
   - Load with `data = load_transform(path, use_nxlink=True)`.
   - The axes order for nxrefine transforms is `['Ql', 'Qk', 'Qh']` ($L, K, H$).
   - To slice the $HK0$ plane ($L=0$): `data[0.0, :, :]`.
4. **Colormap & Lattice Skew Considerations**:
   - In `plot_slice(..., logscale=True)`, set `vmin > 0` (e.g. `vmin=1, vmax=1e4`) to avoid `LogNorm` errors on zero counts.
   - For hexagonal systems (`@angles = [60.0, 90.0, 90.0]`), set `skew_angle=60` in `plot_slice`.

*Detailed reference:* [Cluster Execution Guide](./references/cluster_execution.md)
