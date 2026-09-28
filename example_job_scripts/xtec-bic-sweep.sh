#!/bin/bash
#$ -S /bin/bash
#$ -N xtec_bic_sweep
#$ -cwd
#$ -j y
#$ -l cuda_free=1
#$ -o qsub_xtec_bic.log

# ==============================================================================
# SGE Batch Wrapper: Standalone BIC Model Selection Sweep for XTEC-GPU
#
# Target Hardware: lnx4428.classe.cornell.edu (NVIDIA Titan RTX, 24 GB VRAM)
# Environment:     /nfs/chess/sw/qm2_XTEC312/bin/xtec-gpu (Python 3.12, PyTorch CUDA)
#
# Use this script when executing ONLY the model selection BIC sweep across
# k = 2 ... 14 without immediately proceeding to final clustering.
# ==============================================================================

echo "=== XTEC-GPU BIC Model Selection Sweep Job ==="
echo "Running on host: $(hostname)"
echo "Date: $(date) | User: ${USER} | Job ID: ${JOB_ID}"
echo "CUDA_VISIBLE_DEVICES: ${CUDA_VISIBLE_DEVICES}"

DATA_FILE="/path/to/sample/xtec_data.nxs"
OUTPUT_DIR="/path/to/sample/xtec_results/bic_d"
XTEC_BIN="/nfs/chess/sw/qm2_XTEC312/bin/xtec-gpu"

mkdir -p "${OUTPUT_DIR}"

# Run BIC sweep for Mode d (direct voxel GMM) with streamed preprocessing
${XTEC_BIN} bic-d "${DATA_FILE}" \
  -o "${OUTPUT_DIR}" \
  --streamed-preprocess \
  --min-nc 2 \
  --max-nc 14

echo "=== BIC Sweep Completed at $(date) ==="
