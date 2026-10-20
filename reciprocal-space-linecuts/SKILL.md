---
name: reciprocal-space-linecuts
description: >-
  Extract, integrate, and visualize 1D reciprocal space linecuts from 3D NeXus datasets
  using Scissors from nxs_analysis_tools. Use when performing peak integration, linecuts
  along specific directions, background subtraction, extracting 1D profiles, or comparing
  Bragg and diffuse scattering intensities across cut windows.
---

# 1D Reciprocal Space Linecuts Skill (`reciprocal-space-linecuts`)

This skill provides operational procedures, coordinate ordering rules, and copy-paste-ready recipes for extracting 1D intensity linecuts from 3D reciprocal space volumes using `nxs_analysis_tools.Scissors`.

---

## 1. Golden Rules of `Scissors` Linecuts

1. **Coordinate Ordering Trap**:
   `Scissors.cut_data()` maps `center` and `window` parameters **positionally to `data.nxaxes`**:
   - **Legacy CHESS (`[H, K, L]`)**: Center and window tuples must be ordered as **$(H, K, L)$**.
   - **NXRefine (`[Ql, Qk, Qh]`)**: Center and window tuples must be ordered as **$(L, K, H)$**.
   
   > [!CAUTION]
   > Passing $(H, K, L)$ to an NXRefine dataset transposes $H$ onto $L$, slicing an entirely unintended region of reciprocal space! Always check `data.nxaxes` before specifying cut windows.

2. **Integration Window Sizing**:
   The `window` tuple $(\Delta_0, \Delta_1, \Delta_2)$ defines the integration thickness along the two transverse axes, and the search bounds along the cut axis.
   - For a sharp Bragg peak: Window $\sim 0.05 - 0.1\text{ r.l.u.}$ along transverse axes.
   - For diffuse scattering rods or sheets: Expand transverse window to $\sim 0.2 - 0.4\text{ r.l.u.}$ to capture integrated signal.

3. **Background Subtraction**:
   When comparing peak heights across temperatures, always inspect the baseline. Subtract linear or constant backgrounds to isolate the pure Bragg reflection or order parameter.

---

## 2. Recipes

### Recipe 1: 1D Linecut on Legacy CHESS Dataset (`*hkli*.nxs`)

```python
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import nexusformat.nexus as nx
from nxs_analysis_tools.datareduction import Scissors

# 1. Load volume lazily
nx.nxsetmemory(20000)
root = nx.nxload("3rot_hkli_lite.nxs")
data = root.entry.data

# 2. Initialize Scissors on data
scissors = Scissors(data)

# 3. Cut along H through the (1, 0, 0) reflection:
# Center ordered as (H, K, L):
center = (1.0, 0.0, 0.0)
# Window ordered as (H, K, L): integrate Delta_K = 0.1, Delta_L = 0.1, cut along H in [-0.5, 0.5]
window = (0.5, 0.1, 0.1)

# Cut along H (axis 0 in Legacy CHESS)
linecut = scissors.cut_data(center=center, window=window, axis=0)

# Extract 1D arrays
q_vals = np.asarray(linecut.nxaxes[0].nxdata)
intensity = np.asarray(linecut.nxsignal.nxdata, dtype=np.float32)

# 4. Plot 1D linecut
fig, ax = plt.subplots(figsize=(6, 4), dpi=200)
ax.plot(q_vals, intensity, "o-", color="royalblue", markersize=3, label="Cut along H")
ax.set_xlabel(r"$H$ (r.l.u.)", fontsize=11)
ax.set_ylabel("Integrated Intensity (counts)", fontsize=11)
ax.set_title(r"1D Linecut through $(1, 0, 0)$", fontsize=12)
ax.grid(True, linestyle="--", alpha=0.5)
ax.legend()

plt.tight_layout()
plt.savefig("linecut_H.png", dpi=300)
plt.close(fig)
print("Saved 1D linecut: linecut_H.png")
```

---

### Recipe 2: 1D Linecut on NXRefine Dataset (`FeGeSb_300.nxs`)

```python
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import nexusformat.nexus as nx
from nxs_analysis_tools.datareduction import Scissors

root = nx.nxload("FeGeSb_300.nxs")
data = root.entry.transform

scissors = Scissors(data)

# NXRefine axes are [Ql, Qk, Qh] -> (L, K, H)
# Center ordered as (L, K, H):
center = (0.0, 0.0, 1.0)
# Window ordered as (L, K, H):
window = (0.1, 0.1, 0.5)

# Cut along Qh (axis 2 in NXRefine)
linecut = scissors.cut_data(center=center, window=window, axis=2)

qh = np.asarray(linecut.nxaxes[0].nxdata)
counts = np.asarray(linecut.nxsignal.nxdata, dtype=np.float32)

fig, ax = plt.subplots(figsize=(6, 4), dpi=200)
ax.plot(qh, counts, color="crimson", lw=1.5)
ax.set_xlabel(r"$Q_h$ (r.l.u.)")
ax.set_ylabel("Counts")
ax.set_title(r"NXRefine Linecut along $Q_h$")
plt.tight_layout()
plt.savefig("nxrefine_linecut.png", dpi=300)
plt.close(fig)
```

---

## 3. Standalone CLI Reference Script

Use [`scripts/extract_linecut.py`](./scripts/extract_linecut.py) for turnkey extraction:

```bash
python scripts/extract_linecut.py \
  --nxs path/to/volume.nxs \
  --axis H \
  --center "1.0, 0.0, 0.0" \
  --window "0.5, 0.1, 0.1" \
  --output linecut_H.png \
  --csv linecut_H.csv
```

---

## 4. Sister Skills & Integration

- For **Multi-Temperature Batch Linecuts & Waterfalls**: Consult [`temperature-series-analysis`](../temperature-series-analysis/SKILL.md) to apply Scissors across an entire sample series in a single call.
- For **2D Slice Visualization**: Consult [`reciprocal-space-plotting`](../reciprocal-space-plotting/SKILL.md).
