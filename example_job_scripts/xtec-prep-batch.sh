#!/bin/bash
#$ -S /bin/bash
#$ -N xtec_prep
#$ -cwd
#$ -j y
#$ -q all.q@lnx307*,all.q@lnx311*,all.q@lnx312*,all.q@lnx313*
#$ -l mem_free=200G
#$ -pe sge_pe 16
#$ -o qsub_xtec_prep.log

# ==============================================================================
# SGE Batch Wrapper: 4D NeXus Dataset Preparation for XTEC-GPU
#
# Use this script when executing data preparation non-interactively or from
# automated AI assistant sessions (where interactive qrsh sessions would stall
# on Kerberos authentication prompts).
#
# Submits to AVX2 compute nodes, loads candidate 3D volumes (NXRefine or Legacy),
# performs stub pre-validation and modal exposure filtering, and compiles 4D NXdata.
# ==============================================================================

echo "=== XTEC 4D Dataset Preparation (Stage 0) ==="
echo "Host: $(hostname) | Date: $(date)"
echo "User: ${USER} | Job ID: ${JOB_ID} | Slots: ${NSLOTS}"
echo "============================================="

SAMPLE_DIR="/nfs/chess/id4baux/2026-1/yi-4791-a/nxrefine/KV2Se2O/KVSO-1C"
OUTPUT_FILE="${SAMPLE_DIR}/xtec_data.nxs"
PREP_SCRIPT="${HOME}/.gemini/config/skills/xtec-gpu-analysis/scripts/generate_xtec_input.py"
PYTHON_BIN="/nfs/chess/sw/anaconda3_sgomezalvarado_nightly/bin/python"

echo "Sample Directory: ${SAMPLE_DIR}"
echo "Output File     : ${OUTPUT_FILE}"
echo "Python Binary   : ${PYTHON_BIN}"
echo "Prep Script     : ${PREP_SCRIPT}"
echo "---------------------------------------------"

${PYTHON_BIN} -u "${PREP_SCRIPT}" \
  --sample-dir "${SAMPLE_DIR}" \
  --output "${OUTPUT_FILE}"

EXIT_CODE=$?
echo "---------------------------------------------"
echo "Job finished at $(date) with exit code: ${EXIT_CODE}"
exit ${EXIT_CODE}
