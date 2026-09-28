# Global Assistant Rules & Cluster Etiquette (`GEMINI.md`)

This file defines the mandatory operational constraints, cluster etiquette, and execution rules that apply to all AI assistants and autonomous agents operating within the `chess-qm2-ai-skills` workspace and on the Cornell High Energy Synchrotron Source (CHESS) CLASSE compute cluster.

---

## 1. Strict Remote Environment Immutability

> [!CAUTION]
> **Mandatory Read-Only Policy**: All remote Python and Conda environments on CLASSE (located under `/nfs/chess/sw/`) are **strictly read-only / immutable**.
> 
> 1. **No Package Modifications**: Assistants and automated tools must **NEVER** run `pip install`, `pip uninstall`, `conda install`, `conda update`, or alter packages, binaries, or shebang lines in any cluster environment (`anaconda3_jpcr`, `anaconda3_sgomezalvarado`, `anaconda3_sgomezalvarado_nightly`, `qm2_XTEC312`, etc.).
> 2. **Halt and Report on Missing Dependencies**: If an environment lacks a required package or raises an `ImportError` or `AttributeError`, the assistant must **halt execution immediately and report the discrepancy to the user** for resolution. Never attempt to install or upgrade packages into cluster environments.
> 3. **No Unauthorized Redirection**: Assistants must never substitute an unapproved third environment (such as arbitrarily replacing `anaconda3_sgomezalvarado_nightly` with `anaconda3_sgomezalvarado` to bypass an installation error). Each task must strictly use the designated architectural interpreter mapped to that pipeline stage.

---

## 2. Stage-Specific Architectural Interpreter Mappings

Beamline pipelines strictly segregate processing stages across dedicated environments to prevent library conflicts (e.g. between legacy AVX2 C-extensions and modern PyTorch CUDA stacks). Always dispatch each task to its designated architectural constant:

| Architectural Constant | Remote Interpreter Path | Dedicated Pipeline Stage |
| :--- | :--- | :--- |
| **`PYTHON_EXEC`** | `/nfs/chess/sw/anaconda3_jpcr/bin/python` | **Legacy Reduction**: Raw Pilatus CBF frame stacking (`stack_em_all.py`), headless orientation matrix solving (`orm_solver.py`), and 1rot/3rot reciprocal space conversions (strictly frozen; required for `libhkl.so`). |
| **`NIGHTLY_PYTHON`**<br>(or **`VIS_PYTHON`**) | `/nfs/chess/sw/anaconda3_sgomezalvarado_nightly/bin/python` | **Downstream Analysis & Preparation**: Diagnostic reciprocal slicing (`slice_visualizer.py`), `nxs_analysis_tools.plot_slice()`, linecuts (`Scissors`), and 4D dataset compilation (`generate_xtec_input.py`). |
| **`GPU_PYTHON`**<br>(or **`XTEC_BIN`**) | `/nfs/chess/sw/qm2_XTEC312/bin/python`<br>(CLI: `/nfs/chess/sw/qm2_XTEC312/bin/xtec-gpu`) | **GPU Machine Learning**: Unsupervised clustering (XTEC-GPU), PyTorch, `torchgmm`, and BIC model sweeps on `lnx4428`. |

---

## 3. Remote Node Etiquette & Dual Execution Modes

| Host / Queue Target | Node Class | Permitted Execution Protocol |
| :--- | :--- | :--- |
| **`lnx201.classe.cornell.edu`** | **Login Gateway** | Shell sessions, file editing, git, job submission. **NEVER run compute**, heavy array manipulation, or slicing here. |
| **`interactive.q`** | **Interactive Compute** | **Interactive Human Sessions**: `qrsh -q interactive.q -l mem_free=350G`.<br>*Note for Automated Agents:* Automated `qrsh` sessions over SSH prompt for Kerberos passwords (`Password for <user>@CLASSE.CORNELL.EDU:`), causing unattended scripts to hang. |
| **`all.q@lnx307*,lnx311*,lnx312*,lnx313*`** | **AVX2 Batch Compute** | **Automated / Agentic Sessions**: Submit short-lived SGE batch wrappers via `qsub` (200 GB RAM, AVX2 pool) and stream stdout/stderr via `tail -f <log>` or monitor via `qstat`. |
| **`lnx4428`** via `-l cuda_free=1` | **CUDA GPU Compute** | **Grid Engine GPU Submission**: Mandatory `qsub -l cuda_free=1 <job_script>.sh` for all XTEC clustering workloads. |

---

## 4. Mandatory "Show-Before-Submit" Verification Gate

> [!IMPORTANT]
> **Verification Gate Rule**: Prior to executing `qsub <job_script>.sh` for any stage (data reduction, 4D preparation, or GPU clustering), the assistant **MUST present the complete script text to the user**, highlighting:
> 1. Target queue and hosts (`-q`)
> 2. Memory allocation (`-l mem_free`)
> 3. Parallel environment slots (`-pe sge_pe`) or GPU flags (`-l cuda_free=1`)
> 4. Python binary path (`PYTHON_EXEC`, `NIGHTLY_PYTHON`, `GPU_PYTHON`)
> 5. Output log path (`#$ -o`)
> 6. Exact command-line parameters
> 
> The assistant must obtain explicit user confirmation before issuing the `qsub` submission command.
> 
> *XTEC GPU Batch Rule*: For XTEC-GPU clustering on `lnx4428` (`-l cuda_free=1`), scripts execute the autonomous pipeline (BIC model selection sweep $\rightarrow$ autonomous $k^* = \operatorname{argmin}_k \text{BIC}$ determination $\rightarrow$ final GMM clustering with reordering) in a single reservation. All CLI invocations on full reciprocal volumes must include `--streamed-preprocess` to prevent GPU memory exhaustion.

---

## 5. Pipeline Architecture Detection (Two-Level Sample Hierarchy)

Samples at CHESS ID4B are organized hierarchically:
`/nfs/chess/id4baux/{cycle}/{experiment}/{reduction_pipeline}/{sample_name}/{sample_id}/`

Because the material category (e.g. `FeTe2/`) can exist under *both* `nxrefine/` and `processed_old_way/` simultaneously if different sample mounts were processed with different tools, **always evaluate the specific sample leaf `{sample_name}/{sample_id}/`**:

1. **NXRefine Architecture** (`nxrefine/{sample_name}/{sample_id}/`):
   - Layout: Top-level wrapper files `*_<temp>.nxs` linking via `NXlink` to `<temp>/transform.nxs`.
   - Coordinate Axes: **`['Ql', 'Qk', 'Qh']`** (Axis 0 = $L$, Axis 1 = $K$, Axis 2 = $H$).
   - `Scissors` tuple order: **`(L, K, H)`**.
2. **Legacy CHESS Architecture** (`processed_old_way/{sample_name}/{sample_id}/`):
   - Layout: Subdirectories `<temp>/` containing `stack*.nxs`, `1rot_hkli.nxs`, `3rot_hkli.nxs`.
   - Coordinate Axes: **`['H', 'K', 'L']`** (Axis 0 = $H$, Axis 1 = $K$, Axis 2 = $L$).
   - `Scissors` tuple order: **`(H, K, L)`**.

---

## 6. Strict Data Safety Policy

> [!CAUTION]
> **NEVER delete, remove (`rm`, `os.remove`), or truncate any `.nxs` files** (`transform.nxs`, `*hkli*.nxs`, `stack*.nxs`, `xtec_data.nxs`).
> All re-runs, alternative reconstructions, or test outputs must use non-destructive versioning (`1rot_hkli_1.nxs`, `xtec_data_1.nxs`) rather than replacing or deleting existing datasets.

---

## 7. Legacy Script Codebase (`$HOME/chess_legacy_codebase/`)

Legacy reduction scripts (`stack_em_all.py`, `Pil6M_HKLConv_3D_2022_1rot.py`, `3rot.py`, `hkl.py`, `libhkl.so`) are maintained in the user's home directory:
`$HOME/chess_legacy_codebase/` (overridable with `$CHESS_LEGACY_CODEBASE` or `--codebase`).

Run-cycle paths (such as `/nfs/chess/id4baux/2026-2/...`) get archived periodically and must **never** be hardcoded into tools or submission scripts.
