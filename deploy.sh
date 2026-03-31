#!/usr/bin/env bash
set -euo pipefail

IMAGE="asia-southeast1-docker.pkg.dev/tbrain-services/cloud-run-source-deploy/games-qc:latest"
REGION="asia-southeast1"
SA="863797867932-compute@developer.gserviceaccount.com"

SERVICE_NAME="tbrain-games-qc"
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
  ./deploy.sh full

Commands:
  build                Build image mới
  deploy               Deploy service + batch job
  deploy-job           Deploy chỉ batch job
  workflow-deploy      Deploy lại workflow
  workflow             Chạy workflow (batch QC)
  workflow-recheck-fail  Chạy workflow, chỉ recheck các row đang FAIL
  full                 Build + deploy-job + workflow-deploy + workflow
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
    --memory 8Gi \
    --cpu 2 \
    --timeout 3600 \
    --concurrency 3 \
    --execution-environment gen2 \
    --max-instances 4 \
    --ingress all \
    --no-invoker-iam-check
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
  deploy_service
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
  echo "==> Run workflow"
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
