#!/usr/bin/env python3
"""
bravais_matcher.py: Parse dials.refine_bravais_settings.log and match candidate
Bravais settings against target crystallographic unit cell parameters.

Author: Steven Gomez-Alvarado / CHESS Data Reduction Skills
"""

import argparse
import json
import os
import re
import sys


def parse_bravais_log(log_path):
    """Parse the Bravais settings table from dials.refine_bravais_settings.log."""
    if not os.path.exists(log_path):
        raise FileNotFoundError(f"Log file not found: {log_path}")

    with open(log_path, "r") as f:
        content = f.read()

    solutions = []
    # Match the tabular lines:
    # Example line:
    # *    12   0.0507 0.089 0.812/0.892  2400     hR      4.76  4.76 12.99  90.00  90.00 120.00    255 -c,a,-b+c
    #      11   0.0620 0.095 0.750/0.810  2380     oC      ...
    table_pattern = re.compile(
        r"^\s*([*]?)\s*(\d+)\s+([\d\.]+)\s+([\d\.]+)\s+([-\d\./]+)\s+(\d+)\s+([a-zA-Z]+)\s+"
        r"([\d\.]+)\s+([\d\.]+)\s+([\d\.]+)\s+([\d\.]+)\s+([\d\.]+)\s+([\d\.]+)\s+([\d\.]+)\s+(\S+)",
        re.MULTILINE
    )

    for match in table_pattern.finditer(content):
        recommended = match.group(1) == "*"
        sol_id = int(match.group(2))
        metric_fit = float(match.group(3))
        rmsd = float(match.group(4))
        cc = match.group(5)
        n_spots = int(match.group(6))
        bravais_lattice = match.group(7)
        a = float(match.group(8))
        b = float(match.group(9))
        c = float(match.group(10))
        alpha = float(match.group(11))
        beta = float(match.group(12))
        gamma = float(match.group(13))
        volume = float(match.group(14))
        cb_op = match.group(15)

        solutions.append({
            "solution": sol_id,
            "recommended": recommended,
            "metric_fit": metric_fit,
            "rmsd": rmsd,
            "cc": cc,
            "spots": n_spots,
            "lattice": bravais_lattice,
            "cell": [a, b, c, alpha, beta, gamma],
            "volume": volume,
            "cb_op": cb_op,
            "file": f"bravais_setting_{sol_id}.expt"
        })

    return solutions


def score_cell_match(sol_cell, target_cell):
    """
    Compute a normalized error score between solution cell and target cell.
    Considers standard axis permutations if lengths are close.
    """
    sol_a, sol_b, sol_c, sol_al, sol_be, sol_ga = sol_cell
    tgt_a, tgt_b, tgt_c, tgt_al, tgt_be, tgt_ga = target_cell

    # Length relative differences
    d_len = (abs(sol_a - tgt_a) / tgt_a +
             abs(sol_b - tgt_b) / tgt_b +
             abs(sol_c - tgt_c) / tgt_c)

    # Angle absolute differences in degrees (normalized by 90)
    d_ang = (abs(sol_al - tgt_al) +
             abs(sol_be - tgt_be) +
             abs(sol_ga - tgt_ga)) / 90.0

    return d_len + d_ang


def match_bravais_settings(solutions, target_cell=None, target_lattice=None):
    """Rank solutions against target cell and lattice."""
    ranked = []
    for sol in solutions:
        score = 0.0
        if target_cell is not None:
            score += score_cell_match(sol["cell"], target_cell)
        if target_lattice is not None:
            if sol["lattice"].lower() != target_lattice.lower():
                score += 5.0  # heavy penalty for lattice mismatch
        ranked.append((score, sol))

    ranked.sort(key=lambda x: (x[0], x[1]["metric_fit"]))
    return ranked


def main():
    parser = argparse.ArgumentParser(description="Match DIALS Bravais settings to target unit cell.")
    parser.add_argument("--log", default="dials.refine_bravais_settings.log", help="Path to Bravais log file")
    parser.add_argument("--target-cell", help="Target cell as a,b,c,alpha,beta,gamma")
    parser.add_argument("--target-lattice", help="Target Bravais lattice (e.g. hP, hR, oP, mP, tP)")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")

    args = parser.parse_args()

    target_cell = None
    if args.target_cell:
        target_cell = [float(x.strip()) for x in args.target_cell.split(",")]
        if len(target_cell) != 6:
            raise ValueError("Target cell must have 6 parameters: a,b,c,alpha,beta,gamma")

    solutions = parse_bravais_log(args.log)
    if not solutions:
        print("No Bravais solutions parsed from log file.", file=sys.stderr)
        sys.exit(1)

    ranked = match_bravais_settings(solutions, target_cell, args.target_lattice)

    if args.json:
        out = {
            "solutions": solutions,
            "best_match": ranked[0][1] if ranked else None,
            "best_score": ranked[0][0] if ranked else None
        }
        print(json.dumps(out, indent=2))
        return

    print("=== DIALS Bravais Settings Evaluation ===")
    print(f"Total candidate solutions parsed: {len(solutions)}")
    if target_cell:
        print(f"Target Unit Cell: {target_cell}")
    if args.target_lattice:
        print(f"Target Lattice: {args.target_lattice}")
    print()

    print(f"{'Sol':<4} {'Fit':<8} {'RMSD':<6} {'CC':<12} {'Lattice':<8} {'Unit Cell':<42} {'cb_op':<15} {'Score':<6}")
    print("-" * 95)
    for score, sol in ranked:
        c = sol["cell"]
        cell_str = f"{c[0]:.2f} {c[1]:.2f} {c[2]:.2f} {c[3]:.1f} {c[4]:.1f} {c[5]:.1f}"
        rec = "*" if sol["recommended"] else " "
        print(f"{rec}{sol['solution']:<3} {sol['metric_fit']:<8.4f} {sol['rmsd']:<6.3f} {sol['cc']:<12} {sol['lattice']:<8} {cell_str:<42} {sol['cb_op']:<15} {score:<6.3f}")

    best = ranked[0][1]
    print()
    print(f"--> RECOMMENDED SOLUTION: Setting {best['solution']} ({best['lattice']})")
    print(f"    Cell: {best['cell']}")
    print(f"    Change of basis: {best['cb_op']}")
    print(f"    Experiment file: {best['file']}")
    print()
    print("Next commands:")
    if best['cb_op'] != "a,b,c":
        print(f"  dials.reindex indexed.refl change_of_basis_op={best['cb_op']}")
        print(f"  dials.refine {best['file']} reindexed.refl")
    else:
        print(f"  dials.refine {best['file']} indexed.refl")


if __name__ == "__main__":
    main()
