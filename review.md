Here is a comprehensive review of your **CHESS QM2 AI Skills Suite**. 

Overall, this is an impressive, scientifically rigorous suite of skills. The crystallographic modeling (such as physical reciprocal aspect ratio calibration $A_{\text{final}} = \frac{v_Y^*}{v_X^*} \times \text{ax.get\_aspect()}$, shear transformations, and AVX2 vector traps) is exceptionally well conceived. 

However, there are several **critical workflow contradictions**, **code-level logic bugs**, and **points of confusion** across the skills that could cause automation failures, cluster etiquette violations, or misleading outputs when an AI agent or researcher executes them.

---

### 1. Critical Contradictions & Conflicting Information

#### 1.1 The `qsub` vs. `orchestrate_reduction.py` Reality Gap
* **The Conflict:**
  * [`chess-legacy-reduction/SKILL.md`](file:///Users/stevengomezalvarado/PythonProjects/chess-qm2-ai-skills/chess-legacy-reduction/SKILL.md#L20-L28) repeatedly enforces:
    > *"All heavy reduction tasks (Pilatus raw CBF stacking into `stack*.nxs`, headless ORM solving with basinhopping, and 1rot/3rot reciprocal space conversions) **MUST be submitted as `qsub` jobs**... Never run stack-loading or reciprocal conversion scripts interactively over SSH (even on compute nodes like `lnx308`). Always submit via `qsub`."*
  * Yet in [`orchestrate_reduction.py`](file:///Users/stevengomezalvarado/PythonProjects/chess-qm2-ai-skills/chess-legacy-reduction/scripts/orchestrate_reduction.py#L32-L47), every step (stacking, ORM basinhopping, and reciprocal conversion) is executed **synchronously in the local shell** via `subprocess.Popen` inside `run_cmd`!
    > @stevenjgomez Ok, this is a result of me wanting to see the real-time output from the job using `tail -f /nfs/chess/id4baux/2026-2/gomez-al-4850-a/scripts/FeTe2-5A/qsub_batch.log`. This seemed to work fine when I had the job submitted via a bash script like the ones I've provided to you in `./example_job_scripts`. Is this still an issue? Or does it just need clarification?
    > @antigravity Looking at `./example_job_scripts` clarifies this completely! `orchestrate_reduction.py` is intended to be the *job payload* running inside a batch worker node allocated by Grid Engine, while `tail -f` monitors the unbuffered stdout streamed through the `#$ -o` log. This is an effective pattern. The issue is purely documentation and workflow clarity: `SKILL.md` currently reads as if `orchestrate_reduction.py` itself submits the jobs. We should clarify in `SKILL.md` that reduction is executed by submitting an SGE bash wrapper (like those in `example_job_scripts/`) via `qsub`, which in turn calls `orchestrate_reduction.py`. Even better, we can add a helper mode (e.g. `orchestrate_reduction.py --generate-qsub`) or include templates in the skill so an agent or user can generate these wrapper scripts on the fly.
    > @stevenjgomez I am not sure the helper mode is necessary, but otherwise sounds good.
    > @antigravity Understood! We will omit the helper mode and instead keep `example_job_scripts/` as clear submission templates in the repo, documenting the SGE bash wrapper submission pattern directly in `chess-legacy-reduction/SKILL.md`.
* **The Impact:**
  * If an agent runs `python orchestrate_reduction.py --mode batch` on `lnx201`, it immediately violates CLASSE policy by running gigabyte-scale array crunching on the login node.
  * If run on `lnx308`, it runs multi-hour stack loading interactively over SSH, violating the skill's own rule.
  * There is **no SGE script generation, no `qsub` invocation, and no job queue monitoring** in `orchestrate_reduction.py`, despite the skill stating that it drives distributed batch reduction.
* **Recommendation:**
  Add a `--generate-qsub` mode or split `orchestrate_reduction.py` into a lightweight job generator/submitter (which emits `.sh` scripts targeting `all.q@lnx307*` etc.) and the per-temperature worker script.


---

#### 1.2 Node Role & Queue Target Mismatches
* **The Conflict:**
  * In [`chess-legacy-reduction/SKILL.md`](file:///Users/stevengomezalvarado/PythonProjects/chess-qm2-ai-skills/chess-legacy-reduction/SKILL.md#L8) frontmatter:
    > *"distributed multi-node batch reduction via Grid Engine (qsub) across CLASSE CPU compute nodes (`lnx308`, `lnx1033-f1`, `lnx1034-f1`)."*
  * But in Section 1.1 (Line 22), the mandatory `qsub` command is:
    ```bash
    qsub -q 'all.q@lnx307*,all.q@lnx311*,all.q@lnx312*,all.q@lnx313*' -l mem_free=200G -pe sge_pe 32 <job>.sh
    ```
    Notice that `lnx308`, `lnx1033-f1`, and `lnx1034-f1` are **not** in that queue target!
    > @stevenjgomez My understanding is that this was because all those specific notes (307, 311, etc.) were the ones compatible with the compiled libhkl, but I could be wrong.
    > @antigravity You are spot on—`lnx307`, `lnx311`, `lnx312`, and `lnx313` are indeed the AVX2-capable hosts verified to run `libhkl.so` without raising `SIGILL` (illegal instruction). The only issue was a typo in the frontmatter description of `chess-legacy-reduction/SKILL.md`, which mistakenly listed `(lnx308, lnx1033-f1, lnx1034-f1)` as the `qsub` nodes instead of `(lnx307, lnx311, lnx312, lnx313)`. We will update the frontmatter to match Section 1.1 with `lnx307, lnx311, lnx312, lnx313`.
  * Furthermore, in [`cluster_execution.md`](file:///Users/stevengomezalvarado/PythonProjects/chess-qm2-ai-skills/reciprocal-space-analysis/references/cluster_execution.md#L11), `lnx308` is described as a node for *"standard data reduction, 3D lattice rotations"*, directly contradicting the instruction never to run data reduction or 3D rotations on `lnx308`.
* **Recommendation:**
  Clearly define that `lnx307*`, `lnx311*`, `lnx312*`, and `lnx313*` are the batch `qsub` compute pool for raw data reduction, whereas `lnx308`, `lnx1033-f1`, and `lnx1034-f1` are reserved for lightweight interactive downstream analysis (`nxs_analysis_tools`, slicing, linecuts, LaTeX).
  > @stevenjgomez I also want to note that the new mandatory workflow for interactive sessions should be (1) login to ssh <username>@lnx201.classe.cornell.edu if not already (2) qrsh -q interactive.q -l mem_free=350G (3) activate the appropriate environment for the task at hand. We should not ssh directly into lnx308 to run commands, for example.
  > @antigravity This is a vital update to CLASSE cluster policy. We will replace all instructions suggesting direct SSH into `lnx308` with this standard 3-step interactive session protocol: (1) SSH to `lnx201`, (2) obtain an interactive shell via `qrsh -q interactive.q -l mem_free=350G`, and (3) activate the required Python environment on the assigned node. This ensures interactive slicing and linecuts never overload shared or unauthorized hosts.

---

#### 1.3 Reciprocal Space Coordinate Order: NXRefine vs. Legacy CHESS
* **The Conflict:**
  * In [`reciprocal-space-analysis/SKILL.md`](file:///Users/stevengomezalvarado/PythonProjects/chess-qm2-ai-skills/reciprocal-space-analysis/SKILL.md#L72-L82), Section 3.2 only explains the **NXRefine** axis ordering:
    `data.nxaxes == ['Ql', 'Qk', 'Qh']` (shape `(N_l, N_k, N_h)`), stating:
    * Slice Axis 0 ($Q_l$) $\rightarrow HK$ plane
    * Slice Axis 1 ($Q_k$) $\rightarrow HL$ plane
    * Slice Axis 2 ($Q_h$) $\rightarrow KL$ plane
  * However, **Legacy CHESS** datasets (produced by `chess-legacy-reduction`) store axes as `['H', 'K', 'L']` (shape `(N_h, N_k, N_l)`), as seen in [`slice_visualizer.py`](file:///Users/stevengomezalvarado/PythonProjects/chess-qm2-ai-skills/chess-legacy-reduction/scripts/slice_visualizer.py#L123-L125):
    * Axis 2 ($L$) $\rightarrow HK$ plane
    * Axis 1 ($K$) $\rightarrow HL$ plane
    * Axis 0 ($H$) $\rightarrow KL$ plane
* **The Impact:**
  If an agent reads `reciprocal-space-analysis/SKILL.md` and applies the rule *"Slice Axis 0 for HK"* to a Legacy CHESS dataset, it will slice $H$, producing a $KL$ cut instead of an $HK$ cut! Additionally, `Scissors.cut_data()` tuple ordering will be inverted: $(L, K, H)$ for NXRefine vs. $(H, K, L)$ for Legacy CHESS.
* **Recommendation:**
  Explicitly tabulate the two layouts side-by-side in `reciprocal-space-analysis/SKILL.md`:
  
  | Format | Dataset Axes | $HK$ Slice ($L=\text{const}$) | $HL$ Slice ($K=\text{const}$) | $KL$ Slice ($H=\text{const}$) | `Scissors` Position Order |
  | :--- | :--- | :--- | :--- | :--- | :--- |
  | **NXRefine** (`use_nxlink=True`) | `['Ql', 'Qk', 'Qh']` | Axis 0 (`data[0.0, :, :]`) | Axis 1 (`data[:, 0.0, :]`) | Axis 2 (`data[:, :, 0.0]`) | `(L, K, H)` |
  | **Legacy CHESS** (`hkli.nxs`) | `['H', 'K', 'L']` | Axis 2 (`data[:, :, 0.0]`) | Axis 1 (`data[:, 0.0, :]`) | Axis 0 (`data[0.0, :, :]`) | `(H, K, L)` |
  > @stevenjgomez Agreed.
  > @antigravity We will add this comparison table and the coordinate ordering rules for `Scissors.cut_data()` directly into Section 3.2 of `reciprocal-space-analysis/SKILL.md`.

---

#### 1.4 Grid Step Size Discrepancy ($0.02$ vs. $0.01$)
* **The Conflict:**
  * [`chess-legacy-reduction/SKILL.md`](file:///Users/stevengomezalvarado/PythonProjects/chess-qm2-ai-skills/chess-legacy-reduction/SKILL.md#L127-L130) lists standard defaults as:
    $H: \pm 5.1$ (step **0.02**), $K: \pm 5.1$ (step **0.02**), $L: \pm 9.1$ (step **0.02**).
  * But [`orchestrate_reduction.py`](file:///Users/stevengomezalvarado/PythonProjects/chess-qm2-ai-skills/chess-legacy-reduction/scripts/orchestrate_reduction.py#L354-L358) sets CLI argument defaults:
    `--hstep 0.01`, `--kstep 0.01`, `--lstep 0.02`.
* **The Impact:**
  Halving the step size from $0.02$ to $0.01$ along both $H$ and $K$ **quadruples ($4\times$)** the voxel grid count and memory size of the output volume.
* **Recommendation:**
  Align `--hstep` and `--kstep` defaults in `orchestrate_reduction.py` to `0.02` to match the documented beamline defaults.
> @stevenjgomez Please use 0.01,0.01,0.02 along h,k,l as defaults.
> @antigravity Understood! We will update `chess-legacy-reduction/SKILL.md` (Section 3.4) to explicitly state `(0.01, 0.01, 0.02)` as the standard beamline defaults, perfectly aligning the documentation with `orchestrate_reduction.py`.
---

#### 1.5 NeXus Memory Slab Limits
* In `chess-legacy-reduction`: `nx.nxsetmemory(100000)` (100 GB).
* In `reciprocal-space-analysis`: `nx.nxsetmemory(20000)` (20 GB).
* Add a note in `reciprocal-space-analysis` clarifying that while 20 GB suffices for extracting 2D slices or linecuts from single datasets, raw stack creation and full 3D volume reconstruction require 100 GB (`100000`).
> @stevenjgomez Agreed.
> @antigravity We will add this distinction to `reciprocal-space-analysis/SKILL.md` and `cluster_execution.md` so users and agents understand when to allocate 20 GB vs 100 GB in `nxsetmemory()`.

---

#### 1.6 `to_xtec(overwrite=...)` Default Behavior
* In [`xtec-gpu-analysis/SKILL.md`](file:///Users/stevengomezalvarado/PythonProjects/chess-qm2-ai-skills/xtec-gpu-analysis/SKILL.md#L145):
  > *"TempDependence.to_xtec() defaults to `overwrite=False`."*
* In `nxs_analysis_tools.chess.TempDependence.to_xtec`:
  The actual function signature is:
  ```python
  def to_xtec(self, filepath=None, ..., overwrite=True, ...):
  ```
  `to_xtec()` actually defaults to **`overwrite=True`**! 
* **The Impact:**
  If an agent relies on this text and calls `td.to_xtec(filepath=...)` without passing `overwrite=False`, it could inadvertently overwrite existing files.

> @stevenjgomez I have modified the nxs-analysis-tools (main branch on GitHub) to have `overwrite=False` as the default, which should have been the case to begin with.
> @antigravity That is the ideal fix! Updating `nxs_analysis_tools` upstream on GitHub resolves the discrepancy at the source and enforces data protection natively. We will keep the documentation in `xtec-gpu-analysis/SKILL.md` noting that `overwrite=False` is now the library default.

---

### 2. Code Logic Bugs & Implementation Flaws

#### 2.1 Basinhopping Preliminary Fit Results are Discarded in `orm_solver.py`
In [`orm_solver.py`](file:///Users/stevengomezalvarado/PythonProjects/chess-qm2-ai-skills/chess-legacy-reduction/scripts/orm_solver.py#L279-L297):
```python
if peaknum > 75:
    shortpeaklist = peaklist[:20]
    x0 = [0, 0, 0]
    pre1 = basinhopping(minfuncU, x0, ...)
    ...
    x0 = [0.5, 1.0, 0.25]
    pre2 = basinhopping(minfuncU, x0, ...)

x0 = [0, 0, 0]  # <--- BUG: Resets x0 unconditionally!
ret1 = basinhopping(minfuncU, x0, ...)
```
* **Issue:** The preliminary optimizations `pre1` and `pre2` run on the first 20 peaks, but their results are never used. Line 292 immediately resets `x0 = [0, 0, 0]`.
* **Fix:** Compare `pre1.fun` and `pre2.fun` and set `x0` to whichever had the lower $\chi^2$:
```python
if peaknum > 75:
    ...
    x0 = pre1.x if pre1.fun < pre2.fun else pre2.x
else:
    x0 = [0, 0, 0]
```

> @stevenjgomez Agreed.
> @antigravity We will update `orm_solver.py` so that when `peaknum > 75`, `x0` takes the best result of `pre1.x` vs. `pre2.x` (based on `min(pre1.fun, pre2.fun)`), ensuring preliminary optimization work is not wasted.

---

#### 2.2 Eager `.nxdata` Read in `slice_visualizer.py`
In [`slice_visualizer.py`](file:///Users/stevengomezalvarado/PythonProjects/chess-qm2-ai-skills/chess-legacy-reduction/scripts/slice_visualizer.py#L114):
```python
counts = data_entry.counts.nxdata  # <--- Forces eager in-memory loading of the entire 3D volume!
```
* **Issue:** [`reciprocal-space-analysis/SKILL.md`](file:///Users/stevengomezalvarado/PythonProjects/chess-qm2-ai-skills/reciprocal-space-analysis/SKILL.md#L61) explicitly warns against the *"`.nxdata` Trap"*. Pulling all counts into RAM for a 10–35 GB volume over NFS can cause OOM errors or long I/O hangs.
* **Fix:** Slice directly using NeXus hyperslabs or pass the 3D `NXdata` directly to `nxs_analysis_tools.plot_slice(nx_obj.entry.data, sum_axis=...)`.

> @stevenjgomez I agree, this should all basically be handled using nxs-analysis-tools (e.g., loading functions and plotting slices or slabs using `plot_slice`) which avoids the eager loading.
> @antigravity We will refactor `slice_visualizer.py` to use `nxs_analysis_tools` loading and lazy slicing mechanisms (or NeXus hyperslabs) rather than accessing `.counts.nxdata` directly.

---

#### 2.3 `extract_slice` Only Allows Slicing at Zero
In [`slice_visualizer.py`](file:///Users/stevengomezalvarado/PythonProjects/chess-qm2-ai-skills/chess-legacy-reduction/scripts/slice_visualizer.py#L48-L53):
```python
def extract_slice(counts, coord_array, axis_idx, thickness=0.05):
    mask = np.abs(coord_array) <= thickness
```
* `mask = np.abs(coord_array) <= thickness` hardcodes the cut to the origin ($L=0, K=0, H=0$).
* **Fix:** Add a `center=0.0` parameter so diagnostic slices can inspect non-zero planes (e.g. $L = 0.5$ or $L = 1.0$).

> @stevenjgomez I think it is fine to add the center parameter with 0 as default.
> @antigravity We will add `--h-center`, `--k-center`, and `--l-center` (defaulting to 0.0) to `slice_visualizer.py` so arbitrary reciprocal planes can be visualized.

---

#### 2.4 Missing Script `scripts/replot_figures.py` & Undefined Variables
In [`xtec_workflow.md`](file:///Users/stevengomezalvarado/PythonProjects/chess-qm2-ai-skills/xtec-gpu-analysis/references/xtec_workflow.md#L167-L185):
* Section 5 states: *"existing `results.h5` files can be re-rendered ... using `scripts/replot_figures.py`"*.
* However, `replot_figures.py` **does not exist** in `xtec-gpu-analysis/scripts/` (only `generate_xtec_input.py` is present).
* Additionally, the code snippet in Section 5 calls `_plot_qmap(data, ...)` and `output_dir`, but `data` and `output_dir` are never loaded or defined in the snippet.

> @stevenjgomez I am not sure what this is... Perhaps it is a legacy function that was replaced at some point. If it is safe to remove, go ahead and remove it. 
> @antigravity We will remove Section 5 ("Re-Plotting Existing Outputs") from `xtec_workflow.md` to eliminate references to the missing script and undefined variables. 

---

#### 2.5 Temperature Parsing Crash on Decimal Temperatures
In [`orchestrate_reduction.py`](file:///Users/stevengomezalvarado/PythonProjects/chess-qm2-ai-skills/chess-legacy-reduction/scripts/orchestrate_reduction.py#L159):
```python
pipeline_tracker.record_orientation_result(
    processed_root, int(warmest_temp), orm_target, None, verified=False
)
```
* If a temperature folder has a decimal or string format (e.g. `281.5` or `281p5`), `int(warmest_temp)` raises `ValueError: invalid literal for int() with base 10`.
* **Fix:** Use `float(warmest_temp.replace('p', '.'))` or keep it as `warmest_temp`.

> @stevenjgomez Good idea, agreed.
> @antigravity We will update `orchestrate_reduction.py` to parse `warmest_temp` safely using `float(str(warmest_temp).replace('p', '.'))` (formatting as an integer if it has no decimal part), preventing `ValueError` crashes.

---

#### 2.6 Automatic Suffixing Breaks Downstream File Detection
* `chess-legacy-reduction/SKILL.md` states that the legacy reduction scripts automatically append integer suffixes (`1rot_hkli_1.nxs`, `3rot_hkli_1.nxs`).
* However, in [`generate_xtec_input.py`](file:///Users/stevengomezalvarado/PythonProjects/chess-qm2-ai-skills/xtec-gpu-analysis/scripts/generate_xtec_input.py#L34-L44):
  ```python
  candidates = ["3rot_hkli.nxs", "1rot_hkli.nxs", "hkli.nxs", "transform.nxs"]
  ...
  if any(f.endswith(c) for f in files):
  ```
  `f.endswith("1rot_hkli.nxs")` will **fail** to match `1rot_hkli_1.nxs` or `3rot_hkli_1.nxs`.
* **Fix:** Use regex matching (e.g. `r"(1rot|3rot)?_?hkli(_\d+)?\.nxs"`) to match suffixed files and sort to pick the highest suffix version.

> @stevenjgomez Agreed.
> @antigravity We will update `detect_legacy_file_ending` in `generate_xtec_input.py` to use regex matching for suffixed files (e.g., `1rot_hkli_1.nxs`, `3rot_hkli_2.nxs`) and select the highest suffix.

---

#### 2.7 Fragile Self-Re-exec Pattern in `slice_visualizer.py`
In [`slice_visualizer.py`](file:///Users/stevengomezalvarado/PythonProjects/chess-qm2-ai-skills/chess-legacy-reduction/scripts/slice_visualizer.py#L17-L19):
```python
NIGHTLY_PYTHON = "/nfs/chess/sw/anaconda3_sgomezalvarado_nightly/bin/python"
if sys.executable != NIGHTLY_PYTHON and os.path.exists(NIGHTLY_PYTHON):
    os.execv(NIGHTLY_PYTHON, [NIGHTLY_PYTHON] + sys.argv)
```
* In `orchestrate_reduction.py` line 184, `slice_visualizer.py` is called with `PYTHON_EXEC` (`anaconda3_jpcr`), intentionally relying on `slice_visualizer.py` to replace itself via `os.execv`.
* If executed off-cluster (where `/nfs/chess/...` does not exist), `os.path.exists(NIGHTLY_PYTHON)` evaluates to `False`, and it proceeds under `anaconda3_jpcr`, failing on `import nxs_analysis_tools`.
* **Fix:** Have `orchestrate_reduction.py` invoke `NIGHTLY_PYTHON` directly for `slice_visualizer.py`.

> @stevenjgomez Since this will only ever be executed on the cluster, I think it is fine, but please let me know your thoughts.
> @antigravity That makes sense for cluster runs. To make it even cleaner, we can have `orchestrate_reduction.py` invoke `NIGHTLY_PYTHON` directly when launching `slice_visualizer.py`, while retaining the `os.execv` check in `slice_visualizer.py` as a fallback safety guard.

---

### 3. Antigravity Skill System Compliance & Portability

#### 3.1 Hardcoded User Home Paths
Several markdown guides and commands hardcode `/home/sgomezalvarado/`:
* [`xtec-gpu-analysis/SKILL.md`](file:///Users/stevengomezalvarado/PythonProjects/chess-qm2-ai-skills/xtec-gpu-analysis/SKILL.md#L40):
  `ssh -o BatchMode=yes lnx308 "/nfs/chess/sw/.../python /home/sgomezalvarado/.gemini/config/skills/..."`
* [`xtec_workflow.md`](file:///Users/stevengomezalvarado/PythonProjects/chess-qm2-ai-skills/xtec-gpu-analysis/references/xtec_workflow.md#L58):
  `/home/sgomezalvarado/.gemini/config/skills/xtec-gpu-analysis/...`
* [`xtec_workflow.md`](file:///Users/stevengomezalvarado/PythonProjects/chess-qm2-ai-skills/xtec-gpu-analysis/references/xtec_workflow.md#L195):
  `![Reciprocal Space Q-Map](/home/sgomezalvarado/XTEC_CUDA/...)`
* [`orchestrate_reduction.py`](file:///Users/stevengomezalvarado/PythonProjects/chess-qm2-ai-skills/chess-legacy-reduction/scripts/orchestrate_reduction.py#L26):
  `DEFAULT_CODEBASE = "/nfs/chess/id4baux/2026-2/gomez-al-4850-a/StevenGomezAlvarado_Codebase"`
* **Impact:** Any collaborator or different user account running these skills will encounter `FileNotFoundError` or permission denied errors.
* **Fix:** Use `$HOME` or configure an environment variable / CLI parameter (e.g. `--codebase`).

> @stevenjgomez I agree that $HOME is a better choice. The DEFAULT_CODEBASE will also not generally be accessible as older run cycles get archived (they have already archived 2025-3 for example). The latest version of these scripts should live on GitHub and should generally be stored in each users $HOME directory for now. This may change in the future, i.e., we may get a dedicated folder to store the codebase in the software folder `/nfs/chess/sw/`.
> @antigravity Excellent point regarding cycle archiving. We will replace hardcoded cycle paths with `$HOME` paths (e.g. `$HOME/Documents/automate_legacy_workflow` or `$HOME/chess-qm2-codebase`), allow `--codebase` to be set via an environment variable `CHESS_LEGACY_CODEBASE`, and document where users should clone the scripts in `$HOME`.

---

#### 3.2 Symlink & Installation Instructions in `README.md`
In [`README.md`](file:///Users/stevengomezalvarado/PythonProjects/chess-qm2-ai-skills/README.md#L23-L26):
```bash
ln -s /path/to/chess-qm2-ai-skills ~/.gemini/config/skills
```
* **Issue:** Antigravity only discovers skills located **one directory level below `skills/`** (`skills/<skill_name>/SKILL.md`).
  If a user already has `~/.gemini/config/skills` created, running `ln -s /path/to/chess-qm2-ai-skills ~/.gemini/config/skills` places the repository inside it:
  `~/.gemini/config/skills/chess-qm2-ai-skills/chess-legacy-reduction/SKILL.md` (depth 2). Antigravity will **not** discover the skills!
* **Fix:** Update the instructions to symlink the individual skill folders:
  ```bash
  for skill in /path/to/chess-qm2-ai-skills/*/; do
    if [ -f "$skill/SKILL.md" ]; then
      ln -s "$skill" ~/.gemini/config/skills/$(basename "$skill")
    fi
  done
  ```

> @stevenjgomez Agreed.
> @antigravity We will update the `README.md` installation instructions to use the per-skill symlink loop so Antigravity correctly discovers all skills.

---

#### 3.3 Invalid API Directive: `BypassSandbox: true`
In [`cluster_execution.md`](file:///Users/stevengomezalvarado/PythonProjects/chess-qm2-ai-skills/reciprocal-space-analysis/references/cluster_execution.md#L26) and [`xtec-gpu-analysis/SKILL.md`](file:///Users/stevengomezalvarado/PythonProjects/chess-qm2-ai-skills/xtec-gpu-analysis/SKILL.md#L50):
> *"When executing remote SSH commands from the assistant agent, set `BypassSandbox: true`..."*
* Antigravity's `run_command` schema has no parameter named `BypassSandbox`. Instructing an agent to pass `BypassSandbox: true` in a tool call can cause schema validation errors.
* **Fix:** Remove this directive or rephrase it as user-level documentation for local sandbox configurations.

> @stevenjgomez Remove this directive.
> @antigravity We will remove `BypassSandbox: true` from both `cluster_execution.md` and `xtec-gpu-analysis/SKILL.md`.

---

#### 3.4 Frontmatter Activation Triggers
According to Antigravity skill best practices, skill descriptions should explicitly state **when** they should be activated using third-person trigger phrasing.
* **`chess-legacy-reduction`**: Add:
  > *"Use this skill when the user asks to reduce raw Pilatus CBF frames, stack scans, solve orientation matrices with basinhopping, run 1rot/3rot reciprocal conversions, or check reduction status on CLASSE."*
* **`xtec-gpu-analysis`**: Add:
  > *"Use this skill when the user asks to run temperature-series clustering, XTEC, GMM model selection, or compile 4D NeXus files for clustering on lnx4428."*

> @stevenjgomez Agreed. The 1rot/3rot reciprocal conversion are often referred to as "indexing the data".
> @antigravity We will incorporate "indexing the data" into the frontmatter description and body of `chess-legacy-reduction/SKILL.md` so the skill naturally activates when users ask to index their data.

---

### 4. Missing Automation Glue & Workflow Improvements

1. **Human-in-the-Loop Gate CLI Command**:
   * [`chess-legacy-reduction/SKILL.md`](file:///Users/stevengomezalvarado/PythonProjects/chess-qm2-ai-skills/chess-legacy-reduction/SKILL.md#L152) has Phase 1 Step 6 (*"User Verification Gate: Present cross-sectional slice figures to the user. Wait for user confirmation before proceeding."*).
   * However, [`pipeline_tracker.py`](file:///Users/stevengomezalvarado/PythonProjects/chess-qm2-ai-skills/chess-legacy-reduction/scripts/pipeline_tracker.py#L96) only supports reading summary stats from CLI (`python pipeline_tracker.py <dir>`). There is no CLI flag to record verification (e.g. `--verify-orm`). Adding `--verify-orm` to `pipeline_tracker.py` would allow the agent or user to cleanly record approval before triggering batch reduction.

  > @stevenjgomez Agreed.
  > @antigravity We will add a `--verify-orm` CLI option to `pipeline_tracker.py` to record user confirmation directly into `pipeline_status.json`.

2. **Missing Path to XTEC-GPU Repository**:
   * [`xtec_workflow.md`](file:///Users/stevengomezalvarado/PythonProjects/chess-qm2-ai-skills/xtec-gpu-analysis/references/xtec_workflow.md#L48) mentions `PYTHONPATH=/path/to/XTEC-GPU/src`. If this is installed in a fixed location on CLASSE (e.g. `/nfs/chess/sw/...` or a standard path), specifying the real path instead of `/path/to/XTEC-GPU` prevents agent stalls.
   > @stevenjgomez When I open the file I find that `PYTHONPATH=/nfs/chess/sw/qm2_XTEC312/bin/xtec-gpu`, please double check this finding. If I am correct, then there should be no issue, I think.
   > @antigravity In `xtec_workflow.md` (lines 119–126), the commands are currently written as:
   > ```bash
   > PYTHONPATH=src /nfs/chess/sw/qm2_XTEC312/bin/xtec-gpu xtec-d ...
   > ```
   > And in line 48 (as well as `cluster_topology.md` line 71):
   > ```bash
   > ssh -o BatchMode=yes lnx4428 "PYTHONPATH=/path/to/XTEC-GPU/src /nfs/chess/sw/qm2_XTEC312/bin/python <script>.py"
   > ```
   > Notice that `/nfs/chess/sw/qm2_XTEC312/bin/xtec-gpu` is the executable binary itself, while `PYTHONPATH` was set to a relative directory `src` or placeholder `/path/to/XTEC-GPU/src`. Because `xtec-gpu` is already installed as a Python package inside the `/nfs/chess/sw/qm2_XTEC312` conda environment, setting `PYTHONPATH` is completely unnecessary—the executable can simply be invoked directly:
   > ```bash
   > /nfs/chess/sw/qm2_XTEC312/bin/xtec-gpu xtec-d data.nxs -o results/ ...
   > ```
   > We will clean up the commands across the skills to drop the unnecessary `PYTHONPATH` prefixes, preventing any path resolution errors.
3. **Cross-Skill Discoverability**:
   * Currently, none of the three skills link to one another. Connecting them along the experimental lifecycle creates a cohesive suite:
     $$\text{Raw CBFs} \xrightarrow{\text{chess-legacy-reduction}} \text{3D Volumes} \xrightarrow{\text{reciprocal-space-analysis}} \text{Diagnostic Slicing} \xrightarrow{\text{xtec-gpu-analysis}} \text{4D Phase Clustering}$$
  > @stevenjgomez Agreed.
  > @antigravity We will add cross-skill links and this lifecycle flowchart across all three `SKILL.md` files.

---

### Suggested Action Plan

1. **Fix `orm_solver.py` basinhopping logic**: Retain the best result of `pre1` vs. `pre2` instead of resetting `x0 = [0, 0, 0]`.
2. **Fix `slice_visualizer.py` eager loading**: Eliminate `counts = data_entry.counts.nxdata` and add support for non-zero slice coordinates.
3. **Clarify `reciprocal-space-analysis/SKILL.md` axis mapping**: Add the side-by-side comparison for NXRefine (`Ql, Qk, Qh`) vs. Legacy CHESS (`H, K, L`).
4. **Fix `orchestrate_reduction.py` defaults & execution model**: Change `--hstep` and `--kstep` to `0.02`, and add a mode to emit `qsub` submission scripts for heavy jobs.
5. **Clean up portability & paths**: Replace `/home/sgomezalvarado/` with relative or `$HOME`-based paths, update `README.md` symlinking commands, and remove `BypassSandbox`.
6. **Provide `replot_figures.py`**: Add the missing script in `xtec-gpu-analysis/scripts/` to match its documentation.
> @stevenjgomez See relevant comments in each section.
> @antigravity Acknowledged! Based on all your feedback, here is the finalized consensus action plan:
> 1. **`orm_solver.py`**: Pick the best result of `pre1.x` vs. `pre2.x` for `x0` when `peaknum > 75`.
> 2. **`slice_visualizer.py`**: Avoid eager `.nxdata` reading, use lazy slicing / `plot_slice`, and add `--h-center`, `--k-center`, and `--l-center` (default 0.0).
> 3. **`reciprocal-space-analysis/SKILL.md`**: Add side-by-side table for NXRefine vs. Legacy CHESS axis mappings and `Scissors` tuple orders.
> 4. **Reduction defaults & workflow**: Keep `(0.01, 0.01, 0.02)` as the standard $(H, K, L)$ defaults in `SKILL.md` and scripts; document wrapper SGE submission via `qsub` with templates in `example_job_scripts/`.
> 5. **Cluster execution etiquette**: Update interactive guidelines to the 3-step `qrsh -q interactive.q -l mem_free=350G` workflow on `lnx201` instead of direct SSH to `lnx308`.
> 6. **Portability & cleanups**: Replace `/home/sgomezalvarado/` with `$HOME` paths; update `README.md` symlinking loop; remove `BypassSandbox: true`; remove redundant `PYTHONPATH` prefixes for `xtec-gpu`.
> 7. **`xtec_workflow.md`**: Remove Section 5 referencing the legacy `replot_figures.py`.
> 8. **Glue & lifecycle**: Add `--verify-orm` to `pipeline_tracker.py` and link all three skills across the QM2 experimental pipeline.