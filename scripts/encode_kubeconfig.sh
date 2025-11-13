#!/usr/bin/env bash
set -euo pipefail

# encode_kubeconfig.sh
# Usage: ./scripts/encode_kubeconfig.sh [path-to-kubeconfig] [-c]
# If -c is provided, the base64 output will be copied to the macOS clipboard (pbcopy).

KUBECONFIG_PATH="${1:-${KUBECONFIG:-$HOME/.kube/config}}"
COPY_TO_CLIPBOARD=false

if [ "${2:-}" = "-c" ] || [ "${1:-}" = "-c" ]; then
  COPY_TO_CLIPBOARD=true
fi

if [ ! -f "$KUBECONFIG_PATH" ]; then
  echo "Kubeconfig not found at $KUBECONFIG_PATH" >&2
  exit 2
fi

if command -v openssl >/dev/null 2>&1; then
  B64=$(openssl base64 -A -in "$KUBECONFIG_PATH")
else
  # macOS base64 doesn't support -w0; remove newlines with tr
  B64=$(base64 "$KUBECONFIG_PATH" | tr -d '\n')
fi

if [ "$COPY_TO_CLIPBOARD" = true ]; then
  if command -v pbcopy >/dev/null 2>&1; then
    printf "%s" "$B64" | pbcopy
    echo "Base64-encoded kubeconfig copied to clipboard (pbcopy)."
    echo "Paste into your secret value (KUBECONFIG_DATA)."
    exit 0
  else
    echo "pbcopy not available; printing to stdout instead."
  fi
fi

printf "%s" "$B64"
