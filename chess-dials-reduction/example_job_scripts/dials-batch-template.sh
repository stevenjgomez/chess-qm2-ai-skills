#!/bin/bash
#$ -N dials_reduction
#$ -q 'all.q@lnx307*,all.q@lnx311*,all.q@lnx312*,all.q@lnx313*'
#$ -l mem_free=120G
#$ -pe sge_pe 32
#$ -j y
#$ -o dials_batch.log

set -e
export OMP_NUM_THREADS=32
export MKL_NUM_THREADS=32

DIALS_ENV="/nfs/chess/sw/dials_sgomezalvarado/dials_env.sh"
SKILLS_DIR="$HOME/.gemini/config/skills/chess-dials-reduction"

WORK_DIR="$1"
BRAVAIS_SETTING="$2"
CB_OP="${3:-a,b,c}"
COMPOSITION="${4:-K2Co2TeO6}"

if [ -z "$WORK_DIR" ] || [ -z "$BRAVAIS_SETTING" ]; then
    echo "Usage: qsub dials-batch-template.sh <work_dir> <bravais_setting> [cb_op] [composition]"
    exit 1
fi

echo "=== Launching DIALS Stage 2 Batch Reduction ==="
date
echo "Work Dir: $WORK_DIR"
echo "Bravais Setting: $BRAVAIS_SETTING"
echo "cb_op: $CB_OP"
echo "Composition: $COMPOSITION"

python3 $SKILLS_DIR/scripts/orchestrate_dials.py stage2 \
    --work-dir "$WORK_DIR" \
    --dials-env "$DIALS_ENV" \
    --bravais-setting "$BRAVAIS_SETTING" \
    --cb-op "$CB_OP" \
    --composition "$COMPOSITION" \
    --nproc 32 \
    --absorption-level high \
    --anomalous True

echo "=== DIALS Stage 2 Batch Reduction Completed Successfully ==="
date
