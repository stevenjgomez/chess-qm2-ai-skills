# CLASSE/CHESS Cluster Topology & Execution Guide

This document details the node architecture, access conventions, and environment management when operating on the CLASSE computing infrastructure for synchrotron data analysis.

Per [`GEMINI.md`](../../GEMINI.md), all remote Python and Conda environments on CLASSE are **strictly read-only / immutable**. Never run `pip install` or modify environment configurations.

---

## 1. Node Roles, Specialization & Execution Modes

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
         ▼ (qrsh / qsub)     ▼ (qsub -l cuda_free=1)
┌─────────────────────────┐  ┌────────────────────────────────────────┐
│ CPU Compute Nodes       │  │ Dedicated CUDA GPU Node                │
│ interactive.q / all.q   │  │ lnx4428.classe.cornell.edu             │
│ - Human: qrsh (mem=350G)│  │ - Hardware: NVIDIA Titan RTX (24GB)    │
│ - Agent: qsub batch     │  │ - Tasks: XTEC-GPU, torchgmm, PyTorch   │
│ - to_xtec 4D compilation│  │ - Preprocessing & GMM clustering       │
│ - 3D Reciprocal Slicing │  │ - Discrete Q-Map rendering             │
└─────────────────────────┘  └────────────────────────────────────────┘
```

### Node Profiles & Execution Protocols

1. **Login Node: `lnx201`**:
   - Shared entry point for all CLASSE/CHESS users.
   - Resource quotas are tightly policed.
   - Running compute tasks (such as PyTorch models, NeXus preprocessing, or heavy array math) on `lnx201` is strictly forbidden by facility policy.

2. **CPU Compute Nodes (`interactive.q` & `all.q`)**:
   - High-memory compute instances allocated dynamically via Grid Engine.
   - Workloads: NeXus dataset loading, 4D XTEC input generation via `to_xtec()`, 3D lattice coordinate transformations, hexagonal skew projections, 1D/2D linecut generation, and LaTeX PDF compilation.
   - **Dual Execution Pattern**:
     - **Interactive Human Sessions**: Use `qrsh -q interactive.q -l mem_free=350G` from `lnx201`.
     - **Automated / Agentic Sessions**: In unattended automated sessions over SSH, `qrsh` prompts for Kerberos passwords (`Password for <user>@CLASSE.CORNELL.EDU:`), causing unattended scripts to hang. Automated agents must submit short-lived SGE batch wrappers via `qsub` (e.g. [`example_job_scripts/xtec-prep-batch.sh`](../../example_job_scripts/xtec-prep-batch.sh)) and stream stdout/stderr via `tail -f <log>`.
   - Direct SSH into compute nodes like `lnx308` is prohibited.

3. **Mandatory "Show-Before-Submit" Verification Gate**:
   > [!IMPORTANT]
   > Prior to executing `qsub <job_script>.sh` for any stage (data preparation or GPU clustering), the assistant MUST present the complete script text to the user, highlighting queue targets, memory requests, slot allocations, environment path, and CLI invocation. The user must provide confirmation before the job is submitted.

3. **CUDA GPU Compute Node: `lnx4428`** (The "XTEC Scripts"):
   - Hostname: `lnx4428.classe.cornell.edu`.
   - Accelerator: **NVIDIA Titan RTX** (24 GB VRAM, TU102 architecture, Compute Capability 7.5).
   - Driver: NVIDIA UNIX x86_64 Driver 535.183.01, CUDA Version 12.2.
   - Workloads: GPU Gaussian Mixture Models (`torchgmm`), Kullback-Leibler thresholding on GPU, connected-component peak identification, Bayesian Information Criterion sweeps.
   - Python interpreter: `/nfs/chess/sw/qm2_XTEC312/bin/python`.
   - Binary: `/nfs/chess/sw/qm2_XTEC312/bin/xtec-gpu`.
   - **Execution Protocol**: Submitted via Grid Engine batch script requesting `-l cuda_free=1`.

---

## 2. Python Environments on CLASSE

| Environment Path | Python Version | PyTorch / CUDA Status | Target Workload |
| :--- | :--- | :--- | :--- |
| `/nfs/chess/sw/qm2_XTEC312/bin/python` | **3.12.14** | **PyTorch 2.14.0+cu130** (CUDA Active) | **XTEC-GPU, torchgmm, GPU Preprocessing** |
| `/nfs/chess/sw/anaconda3_sgomezalvarado_nightly/bin/python` | 3.12+ | CPU | Regular scripts (`nxs_analysis_tools`, LaTeX, `to_xtec`) |
| `/nfs/chess/sw/qm2_XTEC/bin/python` | 3.9.7 | Older | **DEPRECATED**. Fails with `TypeError` on PEP 604 union types (`int | None`). |

---

## 3. GPU Batch Execution Mechanics (`qsub -l cuda_free=1`)

All CUDA GPU workloads must be submitted to the Grid Engine queue with the GPU resource request:

```bash
qsub -l cuda_free=1 xtec_job.sh
```

### Standard GPU Job Script Template (`xtec_job.sh`)

```bash
#!/bin/bash
#$ -S /bin/bash
#$ -N xtec_gpu
#$ -cwd
#$ -j y
#$ -l cuda_free=1
#$ -o qsub_xtec.log

echo "=== Running XTEC-GPU on $(hostname) ==="
echo "CUDA_VISIBLE_DEVICES: ${CUDA_VISIBLE_DEVICES}"

# Running xtec-gpu CLI directly
/nfs/chess/sw/qm2_XTEC312/bin/xtec-gpu xtec-d /path/to/data.nxs -o /path/to/results/ --min-k 2 --max-k 14
```

### Facility GPU Policy
- Grid Engine dynamically manages allocation of the Titan RTX accelerator on `lnx4428` via the `cuda_free=1` resource directive.
- Direct interactive GPU compute or executing outside Grid Engine without `-l cuda_free=1` is strictly forbidden.

### Non-Interactive SSH Authentication
To enable AI assistant tools and automated workflows to interact with `lnx201` without stalling on password or Duo prompts, configure your SSH keys or multiplexing following the [SSH Authentication Setup Guide](../../README.md#ssh-remote-access--authentication-setup-suggested-approach).
