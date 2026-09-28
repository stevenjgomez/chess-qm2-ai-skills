# Grid Engine Example Job Scripts (`example_job_scripts/`)

This directory contains production-ready **Sun Grid Engine (SGE)** job script templates for running raw X-ray data reduction and GPU machine learning workflows on the **CLASSE compute cluster**.

All scripts execute unbuffered Python (`python -u`) so job execution logs can be monitored live in real time using `tail -f`.

---

## Script Catalog

| Script | Target Hardware / Queue | Purpose & Operational Phase |
| :--- | :--- | :--- |
| [`legacy-reduction-FeTe2-5A-281-fastpath.sh`](./legacy-reduction-FeTe2-5A-281-fastpath.sh) | `all.q@lnx307*,lnx311*,lnx312*,lnx313*`<br>(AVX2 CPU, 32 cores, 200 GB RAM) | **Phase 1: Warm Reference Fast-Path Reduction**: Stacks raw Pilatus CBF frames into `stack1.nxs`, runs headless orientation matrix (ORM) basinhopping, converts 1-rotation reciprocal volume (`1rot_hkli.nxs`), and renders diagnostic cross-sectional slices (`HK0`, `H0L`, `0KL`). |
| [`legacy-reduction-FeTe2-5A-batch.sh`](./legacy-reduction-FeTe2-5A-batch.sh) | `all.q@lnx307*,lnx311*,lnx312*,lnx313*`<br>(AVX2 CPU, 32 cores, 200 GB RAM) | **Phase 2: Temperature-Series Batch Reduction**: Iterates over all remaining temperature points for the sample, reusing the verified orientation matrix from `--ref-temp` without re-solving. |
| [`xtec-prep-batch.sh`](./xtec-prep-batch.sh) | `all.q@lnx307*,lnx311*,lnx312*,lnx313*`<br>(AVX2 CPU, 16 cores, 200 GB RAM) | **Stage 0: 4D XTEC Dataset Compilation**: Non-interactive batch wrapper for compiling 3D reciprocal volumes into 4D `xtec_data.nxs` with stub pre-validation and modal exposure filtering. Reserved for automated/agentic runs where `qrsh` hangs on Kerberos prompts. |
| [`xtec-gpu-clustering.sh`](./xtec-gpu-clustering.sh) | `lnx4428` via `#$ -l cuda_free=1`<br>(NVIDIA Titan RTX, 24 GB VRAM) | **Autonomous End-to-End XTEC-GPU Workflow**: Runs Phase 1 & 2 (streamed BIC sweep across $k = 2 \dots 14$), automatically determines optimal $k^* = \operatorname{argmin}_k \text{BIC}(k)$, and executes Phase 3 (final GMM clustering with reordering) in a single GPU reservation. |
| [`xtec-bic-sweep.sh`](./xtec-bic-sweep.sh) | `lnx4428` via `#$ -l cuda_free=1`<br>(NVIDIA Titan RTX, 24 GB VRAM) | **Standalone BIC Model Selection Sweep**: Executes only the BIC sweep ($k = 2 \dots 14$) with `--streamed-preprocess` for exploratory model complexity analysis. |

---

## 1. Raw Data Reduction Job Submission

### A. Fast-Path (Single Reference Temperature)
Run this first on your warmest/reference temperature dataset to obtain the initial orientation matrix:

```bash
qsub -q 'all.q@lnx307*,all.q@lnx311*,all.q@lnx312*,all.q@lnx313*' \
     -l mem_free=200G \
     -pe sge_pe 32 \
     legacy-reduction-FeTe2-5A-281-fastpath.sh
```

### B. Full Batch Reduction (All Remaining Temperatures)
Once the reference orientation matrix and diagnostic slice figures have been verified, submit the batch job to process all remaining temperatures:

```bash
qsub -q 'all.q@lnx307*,all.q@lnx311*,all.q@lnx312*,all.q@lnx313*' \
     -l mem_free=200G \
     -pe sge_pe 32 \
     legacy-reduction-FeTe2-5A-batch.sh
```

### Key CLI Parameters to Customize:
- `--cycle`: CHESS run cycle (e.g. `2026-2`).
- `--experiment`: Proposal/experiment directory name (e.g. `gomez-al-4850-a`).
- `--sample` & `--sample-id`: Sample identifier (e.g. `FeTe2` and `FeTe2-5A`).
- `--calib-file`: Path to detector geometry calibration file (`.poni`).
- `--mask-file`: Path to detector mask file (`.edf`).
- `--unit-cell`: Real-space lattice parameters `"a,b,c,alpha,beta,gamma"`.
- `--hlim`, `--klim`, `--llim`: Maximum reciprocal bounds scaled for beam energy and real-space dimensions.

---

## 2. Non-Interactive 4D XTEC Dataset Preparation (`xtec-prep-batch.sh`)

When preparing 4D datasets from automated or agentic sessions (where interactive `qrsh` hangs due to Kerberos password prompts), submit the pre-validation and compilation job via `qsub`:

```bash
qsub xtec-prep-batch.sh
```

Monitors stub validity (`transform.nxs > 0 bytes`), extracts scan count times, automatically filters out exposure outliers, and outputs `xtec_data.nxs`.

---

## 3. CUDA GPU Clustering Job Submission

For temperature-series scattering datasets compiled into `xtec_data.nxs` (via `generate_xtec_input.py`), submit clustering jobs to the dedicated GPU node (`lnx4428`):

### A. Autonomous End-to-End Workflow (Recommended)
Submits a single continuous GPU job that computes the BIC sweep, automatically extracts the optimal $k^* = \operatorname{argmin}_k \text{BIC}(k)$, and performs the final GMM clustering with `--streamed-preprocess` and cluster reordering:

```bash
qsub -l cuda_free=1 xtec-gpu-clustering.sh
```

### B. Standalone Model Selection (BIC Sweep Only)
If you only wish to compute and inspect the BIC score curve without running final clustering:

```bash
qsub -l cuda_free=1 xtec-bic-sweep.sh
```

### Critical GPU Execution Notes:
- **Mandatory Streaming (`--streamed-preprocess`)**: Full 3D reciprocal volumes (20–50+ GB) exceed the 24 GB Titan RTX VRAM. All production job scripts must include `--streamed-preprocess` to stream data in ~1 GiB slabs and prevent CUDA OOM crashes.
- **Auto-$k^*$ Extraction**: `xtec-gpu-clustering.sh` eliminates the need to manually inspect intermediate BIC plots; it mathematically determines $k^*$ and clusters in a single allocation.

---

## 4. Monitoring Running Jobs

Check queue and slot status:
```bash
qstat -u $USER
```

Monitor live stdout/stderr execution log:
```bash
tail -f /path/to/log/qsub_batch.log
```

---

## 5. Mandatory "Show-Before-Submit" Verification Gate

> [!IMPORTANT]
> **Assistant Submission Rule**: AI agents and automated scripts must **never** execute `qsub <job_script>.sh` silently.
> Prior to submission, the assistant MUST display the complete script content to the user, highlighting:
> 1. Target queue and hosts (`-q`)
> 2. Memory limits (`-l mem_free`)
> 3. Core allocation (`-pe sge_pe`) or GPU flag (`-l cuda_free=1`)
> 4. Python binary path (`PYTHON_EXEC`, `NIGHTLY_PYTHON`, `GPU_PYTHON`)
> 5. Output log path (`#$ -o`)
> 6. Exact command-line parameters
> The user must confirm the configuration before the submission command is issued.

