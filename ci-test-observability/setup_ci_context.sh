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

elif [ "${GITLAB_CI:-}" = "true" ]; then
    CI_PROVIDER="gitlab_ci"
    # CI_PIPELINE_NAME and CI_JOB_NAME are also GitLab predefined vars (pipeline name
    # from workflow:name, and job name). We read them here and fall back as needed.
    CI_PIPELINE_NAME="${CI_PIPELINE_NAME:-${CI_PROJECT_NAME:-}}"
    CI_JOB_NAME="${CI_JOB_NAME:-}"
    CI_RUN_ID="${CI_PIPELINE_ID:-}"
    # GitLab has no re-run attempt counter; each re-run creates a new pipeline.
    CI_RUN_ATTEMPT="1"
    # CI_COMMIT_SHA is also a GitLab predefined var — self-assignment with fallback.
    CI_COMMIT_SHA="${CI_COMMIT_SHA:-}"
    CI_REF_NAME="${CI_COMMIT_REF_NAME:-}"
    CI_REF_TYPE="${CI_COMMIT_TAG:+tag}"
    CI_REF_TYPE="${CI_REF_TYPE:-branch}"
    CI_REPOSITORY="${CI_PROJECT_PATH:-}"
    # Use the human-readable runner description as the runner identifier.
    CI_RUNNER_ID="${CI_RUNNER_DESCRIPTION:-}"
    # Derive worker type from disposable/shared environment flags.
    if [ "${CI_DISPOSABLE_ENVIRONMENT:-}" = "true" ]; then
        CI_WORKER_TYPE="cloud-hosted"
    elif [ "${CI_SHARED_ENVIRONMENT:-}" = "true" ]; then
        CI_WORKER_TYPE="shared"
    else
        CI_WORKER_TYPE="self-hosted"
    fi
    CI_RUNNER_OS=""
    CI_RUNNER_ARCH="${CI_RUNNER_EXECUTABLE_ARCH:-}"
    CI_WORKSPACE="${CI_PROJECT_DIR:-$(pwd)}"
    CI_PIPELINE_RUN_URL="${CI_PIPELINE_URL:-}"

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
