# Docker / registry Troubleshooting

This short checklist helps diagnose common failures when `docker compose` or `docker pull` fail with DNS/registry errors such as:

- "lookup registry-1.docker.io: no such host"
- "Cannot connect to the Docker daemon at unix:///var/run/docker.sock"

Follow these steps locally (non-destructive checks). Do not run commands that change system config unless you understand them.

1) Is the Docker daemon running?

```sh
# check Docker client and server
docker version
docker info
docker ps --all
```

If these show connection errors, start Docker Desktop (`open -a Docker`) or Colima (`colima start`).

2) DNS / network checks (if daemon runs but pulls fail)

```sh
# test DNS for Docker registry
dig registry-1.docker.io +short
nslookup registry-1.docker.io

# try curl to Docker registry API (may 401 but should resolve)
curl -v https://registry-1.docker.io/v2/
```

If DNS lookup fails, try switching networks (home vs corporate), disable VPN/proxy temporarily, or test with a public DNS such as 8.8.8.8.

3) Check host /etc/hosts and local DNS overrides

```sh
grep -n "registry-1.docker.io" /etc/hosts || true
```

Remove any incorrect entries there.

4) Corporate proxies / firewalls

Corporate networks sometimes block registry traffic. Check with your IT team. If you need to run behind a proxy, configure Docker's proxy settings (Docker Desktop -> Settings -> Resources -> Proxies) or set `HTTP_PROXY`/`HTTPS_PROXY` for the docker client.

5) Docker daemon DNS settings

If Docker uses an internal DNS and resolution is failing, configure Docker daemon to use a stable DNS (e.g. 8.8.8.8). For Docker Desktop this is in Settings -> Docker Engine (edit daemon.json) or use `colima start --dns 8.8.8.8` for Colima.

Example daemon.json snippet (Docker Desktop):

```json
{
  "dns": ["8.8.8.8", "1.1.1.1"]
}
```

Apply with Docker Desktop restart.

6) Temporary fallback: run SBOM generation on CI runner

If your machine cannot reach docker.io due to network restrictions, you can generate SBOMs and make image-signing steps run in your CI runner (GitHub Actions) where network access is allowed.

7) Collect logs and share

If you still have trouble, collect these outputs and share with the maintainer or IT:

```sh
docker version 2>&1 | tee docker-version.txt
docker info 2>&1 | tee docker-info.txt
dig registry-1.docker.io +short > dig-registry.txt
curl -v https://registry-1.docker.io/v2/ 2>&1 | tee curl-registry.txt
```
