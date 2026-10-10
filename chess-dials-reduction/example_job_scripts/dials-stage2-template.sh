#!/bin/bash
#$ -N dials_stage2
#$ -q 'all.q@lnx307*,all.q@lnx311*,all.q@lnx312*,all.q@lnx313*'
#$ -l mem_free=120G
#$ -pe sge_pe 24
#$ -j y
#$ -o dials_stage2.log

set -e
export OMP_NUM_THREADS=${NSLOTS:-24}
export MKL_NUM_THREADS=${NSLOTS:-24}

DIALS_ENV="/nfs/chess/sw/dials_sgomezalvarado/dials_env.sh"
SKILLS_DIR="$HOME/.gemini/config/skills/chess-dials-reduction"

WORK_DIR="$1"
BRAVAIS_SETTING="$2"
CB_OP="${3:-a,b,c}"
COMPOSITION="${4:-K2Co2TeO6}"

if [ -z "$WORK_DIR" ] || [ -z "$BRAVAIS_SETTING" ]; then
    echo "Usage: qsub dials-stage2-template.sh <work_dir> <bravais_setting> [cb_op] [composition]"
    exit 1
fi

echo "=== Launching DIALS Stage 2 Batch Reduction on Compute Node: $(hostname) ==="
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
    --nproc ${NSLOTS:-24} \
    --fix-cell \
    --absorption-level high \
    --anomalous True

echo "=== DIALS Stage 2 Batch Reduction Completed Successfully ==="
date
