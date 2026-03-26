#!/usr/bin/env bash
set -euo pipefail

IMAGE="asia-southeast1-docker.pkg.dev/tbrain-services/cloud-run-source-deploy/games-qc:latest"
REGION="asia-southeast1"
SA="863797867932-compute@developer.gserviceaccount.com"
BUCKET="tbrain-qc-cache"

SERVICE_NAME="tbrain-games-qc"
INDEX_JOB_NAME="tbrain-games-qc-index"
BATCH_JOB_NAME="tbrain-games-qc-job"
WORKFLOW_NAME="tbrain-games-qc-workflow"
WORKFLOW_SOURCE="deploy/workflow.yaml"

usage() {
  cat <<'EOF'
Usage:
  ./deploy.sh build
  ./deploy.sh deploy
  ./deploy.sh workflow-deploy
  ./deploy.sh full-scan
  ./deploy.sh incremental
  ./deploy.sh workflow
  ./deploy.sh workflow-skip-index
  ./deploy.sh start-day
  ./deploy.sh full

Commands:
  build            Build image mới
  deploy           Deploy service + index job + batch job
  workflow-deploy  Deploy lại workflow
  full-scan        Chạy index job với FULL_SCAN=1
  incremental      Chạy index job dạng incremental
  workflow         Chạy workflow kèm incremental index
  workflow-skip-index  Chạy workflow, bỏ bước index
  start-day        Full scan trước, rồi chạy batch workflow không index lại
  full             Build + deploy + workflow-deploy + workflow
EOF
}

build_image() {
  echo "==> Build image"
  gcloud builds submit --tag "$IMAGE"
}

deploy_service() {
  echo "==> Deploy service: $SERVICE_NAME"
  gcloud run deploy "$SERVICE_NAME" \
    --image "$IMAGE" \
    --region "$REGION" \
    --service-account "$SA" \
    --memory 4Gi \
    --cpu 2 \
    --timeout 3600 \
    --concurrency 3 \
    --execution-environment gen2 \
    --max-instances 4 \
    --ingress all \
    --no-invoker-iam-check \
    --set-env-vars "GCS_BUCKET=$BUCKET"
}

deploy_index_job() {
  echo "==> Deploy index job: $INDEX_JOB_NAME"
  gcloud run jobs deploy "$INDEX_JOB_NAME" \
    --image "$IMAGE" \
    --region "$REGION" \
    --service-account "$SA" \
    --memory 1Gi \
    --cpu 1 \
    --task-timeout 1800 \
    --command python \
    --args="-m,jobs.index_job" \
    --set-env-vars "GCS_BUCKET=$BUCKET"
}

deploy_batch_job() {
  echo "==> Deploy batch job: $BATCH_JOB_NAME"
  gcloud run jobs deploy "$BATCH_JOB_NAME" \
    --image "$IMAGE" \
    --region "$REGION" \
    --service-account "$SA" \
    --memory 4Gi \
    --cpu 2 \
    --task-timeout 7200 \
    --command python \
    --args="-m,jobs.batch_job" \
    --set-env-vars "GCS_BUCKET=$BUCKET"
}

deploy_all() {
  deploy_service
  deploy_index_job
  deploy_batch_job
}

deploy_workflow() {
  echo "==> Deploy workflow: $WORKFLOW_NAME"
  gcloud workflows deploy "$WORKFLOW_NAME" \
    --source "$WORKFLOW_SOURCE" \
    --location "$REGION" \
    --service-account "$SA"
}

run_full_scan() {
  echo "==> Run full scan"
  gcloud run jobs execute "$INDEX_JOB_NAME" \
    --region "$REGION" \
    --update-env-vars FULL_SCAN=1
}

run_full_scan_and_wait() {
  echo "==> Run full scan and wait"
  local execution_name
  execution_name="$(
    gcloud run jobs execute "$INDEX_JOB_NAME" \
      --region "$REGION" \
      --update-env-vars FULL_SCAN=1 \
      --format='value(metadata.name)'
  )"

  if [[ -z "${execution_name}" ]]; then
    echo "Failed to get execution name for full scan"
    exit 1
  fi

  echo "==> Waiting for index execution: ${execution_name}"
  while true; do
    local succeeded failed cancelled completion_time
    succeeded="$(
      gcloud run jobs executions describe "$execution_name" \
        --region "$REGION" \
        --format='value(status.succeededCount)'
    )"
    failed="$(
      gcloud run jobs executions describe "$execution_name" \
        --region "$REGION" \
        --format='value(status.failedCount)'
    )"
    cancelled="$(
      gcloud run jobs executions describe "$execution_name" \
        --region "$REGION" \
        --format='value(status.cancelledCount)'
    )"
    completion_time="$(
      gcloud run jobs executions describe "$execution_name" \
        --region "$REGION" \
        --format='value(status.completionTime)'
    )"

    if [[ -n "${completion_time}" ]]; then
      if [[ "${failed:-0}" != "0" || "${cancelled:-0}" != "0" || "${succeeded:-0}" == "0" ]]; then
        echo "Full scan failed: execution=${execution_name} succeeded=${succeeded:-0} failed=${failed:-0} cancelled=${cancelled:-0}"
        exit 1
      fi
      echo "==> Full scan completed: ${execution_name}"
      break
    fi

    sleep 15
  done
}

run_incremental() {
  echo "==> Run incremental index"
  gcloud run jobs execute "$INDEX_JOB_NAME" \
    --region "$REGION"
}

run_workflow() {
  echo "==> Run workflow"
  gcloud workflows run "$WORKFLOW_NAME" \
    --location "$REGION" \
    --data='{"recheck_all": ""}'
}

run_workflow_skip_index() {
  echo "==> Run workflow (skip index)"
  gcloud workflows run "$WORKFLOW_NAME" \
    --location "$REGION" \
    --data='{"recheck_all": "", "skip_index": true}'
}

main() {
  if [[ $# -lt 1 ]]; then
    usage
    exit 1
  fi

  case "$1" in
    build)
      build_image
      ;;
    deploy)
      deploy_all
      ;;
    workflow-deploy)
      deploy_workflow
      ;;
    full-scan)
      run_full_scan
      ;;
    incremental)
      run_incremental
      ;;
    workflow)
      run_workflow
      ;;
    workflow-skip-index)
      run_workflow_skip_index
      ;;
    start-day)
      run_full_scan_and_wait
      run_workflow_skip_index
      ;;
    full)
      build_image
      deploy_all
      deploy_workflow
      run_workflow
      ;;
    *)
      echo "Unknown command: $1"
      echo
      usage
      exit 1
      ;;
  esac
}

main "$@"
