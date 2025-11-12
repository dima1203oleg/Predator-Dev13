# Example: GitHub Actions pattern to sign images with cosign (safe handling)

This example shows a conservative, audit-friendly pattern for using a private cosign key stored in a GitHub Secret. It decodes the secret at runtime into a temporary file with strict permissions, uses `cosign` to sign an image, and securely removes the key file afterwards.

Notes:
- Store your private key in a repository or organization secret named `COSIGN_PRIVATE_KEY` (base64-encoded) and the passphrase in `COSIGN_PASSWORD`.
- Prefer short-lived keys or OIDC-based signing where possible. This example is intended when you must use a private key.

Example workflow snippet:

```yaml
name: sign-image

on:
  workflow_dispatch:

jobs:
  sign:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Install cosign
        uses: sigstore/cosign-installer@v2

      - name: Restore cosign private key (from secret)
        env:
          COSIGN_PRIVATE_KEY_B64: ${{ secrets.COSIGN_PRIVATE_KEY }}
        run: |
          set -euo pipefail
          echo "Decoding cosign private key into temporary file"
          echo "$COSIGN_PRIVATE_KEY_B64" | base64 -d > cosign.key
          chmod 600 cosign.key

      - name: Sign container image with cosign
        env:
          COSIGN_PASSWORD: ${{ secrets.COSIGN_PASSWORD }}
        run: |
          set -euo pipefail
          IMAGE=ghcr.io/myorg/myrepo:latest
          echo "Signing $IMAGE"
          cosign sign --key cosign.key "$IMAGE"

      - name: Securely remove private key
        run: |
          set -euo pipefail
          if command -v shred >/dev/null 2>&1; then
            shred -u cosign.key || rm -f cosign.key
          else
            rm -f cosign.key
          fi

      - name: Verify signature (optional)
        run: |
          set -euo pipefail
          cosign verify --key cosign.pub ghcr.io/myorg/myrepo:latest || true

```

Security tips:
- Do not echo secrets or key contents in workflow logs.
- Use minimal scope for repository secrets. Consider creating a dedicated CI key with limited permissions.
- Prefer OIDC-based signing (cosign supports `--oidc-client-id` flows) when possible to avoid long-lived private keys.

If you want, I can also add a small GitHub Actions step to generate `COSIGN_PRIVATE_KEY` on a secure machine and show how to upload it to the repo secrets safely (CLI + GitHub UI steps).
