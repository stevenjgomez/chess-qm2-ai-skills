# CHESS ID4B/QM2 Experiment-Time Workflow Operations Guide

This operational manual outlines the day-to-day usage of the headless workflow controller (`qm2`) and the companion agent for synchrotron experiments at CHESS ID4B/QM2.

---

## 1. Quickstart & Configuration

All experiment parameters, directory paths, and cluster settings are declared in a YAML configuration file (e.g. `config.yaml`). Copy the provided template to get started:

```bash
cp config.example.yaml config.yaml
```

### Essential Parameters to Verify Before Beamtime:
- **`sample_name` & `sample_id`**: E.g. `FeTe2` and `FeTe2-5A`.
- **`paths.raw_root`**: Path to incoming raw Pilatus CBF directory (e.g. `/nfs/chess/raw/2026-2/id4b/gomez-al-4850-a/FeTe2-5A/`).
- **`paths.processed_root`**: Destination directory for stacks and reciprocal volumes (e.g. `/nfs/chess/id4baux/2026-2/gomez-al-4850-a/processed_old_way/FeTe2/FeTe2-5A/`).
- **`crystallography.unit_cell`**: Fallback real-space lattice parameters `"a,b,c,alpha,beta,gamma"`.
- **`crystallography.key_temperatures`**: Designated key temperatures for priority HKLI (e.g. `[15.0, 100.0, 281.0]`).
- **`fastpath.frames`**: Sub-sampled frame count for fast orientation determination (e.g. `500` frames = $50^\circ$ wedge).
- **`fastpath.stride`**: Sub-sampling stride (e.g. `1` or `2`).

### Pre-Flight Remote Access Check:
Verify unattended non-interactive SSH connectivity to `lnx201` before launching beamline jobs:
```bash
ssh -o BatchMode=yes -o ConnectTimeout=15 <username>@lnx201.classe.cornell.edu 'echo CHESS_SSH_OK'
```
*(If unconfigured, consult the [SSH First-Time Setup & Non-Interactive Access Guide](../references/ssh-first-use.md)).*

### Initial Lattice Parameter Priority Hierarchy:
The workflow controller resolves starting lattice parameters using a strict priority order:
1. **Priority 1 (Highest)**: Sample metadata JSON at `/nfs/chess/id4baux/{cycle}/{experiment}/metadata/{sample_name}.json` (e.g. `FeGeSb.json`, `SiC.json`), populated by users prior to measurement with `"sample_unit_cell": "a=5.0027, b=5.0027, c=4.0548, alpha=90, beta=90, gamma=120"`.
2. **Priority 2**: `crystallography.unit_cell` declared in `config.yaml`.
3. **Priority 3**: Crystallographic Information File (`*.cif`).
4. **Priority 4**: Local text file `unitcell.txt` in the processed sample directory.

The resolved unit cell and its provenance are tracked in `.manifest.json` and visible in `./scripts/qm2 status`.

---

## 2. Four-Stage Staged Rollout

To ensure data integrity and cluster harmony, transition through these operational modes:

```
[Mode 1: Observe-Only]  -->  [Mode 2: Dry-Run Preview]  -->  [Mode 3: Manual Approval]  -->  [Mode 4: Low-Risk Auto]
  Scan & inspect only         Generate SGE scripts            User triggers jobs             Continuous daemon
```

### Mode 1: Observe-Only
Discover incoming CBF files, group scans, and inspect stability without generating any jobs:
```bash
./scripts/qm2 --config config.yaml scan
./scripts/qm2 --config config.yaml status
```

### Mode 2: Dry-Run Preview
Preview the prioritized job queue and verify generated SGE submission wrapper scripts without touching the SGE queue:
```bash
./scripts/qm2 --config config.yaml plan
./scripts/qm2 --config config.yaml run --dry-run
```
Inspect the generated script in `scripts_dir`:
```bash
cat /nfs/chess/id4baux/2026-2/gomez-al-4850-a/scripts/FeTe2-5A/qm2_FeTe2-5A_orientation_281.sh
```

### Mode 3: Manual Approval (Recommended Initial Beamtime Mode)
The user triggers jobs when ready. The controller enforces priority order and the $\le 3$ CPU job limit:
```bash
# 1. Dispatch highest-priority eligible job
./scripts/qm2 --config config.yaml run --max-jobs 1

# 2. Check cluster jobs and SGE slots
./scripts/qm2 --config config.yaml jobs

# 3. Stream real-time job output log
tail -f /nfs/chess/id4baux/2026-2/gomez-al-4850-a/scripts/FeTe2-5A/qm2_FeTe2-5A_orientation_281.log
```

### Mode 4: Low-Risk Automation Daemon
Runs the continuous background polling loop, automatically dispatching eligible P0, P1, P2, and P3 stages as raw scans complete:
```bash
./scripts/qm2 --config config.yaml watch --auto --interval 30
```
- **Pause at any time**:
  ```bash
  ./scripts/qm2 --config config.yaml pause
  ```
- **Resume**:
  ```bash
  ./scripts/qm2 --config config.yaml resume
  ```

---

## 3. Human-in-the-Loop Orientation Verification Gate

> [!IMPORTANT]
> **Mandatory Orientation Verification Gate**
>
> All 1-rotation and 3-rotation HKLI reductions (`hkl_1rot`, `hkl_3rot`) are strictly halted until the scientist approves the orientation matrix. This prevents undetected lattice shear or pseudosymmetry indexing.

### Verification Procedure:
1. When orientation completes on the reference temperature (e.g. 281 K), the controller alerts:
   ```
   [ACTION REQUIRED] Orientation matrix solved for reference temperature 281K. Human approval required: run 'qm2 approve-orm'.
   ```
2. Inspect the diagnostic cross-sectional projections rendered in the reference processed directory:
   - HK slice: `{processed_root}/281/slice_HK.png`
   - HL slice: `{processed_root}/281/slice_HL.png`
   - KL slice: `{processed_root}/281/slice_KL.png`
   - Summary: `{processed_root}/281/slices_summary.png`
3. Verify that:
   - Bragg reflections align cleanly with reciprocal integer grid lines ($H, K, L \in \mathbb{Z}$).
   - No severe streak shearing or double-peak splitting is present.
   - Mean HKL deviation reported in status is small ($< 0.05$ r.l.u.).
4. Grant human approval:
   ```bash
   ./scripts/qm2 --config config.yaml approve-orm --user "steve"
   ```
   *This immediately marks orientation `VERIFIED` and unblocks the P1/P2/P3 HKLI queues.*

---

## 4. Priority Queue Policy Reference

When an SGE CPU slot becomes available, the controller selects the highest-priority eligible candidate:

| Priority | Stage | Purpose | Conditions |
| :---: | :--- | :--- | :--- |
| **P0** | `orientation` | Determine $UB$ matrix on reference temperature | Reference scan complete & stacked |
| **P1** | `hkl_1rot` (Key Temps) | Rapid 4D HKLI on lowest, highest, and user-selected temps | $UB$ Verified + `stack1.nxs` ready |
| **P2** | `hkl_1rot` (Other Temps) | 1-rotation HKLI for intermediate temperature points | $UB$ Verified + `stack1.nxs` ready |
| **P3** | `hkl_3rot` (Full) | Comprehensive reciprocal reconstruction (3 rotations) | $UB$ Verified + `stack1..3.nxs` ready |
| **P4** | `slicing` & `xtec` | Diagnostic slicing and GPU clustering on `lnx4428` | HKLI volume complete / full series ready |

### Updating Key Temperatures on the Fly:
Scientists can designate or revise key temperatures dynamically without restarting the daemon:
```bash
./scripts/qm2 --config config.yaml set-key-temps 15 50 120 281
```

---

## 5. Diagnostic Validation and Failure Recovery

### Output Validation
Validate all completed stages to ensure files exist, are $>1$ MB, and contain valid NeXus groups:
```bash
./scripts/qm2 --config config.yaml validate
```

### Safe Stage Retries
If an SGE job fails or produces truncated output, it enters `RETRYABLE_FAILURE`:
```bash
./scripts/qm2 --config config.yaml retry --temp 281 --stage stacking
```
- Maximum retries: 3 attempts.
- Beyond 3 attempts, the stage enters `FATAL_FAILURE` and requires scientific inspection of the log.

### Generating Status Reports
Create an updated, timestamped Markdown experiment summary with relative image links:
```bash
./scripts/qm2 --config config.yaml report --out ./experiment_report.md
```
