# Remote Compute Cluster Execution & Headless Processing

Synchrotron reciprocal space datasets (especially 3D volumes) routinely reach gigabytes in memory. Processing these files requires adherence to cluster etiquette and headless execution patterns.

---

## 1. Login Node vs. Compute Node Separation

In environments like CHESS, strictly differentiate between node classes:
- **`lnx201`** is a **login node** intended exclusively for editing files, monitoring jobs, and light shell tasks. **Never run compute here.**
- **`lnx308`** is a **regular CPU compute node** for standard data reduction, 3D lattice rotations, `nxs_analysis_tools`, high-resolution slices, and LaTeX PDF compilation ("usual scripts"). Python: `/nfs/chess/sw/anaconda3_sgomezalvarado_nightly/bin/python`.
- **`lnx4428`** is a **dedicated CUDA GPU compute node** (NVIDIA Titan RTX, 24 GB VRAM) for machine learning, clustering (`XTEC-GPU`), and PyTorch workloads. Python: `/nfs/chess/sw/qm2_XTEC312/bin/python`. (See `xtec-gpu-analysis` skill).

### Non-Interactive Remote Execution via SSH
Execute scripts directly on the target compute node using non-interactive SSH commands:

```bash
# For regular CPU scripts (lnx308)
ssh lnx308 "cd /path/to/workdir && /nfs/chess/sw/anaconda3_sgomezalvarado_nightly/bin/python run_all.py"

# For XTEC GPU scripts (lnx4428)
ssh -o BatchMode=yes lnx4428 "cd /path/to/workdir && /nfs/chess/sw/qm2_XTEC312/bin/python xtec_run.py"
```

> [!IMPORTANT]
> When executing remote SSH commands from the assistant agent, set `BypassSandbox: true` so the SSH connection can authenticate and reach the remote host. Keep command strings simple and prefix-matchable.

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
   `nexusformat` restricts array allocations exceeding 2,000 MB by default (`NX_MEMORY=2000`). For large 3D reciprocal space reconstructions, raise this limit:
   ```python
   import nexusformat.nexus as nx
   nx.nxsetmemory(20000)  # Increase threshold to 20 GB
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

