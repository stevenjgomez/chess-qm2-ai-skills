---
name: temperature-series-analysis
description: >-
  Analyze CHESS temperature-dependent diffraction datasets using TempDependence and
  TempDict from nxs_analysis_tools. Use when performing batch operations across an entire
  temperature series at once (e.g., batch Scissors linecuts), generating waterfall plots,
  (Q, T) false-color intensity heatmaps, multi-temperature peak fitting, tracking order
  parameters across phase transitions, or exporting 4D datasets (to_xtec) for clustering.
---

# CHESS Temperature-Dependent Data Analysis Skill (`temperature-series-analysis`)

This skill provides operational workflows, API runbooks, and reference scripts for analyzing multi-temperature reciprocal space series at the CHESS ID4B/QM2 beamline using `nxs_analysis_tools.chess.TempDependence`.

---

## 1. Key Capabilities of `TempDependence`

The `TempDependence` class wraps a collection of temperature datasets into a unified analysis object:

1. **Polymorphic Temperature Indexing (`TempDict`)**:
   Temperatures can be queried transparently using numeric floats, integers, or string path conventions without key errors:
   ```python
   td.datasets[15.5] == td.datasets['15.5'] == td.datasets['15p5']
   ```
2. **Automated Discovery & Lazy Loading**:
   Scans sample directories, discovers all temperature subdirectories or files, and mounts NeXus volumes lazily ($O(1)$ memory).
3. **Batch Operations Across All Temperatures in One Call**:
   Operations like `Scissors` linecuts are applied across **all loaded temperatures simultaneously**, eliminating tedious manual temperature loops.
4. **Built-in Thermal Evolution Visualizations**:
   Native methods generate waterfall linecut plots, $(Q, T)$ false-color heatmaps, integration window diagnostic overlays, and peak fitting comparisons.
5. **Phase Transition Order Parameters**:
   Fit reflection peaks across temperatures and automatically plot peak height, integrated area, or FWHM as a function of temperature ($I(T)$).

---

## 2. Standard Workflow & API Runbook

### Step 1: Initialization & Temperature Discovery

```python
from nxs_analysis_tools.chess import TempDependence

# Initialize pointing to sample root directory
# e.g. /nfs/chess/id4baux/2026-3/yi-4791-b/processed_old_way/FeGeSb/sample1A/
sample_dir = "/path/to/sample_root"
td = TempDependence(sample_dir)

# 1. Discover all temperature scans
td.find_temperatures()
print("Discovered temperatures:", td.temperatures)

# 2. Lazy load all datasets matching a specific pattern (e.g. streaming lite volumes)
td.load_datasets(file_ending="3rot_hkli_lite.nxs", print_tree=False)
```

---

### Step 2: Batch Linecut Extraction (`td.cut_data()`)

Instead of iterating through temperatures with a for-loop, configure the lattice and cut window once on `TempDependence`:

```python
# 1. Set unit cell (a, b, c, alpha, beta, gamma)
td.set_lattice_params((5.0027, 5.0027, 4.0548, 90.0, 90.0, 120.0))

# 2. Set center of the target reflection (H, K, L)
td.set_center((1.0, 0.0, 0.0))

# 3. Set window (integration thickness along transverse axes, cut bounds along main axis)
td.set_window((0.5, 0.1, 0.1))

# 4. Execute batch cut across all temperatures in a single call!
# axis: 0 for H, 1 for K, 2 for L (Legacy CHESS)
td.cut_data(axis=0)
```

---

### Step 3: Multi-Temperature Visualizations

#### A. Waterfall Linecut Plot
Visualizes the evolution of the 1D linecut profile stacked vertically across temperatures:
```python
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

fig, ax = plt.subplots(figsize=(7, 8), dpi=200)
td.plot_linecuts(
    ax=ax,
    vertical_offset=500.0,  # Vertical spacing between temperature traces
    cmap="coolwarm",        # Temperature-mapped colormap
)
ax.set_title(r"Temperature Evolution through $(1, 0, 0)$ Reflection")
plt.tight_layout()
plt.savefig("waterfall_linecuts.png", dpi=300)
plt.close(fig)
```

#### B. $(Q, T)$ 2D False-Color Heatmap
Renders a continuous intensity surface where the x-axis is reciprocal coordinate $Q$, the y-axis is temperature $T$, and color represents scattering intensity:
```python
fig, ax = plt.subplots(figsize=(6, 5), dpi=200)
td.plot_linecuts_heatmap(ax=ax, cmap="inferno")
ax.set_xlabel(r"$H$ (r.l.u.)")
ax.set_ylabel(r"Temperature (K)")
ax.set_title(r"$(Q, T)$ Intensity Heatmap")
plt.tight_layout()
plt.savefig("linecuts_heatmap.png", dpi=300)
plt.close(fig)
```

#### C. Integration Window Overlay Diagnostic
Verifies the integration bounds superimposed on a real reciprocal space slice:
```python
fig, ax = plt.subplots(figsize=(6, 5), dpi=200)
td.plot_integration_window(temperature=300, ax=ax)
plt.savefig("window_diagnostic.png", dpi=300)
plt.close(fig)
```

---

### Step 4: Peak Fitting & Order Parameter Extraction

```python
# 1. Define model components (e.g. Gaussian peak + Linear background)
from lmfit.models import GaussianModel, LinearModel

model = GaussianModel(prefix="peak_") + LinearModel(prefix="bg_")
td.set_model_components(model)

# 2. Generate parameter hints and fit across all temperatures
td.guess()
td.fit(verbose=False)

# 3. Print fit report
td.print_fit_report()

# 4. Plot order parameter (peak height vs temperature)
fig, ax = plt.subplots(figsize=(6, 4), dpi=200)
td.plot_order_parameter(param_name="peakheight", ax=ax, marker="o", color="crimson")
ax.set_xlabel("Temperature (K)", fontsize=11)
ax.set_ylabel("Peak Intensity (counts)", fontsize=11)
ax.set_title("Order Parameter: $I(T)$ across Transition", fontsize=12)
ax.grid(True, linestyle="--", alpha=0.5)
plt.tight_layout()
plt.savefig("order_parameter.png", dpi=300)
plt.close(fig)
```

---

### Step 5: Downstream Export to 4D NeXus (`td.to_xtec()`)

When preparing a complete temperature series for unsupervised clustering in `xtec-gpu-analysis`:
```python
# Compiles a 4D NeXus array (shape: N_T x N_H x N_K x N_L)
td.to_xtec(
    filepath="/path/to/sample/xtec_data.nxs",
    overwrite=False,
)
```

---

## 3. Standalone CLI Reference Scripts

This skill includes turnkey standalone CLI tools in [`scripts/`](./scripts/):

1. **`batch_temp_linecuts.py`**:
   Discovers all temperatures in a sample folder, extracts a batch `Scissors` cut, and exports both a waterfall plot and a $(Q, T)$ heatmap:
   ```bash
   python scripts/batch_temp_linecuts.py \
     --sample-dir /path/to/sample_root \
     --file-ending "3rot_hkli_lite.nxs" \
     --axis H \
     --center "1.0, 0.0, 0.0" \
     --window "0.5, 0.1, 0.1" \
     --outdir ./temperature_cuts/
   ```

2. **`temp_order_parameter.py`**:
   Fits a reflection across temperatures and generates the order parameter curve:
   ```bash
   python scripts/temp_order_parameter.py \
     --sample-dir /path/to/sample_root \
     --file-ending "3rot_hkli_lite.nxs" \
     --center "1.0, 0.0, 0.0" \
     --window "0.5, 0.1, 0.1" \
     --output order_parameter.png
   ```

---

## 4. Sister Skills & Integration

- For **Single-Volume Slicing & Plotting**: Consult [`reciprocal-space-plotting`](../reciprocal-space-plotting/SKILL.md).
- For **Animations (GIF/MP4)**: Consult [`reciprocal-space-animation`](../reciprocal-space-animation/SKILL.md).
- For **Single-Volume 1D Linecuts**: Consult [`reciprocal-space-linecuts`](../reciprocal-space-linecuts/SKILL.md).
- For **GPU Clustering (XTEC)**: Consult [`xtec-gpu-analysis`](../xtec-gpu-analysis/SKILL.md) after running `td.to_xtec()`.
