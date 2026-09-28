# CHESS QM2 AI Skills Suite (`chess-qm2-ai-skills`)

A modular collection of domain-specific scientific computing and synchrotron skills for **Google Antigravity** and the **Gemini CLI**. Tailored specifically for X-ray diffraction, reciprocal space volume reconstruction, and temperature-series scattering analysis at the **Cornell High Energy Synchrotron Source (CHESS)** ID4B / QM2 beamline.

---

## Skill Catalog

| Skill | Directory | Description & Capabilities |
| :--- | :--- | :--- |
| **`chess-legacy-reduction`** | [`chess-legacy-reduction/`](./chess-legacy-reduction/) | **Autonomous Beamline Reduction Pipeline**: Automates stacking raw Pilatus 6M CBF detector frames, headless orientation matrix (ORM) solving via `scipy.optimize.basinhopping`, 3D reciprocal space HKL conversion (`1rot` and `3rot`), cross-sectional plane visualization ($(HK0)$, $(H0L)$, $(0KL)$), human-in-the-loop verification gates, and Grid Engine (`qsub`) batch scheduling across AVX2-capable CLASSE nodes. Includes a turnkey Python CLI suite in `scripts/`. |
| **`reciprocal-space-analysis`** | [`reciprocal-space-analysis/`](./reciprocal-space-analysis/) | **3D Reciprocal Space & NeXus Analysis**: Reconstruction, indexing, alignment, and slicing of 3D reciprocal space volumes (NeXus/HDF5) via `nxs_analysis_tools`. Enforces skew projections for non-orthogonal/hexagonal lattices, multi-dataset linecuts, and interactive cluster execution etiquette (`qrsh`). |
| **`xtec-gpu-analysis`** | [`xtec-gpu-analysis/`](./xtec-gpu-analysis/) | **GPU Temperature Clustering (XTEC-GPU)**: High-throughput clustering of temperature-series scattering datasets using PyTorch and `torchgmm`. Features automated 4D NeXus compilation from 3D volumes (NXRefine and legacy CHESS) via `TempDependence.to_xtec()`, enforces cluster node etiquette (interactive CPU nodes via `qrsh` vs GPU node `lnx4428`), discrete Q-map visualization, and automated Markdown reporting. Includes turnkey input generation CLI in `scripts/`. |

---

## Installation & Setup

These skills install directly into your user-level Antigravity/Gemini configuration directory. Because Antigravity discovers skills located strictly one directory level below `skills/` (`skills/<skill_name>/SKILL.md`), symlink each individual skill folder:

```bash
# Ensure the destination skills directory exists
mkdir -p ~/.gemini/config/skills

# Symlink each skill folder into ~/.gemini/config/skills/
for skill in /path/to/chess-qm2-ai-skills/*/; do
  if [ -f "$skill/SKILL.md" ]; then
    ln -s "$skill" ~/.gemini/config/skills/$(basename "$skill")
  fi
done
```

Once installed, Antigravity automatically discovers and progressively mounts each skill whenever relevant tasks (data reduction, reciprocal space slicing, or XTEC clustering) are triggered.

---

## Cluster & Beamline Etiquette

All skills in this suite strictly adhere to CLASSE compute cluster etiquette, Grid Engine allocation rules, and beamline hardware constraints.

### Node Topology & Execution Protocols

| Node Class | Host / Queue Target | Role & Hardware Profile | Permitted Execution Protocol |
| :--- | :--- | :--- | :--- |
| **Login Gateway** | `lnx201.classe.cornell.edu` | Shell sessions, file editing, git, job submission. **No compute.** | Interactive login via `ssh <user>@lnx201.classe.cornell.edu`. Never run compute, heavy array manipulation, or slicing here. |
| **Batch Reduction Nodes** | `all.q@lnx307*`<br>`all.q@lnx311*`<br>`all.q@lnx312*`<br>`all.q@lnx313*` | Heavy raw reduction, Pilatus CBF frame stacking (10–35+ GB/rotation), ORM basinhopping, 3D volume reconstruction. Verified AVX2 CPU instruction set for `libhkl.so`. | **Mandatory Grid Engine batch submission (`qsub`)** using bash wrapper scripts (see [`example_job_scripts/`](./example_job_scripts/)). |
| **Interactive Analysis Nodes** | `interactive.q` (Grid Engine) | Downstream analysis (`nxs_analysis_tools`), 2D reciprocal slicing (`plot_slice`), 1D linecuts (`Scissors`), 4D XTEC input compilation (`to_xtec`), LaTeX compilation. | **Mandatory 3-step `qrsh` interactive session from `lnx201`** (see below). Direct SSH into compute nodes (such as `lnx308`) is strictly prohibited. |
| **CUDA GPU Compute Node** | `lnx4428.classe.cornell.edu` | GPU-accelerated machine learning, XTEC-GPU clustering, PyTorch, `torchgmm`. **NVIDIA Titan RTX (24 GB VRAM).** | Non-interactive SSH execution via `/nfs/chess/sw/qm2_XTEC312/bin/xtec-gpu`. |

---

### Mandatory Interactive Analysis Protocol (`qrsh`)

> [!IMPORTANT]
> **Never SSH directly into compute nodes** (e.g. `ssh lnx308` is prohibited by facility policy to prevent host overloading).
> All interactive work, downstream visualization, and 4D dataset compilation must follow this 3-step workflow:
>
> 1. **Connect to the login gateway**:
>    ```bash
>    ssh <username>@lnx201.classe.cornell.edu
>    ```
> 2. **Allocate an interactive compute session with Grid Engine**:
>    ```bash
>    qrsh -q interactive.q -l mem_free=350G
>    ```
> 3. **Run your analysis or activate the appropriate Python environment**:
>    ```bash
>    /nfs/chess/sw/anaconda3_sgomezalvarado_nightly/bin/python my_script.py
>    ```

---

### Operational Guidelines

1. **Batch Reduction Pipeline (`qsub`)**:
   - Heavy data processing (raw Pilatus CBF frame stacking, headless ORM basinhopping, and 3D reciprocal conversions) consumes massive memory bandwidth and RAM. They **must** be submitted via `qsub` targeting the AVX2 pool:
     ```bash
     qsub -q 'all.q@lnx307*,all.q@lnx311*,all.q@lnx312*,all.q@lnx313*' -l mem_free=200G -pe sge_pe 32 <job_script>.sh
     ```
2. **Two-Stage Routing for XTEC-GPU Workflows**:
   - **Stage 0 (Input Compilation)**: Executed in an interactive CPU session (`qrsh -q interactive.q -l mem_free=350G`) using `/nfs/chess/sw/anaconda3_sgomezalvarado_nightly/bin/python` to compile 3D datasets into a 4D `NXdata` volume via `generate_xtec_input.py` / `TempDependence.to_xtec()`.
   - **Stages 1–4 (ML Preprocessing & Clustering)**: Executed exclusively on dedicated CUDA GPU node `lnx4428` (NVIDIA Titan RTX) using `/nfs/chess/sw/qm2_XTEC312/bin/xtec-gpu`.
3. **AVX2 Vector Instruction Enforcing**:
   - The beamline's compiled C library (`libhkl.so`) requires AVX2 vector instructions. Jobs dispatched to older nodes (e.g. `lnx327`) crash with `SIGILL` (Exit Code `-4`). Queue targets are strictly restricted to verified AVX2 hosts (`lnx307`, `lnx311`, `lnx312`, `lnx313`).
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
├── example_job_scripts/
│   ├── legacy-reduction-FeTe2-5A-281-fastpath.sh
│   └── legacy-reduction-FeTe2-5A-batch.sh
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
