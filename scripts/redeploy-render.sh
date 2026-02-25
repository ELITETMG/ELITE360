#!/usr/bin/env bash
set -euo pipefail

: "${RENDER_DEPLOY_HOOK_URL:?Set RENDER_DEPLOY_HOOK_URL first.}"

curl --fail --silent --show-error -X POST "$RENDER_DEPLOY_HOOK_URL"
echo "Render redeploy triggered."
