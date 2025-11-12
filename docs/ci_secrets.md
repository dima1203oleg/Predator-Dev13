# CI secrets and safe handling

This document explains the minimal secrets the CI workflows expect and how to generate and add them safely to GitHub Secrets.

1) `COSIGN_PRIVATE_KEY` and `COSIGN_PASSWORD` (optional — only if you enable signing)

- Purpose: cosign signs container images or artifacts in CI. `COSIGN_PRIVATE_KEY` is the PEM/PKCS8 private key material used by cosign. `COSIGN_PASSWORD` is the passphrase used by the key (if any).
- How to generate locally (recommended on your machine, never commit private key):

```sh
# generate a new key-pair using cosign (installed locally):
cosign generate-key-pair
# This creates cosign.key (private) and cosign.pub (public). Protect cosign.key.

# Encrypt or copy private key as a single-line secret. Example to base64 (not required, but OK):
base64 -w0 cosign.key > cosign.key.b64   # Linux
openssl base64 -A -in cosign.key > cosign.key.b64  # macOS
```

- Upload `cosign.key.b64` content to the GitHub secret `COSIGN_PRIVATE_KEY` (or store raw PEM if you prefer). Put passphrase (if used) in `COSIGN_PASSWORD`.
- CI note: workflow should load the private key into a file at runtime and set permissions 600, then run cosign commands. Never print the private key in logs.

2) `KUBECONFIG_DATA` (required for rollout gating / promotion)

- Purpose: the base64-encoded kubeconfig used by GitHub Actions to access your cluster for promotion/rollout steps.
- How to create (macOS-safe):

```sh
# one-line base64 (macOS):
openssl base64 -A < ~/.kube/config > kubeconfig.b64
cat kubeconfig.b64
```

- Copy the single-line content and paste into the repository secret `KUBECONFIG_DATA` (or organization secret). Keep scope minimal (only the repo/workflow that needs it).

3) Additional secrets used by workflows

- `ALLOW_AUTO_PROMOTE` — set to `true` to permit automatic promotion in the rollout gating workflow (or leave unset to require manual approval).
- `DB_URL`, `OPENSEARCH_URL`, `QDRANT_URL`, `MINIO_URL` — used by smoke tests / scripts; consider using separate CI-only test credentials so production secrets aren't exposed.

Security best practices

- Never commit private keys to git. Use GitHub Secrets only.
- Limit secret scope (repo vs org) and rotate keys periodically.
- Use short-lived service accounts for `KUBECONFIG_DATA` where possible (least privilege). For example, create a Kubernetes service account with a namespace-scoped RoleBinding that only allows `argoproj.io` rollout promotion if needed.
