#!/usr/bin/env bash
set -euo pipefail

echo "== collect_and_upload_logs.sh =="
echo "Collect docker diagnostics and optionally upload as a private gist + create an issue referencing it."

if ! command -v bash >/dev/null 2>&1; then
  echo "bash not found" >&2
  exit 2
fi

SCRIPTDIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPTDIR/.."

echo "Running local collector..."
bash ./scripts/collect_docker_logs.sh

# find newest diagnostics dir (not the tar.gz)
LATEST_DIR=$(ls -td logs/docker-diagnostics-* 2>/dev/null | head -n1 || true)
if [ -z "$LATEST_DIR" ]; then
  echo "No diagnostics directory found in logs/" >&2
  exit 1
fi

echo "Found diagnostics dir: $LATEST_DIR"

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI not found. To upload diagnostics as a gist, install GitHub CLI and authenticate (gh auth login)." >&2
  echo "Local diagnostic archive is at: ${LATEST_DIR}.tar.gz" >&2
  exit 0
fi

echo "Checking gh authentication..."
if ! gh auth status >/dev/null 2>&1; then
  echo "gh not authenticated. Run: gh auth login" >&2
  echo "Local diagnostic archive is at: ${LATEST_DIR}.tar.gz" >&2
  exit 0
fi

GIST_FILES=()
for f in "$LATEST_DIR"/*; do
  # include only text files (skip binary tar.gz)
  if file --brief --mime-type "$f" | grep -qE '^text/'; then
    GIST_FILES+=("$f")
  fi
done

if [ ${#GIST_FILES[@]} -eq 0 ]; then
  echo "No text diagnostics files to upload as gist. Local archive: ${LATEST_DIR}.tar.gz" >&2
  exit 0
fi

echo "Creating private gist with ${#GIST_FILES[@]} files..."
GIST_CREATE_CMD=(gh gist create --private)
for gf in "${GIST_FILES[@]}"; do
  GIST_CREATE_CMD+=("$gf")
done

GIST_URL=$("${GIST_CREATE_CMD[@]}" --debug 2>&1 | awk '/https:\/\// { print $NF }' | tail -n1 || true)

if [ -z "$GIST_URL" ]; then
  # fallback: try a simpler invocation and capture output
  GIST_URL=$(gh gist create --private "${GIST_FILES[@]}" --description "Docker diagnostics from $(hostname)" 2>&1 | awk '/https:\/\// { print $NF }' | tail -n1 || true)
fi

if [ -z "$GIST_URL" ]; then
  echo "Failed to create gist via gh. Local archive: ${LATEST_DIR}.tar.gz" >&2
  exit 1
fi

echo "Created gist: $GIST_URL"

ISSUE_TITLE="Docker diagnostics from $(hostname)"
ISSUE_BODY="Diagnostics collected at $(date -u). Gist: ${GIST_URL}\n\nPlease attach this link to a support ticket or share it with the maintainer."

echo "Creating GitHub issue in current repo..."
ISSUE_URL=$(gh issue create --title "$ISSUE_TITLE" --body "$ISSUE_BODY" --assignee @me --label diagnostics --json url -q .url 2>/dev/null || true)

if [ -n "$ISSUE_URL" ]; then
  echo "Created issue: $ISSUE_URL"
else
  echo "Issue creation skipped or failed. Gist: $GIST_URL";
fi

echo "Done."
