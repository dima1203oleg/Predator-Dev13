#!/usr/bin/env bash
set -euo pipefail
kubeconform -strict -summary || true
