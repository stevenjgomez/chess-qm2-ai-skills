# CHESS QM2 AI Skills Suite (`chess-qm2-ai-skills`)

A modular collection of domain-specific scientific computing and synchrotron skills for **Google Antigravity** and the **Gemini CLI**. Tailored specifically for X-ray diffraction, reciprocal space volume reconstruction, and temperature-series scattering analysis at the **Cornell High Energy Synchrotron Source (CHESS)** ID4B / QM2 beamline.

---

## Skill Catalog

| Skill | Directory | Description & Capabilities |
| :--- | :--- | :--- |
| **`chess-legacy-reduction`** | [`chess-legacy-reduction/`](./chess-legacy-reduction/) | **Autonomous Beamline Reduction Pipeline**: Automates stacking raw Pilatus 6M CBF detector frames, headless orientation matrix (ORM) solving via `scipy.optimize.basinhopping`, 3D reciprocal space HKL conversion (`1rot` and `3rot`), cross-sectional plane visualization ($(HK0)$, $(H0L)$, $(0KL)$), human-in-the-loop verification gates, and Grid Engine (`qsub`) batch scheduling across AVX2-capable CLASSE nodes. Includes a turnkey Python CLI suite in `scripts/`. |
| **`reciprocal-space-analysis`** | [`reciprocal-space-analysis/`](./reciprocal-space-analysis/) | **3D Reciprocal Space & NeXus Analysis**: Reconstruction, indexing, alignment, and slicing of 3D reciprocal space volumes (NeXus/HDF5) via `nxs_analysis_tools`. Enforces skew projections for non-orthogonal/hexagonal lattices, multi-dataset linecuts, and cluster execution etiquette. |
| **`xtec-gpu-analysis`** | [`xtec-gpu-analysis/`](./xtec-gpu-analysis/) | **GPU Temperature Clustering (XTEC-GPU)**: High-throughput clustering of temperature-series scattering datasets using PyTorch and `torchgmm`. Enforces CLASSE cluster node etiquette (distinguishing CPU nodes vs dedicated CUDA GPU nodes like `lnx4428`), discrete Q-map visualization, and automated Markdown reporting. |

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

1. **Mandatory Batch Execution (`qsub`)**:
   - Because single-rotation CBF data stacks (`stack*.nxs`) range from 10 GB to 35+ GB, loading frames over NFS requires tens of minutes and significant memory bandwidth.
   - All stack loading, ORM solving, and 3D HKL conversions must be submitted via Grid Engine:
     ```bash
     qsub -q 'all.q@lnx307*,all.q@lnx311*,all.q@lnx312*,all.q@lnx313*' -l mem_free=200G -pe sge_pe 32 <job_script>.sh
     ```
2. **AVX2 Vector Instruction Enforcing**:
   - The beamline's compiled C library (`libhkl.so`) requires AVX2 vector instructions. Jobs dispatched to older nodes (e.g. `lnx327`) crash with `SIGILL` (Exit Code `-4`). Queue targets are restricted to verified AVX2 hosts (`lnx307`, `lnx311`, `lnx312`, `lnx313`, `lnx308`, `lnx1033-f1`, `lnx1034-f1`).
3. **Dedicated Python Environment**:
   - Executes using the shared beamline environment at `/nfs/chess/sw/anaconda3_jpcr/bin/python`. The shared environment is never modified (`pip`/`conda` installs are prohibited).
4. **Energy & Lattice Parameter Scaling**:
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
    └── references/
        ├── cluster_topology.md
        └── xtec_workflow.md
```

---

## License

MIT License. Copyright (c) 2026 Steven J. Gomez Alvarado.
