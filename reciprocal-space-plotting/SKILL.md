---
name: reciprocal-space-plotting
description: >-
  Fast, recipe-driven 2D slice visualization and orthogonal multi-panel plotting
  for 3D reciprocal space X-ray and neutron diffraction datasets (NeXus/HDF5).
  Use when generating 2D cross-sectional slices (HK, HL, KL planes), 3-panel
  summary figures, calibrated physical aspect ratio (b*/a*, c*/a*) projections,
  crystallographic skew grid lines, integer tick locators, or logarithmic colormaps.
---

# 2D Reciprocal Space Plotting & Slicing Skill (`reciprocal-space-plotting`)

This skill provides fast, copy-paste-ready Python recipes and operational standards for generating 2D reciprocal space cross-sections and publication-quality diagnostic figures from 3D NeXus datasets (`.nxs`, `.h5`).

---

## 1. Golden Rules of Reciprocal Space Plotting

1. **Strictly Enforce Headless Rendering**:
   Always set the non-interactive backend before importing `pyplot`:
   ```python
   import matplotlib
   matplotlib.use("Agg")
   import matplotlib.pyplot as plt
   ```
2. **Never Read Full 3D Volumes into Memory (`.nxdata` Trap)**:
   Accessing `.nxdata` directly on an unsliced 3D dataset forces an eager read of the entire 1–25 GB volume into RAM. Always slice lazily using hyperslab indexing (`data[:, :, 0.0]`) or `h5py` dataset slicing.
3. **Logarithmic Scaling (`LogNorm`) Requires `vmin > 0`**:
   Zero or negative pixels (e.g. from background subtraction or unvisited detector pixels) cause `LogNorm` to fail or render black artifacts. Always set `vmin >= 1.0` (or `vmin = max(1.0, np.nanpercentile(slice_data[slice_data > 0], 5))`).
4. **Physical Aspect Ratio Calibration is Mandatory**:
   Synchrotron reciprocal lattice parameters frequently differ between axes ($a^* \ne c^*$). If aspect ratio is left uncalibrated, circular diffuse rings elongate into ellipses along $L$. Always scale the display aspect ratio:
   $$A_{\text{display}} = \frac{v_Y^*}{v_X^*} \times \sin(\theta_{\text{skew}})$$

---

## 2. Dataset Format Coordinates & Plane Slicing

A reciprocal lattice plane is defined by **fixing the coordinate perpendicular to the plane**:
- **$HK$ Plane**: Hold $L$ constant (free axes: $H, K$).
- **$HL$ Plane**: Hold $K$ constant (free axes: $H, L$).
- **$KL$ Plane**: Hold $H$ constant (free axes: $K, L$).

Because NXRefine and Legacy CHESS data structures use different axis ordering conventions, slice axes differ:

| Dataset Format | Native Axes | $HK$ Slice ($L=\text{const}$) | $HL$ Slice ($K=\text{const}$) | $KL$ Slice ($H=\text{const}$) |
| :--- | :--- | :--- | :--- | :--- |
| **Legacy CHESS** (`*hkli*.nxs`) | `['H', 'K', 'L']` | Axis 2: `data[:, :, l_val]` | Axis 1: `data[:, k_val, :]` | Axis 0: `data[h_val, :, :]` |
| **NXRefine** (`use_nxlink=True`) | `['Ql', 'Qk', 'Qh']` | Axis 0: `data[l_val, :, :]` | Axis 1: `data[:, k_val, :]` | Axis 2: `data[:, :, h_val]` |

> [!WARNING]
> Always check `data.nxaxes` before indexing! In NXRefine, indexing Axis 2 fixes $Q_h$ (yielding the $KL$ plane, NOT the $HK$ plane).

---

## 3. Recipes

### Recipe 1: Quick Single 2D Slice (with Aspect Ratio & Skew)

```python
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from matplotlib.ticker import MultipleLocator
import numpy as np
import nexusformat.nexus as nx

# 1. Open volume lazily
nx.nxsetmemory(20000)
root = nx.nxload("3rot_hkli_lite.nxs")
data = root.entry.data

# 2. Extract HK plane lazily at L = 0.0
# For Legacy CHESS: axes are [H, K, L] -> slice along axis 2
slice_nx = data[:, :, 0.0]
counts = np.asarray(slice_nx.nxsignal.nxdata, dtype=np.float32)
h_axis = np.asarray(slice_nx.nxaxes[0].nxdata)
k_axis = np.asarray(slice_nx.nxaxes[1].nxdata)

# 3. Setup figure
fig, ax = plt.subplots(figsize=(6, 5), dpi=200)

# 4. Aspect ratio: b* / a* (for hexagonal/tetragonal a* == b* -> 1.0)
aspect_ratio = 1.0  # b_star / a_star
vmin = max(1.0, float(np.nanpercentile(counts[counts > 0], 5)))
vmax = float(np.nanpercentile(counts[counts > 0], 99.8))

im = ax.imshow(
    counts.T,
    origin="lower",
    extent=[h_axis[0], h_axis[-1], k_axis[0], k_axis[-1]],
    norm=LogNorm(vmin=vmin, vmax=vmax),
    cmap="viridis",
    aspect=aspect_ratio,
)

# 5. Crystallographic integer ticks and labels
ax.xaxis.set_major_locator(MultipleLocator(2))
ax.xaxis.set_minor_locator(MultipleLocator(1))
ax.yaxis.set_major_locator(MultipleLocator(2))
ax.yaxis.set_minor_locator(MultipleLocator(1))
ax.tick_params(direction="in", top=True, right=True, which="both")

ax.set_xlabel(r"$H$ (r.l.u.)", fontsize=11)
ax.set_ylabel(r"$K$ (r.l.u.)", fontsize=11)
ax.set_title(r"$(HK0)$ Reciprocal Slice", fontsize=12)

cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
cbar.set_label("Intensity (counts)", fontsize=10)

plt.tight_layout()
plt.savefig("slice_HK.png", dpi=300)
plt.close(fig)
```

---

### Recipe 2: Standard 3-Panel Orthogonal Summary Plot ($HK, HL, KL$)

```python
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from matplotlib.ticker import MultipleLocator
import numpy as np
import nexusformat.nexus as nx

def generate_3panel_summary(nxs_path, out_png, h_val=0.0, k_val=0.0, l_val=0.0,
                             a_star=0.2304, b_star=0.2304, c_star=0.2467):
    """
    Generate side-by-side 3-panel figure for HK, HL, and KL planes.
    """
    nx.nxsetmemory(20000)
    root = nx.nxload(nxs_path)
    data = root.entry.data

    # Extract 2D hyperslabs lazily
    slice_hk = data[:, :, l_val]
    slice_hl = data[:, k_val, :]
    slice_kl = data[h_val, :, :]

    img_hk = np.asarray(slice_hk.nxsignal.nxdata, dtype=np.float32)
    img_hl = np.asarray(slice_hl.nxsignal.nxdata, dtype=np.float32)
    img_kl = np.asarray(slice_kl.nxsignal.nxdata, dtype=np.float32)

    h = np.asarray(slice_hk.nxaxes[0].nxdata)
    k = np.asarray(slice_hk.nxaxes[1].nxdata)
    l = np.asarray(slice_hl.nxaxes[1].nxdata)

    # Global normalization range across all 3 slices
    all_pos = np.concatenate([img_hk[img_hk > 0], img_hl[img_hl > 0], img_kl[img_kl > 0]])
    vmin = max(1.0, float(np.nanpercentile(all_pos, 5)))
    vmax = float(np.nanpercentile(all_pos, 99.8))
    norm = LogNorm(vmin=vmin, vmax=vmax)

    fig, axes = plt.subplots(1, 3, figsize=(15, 5), dpi=200)

    # 1. HK Plane (X=H, Y=K) -> Aspect: b* / a*
    im0 = axes[0].imshow(img_hk.T, origin="lower", extent=[h[0], h[-1], k[0], k[-1]],
                         norm=norm, cmap="viridis", aspect=(b_star / a_star))
    axes[0].set_xlabel(r"$H$ (r.l.u.)")
    axes[0].set_ylabel(r"$K$ (r.l.u.)")
    axes[0].set_title(f"$(HK{l_val:g})$ Slice")

    # 2. HL Plane (X=H, Y=L) -> Aspect: c* / a*
    axes[1].imshow(img_hl.T, origin="lower", extent=[h[0], h[-1], l[0], l[-1]],
                   norm=norm, cmap="viridis", aspect=(c_star / a_star))
    axes[1].set_xlabel(r"$H$ (r.l.u.)")
    axes[1].set_ylabel(r"$L$ (r.l.u.)")
    axes[1].set_title(f"$(H{k_val:g}L)$ Slice")

    # 3. KL Plane (X=K, Y=L) -> Aspect: c* / b*
    axes[2].imshow(img_kl.T, origin="lower", extent=[k[0], k[-1], l[0], l[-1]],
                   norm=norm, cmap="viridis", aspect=(c_star / b_star))
    axes[2].set_xlabel(r"$K$ (r.l.u.)")
    axes[2].set_ylabel(r"$L$ (r.l.u.)")
    axes[2].set_title(f"$({h_val:g}KL)$ Slice")

    for ax in axes:
        ax.xaxis.set_major_locator(MultipleLocator(2))
        ax.xaxis.set_minor_locator(MultipleLocator(1))
        ax.yaxis.set_major_locator(MultipleLocator(2))
        ax.yaxis.set_minor_locator(MultipleLocator(1))
        ax.tick_params(direction="in", top=True, right=True, which="both")

    fig.subplots_adjust(right=0.90, wspace=0.25)
    cbar_ax = fig.add_axes([0.92, 0.15, 0.015, 0.70])
    cbar = fig.colorbar(im0, cax=cbar_ax)
    cbar.set_label("Intensity (counts)")

    plt.savefig(out_png, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved 3-panel summary: {out_png}")
```

---

## 4. Standalone CLI Reference Scripts

This skill includes turnkey standalone CLI tools in [`scripts/`](./scripts/):

1. **`plot_slice.py`**:
   ```bash
   python scripts/plot_slice.py --nxs path/to/volume.nxs --plane HK --coord 0.0 --output slice_HK0.png
   ```
2. **`plot_summary.py`**:
   ```bash
   python scripts/plot_summary.py --nxs path/to/volume.nxs --output slices_summary.png --unit-cell "5.0027,5.0027,4.0548,90,90,120"
   ```

---

## 5. Sister Skills & Integration

- For **Volume & Temperature Animations (GIF/MP4)**: Consult [`reciprocal-space-animation`](../reciprocal-space-animation/SKILL.md).
- For **1D Linecuts with Scissors**: Consult [`reciprocal-space-linecuts`](../reciprocal-space-linecuts/SKILL.md).
- For **Temperature Series & TempDependence**: Consult [`temperature-series-analysis`](../temperature-series-analysis/SKILL.md).
- For **Upstream Data Reduction & Streaming**: Consult [`chess-legacy-reduction`](../chess-legacy-reduction/SKILL.md).
