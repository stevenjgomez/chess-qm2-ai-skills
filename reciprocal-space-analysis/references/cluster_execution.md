# Remote Compute Cluster Execution & Headless Processing

Synchrotron reciprocal space datasets (especially 3D volumes) routinely reach gigabytes in memory. Processing these files requires adherence to cluster etiquette and headless execution patterns.

---

## 1. Login Node vs. Compute Node Separation & Interactive Sessions

In the CLASSE cluster environment, strictly differentiate between node classes:
- **`lnx201`** is a **login node** intended exclusively for editing files, monitoring jobs, git operations, and light shell tasks. **Never run compute here.**
- **`all.q@lnx307*,all.q@lnx311*,all.q@lnx312*,all.q@lnx313*`** are **AVX2-capable batch compute nodes** reserved for raw data reduction and 3D lattice reconstruction via `qsub`.
- **Interactive Compute Nodes (`interactive.q`)**: For downstream analysis (`nxs_analysis_tools`, diagnostic reciprocal space slicing, linecuts, LaTeX PDF compilation).
- **`lnx4428`** is a **dedicated CUDA GPU compute node** (NVIDIA Titan RTX, 24 GB VRAM) for machine learning, clustering (`XTEC-GPU`), and PyTorch workloads. Python: `/nfs/chess/sw/qm2_XTEC312/bin/python`. (See `xtec-gpu-analysis` skill).

### Mandatory Interactive Session Protocol
Do not SSH directly into compute nodes (such as `lnx308`) for interactive analysis. Follow this 3-step protocol:
1. **Login to gateway**:
   ```bash
   ssh <username>@lnx201.classe.cornell.edu
   ```
2. **Request an interactive compute session with Grid Engine**:
   ```bash
   qrsh -q interactive.q -l mem_free=350G
   ```
3. **Execute analysis or activate environment**:
   ```bash
   /nfs/chess/sw/anaconda3_sgomezalvarado_nightly/bin/python my_analysis_script.py
   ```

### Non-Interactive Remote GPU Execution (lnx4428)
For GPU-accelerated XTEC clustering on `lnx4428`, execute non-interactively via SSH:
```bash
ssh -o BatchMode=yes lnx4428 "/nfs/chess/sw/qm2_XTEC312/bin/xtec-gpu xtec-d /path/to/data.nxs -o /path/to/results/ --min-k 2 --max-k 10"
```

---

## 2. Headless Matplotlib Configuration

When executing Python scripts over SSH or in automated background pipelines without an X11 display:
```python
import matplotlib
matplotlib.use("Agg")  # Must be called BEFORE importing pyplot
import matplotlib.pyplot as plt
```
Failing to set backend `Agg` can cause `_tkinter.TclError: no display name and no $DISPLAY environment variable` crashes.

---

## 3. Memory Optimization for 3D Reciprocal Space Volumes

When working with multiple 3D datasets simultaneously (e.g. comparing two 1000×1000×200 float arrays):
1. **NeXus Memory Slab Limits (`nxsetmemory`)**:
   `nexusformat` restricts array allocations exceeding 2,000 MB by default (`NX_MEMORY=2000`). Adjust the slab allocation threshold according to the operational phase:
   - **Diagnostic Slicing & Linecuts (Downstream Analysis)**: 20 GB (`20000`) is sufficient for extracting 2D slices or 1D linecuts from single pre-reduced datasets:
     ```python
     import nexusformat.nexus as nx
     nx.nxsetmemory(20000)  # 20 GB threshold for interactive slicing
     ```
   - **Raw Stack Creation & 3D Reciprocal Volume Reconstruction (Heavy Batch Jobs)**: Requires 100 GB (`100000`) on batch nodes:
     ```python
     import nexusformat.nexus as nx
     nx.nxsetmemory(100000)  # 100 GB threshold for full 3D volume reduction
     ```
2. **Slice on Demand**: Load 2D slices from HDF5 instead of reading entire 3D arrays into memory if only a few slices are needed.
3. **Explicit Garbage Collection**:
   ```python
   import gc
   del raw_volume
   gc.collect()
   ```
4. **Close Matplotlib Figures**: In batch loops generating dozens of figures, always close figures after saving:
   ```python
   fig.savefig("output.png", dpi=300, bbox_inches="tight")
   plt.close(fig)
   ```

---

## 4. Automated LaTeX PDF Summary Generation

Compiling publication-ready PDF summaries of generated figures:
```python
import subprocess
import os

def compile_latex_pdf(tex_filepath):
    """
    Compile a LaTeX file to PDF using pdflatex.
    """
    workdir = os.path.dirname(os.path.abspath(tex_filepath))
    filename = os.path.basename(tex_filepath)
    cmd = ["/usr/bin/pdflatex", "-interaction=nonstopmode", filename]
    
    # Run twice for cross-references and page numbers
    for run_idx in range(2):
        result = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Compilation error on run {run_idx+1}:")
            print(result.stdout[-1000:])
            raise RuntimeError(f"pdflatex failed with exit code {result.returncode}")
    print(f"Successfully compiled {filename.replace('.tex', '.pdf')}")
```

