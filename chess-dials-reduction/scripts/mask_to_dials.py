#!/usr/bin/env python3
"""
mask_to_dials.py: Convert beamline detector masks (.edf from pyFAI/Fit2D)
or create DIALS-compatible boolean mask pickle files (pixels.mask).

DIALS Mask Convention:
- True: Trusted / valid pixel
- False: Untrusted / masked pixel (bad pixel, intermodule gap, beamstop shadow)
- Saved as a pickle containing a tuple of scitbx.array_family.flex.bool arrays (one per detector panel).

Author: Steven Gomez-Alvarado / CHESS Data Reduction Skills
"""

import argparse
import os
import pickle
import sys


def convert_edf_to_dials_mask(edf_file, output_mask, existing_dials_mask=None):
    """
    Convert an EDF mask to a DIALS pixels.mask file.
    If an existing DIALS mask is provided, perform a logical AND (both must be trusted).
    """
    try:
        import fabio
    except ImportError:
        print("Error: fabio is required to read EDF files. Please install fabio or run in dials.python.", file=sys.stderr)
        sys.exit(1)

    try:
        from scitbx.array_family import flex
        import numpy as np
    except ImportError:
        print("Error: scitbx/flex is required. Run this script using `dials.python`.", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(edf_file):
        raise FileNotFoundError(f"EDF mask not found: {edf_file}")

    print(f"Reading EDF mask: {edf_file}")
    img = fabio.open(edf_file)
    data = img.data  # shape typically (2527, 2463) for Pilatus 6M

    # EDF convention: 0 = valid / trusted, >0 = masked / untrusted
    trusted_np = (data == 0)
    print(f"EDF dimensions: {data.shape}, Trusted pixels: {np.count_nonzero(trusted_np)} / {data.size}")

    if existing_dials_mask and os.path.exists(existing_dials_mask):
        print(f"Merging with existing DIALS mask: {existing_dials_mask}")
        with open(existing_dials_mask, "rb") as f:
            base_mask = pickle.load(f)
        base_np = base_mask[0].as_numpy_array()
        trusted_np = trusted_np & base_np
        print(f"Combined trusted pixels: {np.count_nonzero(trusted_np)} / {data.size}")

    # Convert to DIALS flex.bool tuple
    dials_mask_tuple = (flex.bool(trusted_np),)

    with open(output_mask, "wb") as f:
        pickle.dump(dials_mask_tuple, f, protocol=pickle.HIGHEST_PROTOCOL)

    print(f"Successfully saved DIALS mask to: {output_mask}")


def main():
    parser = argparse.ArgumentParser(description="Convert EDF mask to DIALS pixels.mask format.")
    parser.add_argument("--edf", required=True, help="Path to input .edf mask file")
    parser.add_argument("--out", default="pixels.mask", help="Path to output DIALS .mask file")
    parser.add_argument("--combine-with", help="Path to existing DIALS pixels.mask to combine with")

    args = parser.parse_args()
    convert_edf_to_dials_mask(args.edf, args.out, args.combine_with)


if __name__ == "__main__":
    main()
