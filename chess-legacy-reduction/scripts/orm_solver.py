#!/usr/bin/env python
"""
Headless Orientation Matrix Finder (ORM Solver)
Extracted and refactored from auto_ormfinder_tkinter.py for automated execution.
Compatible with /nfs/chess/sw/anaconda3_jpcr/ environment without modifications.
"""

import os
import sys
import argparse
import logging
import gc
import numpy as np
from os.path import exists
from scipy.spatial.transform import Rotation as R
from scipy.optimize import basinhopping

# Ensure headless plotting
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# NeXus import
from nexusformat.nexus import NXroot, NXentry, NXfield, nxload, nxsetmemory


def setup_codebase_imports(codebase_dir):
    """Add codebase dir containing hkl.py and libhkl.so to sys.path."""
    if codebase_dir and codebase_dir not in sys.path:
        sys.path.insert(0, codebase_dir)
    try:
        import hkl
        return hkl
    except ImportError as e:
        raise ImportError(f"Failed to import hkl from {codebase_dir}: {e}")


def parse_cif(cif_path):
    """
    Parse unit cell parameters from a CIF file using standard crystallographic tags.
    Strips parenthetical uncertainties, e.g., 5.271(4) -> 5.271.
    """
    import re
    tags = {
        'a': r'_cell_length_a\s+([\d\.\(\)]+)',
        'b': r'_cell_length_b\s+([\d\.\(\)]+)',
        'c': r'_cell_length_c\s+([\d\.\(\)]+)',
        'alpha': r'_cell_angle_alpha\s+([\d\.\(\)]+)',
        'beta': r'_cell_angle_beta\s+([\d\.\(\)]+)',
        'gamma': r'_cell_angle_gamma\s+([\d\.\(\)]+)',
    }
    values = {}
    with open(cif_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    for k, pattern in tags.items():
        match = re.search(pattern, content, re.IGNORECASE)
        if not match:
            raise ValueError(f"Could not find crystallographic tag for '{k}' in CIF file: {cif_path}")
        val_str = re.sub(r'\(.*?\)', '', match.group(1)).strip()
        values[k] = float(val_str)

    return values['a'], values['b'], values['c'], values['alpha'], values['beta'], values['gamma']


def load_unitcell(unitcell_source):
    """
    Parse unit cell parameters (a, b, c, alpha, beta, gamma) from a CIF file, CSV text file,
    or comma-separated string.
    """
    if os.path.isfile(unitcell_source):
        if unitcell_source.lower().endswith(".cif"):
            return parse_cif(unitcell_source)
        with open(unitcell_source, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    parts = [float(x.strip()) for x in line.split(",") if x.strip()]
                    if len(parts) == 6:
                        return parts[0], parts[1], parts[2], parts[3], parts[4], parts[5]
        raise ValueError(f"Could not parse 6 comma-separated unit cell values from {unitcell_source}")
    else:
        parts = [float(x.strip()) for x in unitcell_source.split(",") if x.strip()]
        if len(parts) != 6:
            raise ValueError(f"Expected 6 unit cell parameters, got {len(parts)} in '{unitcell_source}'")
        return parts[0], parts[1], parts[2], parts[3], parts[4], parts[5]


def generate_histogram(projectdir, stack_file):
    """Generate intensity distribution histogram."""
    stack_path = os.path.join(projectdir, stack_file)
    print(f"Loading stack for histogram: {stack_path}")
    nxsetmemory(100000)
    stack = nxload(stack_path)
    counts = stack.data.counts.nxdata
    Iall = counts[counts > 1000]
    peaksmax = np.max(Iall)

    fig, ax = plt.subplots(figsize=(4, 3), dpi=180)
    ax.hist(Iall / peaksmax, bins=20, color='royalblue', edgecolor='black')
    ax.set_yscale('log')
    ax.set_xlabel(r'$I/I_{\max}$')
    ax.set_ylabel('# pixels (log scale)')
    ax.set_title('Histogram of Pixel Intensities')

    hist_out = os.path.join(projectdir, 'histogram.png')
    fig.savefig(hist_out, bbox_inches='tight', dpi=300)
    plt.close(fig)
    print(f"Saved histogram to {hist_out}")
    del Iall, stack, counts
    gc.collect()


def get_peaklist(projectdir, stack_file, valmin=0.9, valmax=1.0, lower_bound=50, upper_bound=150):
    """
    Adaptive peak finding within threshold intensity ranges.
    """
    nxsetmemory(100000)
    stack_path = os.path.join(projectdir, stack_file)
    print(f"Loading stack for peak finding: {stack_path}")
    stack = nxload(stack_path)
    Iall = stack.data.counts.nxdata
    peaksmax = np.max(Iall)
    print(f"Max intensity is {peaksmax}")

    percofmax = float(valmax)
    percofmin = float(valmin)
    lower_bound = float(lower_bound)
    upper_bound = float(upper_bound)

    if percofmax != 1.0:
        peaks = np.logical_and(Iall < percofmax * peaksmax, Iall > percofmin * peaksmax)
    else:
        peaks = Iall > percofmin * peaksmax

    listofpeaks = np.asarray(np.where(peaks)).T
    print(f"Initial peaks found: {len(listofpeaks)} (target range: {lower_bound} - {upper_bound})")

    # Adaptive decrement if too few peaks
    while len(listofpeaks) < lower_bound and percofmin > 0.05:
        percofmin -= 0.1
        if percofmin < 0.01:
            percofmin = 0.01
        print(f"Not enough peaks ({len(listofpeaks)}). Decreasing threshold to: {percofmin:.3f}")
        gc.collect()
        if percofmax != 1.0:
            peaks = np.logical_and(Iall < percofmax * peaksmax, Iall > percofmin * peaksmax)
        else:
            peaks = Iall > percofmin * peaksmax
        listofpeaks = np.asarray(np.where(peaks)).T

    # Adaptive increment if too many peaks
    if len(listofpeaks) > upper_bound:
        while len(listofpeaks) > upper_bound and percofmin < percofmax:
            percofmin += 0.02
            print(f"Too many peaks ({len(listofpeaks)}). Increasing threshold to: {percofmin:.3f}")
            if percofmax != 1.0:
                peaks = np.logical_and(Iall < percofmax * peaksmax, Iall > percofmin * peaksmax)
            else:
                peaks = Iall > percofmin * peaksmax
            listofpeaks = np.asarray(np.where(peaks)).T

        # Fine-tune if it dropped below lower bound
        if len(listofpeaks) < lower_bound:
            while len(listofpeaks) < lower_bound and percofmin > 0.01:
                percofmin -= 0.01
                print(f"Fine-tuning: increasing sensitivity to: {percofmin:.3f}")
                gc.collect()
                if percofmax != 1.0:
                    peaks = np.logical_and(Iall < percofmax * peaksmax, Iall > percofmin * peaksmax)
                else:
                    peaks = Iall > percofmin * peaksmax
                listofpeaks = np.asarray(np.where(peaks)).T

    print(f"Final peaks selected: {len(listofpeaks)}")
    peakfile = os.path.join(projectdir, "peaklist1.npy")
    np.save(peakfile, listofpeaks)
    print(f"Saved peaklist to {peakfile}")
    del Iall, stack
    gc.collect()
    return peakfile, len(listofpeaks)


def calcB(a, b, c, alpha, beta, gamma):
    """Calculate B matrix from lattice constants."""
    a1, a2, a3 = a, b, c
    alpha1 = alpha * np.pi / 180.0
    alpha2 = beta * np.pi / 180.0
    alpha3 = gamma * np.pi / 180.0
    Vt = (1.0 - (np.cos(alpha1)**2) - (np.cos(alpha2)**2) - (np.cos(alpha3)**2))
    Vt += (2.0 * np.cos(alpha1) * np.cos(alpha2) * np.cos(alpha3))
    V = (Vt**0.5) * a1 * a2 * a3
    b1 = 2.0 * np.pi * a2 * a3 * np.sin(alpha1) / V
    b2 = 2.0 * np.pi * a3 * a1 * np.sin(alpha2) / V
    b3 = 2.0 * np.pi * a1 * a2 * np.sin(alpha3) / V
    betanum = (np.cos(alpha2) * np.cos(alpha3) - np.cos(alpha1))
    betaden = (np.sin(alpha2) * np.sin(alpha3))
    beta1 = np.arccos(betanum / betaden)
    betanum = (np.cos(alpha1) * np.cos(alpha3) - np.cos(alpha2))
    betaden = (np.sin(alpha1) * np.sin(alpha3))
    beta2 = np.arccos(betanum / betaden)
    betanum = (np.cos(alpha1) * np.cos(alpha2) - np.cos(alpha3))
    betaden = (np.sin(alpha1) * np.sin(alpha2))
    beta3 = np.arccos(betanum / betaden)
    UB = np.zeros(9)
    UB[0] = b1
    UB[1] = b2 * np.cos(beta3)
    UB[2] = b3 * np.cos(beta2)
    UB[3] = 0.0
    UB[4] = -b2 * np.sin(beta3)
    UB[5] = b3 * np.sin(beta2) * np.cos(alpha1)
    UB[6] = 0.0
    UB[7] = 0.0
    UB[8] = -b3
    return UB


def calcUB(eu1, eu2, eu3, UB):
    r = R.from_euler('zxz', [eu1, eu2, eu3])
    UBR = np.matmul(r.as_matrix(), UB.reshape(3, 3))
    return UBR


def find_euler(projectdir, stack_file, uca, ucb, ucc, ucal, ucbe, ucga, hkl_module, fixed_euler=None):
    """Optimize Euler angles against peak positions using Basinhopping, or apply fixed angles."""
    stack_path = os.path.join(projectdir, stack_file)
    w = nxload(stack_path)
    peakfile = os.path.join(projectdir, "peaklist1.npy")
    peaklist = np.load(peakfile)
    peaknum = len(peaklist)
    print(f"Loaded {peaknum} peaks for orientation optimization.")

    log_path = os.path.join(projectdir, "ormfinder.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_path, mode='w'),
            logging.StreamHandler(sys.stdout)
        ]
    )

    logging.info(f"Unit Cell: {uca} {ucb} {ucc} {ucal} {ucbe} {ucga}")
    philu = w.data.phi.nxdata
    wl = float(w.geo.wl)
    logging.info(f"Wavelength = {wl}")
    eta = float(w.psic.eta)
    mu = float(w.psic.mu)
    chi = float(w.psic.chi)
    myaz = np.asarray(w.geo.az.data)
    mypol = np.asarray(w.geo.pol.data)

    def XYtoPOLAZ(X, Y):
        return mypol[X, Y], myaz[X, Y]

    def chisq_U(plist, wave, UBR_mat):
        n = len(plist)
        chisq = 0.0
        for i in range(n):
            pol, az = XYtoPOLAZ(plist[i][0], plist[i][1])
            phi = philu[plist[i][2]]
            IN = hkl_module.Calc_HKL(np.asarray([pol]), np.asarray([az]), eta, mu, chi, phi, wave, UBR_mat)
            dvec = IN - np.rint(IN)
            chisq += np.linalg.norm(dvec)
        return chisq / n

    def minfuncU(eu, UB_mat, plist, wave):
        UBR = calcUB(eu[0], eu[1], eu[2], UB_mat)
        return chisq_U(plist, wave, UBR.T)

    myUB = calcB(uca, ucb, ucc, ucal, ucbe, ucga)
    logging.info(f"Calculated B matrix: {myUB}")

    if fixed_euler is not None:
        eu_final = np.array(fixed_euler, dtype=float)
        logging.info(f"Using fixed Euler angles: {eu_final}")
    else:
        # Preliminary fit if more than 75 peaks
        if peaknum > 75:
            shortpeaklist = peaklist[:20]
            x0 = [0, 0, 0]
            logging.info("Preliminary fitting on first 20 peaks (config A)...")
            min_kwargs = {"method": "BFGS", "args": (myUB, shortpeaklist, wl)}
            pre1 = basinhopping(minfuncU, x0, T=0.002, minimizer_kwargs=min_kwargs)
            logging.info(f"Eu angles A: {pre1.x}, chisq: {pre1.fun:.4f}")

            x0 = [0.5, 1.0, 0.25]
            logging.info("Preliminary fitting on first 20 peaks (config B)...")
            pre2 = basinhopping(minfuncU, x0, T=0.002, minimizer_kwargs=min_kwargs)
            logging.info(f"Eu angles B: {pre2.x}, chisq: {pre2.fun:.4f}")

        x0 = [0, 0, 0]
        logging.info("Stage 1 full peak optimization...")
        min_kwargs = {"method": "BFGS", "args": (myUB, peaklist, wl)}
        ret1 = basinhopping(minfuncU, x0, T=0.002, minimizer_kwargs=min_kwargs)
        logging.info(f"Stage 1 Eu angles: {ret1.x}, chisq: {ret1.fun:.4f}")

        x0 = ret1.x
        logging.info("Stage 2 full peak optimization (300 iter)...")
        ret2 = basinhopping(minfuncU, x0, minimizer_kwargs=min_kwargs, niter=300, seed=23)
        logging.info(f"Stage 2 Eu angles: {ret2.x}, chisq: {ret2.fun:.4f}")

        x0 = ret2.x
        logging.info("Stage 3 full peak refinement...")
        ret3 = basinhopping(minfuncU, x0, stepsize=np.pi / 30.0, T=0.005, minimizer_kwargs=min_kwargs, niter=100, seed=24)
        logging.info(f"Stage 3 Eu angles: {ret3.x}, final chisq: {ret3.fun:.4f}")
        eu_final = ret3.x

    # Compute final UBR
    UBRfinal = calcUB(eu_final[0], eu_final[1], eu_final[2], myUB)

    # Calculate reflection table and quality stats
    deviations = []
    print("\n--- Diagnostic Peak Indexing Table (First 15 Peaks) ---")
    print(f"{'Idx':<4} {'H':>7} {'K':>7} {'L':>7} {'d(H,K,L)':>10}")
    for i in range(len(peaklist)):
        pol, az = XYtoPOLAZ(peaklist[i][0], peaklist[i][1])
        phi = philu[peaklist[i][2]]
        hkl_raw = hkl_module.Calc_HKL(np.asarray([pol]), np.asarray([az]), eta, mu, chi, phi, wl, UBRfinal.T)
        hkl_calc = np.asarray(hkl_raw).flatten()
        dvec = hkl_calc - np.rint(hkl_calc)
        dev = float(np.linalg.norm(dvec))
        deviations.append(dev)
        if i < 15:
            print(f"{i:<4} {hkl_calc[0]:7.3f} {hkl_calc[1]:7.3f} {hkl_calc[2]:7.3f} {dev:10.4f}")

    mean_dev = float(np.mean(deviations))
    median_dev = float(np.median(deviations))
    close_peaks = int(np.sum(np.array(deviations) < 0.1))
    logging.info(f"Indexing Quality: Mean deviation = {mean_dev:.4f}, Median = {median_dev:.4f}")
    logging.info(f"Peaks within 0.1 r.l.u. of integer: {close_peaks}/{peaknum} ({100*close_peaks/peaknum:.1f}%)")

    return UBRfinal, eu_final, mean_dev, peaknum


def save_orm(projectdir, UBRfinal, uca, ucb, ucc, ucal, ucbe, ucga):
    """Save orientation matrix in NeXus and numpy formats."""
    ormout = os.path.join(projectdir, "ormatrix_auto.nxs")
    dpsi = 0.0

    # Save numpy array version
    np.save(ormout, UBRfinal)

    # Save NeXus version
    ormnex = NXroot()
    ormnex.unitcell = NXentry()
    ormnex.unitcell.a = NXfield(uca, name='a')
    ormnex.unitcell.b = NXfield(ucb, name='b')
    ormnex.unitcell.c = NXfield(ucc, name='c')
    ormnex.unitcell.alpha = NXfield(ucal, name='alpha')
    ormnex.unitcell.beta = NXfield(ucbe, name='beta')
    ormnex.unitcell.gamma = NXfield(ucga, name='gamma')

    ormnex.ormatrix = NXentry()
    ormnex.ormatrix.U = NXfield(UBRfinal, name='Orientation_Matrix')
    ormnex.dspi = NXentry()
    ormnex.dspi.dpsi = NXfield(dpsi, name='detector psi offset')
    ormnex.save(ormout)
    print(f"Successfully saved orientation matrix to {ormout}")


def main():
    parser = argparse.ArgumentParser(description="Headless Orientation Matrix Finder")
    parser.add_argument("--projectdir", required=True, help="Processed temperature directory (where stack1.nxs is located)")
    parser.add_argument("--unitcell", required=True, help="Unit cell CSV file or 'a,b,c,alpha,beta,gamma'")
    parser.add_argument("--codebase", default="/nfs/chess/id4baux/2026-2/gomez-al-4850-a/StevenGomezAlvarado_Codebase",
                        help="Path to legacy codebase containing hkl.py and libhkl.so")
    parser.add_argument("--valmin", type=float, default=0.9, help="Initial minimum intensity fraction")
    parser.add_argument("--valmax", type=float, default=1.0, help="Maximum intensity fraction")
    parser.add_argument("--lower-bound", type=int, default=50, help="Minimum acceptable number of peaks")
    parser.add_argument("--upper-bound", type=int, default=150, help="Maximum acceptable number of peaks")
    parser.add_argument("--skip-peaks", action="store_true", help="Skip peak finding if peaklist1.npy exists")
    parser.add_argument("--fixed-euler", type=str, default=None,
                        help="Skip optimization and apply fixed Euler angles 'e0,e1,e2'")

    args = parser.parse_args()

    projectdir = os.path.abspath(args.projectdir)
    if not projectdir.endswith(os.path.sep):
        projectdir += os.path.sep

    # Setup hkl import
    hkl_module = setup_codebase_imports(args.codebase)

    # Locate stack file
    stack_files = sorted([f for f in os.listdir(projectdir) if f.startswith("stack") and f.endswith(".nxs")])
    if not stack_files:
        raise FileNotFoundError(f"No stack*.nxs file found in {projectdir}")
    stack_file = stack_files[0]
    print(f"Using primary stack: {stack_file}")

    # Load unit cell
    uca, ucb, ucc, ucal, ucbe, ucga = load_unitcell(args.unitcell)
    print(f"Lattice constants: a={uca}, b={ucb}, c={ucc}, alpha={ucal}, beta={ucbe}, gamma={ucga}")

    # Write unitcell.txt in projectdir for consistency
    unitcell_txt = os.path.join(projectdir, "unitcell.txt")
    with open(unitcell_txt, "w") as f:
        f.write(f"{uca},{ucb},{ucc},{ucal},{ucbe},{ucga}\n")

    # Generate histogram
    generate_histogram(projectdir, stack_file)

    # Peak finding
    peakfile = os.path.join(projectdir, "peaklist1.npy")
    if not (args.skip_peaks and os.path.exists(peakfile)):
        get_peaklist(projectdir, stack_file, valmin=args.valmin, valmax=args.valmax,
                     lower_bound=args.lower_bound, upper_bound=args.upper_bound)

    # Orient
    fixed_eu = None
    if args.fixed_euler:
        fixed_eu = [float(x.strip()) for x in args.fixed_euler.split(",") if x.strip()]
    UBRfinal, eu_angles, mean_dev, peaknum = find_euler(
        projectdir, stack_file, uca, ucb, ucc, ucal, ucbe, ucga, hkl_module, fixed_euler=fixed_eu
    )

    # Save
    save_orm(projectdir, UBRfinal, uca, ucb, ucc, ucal, ucbe, ucga)
    print("\n--- ORM Solver Completed Successfully ---")
    print(f"Final Euler angles: {eu_angles}")
    print(f"Average integer HKL deviation: {mean_dev:.4f} r.l.u.")


if __name__ == "__main__":
    main()
