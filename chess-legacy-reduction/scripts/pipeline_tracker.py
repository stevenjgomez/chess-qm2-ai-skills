#!/usr/bin/env python
"""
Pipeline Status Ledger and Tracker for CHESS Legacy Reduction.
Manages persistent JSON state tracking sample progress across stacking, ORM solving,
HKL conversion, user verification, and distributed batch processing.
Compatible with /nfs/chess/sw/anaconda3_jpcr/ without modifications.
"""

import os
import sys
import json
from datetime import datetime


def get_status_filepath(sample_root):
    return os.path.join(sample_root, "pipeline_status.json")


def load_status(sample_root):
    status_file = get_status_filepath(sample_root)
    if os.path.exists(status_file):
        with open(status_file, "r") as f:
            return json.load(f)
    return None


def save_status(sample_root, data):
    os.makedirs(sample_root, exist_ok=True)
    status_file = get_status_filepath(sample_root)
    data["last_updated"] = datetime.now().isoformat()
    with open(status_file, "w") as f:
        json.dump(data, f, indent=2)
    return status_file


def init_sample(sample_root, sample_name, sample_id, cycle, experiment,
                spec_file, calib_file, mask_file, unit_cell=None):
    """Initialize a new sample status entry or load existing."""
    existing = load_status(sample_root)
    if existing:
        print(f"Status file already exists for {sample_id} at {sample_root}")
        return existing

    status = {
        "sample": sample_name,
        "sample_id": sample_id,
        "cycle": cycle,
        "experiment": experiment,
        "created_at": datetime.now().isoformat(),
        "last_updated": datetime.now().isoformat(),
        "config": {
            "spec_file": spec_file,
            "calib_file": calib_file,
            "mask_file": mask_file,
            "unit_cell": unit_cell
        },
        "orientation": {
            "reference_temperature": None,
            "status": "NOT_STARTED",
            "orm_file": None,
            "mean_hkl_deviation": None,
            "verified_by_user": False,
            "verified_at": None
        },
        "temperatures": {}
    }
    save_status(sample_root, status)
    print(f"Initialized status tracking at {sample_root}/pipeline_status.json")
    return status


def update_temp_step(sample_root, temp_str, step_name, state, details=None):
    """
    Update step state for a specific temperature.
    step_name: 'stacking', 'hkl_1rot', 'hkl_3rot'
    state: 'PENDING', 'RUNNING', 'COMPLETED', 'FAILED'
    """
    status = load_status(sample_root)
    if not status:
        raise ValueError(f"No status file found at {sample_root}")

    if temp_str not in status["temperatures"]:
        status["temperatures"][temp_str] = {
            "temperature_K": int(temp_str) if str(temp_str).isdigit() else temp_str,
            "steps": {}
        }

    status["temperatures"][temp_str]["steps"][step_name] = {
        "state": state,
        "updated_at": datetime.now().isoformat(),
        "details": details or {}
    }
    save_status(sample_root, status)


def record_orientation_result(sample_root, ref_temp, orm_file, mean_dev, verified=False):
    """Update orientation matrix state."""
    status = load_status(sample_root)
    if not status:
        raise ValueError(f"No status file found at {sample_root}")

    status["orientation"]["reference_temperature"] = ref_temp
    status["orientation"]["orm_file"] = orm_file
    status["orientation"]["mean_hkl_deviation"] = mean_dev
    status["orientation"]["status"] = "VERIFIED" if verified else "PENDING_USER_VERIFICATION"
    status["orientation"]["verified_by_user"] = verified
    if verified:
        status["orientation"]["verified_at"] = datetime.now().isoformat()

    save_status(sample_root, status)


def verify_orientation(sample_root):
    """Mark the orientation matrix as verified by user in pipeline_status.json."""
    status = load_status(sample_root)
    if not status:
        raise ValueError(f"No status file found at {sample_root}")
    status["orientation"]["status"] = "VERIFIED"
    status["orientation"]["verified_by_user"] = True
    status["orientation"]["verified_at"] = datetime.now().isoformat()
    save_status(sample_root, status)
    print(f"Orientation matrix successfully marked as VERIFIED for {status.get('sample_id', 'sample')} at {sample_root}")


def print_summary(sample_root):
    """Print readable progress summary."""
    status = load_status(sample_root)
    if not status:
        print(f"No status file found at {sample_root}")
        return

    print("=" * 60)
    print(f"Sample: {status['sample']} ({status['sample_id']})")
    print(f"Cycle:  {status['cycle']} | Experiment: {status['experiment']}")
    print(f"Spec:   {status['config'].get('spec_file')}")
    print(f"Calib:  {status['config'].get('calib_file')}")
    print(f"Mask:   {status['config'].get('mask_file')}")
    print(f"UCell:  {status['config'].get('unit_cell')}")
    print("-" * 60)
    orm = status["orientation"]
    print(f"Orientation (Ref T = {orm['reference_temperature']} K):")
    print(f"  Status:         {orm['status']}")
    print(f"  ORM File:       {orm['orm_file']}")
    print(f"  Mean Deviation: {orm['mean_hkl_deviation']}")
    print(f"  User Verified:  {orm['verified_by_user']}")
    print("-" * 60)
    print("Temperatures Progress:")
    for temp, tdata in sorted(status["temperatures"].items(), key=lambda x: int(x[0]) if str(x[0]).isdigit() else 0):
        steps = tdata.get("steps", {})
        stack_st = steps.get("stacking", {}).get("state", "NONE")
        hkl1_st = steps.get("hkl_1rot", {}).get("state", "NONE")
        hkl3_st = steps.get("hkl_3rot", {}).get("state", "NONE")
        print(f"  {temp:>5} K | Stack: {stack_st:<10} | 1rot: {hkl1_st:<10} | 3rot: {hkl3_st:<10}")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Pipeline Status Ledger and Tracker for CHESS Legacy Reduction")
    parser.add_argument("sample_root", help="Processed sample root directory (containing pipeline_status.json)")
    parser.add_argument("--verify-orm", "-v", action="store_true",
                        help="Record human-in-the-loop verification of the orientation matrix")
    args = parser.parse_args()

    sample_root = os.path.abspath(args.sample_root)
    if args.verify_orm:
        verify_orientation(sample_root)
    print_summary(sample_root)
