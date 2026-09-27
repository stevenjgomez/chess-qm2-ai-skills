# CHESS QM2 AI Skills Suite (`chess-qm2-ai-skills`)

A modular collection of domain-specific scientific computing and synchrotron skills for **Google Antigravity** and the **Gemini CLI**. Tailored specifically for X-ray diffraction, reciprocal space volume reconstruction, and temperature-series scattering analysis at the **Cornell High Energy Synchrotron Source (CHESS)** ID4B / QM2 beamline.

---

## Skill Catalog

| Skill | Directory | Description & Capabilities |
| :--- | :--- | :--- |
| **`chess-legacy-reduction`** | [`chess-legacy-reduction/`](./chess-legacy-reduction/) | **Autonomous Beamline Reduction Pipeline**: Automates stacking raw Pilatus 6M CBF detector frames, headless orientation matrix (ORM) solving via `scipy.optimize.basinhopping`, 3D reciprocal space HKL conversion (`1rot` and `3rot`), cross-sectional plane visualization ($(HK0)$, $(H0L)$, $(0KL)$), human-in-the-loop verification gates, and Grid Engine (`qsub`) batch scheduling across AVX2-capable CLASSE nodes. Includes a turnkey Python CLI suite in `scripts/`. |
| **`reciprocal-space-analysis`** | [`reciprocal-space-analysis/`](./reciprocal-space-analysis/) | **3D Reciprocal Space & NeXus Analysis**: Reconstruction, indexing, alignment, and slicing of 3D reciprocal space volumes (NeXus/HDF5) via `nxs_analysis_tools`. Enforces skew projections for non-orthogonal/hexagonal lattices, multi-dataset linecuts, and cluster execution etiquette. |
| **`xtec-gpu-analysis`** | [`xtec-gpu-analysis/`](./xtec-gpu-analysis/) | **GPU Temperature Clustering (XTEC-GPU)**: High-throughput clustering of temperature-series scattering datasets using PyTorch and `torchgmm`. Features automated 4D NeXus compilation from 3D volumes (NXRefine and legacy CHESS) via `TempDependence.to_xtec()`, enforces cluster node etiquette (CPU node `lnx308` vs GPU node `lnx4428`), discrete Q-map visualization, and automated Markdown reporting. Includes turnkey input generation CLI in `scripts/`. |

---

## Installation & Setup

These skills install directly into your user-level Antigravity/Gemini configuration directory:

```bash
# Clone the repository directly into your Antigravity skills directory
git clone git@github.com:<username>/chess-qm2-ai-skills.git ~/.gemini/config/skills

# Or, if already cloned to another location, symlink it:
ln -s /path/to/chess-qm2-ai-skills ~/.gemini/config/skills
```

Once installed, Antigravity automatically discovers and progressively mounts each skill whenever relevant tasks (data reduction, reciprocal space slicing, or XTEC clustering) are triggered.

---

## Cluster & Beamline Etiquette

All skills in this suite strictly follow CLASSE compute cluster etiquette and beamline constraints:

1. **Execution Modes: Data Reduction (`qsub`) vs. Data Analysis (SSH on Compute Nodes)**:
   - **Data Reduction Pipeline (Mandatory `qsub`)**: Raw Pilatus CBF frame stacking (10–35+ GB per rotation), headless ORM basinhopping, and 3D reciprocal conversions consume massive memory bandwidth and RAM. They **must** be submitted via Grid Engine:
     ```bash
     qsub -q 'all.q@lnx307*,all.q@lnx311*,all.q@lnx312*,all.q@lnx313*' -l mem_free=200G -pe sge_pe 32 <job_script>.sh
     ```
   - **Downstream Data Analysis (Non-Interactive SSH)**: Downstream tasks using `nxs_analysis_tools` (generating diagnostic 2D slices with `plot_slice()`, 1D linecuts with `Scissors`, order parameters, and LaTeX compilation) operate on converted volumes using lazy loading ($O(1)$ RAM). These do **NOT** require `qsub` and are executed directly via non-interactive SSH on dedicated CPU compute nodes (e.g. `ssh lnx308 /nfs/chess/sw/anaconda3_sgomezalvarado_nightly/bin/python ...`).
   - **Login Node (`lnx201`)**: Strictly for text editing, git, and job submission. Computing or figure rendering on `lnx201` is strictly forbidden.
2. **Two-Stage Node Routing for XTEC-GPU**:
   - **Stage 0 (Input Compilation)**: Executed on regular CPU node `lnx308` using `/nfs/chess/sw/anaconda3_sgomezalvarado_nightly/bin/python` to stack 3D datasets into a 4D `NXdata` structure via `TempDependence.to_xtec()`.
   - **Stages 1–4 (ML Preprocessing & Clustering)**: Executed exclusively on dedicated CUDA GPU node `lnx4428` (NVIDIA Titan RTX) using `/nfs/chess/sw/qm2_XTEC312/bin/python`.
3. **AVX2 Vector Instruction Enforcing**:
   - The beamline's compiled C library (`libhkl.so`) requires AVX2 vector instructions. Jobs dispatched to older nodes (e.g. `lnx327`) crash with `SIGILL` (Exit Code `-4`). Queue targets are restricted to verified AVX2 hosts (`lnx307`, `lnx311`, `lnx312`, `lnx313`, `lnx308`, `lnx1033-f1`, `lnx1034-f1`).
4. **Designated Python Environments**:
   - **Legacy Reduction Pipeline**: `/nfs/chess/sw/anaconda3_jpcr/bin/python` (shared beamline environment, frozen/never modified).
   - **Modern Analysis & Visualization**: `/nfs/chess/sw/anaconda3_sgomezalvarado_nightly/bin/python` (hosts `nxs_analysis_tools`, PyTorch, and `plot_slice()`).
   - **CUDA ML / Clustering**: `/nfs/chess/sw/qm2_XTEC312/bin/python` (hosts `torchgmm`, PyTorch CUDA 12.2 on `lnx4428`).
5. **Strict Data Safety Policy**:
   - **NEVER delete or remove any `.nxs` files**. All reduction and transformation workflows generate non-destructively suffixed files (`1rot_hkli_1.nxs`, `xtec_data_1.nxs`, etc.) rather than overwriting or deleting prior datasets.
6. **Energy & Lattice Parameter Scaling**:
   - Miller index bounds $(H, K, L)$ scale with incident beam energy ($E$) and real-space lattice parameters ($a, b, c$). Customized bounds (e.g. $H, K: \pm 3.0, L: \pm 3.5$ at $15\text{ keV}$) prevent generating oversized, zero-padded reciprocal volumes.

---

## Repository Structure

```text
chess-qm2-ai-skills/
├── .gitignore
├── README.md
├── LICENSE
├── chess-legacy-reduction/
│   ├── SKILL.md
│   └── scripts/
│       ├── orchestrate_reduction.py
│       ├── orm_solver.py
│       ├── slice_visualizer.py
│       └── pipeline_tracker.py
├── reciprocal-space-analysis/
│   ├── SKILL.md
│   └── references/
│       └── cluster_execution.md
└── xtec-gpu-analysis/
    ├── SKILL.md
    ├── scripts/
    │   └── generate_xtec_input.py
    └── references/
        ├── cluster_topology.md
        └── xtec_workflow.md
```

---

## License

MIT License. Copyright (c) 2026 Steven J. Gomez Alvarado.
