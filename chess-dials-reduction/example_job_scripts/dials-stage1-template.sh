#!/bin/bash
#$ -N dials_stage1
#$ -q 'all.q@lnx307*,all.q@lnx311*,all.q@lnx312*,all.q@lnx313*'
#$ -l mem_free=64G
#$ -pe sge_pe 24
#$ -j y
#$ -o dials_stage1.log

set -e
export OMP_NUM_THREADS=${NSLOTS:-24}
export MKL_NUM_THREADS=${NSLOTS:-24}

DIALS_ENV="/nfs/chess/sw/dials_sgomezalvarado/dials_env.sh"
SKILLS_DIR="$HOME/.gemini/config/skills/chess-dials-reduction"

WORK_DIR="$1"
RAW_DIR="$2"
PONI_FILE="$3"
EDF_MASK="${4:-}"
UNIT_CELL="${5:-}"
SPACE_GROUP="${6:-}"

if [ -z "$WORK_DIR" ] || [ -z "$RAW_DIR" ] || [ -z "$PONI_FILE" ]; then
    echo "Usage: qsub dials-stage1-template.sh <work_dir> <raw_dir> <poni_file> [edf_mask] [unit_cell] [space_group]"
    exit 1
fi

echo "=== Launching DIALS Stage 1 Batch Reduction on Compute Node: $(hostname) ==="
date
echo "Work Dir: $WORK_DIR"
echo "Raw Dir: $RAW_DIR"
echo "PONI: $PONI_FILE"

CMD="python3 $SKILLS_DIR/scripts/orchestrate_dials.py stage1 \
    --work-dir \"$WORK_DIR\" \
    --raw-dir \"$RAW_DIR\" \
    --poni-file \"$PONI_FILE\" \
    --dials-env \"$DIALS_ENV\" \
    --nproc ${NSLOTS:-24}"

if [ -n "$EDF_MASK" ]; then
    CMD="$CMD --edf-mask \"$EDF_MASK\""
fi
if [ -n "$UNIT_CELL" ]; then
    CMD="$CMD --unit-cell \"$UNIT_CELL\""
fi
if [ -n "$SPACE_GROUP" ]; then
    CMD="$CMD --space-group \"$SPACE_GROUP\""
fi

eval $CMD

echo "=== DIALS Stage 1 Completed Successfully ==="
date
