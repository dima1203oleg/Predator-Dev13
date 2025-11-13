# Rollout gating and auto-promotion

This document explains how the repository's Argo Rollouts gating works and how to enable automatic promotion from GitHub Actions.

## What was added
- `helm/predator-umbrella/charts/api/templates/rollout.yaml` — a Rollout manifest (Canary) with an `AnalysisTemplate` that queries Prometheus for `error-rate`.
- `.github/workflows/rollout-gating.yml` — a GitHub Action that can promote the Argo Rollout when configured.

## Enabling automatic promotion
1. Create a kubeconfig for the target cluster with permissions to `get` and `promote` rollouts in the namespace (default `predator-dev`).
2. Base64-encode the kubeconfig and add it to repository secrets as `KUBECONFIG_DATA`.
3. Add `ALLOW_AUTO_PROMOTE` secret with value `true` to enable automatic promotion from the workflow.

Example (locally):

```bash
# encode
base64 -w0 ~/.kube/config > kubeconfig.b64
# then copy contents to GitHub secret KUBECONFIG_DATA
```

## Security notes
- Do NOT store private signing keys as artifacts. The SBOM workflow has been updated to avoid uploading the `cosign` key.
- Grant the least privilege necessary to the kubeconfig used by the CI workflow.

## Troubleshooting
- If auto-promotion fails, run the workflow manually (`Actions -> Rollout gating & auto-promotion -> Run workflow`) and inspect logs.
- Ensure Prometheus is reachable by Argo and that the `AnalysisTemplate` query matches your metric names and labels.
