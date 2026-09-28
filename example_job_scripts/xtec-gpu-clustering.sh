#!/bin/bash
#$ -S /bin/bash
#$ -N xtec_gpu_auto
#$ -cwd
#$ -j y
#$ -l cuda_free=1
#$ -o qsub_xtec.log

# ==============================================================================
# SGE Batch Wrapper: Autonomous End-to-End XTEC-GPU Workflow
#
# Target Hardware: lnx4428.classe.cornell.edu (NVIDIA Titan RTX, 24 GB VRAM)
# Environment:     /nfs/chess/sw/qm2_XTEC312/bin/xtec-gpu (Python 3.12, PyTorch CUDA)
#
# Pipeline Lifecycle:
#   1. Phase 1 & 2: Background thresholding + BIC sweep across k = 2 ... 14
#   2. Autonomous Model Selection: Evaluates k* = argmin(BIC) from bic_xtec_d.h5
#   3. Phase 3: Final GMM clustering using optimal k* with deterministic reordering
#
# All steps enforce --streamed-preprocess to safely process large synchrotron
# volumes (>24 GB) without exceeding physical GPU VRAM.
# ==============================================================================

echo "=== Autonomous XTEC-GPU Workflow Job ==="
echo "Running on host: $(hostname)"
echo "Date: $(date) | User: ${USER} | Job ID: ${JOB_ID}"
echo "CUDA_VISIBLE_DEVICES: ${CUDA_VISIBLE_DEVICES}"

DATA_FILE="/path/to/sample/xtec_data.nxs"
OUTPUT_DIR="/path/to/sample/xtec_results"
XTEC_BIN="/nfs/chess/sw/qm2_XTEC312/bin/xtec-gpu"
PYTHON_BIN="/nfs/chess/sw/qm2_XTEC312/bin/python"

mkdir -p "${OUTPUT_DIR}/bic_d"

# ------------------------------------------------------------------------------
# Step 1: BIC Sweep for Model Selection (k = 2 ... 14)
# ------------------------------------------------------------------------------
echo ">>> [Phase 1 & 2] Starting BIC Model Selection Sweep..."
${XTEC_BIN} bic-d "${DATA_FILE}" \
  -o "${OUTPUT_DIR}/bic_d" \
  --streamed-preprocess \
  --min-nc 2 \
  --max-nc 14

# ------------------------------------------------------------------------------
# Step 2: Autonomous k* Determination (Locate Global Minimum of the BIC Curve)
# ------------------------------------------------------------------------------
BEST_K=$(${PYTHON_BIN} -c "
import h5py, numpy as np
with h5py.File('${OUTPUT_DIR}/bic_d/bic_xtec_d.h5', 'r') as f:
    ks = f['n_clusters'][...].astype(int)
    bics = f['bic_scores'][...].astype(float)
best_k = int(ks[np.argmin(bics)])
print(best_k)
")

echo ">>> [Model Selection Complete] Optimal Cluster Count: k* = ${BEST_K}"

# ------------------------------------------------------------------------------
# Step 3: Final GMM Clustering with Optimal k*
# ------------------------------------------------------------------------------
FINAL_OUT="${OUTPUT_DIR}/xtec_d_k${BEST_K}"
mkdir -p "${FINAL_OUT}"

echo ">>> [Phase 3] Running Final GMM Clustering with k = ${BEST_K}..."
${XTEC_BIN} xtec-d "${DATA_FILE}" \
  -o "${FINAL_OUT}" \
  --streamed-preprocess \
  -n "${BEST_K}" \
  --rescale mean \
  --reorder-clusters

echo "=== Autonomous XTEC-GPU Workflow Completed at $(date) ==="
