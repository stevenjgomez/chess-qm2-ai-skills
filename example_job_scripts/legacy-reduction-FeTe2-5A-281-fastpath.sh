#!/bin/bash
#$ -S /bin/bash
#$ -N leg_FeTe2_281
#$ -cwd
#$ -j y
#$ -o /nfs/chess/id4baux/2026-2/gomez-al-4850-a/processed_old_way/FeTe2/FeTe2-5A/281/qsub_fastpath.log

echo "=== Legacy CHESS Reduction Fast-Path Job ==="
echo "Running on host: $(hostname)"
echo "Date: $(date) | User: ${USER} | Job ID: ${JOB_ID}"

/nfs/chess/sw/anaconda3_jpcr/bin/python -u ${HOME}/Documents/automate_legacy_workflow/scripts/orchestrate_reduction.py \
  --cycle 2026-2 \
  --experiment gomez-al-4850-a \
  --sample FeTe2 \
  --sample-id FeTe2-5A \
  --calib-file /nfs/chess/id4baux/2026-2/gomez-al-4850-a/calibrations/ceO2_15keV_trans.poni \
  --mask-file /nfs/chess/id4baux/2026-2/gomez-al-4850-a/calibrations/mask_trans.edf \
  --unit-cell "3.73970,3.73970,5.77800,90,90,120"

echo "=== Job Completed at $(date) ==="
