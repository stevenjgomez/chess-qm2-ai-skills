#!/bin/bash
#$ -S /bin/bash
#$ -N xtec_gpu
#$ -cwd
#$ -j y
#$ -l cuda_free=1
#$ -o qsub_xtec.log

echo "=== XTEC-GPU Clustering Job ==="
echo "Running on host: $(hostname)"
echo "Date: $(date) | User: ${USER} | Job ID: ${JOB_ID}"
echo "CUDA_VISIBLE_DEVICES: ${CUDA_VISIBLE_DEVICES}"

/nfs/chess/sw/qm2_XTEC312/bin/xtec-gpu xtec-d \
  /path/to/sample/xtec_data.nxs \
  -o /path/to/sample/xtec_results/ \
  --min-k 2 \
  --max-k 14

echo "=== XTEC-GPU Job Completed at $(date) ==="
