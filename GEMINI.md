# Global Assistant Rules (`GEMINI.md`)

This file defines global guidelines and constraints that apply across all projects and workspaces.

---

## 1. Markdown Reports & Artifact Asset References

When generating, exporting, or copying Markdown reports, summaries, or artifacts for the user in their workspace:
- **Mandatory Relative Filepaths**: All embedded assets (such as images, plots, diagrams, or linked artifacts) **MUST use relative filepaths** (e.g. `![Caption](./slices_summary.png)` or `![Figure](figures/plot.png)`).
- **Prohibition on Absolute Paths**: Never use absolute filesystem paths (e.g. `/Users/...` or `/home/...`) or paths pointing into hidden agent internal directories (e.g. `~/.gemini/antigravity-cli/brain/...`) inside user-facing Markdown documents.
- **Rationale**:
  1. **Workspace Sandboxing / Security**: Modern Markdown previewers (including VS Code Markdown Preview, Cursor, and webviews) enforce strict Content Security Policies (`localResourceRoots`) that explicitly block loading local resources located outside the active workspace directory.
  2. **URL / Domain Root Resolution**: In web-based or HTML-based markdown renderers, paths beginning with `/` are interpreted as relative to the web server root rather than the local filesystem root, causing broken 404 links.
  3. **Portability & Collaboration**: Relative asset paths ensure that Markdown reports remain self-contained, reproducible, and fully functional when synced across machines, viewed in OneDrive, or committed to version control.

---

## 2. Python Execution Etiquette: Always Save to `.py` Files

- **Prohibition on Complex Inline `python -c "..."` Commands**: Never run complex, multi-line, or string-heavy Python scripts as inline command-line arguments (e.g. `python3 -c "..."`).
- **Rationale**:
  1. **Shell Expansion & Escaping Pitfalls**: In shells like `zsh` and `bash`, characters such as `$`, `\`, `(`, `)`, `{`, `}`, `"`, and `'` are parsed before reaching Python. Specifically, LaTeX strings (e.g., `$(\frac{1}{2}, 0, 1)$`) trigger zsh command substitution `$()`, resulting in immediate syntax errors like `zsh: command not found`.
  2. **Quoting Hell**: Nesting single and double quotes inside inline shell strings frequently breaks code strings and leads to silent syntax truncation.
  3. **Reproducibility & Debuggability**: Standalone `.py` files provide precise traceback line numbers, are easily versioned, and can be inspected and re-run directly by the user.
- **Mandatory Procedure**:
  - Always write the code to a proper `.py` script (e.g. in `scripts/`, or in `scratch/test_*.py` for scratch/testing scripts) using file writing tools (`write_to_file`).
  - Execute the script cleanly via `python3 path/to/script.py [args]`.

---

## 3. Remote Compute Cluster Etiquette: ZERO Data Processing on Login Nodes (`lnx201`)

> [!CAUTION]
> **STRICT PROHIBITION ON COMPUTE & DATA PROCESSING ON `lnx201`**
>
> `lnx201` is a shared interactive login gateway for all CLASSE/CHESS beamline users. **NO data processing, computation, or memory/CPU-intensive tasks may be run directly on `lnx201` under any circumstances.**
> Violating this slows down the beamline infrastructure for other scientists and violates facility policy.

### 3.1 Prohibited Activities on `lnx201`
Never run the following on `lnx201`:
- Spot finding (`dials.find_spots`)
- Unit cell indexing (`dials.index`)
- Bravais setting refinement (`dials.refine_bravais_settings`)
- Profile integration (`dials.integrate`)
- Symmetry & scaling (`dials.symmetry`, `dials.scale`)
- Mask generation / conversion reading full detector arrays (`mask_to_dials.py`)
- Raw CBF diffraction frame stacking (`stack_em_all.py`)
- Orientation matrix (ORM) solving with basinhopping (`solve_orm.py`)
- 3D reciprocal space HKL conversion (`Pil6M_HKLConv_3D_2022_1rot.py` / `3rot.py`)
- Reciprocal volume slicing and diagnostic projection rendering (`slice_visualizer.py` / `plot_slice`)
- Temperature series clustering / XTEC / GMM execution

### 3.2 Permitted Activities on `lnx201` (Inspection & Dispatch Only)
The login node is strictly restricted to:
- Filesystem navigation and lightweight directory listings (`ls`, `cd`, `find` with depth limits)
- Reading/editing configuration files, job scripts, and logs (`cat`, `head`, `tail`, `grep`, `nano`)
- Git operations (`git status`, `git pull`, `git commit`, `git push`)
- Cluster monitoring (`qstat`, `qhost`, streaming logs via `tail -f`)
- Submitting batch jobs to Sun Grid Engine (`qsub`)

### 3.3 Mandatory Execution Protocol
1. **Batch Compute via Sun Grid Engine (`qsub`)**:
   All data processing pipelines must be packaged as bash wrapper scripts and submitted to SGE:
   - **AVX2 Compute Nodes**: `qsub -q 'all.q@lnx307*,all.q@lnx311*,all.q@lnx312*,all.q@lnx313*' -l mem_free=120G -pe sge_pe 24/32 script.sh`
   - **Dedicated GPU Compute**: `qsub -l cuda_free=1 script.sh` (targeting `lnx4428`)
2. **Interactive Worker Sessions (`qrsh` / `qlogin`)**:
   If step-by-step interactive debugging or immediate visual inspection is strictly required, request an interactive compute worker slot:
   ```bash
   qrsh -q interactive.q -l mem_free=64G -pe sge_pe 8
   ```
   Execute the interactive workflow **only after the interactive shell session opens on the allocated worker node** (`lnx307`, `lnx308`, etc.). Never execute directly in the initial `lnx201` shell.
