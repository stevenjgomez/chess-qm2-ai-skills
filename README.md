# CHESS QM2 AI Skills Suite (`chess-qm2-ai-skills`)

A modular collection of domain-specific scientific computing and synchrotron skills for **Google Antigravity** and the **Gemini CLI**. Tailored specifically for X-ray diffraction, reciprocal space volume reconstruction, and temperature-series scattering analysis at the **Cornell High Energy Synchrotron Source (CHESS)** ID4B / QM2 beamline.

---

## Skill Catalog

| Skill | Directory | Description & Capabilities |
| :--- | :--- | :--- |
| **`chess-legacy-reduction`** | [`chess-legacy-reduction/`](./chess-legacy-reduction/) | **Autonomous Beamline Reduction Pipeline**: Automates stacking raw Pilatus 6M CBF detector frames, headless orientation matrix (ORM) solving via `scipy.optimize.basinhopping`, 3D reciprocal space HKL conversion (`1rot` and `3rot`), cross-sectional plane visualization ($(HK0)$, $(H0L)$, $(0KL)$), human-in-the-loop verification gates, and Grid Engine (`qsub`) batch scheduling across AVX2-capable CLASSE nodes. Includes a turnkey Python CLI suite in `scripts/`. |
| **`reciprocal-space-analysis`** | [`reciprocal-space-analysis/`](./reciprocal-space-analysis/) | **3D Reciprocal Space & NeXus Analysis**: Reconstruction, indexing, alignment, and slicing of 3D reciprocal space volumes (NeXus/HDF5) via `nxs_analysis_tools`. Enforces skew projections for non-orthogonal/hexagonal lattices, multi-dataset linecuts, and interactive cluster execution etiquette (`qrsh`). |
| **`xtec-gpu-analysis`** | [`xtec-gpu-analysis/`](./xtec-gpu-analysis/) | **GPU Temperature Clustering (XTEC-GPU)**: High-throughput clustering of temperature-series scattering datasets using PyTorch and `torchgmm`. Features automated 4D NeXus compilation from 3D volumes (NXRefine and legacy CHESS) via `TempDependence.to_xtec()`, enforces cluster node etiquette (interactive CPU nodes via `qrsh` vs Grid Engine GPU queue `qsub -l cuda_free=1`), autonomous model selection ($k^* = \operatorname{argmin}_k \text{BIC}$), mandatory streamed preprocessing (`--streamed-preprocess`) for large volumes (>24 GB), discrete Q-map visualization, and automated Markdown reporting. Includes turnkey input generation CLI in `scripts/`. |

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

## SSH Remote Access & Authentication Setup (Suggested Approach)

To allow automated assistant tools, job monitoring (`qstat`), and remote analysis commands to run non-interactively without stalling on password or two-factor authentication prompts, configure SSH access from your local machine to the CLASSE login gateway (`lnx201.classe.cornell.edu`).

Different users and institutions maintain different security policies and authentication pathways. Below is the **recommended approach**, followed by alternative pathways.

### Recommended Pathway: Ed25519 Key Pair with Keychain / Agent

1. **Generate a dedicated SSH key pair** (on your local machine):
   ```bash
   ssh-keygen -t ed25519 -C "<user>@classe" -f ~/.ssh/id_ed25519_classe
   ```
   *(Setting a passphrase on the private key is strongly recommended for security).*

2. **Copy the public key to CLASSE**:
   ```bash
   ssh-copy-id -i ~/.ssh/id_ed25519_classe.pub <username>@lnx201.classe.cornell.edu
   ```
   *(Authenticate once interactively with your CLASSE password and Duo 2FA).*

3. **Configure `~/.ssh/config` on your local machine**:
   ```ssh-config
   Host lnx201.classe.cornell.edu lnx201
     HostName lnx201.classe.cornell.edu
     User <username>
     IdentityFile ~/.ssh/id_ed25519_classe
     IdentitiesOnly yes
     AddKeysToAgent yes
     UseKeychain yes  # macOS: saves passphrase in Apple Keychain
   ```

4. **Load the key into your SSH agent / Keychain (one-time)**:
   - On **macOS**:
     ```bash
     ssh-add --apple-use-keychain ~/.ssh/id_ed25519_classe
     ```
   - On **Linux**:
     ```bash
     ssh-add ~/.ssh/id_ed25519_classe
     ```

5. **Verify non-interactive login**:
   ```bash
   ssh lnx201 "echo 'Connected successfully to ' \$(hostname) ' as ' \$(whoami)"
   ```

### Alternative Authentication Pathways

- **Pathway B: SSH Connection Multiplexing (`ControlMaster`)**:
  If institutional policy requires Duo 2FA on every distinct handshake and restricts standalone public key authentication, configure connection multiplexing. You authenticate once in an interactive terminal, and all subsequent background or assistant commands share the open connection:
  ```ssh-config
  Host lnx201.classe.cornell.edu lnx201
    HostName lnx201.classe.cornell.edu
    User <username>
    ControlMaster auto
    ControlPath ~/.ssh/sockets/%r@%h:%p
    ControlPersist 4h
  ```
  *(Create the socket directory with `mkdir -p ~/.ssh/sockets` and connect once via `ssh lnx201` in your terminal).*

- **Pathway C: Kerberos / GSSAPI Ticket Authentication**:
  For systems with local Kerberos realm integration (e.g., Cornell-managed workstations):
  ```bash
  kinit <username>@CLASSE.CORNELL.EDU
  ```
  With `~/.ssh/config` configured:
  ```ssh-config
  Host lnx201.classe.cornell.edu lnx201
    HostName lnx201.classe.cornell.edu
    User <username>
    GSSAPIAuthentication yes
    GSSAPIDelegateCredentials yes
  ```

---

## Cluster & Beamline Etiquette

All skills in this suite strictly adhere to CLASSE compute cluster etiquette, Grid Engine allocation rules, and beamline hardware constraints.

### Node Topology & Execution Protocols

| Node Class | Host / Queue Target | Role & Hardware Profile | Permitted Execution Protocol |
| :--- | :--- | :--- | :--- |
| **Login Gateway** | `lnx201.classe.cornell.edu` | Shell sessions, file editing, git, job submission. **No compute.** | Interactive login via `ssh <user>@lnx201.classe.cornell.edu`. Never run compute, heavy array manipulation, or slicing here. |
| **Batch Reduction Nodes** | `all.q@lnx307*`<br>`all.q@lnx311*`<br>`all.q@lnx312*`<br>`all.q@lnx313*` | Heavy raw reduction, Pilatus CBF frame stacking (10–35+ GB/rotation), ORM basinhopping, 3D volume reconstruction. Verified AVX2 CPU instruction set for `libhkl.so`. | **Mandatory Grid Engine batch submission (`qsub`)** using bash wrapper scripts (see [`example_job_scripts/`](./example_job_scripts/)). |
| **Interactive Analysis Nodes** | `interactive.q` (Grid Engine) | Downstream analysis (`nxs_analysis_tools`), 2D reciprocal slicing (`plot_slice`), 1D linecuts (`Scissors`), 4D XTEC input compilation (`to_xtec`), LaTeX compilation. | **Mandatory 3-step `qrsh` interactive session from `lnx201`** (see below). Direct SSH into compute nodes (such as `lnx308`) is strictly prohibited. |
| **CUDA GPU Compute Node** | `lnx4428.classe.cornell.edu` | GPU-accelerated machine learning, XTEC-GPU clustering, PyTorch, `torchgmm`. **NVIDIA Titan RTX (24 GB VRAM).** | **Mandatory Grid Engine GPU batch submission (`qsub`)** requesting the GPU resource: `qsub -l cuda_free=1 <job_script>.sh` (see [`example_job_scripts/`](./example_job_scripts/)). |

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

1. **Pipeline Architecture Detection & Two-Level Sample Hierarchy**:
   - In `/nfs/chess/id4baux/{cycle}/{experiment}/`, samples are structured hierarchically: `{sample_name}/{sample_id}/` (e.g. `FeTe2/FeTe2-5A` vs. `FeTe2/FeTe2-8A`, or `KV2Se2O/KVSO-1C`).
   - The top-level category (`FeTe2/`) can exist under *both* `nxrefine/` and `processed_old_way/` simultaneously if different sample mounts were reduced with different pipelines.
   - **Architecture Detection Rule**: Always evaluate the specific sample leaf `{sample_name}/{sample_id}/`:
     - **NXRefine Architecture** (`nxrefine/{sample_name}/{sample_id}/`): Top-level `*_<temp>.nxs` wrappers linking to `<temp>/transform.nxs`. Coordinate axes: **`['Ql', 'Qk', 'Qh']`** (Axis 0 = $L$, Axis 1 = $K$, Axis 2 = $H$). `Scissors` cuts follow $(L, K, H)$ order.
     - **Legacy CHESS Architecture** (`processed_old_way/{sample_name}/{sample_id}/`): Subdirectories `<temp>/` containing `stack*.nxs`, `1rot_hkli.nxs`, `3rot_hkli.nxs`. Coordinate axes: **`['H', 'K', 'L']`** (Axis 0 = $H$, Axis 1 = $K$, Axis 2 = $L$). `Scissors` cuts follow $(H, K, L)$ order.

2. **Strict Remote Environment Immutability**:
   - > [!CAUTION]
   - > **Mandatory Read-Only Policy**: All remote Python/Conda environments on CLASSE (`anaconda3_jpcr`, `anaconda3_sgomezalvarado`, `anaconda3_sgomezalvarado_nightly`, `qm2_XTEC312`) are **strictly read-only / immutable**.
   - > Never execute `pip install`, `conda install`, or alter environment configuration files or shebangs.
   - > If an environment lacks a required package or fails an import, the assistant must **halt and report the discrepancy to the user** immediately rather than attempting installation or modifying system paths.

3. **Stage-Specific Architectural Interpreter Constants**:
   - Beamline automation explicitly segregates pipeline stages across designated environments using architectural constants:
     - **`PYTHON_EXEC`** (`/nfs/chess/sw/anaconda3_jpcr/bin/python`): Dedicated to raw frame stacking, ORM basinhopping, and 1rot/3rot reciprocal conversions (strictly frozen; required for `libhkl.so`).
     - **`NIGHTLY_PYTHON` / `VIS_PYTHON`** (`/nfs/chess/sw/anaconda3_sgomezalvarado_nightly/bin/python`): Dedicated to downstream reciprocal slicing (`slice_visualizer.py`), `nxs_analysis_tools.plot_slice()`, and 4D dataset compilation (`generate_xtec_input.py`).
     - **`GPU_PYTHON` / `XTEC_BIN`** (`/nfs/chess/sw/qm2_XTEC312/bin/xtec-gpu`): Dedicated to GPU-accelerated GMM clustering on `lnx4428`.
   - *Defining "Unauthorized Redirection"*: Substituting an unapproved third environment (such as arbitrarily replacing `anaconda3_sgomezalvarado_nightly` with `anaconda3_sgomezalvarado` to bypass an installation error) is prohibited. Orchestrators using stage-appropriate designated constants for each specific step is standard architecture.

4. **Dual Execution Pattern: Interactive Sessions (`qrsh`) vs. Batch (`qsub`)**:
   - **Interactive Human Sessions**: Use `qrsh -q interactive.q -l mem_free=350G` from `lnx201`.
   - **Automated / Agentic Sessions**: In unattended automated sessions, `qrsh` spawns an SSH/rsh connection that prompts interactively for Kerberos passwords (`Password for <user>@CLASSE.CORNELL.EDU:`), causing headless scripts to hang. Automated workflows must submit short-lived SGE batch wrappers via `qsub` (e.g. [`example_job_scripts/xtec-prep-batch.sh`](./example_job_scripts/xtec-prep-batch.sh)), streaming stdout/stderr via `tail -f <log>`.

5. **Mandatory "Show-Before-Submit" Verification Gate**:
   - Prior to executing `qsub <job_script>.sh` for any stage (data reduction, 4D preparation, or GPU clustering), the assistant MUST display the full script content to the user, highlighting queue targets, memory requests, core allocations, environment path, and command arguments. The user must provide confirmation before the job is submitted.

6. **Metadata Verification & Modal Exposure Filtering**:
   - In 4D XTEC input preparation (`generate_xtec_input.py`), the assistant extracts scan count times via NeXus (`logs/T`) or raw SPEC files (`#T`), verifies that `transform.nxs` exists and has non-zero size (>0 bytes), and automatically excludes outlier exposure scans (such as parent orientation runs) via modal exposure filtering to preserve Poisson statistics and prevent false clustering boundaries.

7. **AVX2 Vector Instruction Enforcing**:
   - The beamline's compiled C library (`libhkl.so`) requires AVX2 vector instructions. Jobs dispatched to older nodes (e.g. `lnx327`) crash with `SIGILL` (Exit Code `-4`). Queue targets are strictly restricted to verified AVX2 hosts (`lnx307`, `lnx311`, `lnx312`, `lnx313`).

8. **Strict Data Safety Policy**:
   - **NEVER delete or remove any `.nxs` files**. All reduction and transformation workflows generate non-destructively suffixed files (`1rot_hkli_1.nxs`, `xtec_data_1.nxs`, etc.) rather than overwriting or deleting prior datasets.

9. **Energy & Lattice Parameter Scaling**:
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
│   ├── legacy-reduction-FeTe2-5A-batch.sh
│   ├── xtec-prep-batch.sh
│   ├── xtec-gpu-clustering.sh
│   └── xtec-bic-sweep.sh
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
