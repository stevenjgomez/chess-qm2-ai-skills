# Jana2020 & Olex2 Import Guide for DIALS Refinement Bundles

This document explains how to import reflection data exported from the `chess-dials-reduction` workflow into **Jana2020** and **Olex2 / SHELXL**.

---

## 1. Directory Structure of Refinement Files

Upon completion of Stage 2, the pipeline creates a standardized folder:
```text
<work_dir>/for_refinement/
├── unmerged.hkl    # Unmerged reflections (HKLF 4) with all symmetry-equivalent observations
├── unmerged.ins    # SHELX instruction header matching unmerged reflections
├── merged.hkl      # Merged reflections (HKLF 4) with symmetry-averaged F^2 and sigmas
├── merged.ins      # SHELX instruction header matching merged reflections
└── refinement_prep_report.md
```

---

## 2. Importing into Jana2020

Jana2020 is designed for advanced crystallographic refinement, including standard 3D periodic structures, modulated incommensurate/commensurate structures, composite crystals, and multipole refinements.

### Recommended Input: Unmerged Reflections (`unmerged.ins` + `unmerged.hkl`)
Using unmerged data allows Jana2020 to apply internal scaling, spherical/analytical crystal absorption corrections, and twinned/anomalous refinement directly.

### Step-by-Step Import:
1. **Create New Project**:
   - Open Jana2020.
   - Go to **File $\rightarrow$ New Structure**.
   - Set project directory and structure title.
2. **Select Reflection Format**:
   - In the import dialog, select **SHELX format (*.ins, *.hkl)**.
   - Browse to `for_refinement/unmerged.ins` (Jana automatically pairs with `unmerged.hkl`).
3. **Verify Cell and Symmetry**:
   - Jana2020 reads unit cell parameters and space group symmetry from `unmerged.ins`.
   - Confirm or adjust the space group if non-standard settings or alternate origins were chosen.
4. **Modulated / Commensurate Structures (Optional)**:
   - If refining a supercell or modulated structure:
     - Under **Basic Parameters $\rightarrow$ Symmetry**, change dimension from $3\text{D}$ to $(3+d)\text{D}$.
     - Define the modulation vectors $\mathbf{q}$ (e.g. $\mathbf{q} = (\frac{1}{12}, 0, 0)$ or similar modulation coordinates).
     - Jana will classify reflections into main ($m=0$) and satellites ($m = \pm 1, \pm 2$).
5. **Solve / Refine**:
   - Proceed to **Tools $\rightarrow$ Solve** (Superflip) or import starting atomic coordinates.

---

## 3. Importing into Olex2 / SHELXL

Olex2 is optimized for rapid molecular and small-molecule crystal structure solution and SHELXL refinement.

### Recommended Input: Merged Reflections (`merged.ins` + `merged.hkl`)
Merged reflections are averaged over symmetry equivalents, providing standard input for SHELXT / SHELXD and SHELXL.

### Step-by-Step Import:
1. **Open Structure in Olex2**:
   - Launch Olex2.
   - Open file: `File -> Open` and select `for_refinement/merged.ins`.
   - Alternatively, from the terminal:
     ```bash
     olex2 for_refinement/merged.ins
     ```
2. **Structure Solution**:
   - In the Olex2 GUI, open the **Solve** panel.
   - Method: Select **SHELXT** (default, automatic space group and heavy atom assignment) or **ShelxS**.
   - Click **Solve**.
3. **Structure Refinement**:
   - Open the **Refine** panel.
   - Engine: **SHELXL**.
   - Refine isotropic displacement parameters, assign atom types, and convert to anisotropic ADPs (`aniso`).
