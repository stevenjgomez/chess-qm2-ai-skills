---
name: chess-legacy-reduction
description: >-
  Automate the legacy CHESS ID4B/QM2 beamline data reduction pipeline.
  Covers raw Pilatus CBF frame stacking, headless orientation matrix (ORM) solving
  with basinhopping, 3D reciprocal space HKL conversion (1rot and 3rot), cross-sectional
  projection visualization (HK, HL, KL planes), human-in-the-loop verification, and
  distributed multi-node batch reduction via Grid Engine (qsub) across CLASSE CPU compute nodes (lnx308, lnx1033-f1, lnx1034-f1).
---

# CHESS Legacy Data Reduction Pipeline Skill

This skill defines the operational standards, path conventions, cluster etiquette, and execution procedures for automating the legacy "CHESS" data reduction workflow for the QM2 beamline.

---

## 1. Remote Compute Etiquette & Python Environment

1. **Mandatory Cluster Execution via Grid Engine (`qsub`)**:
   - **All tasks that load or process data stacks** (frame stacking, ORM solving, 1rot/3rot reciprocal space conversions, and any tests reading `stack*.nxs`) **MUST be submitted as `qsub` jobs**:
     ```bash
     qsub -q 'all.q@lnx307*,all.q@lnx311*,all.q@lnx312*,all.q@lnx313*' -l mem_free=200G -pe sge_pe 32 <path-to-submission-script>.sh
     ```
   - This allocates 200 GB RAM and 32 threads, running independently under Grid Engine so jobs continue even if client workstations disconnect or shut down.
   - Monitor jobs with `/usr/local/bin/qstat -u ${USER}`.
   - > [!IMPORTANT]
   - > **Stack Loading I/O Latency & Memory Demands**:
   - > Data stacks (`stack*.nxs`) are 10–35+ GB each. Loading a stack into memory over NFS takes **tens of minutes** and consumes high memory bandwidth and RAM.
   - > **Never run stack-loading scripts interactively over SSH** (even on compute nodes like `lnx308`). Interactive runs risk session timeouts/disconnects and node overload. Always submit via `qsub`.
   - > [!WARNING]
   - > **AVX2 Vector Instruction Requirement & Node Compatibility (Exit Code -4 / SIGILL)**:
   - > The shared C library `libhkl.so` in `StevenGomezAlvarado_Codebase/` was compiled with **AVX2 vector instructions**.
   - > If a job is dispatched to older compute nodes in `all.q` that lack AVX2 (e.g. `lnx327` with Ivy Bridge Xeon E5-2660 v2), the CPU raises an invalid opcode trap (`traps: python invalid opcode in libhkl.so`), instantly killing the process with **exit code `-4` (`SIGILL`)**.
   - > Because users may not have submission permissions for dedicated `chess.q` queues (`has no permission for cluster queue`), always restrict `all.q` to verified AVX2-capable nodes using host wildcards:
   - > `-q 'all.q@lnx307*,all.q@lnx311*,all.q@lnx312*,all.q@lnx313*'`
   - > Known verified AVX2 hosts: `lnx307` (Broadwell), `lnx311`, `lnx312`, `lnx313` (Skylake Gold 6130), `lnx308`, `lnx1033-f1`, `lnx1034-f1`.
2. **Compute Nodes vs. Login Node**:
   - **`lnx201`** is a **login node** only. Never execute data reduction jobs directly here.
   - Direct interactive SSH execution is strictly limited to lightweight tasks (file inspection, checking logs, monitoring `qstat`, or visualizing pre-existing slices). All data reduction and stack processing must go through `qsub`.
3. **Designated Python Environments**:
   - **Legacy Reduction Pipeline**: All raw beamline stacking, ORM solving, and C-extension conversions (`libhkl.so`) strictly execute with:
     ```bash
     /nfs/chess/sw/anaconda3_jpcr/bin/python
     ```
     > [!CAUTION]
     > The `/nfs/chess/sw/anaconda3_jpcr` environment is a shared beamline resource and **must never be modified** (no `pip install`, no `conda install`).
   - **Modern Analysis & Visualization (`nxs_analysis_tools`)**: All post-conversion slicing, reciprocal volume visualization, and `plot_slice()` rendering strictly execute with:
     ```bash
     /nfs/chess/sw/anaconda3_sgomezalvarado_nightly/bin/python
     ```
     The diagnostic visualizer (`slice_visualizer.py`) automatically re-executes itself inside this environment to leverage `nxs_analysis_tools.plot_slice()` with dynamic crystallographic skew angles (e.g. `skew_angle=60°` for hexagonal $HK$).
4. **Headless Execution**:
   - Always set `matplotlib.use("Agg")` prior to importing `pyplot` to prevent display connection errors during remote runs.
5. **NeXus Memory Configuration**:
   - NeXus default memory slab limit is 2,000 MB. In all scripts handling stacks or 3D volumes, raise the limit immediately:
     ```python
     import nexusformat.nexus as nx
     nx.nxsetmemory(100000)  # 100 GB
     ```
6. **Real-Time Log Streaming & Unbuffered Execution (`python -u`)**:
   - Long-running reduction and conversion jobs (which process thousands of frames over 30–60+ minutes) must always be executed in unbuffered mode (`/nfs/chess/sw/anaconda3_jpcr/bin/python -u`).
   - Orchestrator wrappers must never use `subprocess.run(stdout=subprocess.PIPE)`, which traps stdout in memory until exit. Always use `subprocess.Popen` with line-by-line streaming and `flush=True` so that real-time progress updates (e.g. `Loaded frame X...`) stream immediately to cluster log files for user inspection.

---

## 2. Directory Conventions & File Discovery

Standard path patterns at CHESS ID4B:

- **Raw CBF Frames**:
  `/nfs/chess/id4b/{cycle}/{experiment-name}/raw6M/{sample}/{sample_id}/{temp}/{scan_folder}/`
  *Frames:* e.g. `FeTe2_PIL10_046_00000.cbf`, ...
- **Processed Data Output**:
  `/nfs/chess/id4baux/{cycle}/{experiment-name}/processed_old_way/{sample}/{sample_id}/{temp}/`
  *Outputs:* `stack1.nxs`, `unitcell.txt`, `ormatrix_auto.nxs`, `1rot_hkli.nxs`, `3rot_hkli.nxs`.
- **SPEC Data File**:
  `/nfs/chess/id4b/{cycle}/{experiment-name}/{sample}` (e.g. `/nfs/chess/id4b/2026-2/gomez-al-4850-a/FeTe2`)
- **Calibration Geometry & Masks**:
  `/nfs/chess/id4baux/{cycle}/{experiment-name}/calibrations/` (`.poni` and `.edf` masks)
- **Cluster Submission Scripts**:
  `/nfs/chess/id4baux/{cycle}/{experiment-name}/scripts/{sample_id}/`
- **Legacy Script Codebase**:
  `/nfs/chess/id4baux/2026-2/gomez-al-4850-a/StevenGomezAlvarado_Codebase/`

---

## 3. Human-in-the-Loop Clarification Rules

### 3.1 Ambiguous Calibration (.poni) and Mask (.edf) Files
- **Modes**: Two experimental geometries exist:
  - **`transmission`**: Bulk samples in transmission (e.g. `ceO2_15keV_trans.poni`, `mask_trans.edf`).
  - **`reflection`**: Thin-film / grazing-incidence reflection (e.g. `ceO2_15keV_new.poni`, `mask_new1.edf`).
- **Mandatory Rule**: If more than one `.poni` file or more than one `.edf` mask file is found, or geometry mode is unconfirmed, **never guess**.
- **Action**: Halt and consult the user (using `ask_question` or direct prompt) with the detected filenames to confirm the exact files to apply.

### 3.2 Unit Cell Parameters & CIF Support
- Accept either a Crystallographic Information File (**`.cif`**)—the crystallography standard—or raw lattice parameters $a, b, c, \alpha, \beta, \gamma$.
- When a `.cif` is provided, automatically extract `_cell_length_*` and `_cell_angle_*`, stripping uncertainties (e.g. `5.271(4)` $\rightarrow$ `5.271`).
- Cache the parameters to `unitcell.txt`:
  ```text
  a,b,c,alpha,beta,gamma
  ```

### 3.3 Rotation Scan Count Verification (1 vs. 3 vs. >3)
- **Standard Counts**: Data reduction pipelines expect either:
  - **1 rotation scan** (e.g. `FeTe2-5A`): Reconstructed using `Pil6M_HKLConv_3D_2022_1rot.py` $\rightarrow$ `1rot_hkli.nxs`.
  - **3 rotation scans** (e.g. `FeGe-ST-2A`): Stacks 3 scans (`stack1.nxs`, `stack2.nxs`, `stack3.nxs`) and converts using `Pil6M_HKLConv_3D_2022_3rot.py` $\rightarrow$ `3rot_hkli.nxs`.
- **Anomalous Cases (>3 Rotations)**:
  - Having more than 3 scans in any temperature directory is unusual and suggests interrupted scans or non-standard configurations.
  - **Mandatory Rule**: If more than 3 scans are detected for any temperature, the agent **must halt and consult the user** to clarify which scans should be processed.

### 3.4 Reciprocal Space Grid Limits: Energy & Lattice Parameter Scaling
- **Physics of Accessible Miller Indices**:
  - The maximum observable momentum transfer is bounded by the Ewald sphere and detector geometry: $Q_{\text{max}} = \frac{4\pi \sin\theta_{\text{max}}}{\lambda}$, where $\lambda \propto 1/E$.
  - Because reciprocal lattice vector lengths are inversely proportional to real-space lattice parameters ($a^* \approx 2\pi/a$, $c^* \approx 2\pi/c$), the maximum accessible Miller indices scale directly with both the incident energy and the real-space lattice dimensions:
    $$H_{\text{max}} \sim \frac{2 \sin\theta_{\text{max}}}{\lambda} \cdot a, \quad K_{\text{max}} \sim \frac{2 \sin\theta_{\text{max}}}{\lambda} \cdot b, \quad L_{\text{max}} \sim \frac{2 \sin\theta_{\text{max}}}{\lambda} \cdot c$$
  - **Lattice Anisotropy**: When a crystal has anisotropic lattice constants (e.g. $\text{FeTe}_2$ with $a = 3.74\text{ \AA}$ and $c = 5.78\text{ \AA}$), the reciprocal spacing along $c^*$ is smaller. For the same physical $Q$-cutoff, more $L$ reciprocal lattice units fit into the detector's scattering volume than $H$ or $K$ (e.g. $L \in [-3.5, 3.5]$ vs. $H, K \in [-3.0, 3.0]$).
  - **Large Unit Cells**: Materials with large unit cells (e.g. superlattices or layered compounds with $c \ge 20\text{ \AA}$) will have densely spaced reciprocal points and require substantially higher index bounds (e.g. $L \ge 15$) even at lower incident energies.
- **Default Grid Limits**: For standard full-energy ID4B beamline experiments (~28 keV) with typical small-unit-cell inorganic crystals, the default conversion grid in `Pil6M_HKLConv_3D_2022_1rot.py` and `orchestrate_reduction.py` is:
  - $H: \pm 5.1$ (step 0.02)
  - $K: \pm 5.1$ (step 0.02)
  - $L: \pm 9.1$ (step 0.02)
- **Operational Rule**: Retain the standard beamline defaults ($5.1, 5.1, 9.1$) in the underlying reduction codebase, but always evaluate the expected $(H_{\text{max}}, K_{\text{max}}, L_{\text{max}})$ based on the combination of beam energy ($E$) and unit cell dimensions ($a, b, c$), passing customized tighter bounds via CLI flags (`--hlim`, `--klim`, `--llim`) to prevent generating oversized, zero-padded volumes.

---

## 4. Standard Reduction Workflow

### Phase 1: Warmest Temperature Single-Rotation Fast Path
1. **Identify Warmest Temperature**: Sort temperature folders numerically and select the maximum $T$ (e.g., $281\text{ K}$).
2. **Stack Rotation 1 Only**: Run `stack_em_all.py` on the first scan folder of the warmest temperature to produce `stack1.nxs`.
3. **Headless ORM Solving**: Run the headless orientation solver (`orm_solver.py`):
   - Adaptive peak finding between bounds (`valmin`, `lower_bound`, `upper_bound`).
   - Euler angle optimization via `scipy.optimize.basinhopping` and `hkl.Calc_HKL`.
   - > [!NOTE]
   - > **Runtime Expectation**: ORM solving involves multi-stage non-linear basinhopping with local BFGS iterations over dozens of reflections and can take **from tens of minutes up to several hours**. Submitting as a batch job via `qsub` is strictly required to decouple from local client uptime.
   - Export `ormatrix_auto.nxs`, `peaklist1.npy`, and `ormfinder.log`.
4. **1-Rotation HKL Conversion**: Execute `Pil6M_HKLConv_3D_2022_1rot.py` to produce `1rot_hkli.nxs`.
5. **Cross-Sectional Visualization**: Slice the 3D volume along principal planes using `nxs_analysis_tools.plot_slice()` executed under `/nfs/chess/sw/anaconda3_sgomezalvarado_nightly/`:
   - $(HK0)$: Central cut along $L$, sheared by dynamic crystallographic skew angle $\gamma^*$ (e.g. `skew_angle=60°` for hexagonal lattices) to preserve true lattice symmetry.
   - $(H0L)$: Central cut along $K$, with skew angle $\beta^*$ (typically $90^\circ$).
   - $(0KL)$: Central cut along $H$, with skew angle $\alpha^*$ (typically $90^\circ$).
   Save as `slice_HK.png`, `slice_HL.png`, `slice_KL.png`, and `slices_summary.png`.
6. **User Verification Gate**: Present cross-sectional slice figures to the user. **Wait for user confirmation** before proceeding.

### Phase 2: Full Distributed Batch Reduction
Upon user approval of the orientation matrix:
1. Stack rotations 2 and 3 for the reference temperature (`stack2.nxs`, `stack3.nxs`).
2. Stack all 3 rotations for all remaining temperatures.
3. Submit `Pil6M_HKLConv_3D_2022_3rot.py` jobs across available compute nodes via `qsub` or parallel SSH, applying the verified orientation matrix.
4. Generate final summary figures and update `pipeline_status.json`.

---

## 5. Sample Audit Log (`pipeline_status.json`)

Maintain a persistent status JSON file in the sample's processed root directory tracking configuration, temperature status, timestamps, and orientation matrix verification state.
