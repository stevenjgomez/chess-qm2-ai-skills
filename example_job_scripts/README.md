# Grid Engine Example Job Scripts (`example_job_scripts/`)

This directory contains production-ready **Sun Grid Engine (SGE)** job script templates for running raw X-ray data reduction and GPU machine learning workflows on the **CLASSE compute cluster**.

All scripts execute unbuffered Python (`python -u`) so job execution logs can be monitored live in real time using `tail -f`.

---

## Script Catalog

| Script | Target Hardware / Queue | Purpose & Operational Phase |
| :--- | :--- | :--- |
| [`legacy-reduction-FeTe2-5A-281-fastpath.sh`](./legacy-reduction-FeTe2-5A-281-fastpath.sh) | `all.q@lnx307*,lnx311*,lnx312*,lnx313*`<br>(AVX2 CPU, 32 cores, 200 GB RAM) | **Phase 1: Warm Reference Fast-Path Reduction**: Stacks raw Pilatus CBF frames into `stack1.nxs`, runs headless orientation matrix (ORM) basinhopping, converts 1-rotation reciprocal volume (`1rot_hkli.nxs`), and renders diagnostic cross-sectional slices (`HK0`, `H0L`, `0KL`). |
| [`legacy-reduction-FeTe2-5A-batch.sh`](./legacy-reduction-FeTe2-5A-batch.sh) | `all.q@lnx307*,lnx311*,lnx312*,lnx313*`<br>(AVX2 CPU, 32 cores, 200 GB RAM) | **Phase 2: Temperature-Series Batch Reduction**: Iterates over all remaining temperature points for the sample, reusing the verified orientation matrix from `--ref-temp` without re-solving. |
| [`xtec-gpu-clustering.sh`](./xtec-gpu-clustering.sh) | `lnx4428` via `#$ -l cuda_free=1`<br>(NVIDIA Titan RTX, 24 GB VRAM) | **Phase 4: XTEC-GPU Clustering**: Executes high-throughput GMM clustering (`xtec-d`, `xtec-s`, `bic-d`, `bic-s`) on compiled 4D NeXus files using PyTorch and `torchgmm`. |

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

## 2. CUDA GPU Clustering Job Submission

For temperature-series scattering datasets compiled into `xtec_data.nxs` (via `generate_xtec_input.py`), submit clustering jobs to the dedicated GPU node (`lnx4428`):

```bash
qsub -l cuda_free=1 xtec-gpu-clustering.sh
```

### Customizing Clustering Parameters:
Edit `xtec-gpu-clustering.sh` to adjust:
- Direct voxel GMM mode (`xtec-d`) vs. peak-averaged mode (`xtec-s`).
- `--min-k` and `--max-k`: Range of cluster counts for model selection / BIC sweep.
- `-o`: Output directory for clustered HDF5 results and discrete Q-map figures.

---

## 3. Monitoring Running Jobs

Check queue and slot status:
```bash
qstat -u $USER
```

Monitor live stdout/stderr execution log:
```bash
tail -f /path/to/log/qsub_batch.log
```
