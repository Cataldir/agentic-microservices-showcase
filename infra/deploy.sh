#!/usr/bin/env bash
# Optional Google Cloud Terraform entry. This file is not run by local QA or CI.
set -euo pipefail
TASK_TERRAFORM_DIR="$(cd "$(dirname "$0")/../examples/gcp/terraform" && pwd)"
TASK_MODE="${1:-help}"
case "$TASK_MODE" in
  help)
    cat <<'EOF'
Google Cloud proposal: inspect examples/gcp/README-GCP.md and terraform inputs.
Modes: validate, plan, apply. Toolchain, ADC, project inputs and approval are
operator prerequisites. Default help performs no cloud operation.
EOF
    ;;
  validate)
    terraform -chdir="$TASK_TERRAFORM_DIR" init -backend=false
    terraform -chdir="$TASK_TERRAFORM_DIR" validate
    ;;
  plan)
    terraform -chdir="$TASK_TERRAFORM_DIR" init
    terraform -chdir="$TASK_TERRAFORM_DIR" plan
    ;;
  apply)
    terraform -chdir="$TASK_TERRAFORM_DIR" init
    terraform -chdir="$TASK_TERRAFORM_DIR" apply
    ;;
  *) echo 'Unknown mode. Use help, validate, plan or apply.' >&2; exit 2 ;;
esac
