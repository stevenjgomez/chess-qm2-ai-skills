# CLASSE/CHESS Cluster Topology & Execution Guide

This document details the node architecture, access conventions, and environment management when operating on the CLASSE computing infrastructure for synchrotron data analysis.

---

## 1. Node Roles & Specialization

Understanding node specialization is critical to avoid degrading interactive performance for other beamline users and to ensure workloads have access to necessary compute accelerators.

```text
[User / Antigravity Agent]
            │
            ▼ (SSH / Local Shell)
┌──────────────────────────────────────┐
│  Login Node: lnx201                  │
│  - Architecture: Intel Xeon (No GPU) │
│  - Purpose: Shell, Git, Editing      │
│  - RULE: NO COMPUTE / NO ML          │
└──────────────────┬───────────────────┘
                   │
         ┌─────────┴─────────┐
         ▼ (qrsh)            ▼ (SSH BatchMode)
┌─────────────────────────┐  ┌────────────────────────────────────────┐
│ Interactive CPU Nodes   │  │ Dedicated CUDA GPU Node                │
│ interactive.q (mem=350G)│  │ lnx4428.classe.cornell.edu             │
│ - 3-step qrsh workflow  │  │ - Hardware: NVIDIA Titan RTX (24GB)    │
│ - nxs_analysis_tools    │  │ - Tasks: XTEC-GPU, torchgmm, PyTorch   │
│ - to_xtec 4D compilation│  │ - Preprocessing & GMM clustering       │
│ - 3D Reciprocal Slicing │  │ - Discrete Q-Map rendering             │
└─────────────────────────┘  └────────────────────────────────────────┘
```

### Node Profiles

1. **Login Node: `lnx201`**:
   - Shared entry point for all CLASSE/CHESS users.
   - Resource quotas are tightly policed.
   - Running compute tasks (such as PyTorch models, NeXus preprocessing, or heavy array math) on `lnx201` is strictly forbidden by facility policy.

2. **Interactive CPU Compute Nodes (`interactive.q`)**:
   - High-memory compute instances allocated dynamically via Grid Engine.
   - Workloads: NeXus dataset loading, 4D XTEC input generation via `to_xtec()`, 3D lattice coordinate transformations, hexagonal skew projections, 1D/2D linecut generation, and LaTeX PDF compilation.
   - **Mandatory Workflow**:
     ```bash
     # 1. Connect to gateway
     ssh <user>@lnx201.classe.cornell.edu
     # 2. Allocate interactive session
     qrsh -q interactive.q -l mem_free=350G
     # 3. Run analysis
     /nfs/chess/sw/anaconda3_sgomezalvarado_nightly/bin/python my_script.py
     ```
   - Direct SSH into compute nodes like `lnx308` is prohibited.

3. **CUDA GPU Compute Node: `lnx4428`** (The "XTEC Scripts"):
   - Hostname: `lnx4428.classe.cornell.edu`.
   - Accelerator: **NVIDIA Titan RTX** (24 GB VRAM, TU102 architecture, Compute Capability 7.5).
   - Driver: NVIDIA UNIX x86_64 Driver 535.183.01, CUDA Version 12.2.
   - Workloads: GPU Gaussian Mixture Models (`torchgmm`), Kullback-Leibler thresholding on GPU, connected-component peak identification, Bayesian Information Criterion sweeps.
   - Python interpreter: `/nfs/chess/sw/qm2_XTEC312/bin/python`.
   - Binary: `/nfs/chess/sw/qm2_XTEC312/bin/xtec-gpu`.

---

## 2. Python Environments on CLASSE

| Environment Path | Python Version | PyTorch / CUDA Status | Target Workload |
| :--- | :--- | :--- | :--- |
| `/nfs/chess/sw/qm2_XTEC312/bin/python` | **3.12.14** | **PyTorch 2.14.0+cu130** (CUDA Active) | **XTEC-GPU, torchgmm, GPU Preprocessing** |
| `/nfs/chess/sw/anaconda3_sgomezalvarado_nightly/bin/python` | 3.12+ | CPU | Regular scripts (`nxs_analysis_tools`, LaTeX, `to_xtec`) |
| `/nfs/chess/sw/qm2_XTEC/bin/python` | 3.9.7 | Older | **DEPRECATED**. Fails with `TypeError` on PEP 604 union types (`int | None`). |

---

## 3. Remote Execution Mechanics

For GPU workloads on `lnx4428`, execute non-interactively via SSH:

```bash
# Running xtec-gpu CLI directly
ssh -o BatchMode=yes lnx4428 "/nfs/chess/sw/qm2_XTEC312/bin/xtec-gpu xtec-d /path/to/data.nxs -o /path/to/results/ --min-k 2 --max-k 14"

# Running custom Python scripts
ssh -o BatchMode=yes lnx4428 "/nfs/chess/sw/qm2_XTEC312/bin/python <script>.py"
```

### SSH Configuration Tips
- `-o BatchMode=yes`: Prevents the command from hanging indefinitely on interactive password or passphrase prompts.

### Grid Engine (SGE) Quota Notice
- CLASSE provides `qsub` for batch queues (`all.q`, `cuda.q`).
- However, load sensors on specific nodes (including `lnx4428`) frequently report `cuda_free=0` or negative values due to sensor configuration mismatches.
- Direct non-interactive SSH execution has been verified and approved by the user for dedicated processing on `lnx4428`.
