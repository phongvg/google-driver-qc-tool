#!/usr/bin/env bash
set -euo pipefail

IMAGE="asia-southeast1-docker.pkg.dev/tbrain-services/cloud-run-source-deploy/games-qc:latest"
REGION="asia-southeast1"
SA="863797867932-compute@developer.gserviceaccount.com"

BATCH_JOB_NAME="tbrain-games-qc-job"
WORKFLOW_NAME="tbrain-games-qc-workflow"
WORKFLOW_SOURCE="deploy/workflow.yaml"

usage() {
  cat <<'EOF'
Usage:
  ./deploy.sh build
  ./deploy.sh deploy
  ./deploy.sh deploy-job
  ./deploy.sh workflow-deploy
  ./deploy.sh workflow
  ./deploy.sh workflow-recheck-fail
  ./deploy.sh workflow-recheck-all
  ./deploy.sh run-batch <BATCH_NUMBERS>
  ./deploy.sh run-batch-recheck-fail <BATCH_NUMBERS>
  ./deploy.sh run-batch-recheck-all <BATCH_NUMBERS>
  ./deploy.sh full

Commands:
  build                        Build image mới
  deploy                       Deploy batch job
  deploy-job                   Deploy chỉ batch job
  workflow-deploy              Deploy lại workflow
  workflow                     Chạy workflow (chỉ fill duration cho row PASS đang trống duration)
  workflow-recheck-fail        Chạy workflow, chỉ recheck row đang FAIL
  workflow-recheck-all         Chạy workflow, recheck tất cả kể cả PASS
  run-batch <BATCHES>          Chạy thủ công batch cụ thể (vd: 101 hoặc 101-110)
  run-batch-recheck-fail <BATCHES>  Recheck FAIL của batch cụ thể
  run-batch-recheck-all <BATCHES>   Recheck tất cả của batch cụ thể
  full                         Build + deploy-job + workflow-deploy + workflow
EOF
}

build_image() {
  echo "==> Build image"
  gcloud builds submit --tag "$IMAGE"
}

deploy_batch_job() {
  echo "==> Deploy batch job: $BATCH_JOB_NAME"
  gcloud run jobs deploy "$BATCH_JOB_NAME" \
    --image "$IMAGE" \
    --region "$REGION" \
    --service-account "$SA" \
    --memory 6Gi \
    --cpu 2 \
    --task-timeout 7200 \
    --command python \
    --args="-m,jobs.batch_job"
}

deploy_all() {
  deploy_batch_job
}

deploy_workflow() {
  echo "==> Deploy workflow: $WORKFLOW_NAME"
  gcloud workflows deploy "$WORKFLOW_NAME" \
    --source "$WORKFLOW_SOURCE" \
    --location "$REGION" \
    --service-account "$SA"
}

run_workflow() {
  echo "==> Run workflow (fill missing duration for PASS rows only)"
  gcloud workflows run "$WORKFLOW_NAME" \
    --location "$REGION" \
    --data='{"recheck_all": ""}'
}

run_workflow_recheck_fail() {
  echo "==> Run workflow (recheck FAIL only)"
  gcloud workflows run "$WORKFLOW_NAME" \
    --location "$REGION" \
    --data='{"recheck_all": "", "recheck_fail": "fail"}'
}

run_workflow_recheck_all() {
  echo "==> Run workflow (recheck ALL including PASS)"
  gcloud workflows run "$WORKFLOW_NAME" \
    --location "$REGION" \
    --data='{"recheck_all": "all", "recheck_fail": ""}'
}

run_batch() {
  local batches="${1:?Thiếu BATCH_NUMBERS, vd: 101 hoặc 101-110}"
  echo "==> Run batch $batches (fill missing duration for PASS rows only)"
  gcloud run jobs execute "$BATCH_JOB_NAME" \
    --region "$REGION" \
    --update-env-vars "BATCH_NUMBERS=${batches},RECHECK_ALL=,RECHECK_FAIL="
}

run_batch_recheck_fail() {
  local batches="${1:?Thiếu BATCH_NUMBERS, vd: 101 hoặc 101-110}"
  echo "==> Run batch $batches (recheck FAIL only)"
  gcloud run jobs execute "$BATCH_JOB_NAME" \
    --region "$REGION" \
    --update-env-vars "BATCH_NUMBERS=${batches},RECHECK_ALL=,RECHECK_FAIL=fail"
}

run_batch_recheck_all() {
  local batches="${1:?Thiếu BATCH_NUMBERS, vd: 101 hoặc 101-110}"
  echo "==> Run batch $batches (recheck ALL including PASS)"
  gcloud run jobs execute "$BATCH_JOB_NAME" \
    --region "$REGION" \
    --update-env-vars "BATCH_NUMBERS=${batches},RECHECK_ALL=all,RECHECK_FAIL="
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
    deploy-job)
      deploy_batch_job
      ;;
    workflow-deploy)
      deploy_workflow
      ;;
    workflow)
      run_workflow
      ;;
    workflow-recheck-fail)
      run_workflow_recheck_fail
      ;;
    workflow-recheck-all)
      run_workflow_recheck_all
      ;;
    run-batch)
      run_batch "${2:-}"
      ;;
    run-batch-recheck-fail)
      run_batch_recheck_fail "${2:-}"
      ;;
    run-batch-recheck-all)
      run_batch_recheck_all "${2:-}"
      ;;
    full)
      build_image
      deploy_batch_job
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
