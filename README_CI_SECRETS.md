# Required GitHub secrets for CI/CD pipeline

This repository's pipeline expects the following GitHub Secrets to be configured in the repository (Settings → Secrets → Actions):

- `GH_TOKEN` or `GH_PAT` — a personal access token with repo access used when checking out and pushing to the `predator-gitops` repository (if you don't rely on the default `GITHUB_TOKEN`). The workflow reads `GH_TOKEN`.
- Registry credentials (optional when using GHCR + `GITHUB_TOKEN`):
  - `REGISTRY` — registry host (default: `ghcr.io`)
  - `REGISTRY_USERNAME` — registry username (if required)
  - `REGISTRY_PASSWORD` — registry password (if required)
- `COSIGN_VERIFY_REQUIRED` (optional) — set to `true` to require cosign verification to block the pipeline when signatures are missing/invalid.

GitOps access:

- `GITOPS_REPO` (optional) — repository name for gitops (e.g. `org/predator-gitops`) if not hard-coded.
- `GH_TOKEN` — (see above) used to push changes into the gitops repo. Ensure the token has write access to that repo.

ArgoCD credentials (used by the post-bump sync/wait step):

- `ARGOCD_SERVER` — Argo CD server URL (e.g. `argocd.example.com`)
- `ARGOCD_TOKEN` — preferred (token-based) auth for Argo CD
- or `ARGOCD_USER` and `ARGOCD_PASS` — username/password alternative

Kubeconfig for smoke tests (optional):

- `KUBE_CONFIG_DATA` — base64-encoded kubeconfig file contents. The workflow decodes this into `~/.kube/config` when present.

Notes on formats and usage

- To create `KUBE_CONFIG_DATA` locally (macOS zsh):

```bash
cat ~/.kube/config | base64 -w0 | pbcopy
# Paste clipboard into GitHub secret `KUBE_CONFIG_DATA`
```

- `GH_TOKEN` should be a PAT with `repo` (and write) permissions for the target `predator-gitops` repo if that repo is in another org or needs elevated scopes.

- The workflow contains some graceful fallbacks; however, critical missing secrets (e.g. GH/GITHUB token) will fail the job early (fail-fast). ArgoCD sync and smoke tests are skipped if their credentials are not provided.

If you'd like, I can:

- add a stricter preflight step that enumerates and enforces all required secrets (I already added a basic validate step in the workflow), or
- make the `GITOPS_REPO` configurable via workflow inputs or repository variables instead of being hard-coded.
