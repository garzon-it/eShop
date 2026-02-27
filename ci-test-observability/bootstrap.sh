#!/usr/bin/env bash
# Detect the CI provider and export normalized CI_* env vars used by the
# OTel Collector config and the ciwrap Python scripts.
#
# On GitHub Actions, variables are written to $GITHUB_ENV so they persist
# across steps. In other environments, they are exported for the current shell
# (source this script instead of executing it).

set -euo pipefail

if [ "${GITHUB_ACTIONS:-}" = "true" ]; then
    CI_PROVIDER="github_actions"
    CI_PIPELINE_NAME="${GITHUB_WORKFLOW:-}"
    CI_JOB_NAME="${GITHUB_JOB:-}"
    CI_RUN_ID="${GITHUB_RUN_ID:-}"
    CI_RUN_ATTEMPT="${GITHUB_RUN_ATTEMPT:-1}"
    CI_COMMIT_SHA="${GITHUB_SHA:-}"
    CI_REF_NAME="${GITHUB_REF_NAME:-}"
    CI_REF_TYPE="${GITHUB_REF_TYPE:-}"
    CI_REPOSITORY="${GITHUB_REPOSITORY:-}"
    CI_RUNNER_ID="${RUNNER_NAME:-}"
    CI_WORKER_TYPE="${RUNNER_ENVIRONMENT:-}"
    CI_RUNNER_OS="${RUNNER_OS:-}"
    CI_RUNNER_ARCH="${RUNNER_ARCH:-}"
    CI_WORKSPACE="${GITHUB_WORKSPACE:-$(pwd)}"
    CI_PIPELINE_RUN_URL="${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}/actions/runs/${GITHUB_RUN_ID}"

else
    echo "WARNING: Unknown CI provider; CI_* vars will be empty." >&2
    CI_PROVIDER="unknown"
    CI_PIPELINE_NAME=""
    CI_JOB_NAME=""
    CI_RUN_ID=""
    CI_RUN_ATTEMPT="1"
    CI_COMMIT_SHA=""
    CI_REF_NAME=""
    CI_REF_TYPE=""
    CI_REPOSITORY=""
    CI_RUNNER_ID=""
    CI_WORKER_TYPE=""
    CI_RUNNER_OS=""
    CI_RUNNER_ARCH=""
    CI_WORKSPACE="$(pwd)"
    CI_PIPELINE_RUN_URL=""
fi

if [ "${GITHUB_ENV:-}" != "" ]; then
    # Persist vars across steps on GitHub Actions.
    cat >> "$GITHUB_ENV" <<EOF
CI_PROVIDER=$CI_PROVIDER
CI_PIPELINE_NAME=$CI_PIPELINE_NAME
CI_JOB_NAME=$CI_JOB_NAME
CI_RUN_ID=$CI_RUN_ID
CI_RUN_ATTEMPT=$CI_RUN_ATTEMPT
CI_COMMIT_SHA=$CI_COMMIT_SHA
CI_REF_NAME=$CI_REF_NAME
CI_REF_TYPE=$CI_REF_TYPE
CI_REPOSITORY=$CI_REPOSITORY
CI_RUNNER_ID=$CI_RUNNER_ID
CI_WORKER_TYPE=$CI_WORKER_TYPE
CI_RUNNER_OS=$CI_RUNNER_OS
CI_RUNNER_ARCH=$CI_RUNNER_ARCH
CI_WORKSPACE=$CI_WORKSPACE
CI_PIPELINE_RUN_URL=$CI_PIPELINE_RUN_URL
EOF
else
    export CI_PROVIDER CI_PIPELINE_NAME CI_JOB_NAME CI_RUN_ID CI_RUN_ATTEMPT \
           CI_COMMIT_SHA CI_REF_NAME CI_REF_TYPE CI_REPOSITORY CI_RUNNER_ID \
           CI_WORKER_TYPE CI_RUNNER_OS CI_RUNNER_ARCH CI_WORKSPACE CI_PIPELINE_RUN_URL
fi

echo "CI provider: $CI_PROVIDER (job=$CI_JOB_NAME, run=$CI_RUN_ID)"
