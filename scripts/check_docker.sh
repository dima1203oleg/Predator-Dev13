#!/usr/bin/env bash
set -euo pipefail

echo "== check_docker.sh =="

if command -v docker >/dev/null 2>&1; then
  if docker info >/dev/null 2>&1; then
    echo "Docker daemon is reachable."
    docker info --format 'Server: {{.ServerVersion}}' || true
    exit 0
  fi
fi

echo "Docker daemon is NOT reachable."
echo "Common fixes:"
echo "  - If you use Docker Desktop: open -a Docker  # wait until it's running"
echo "  - If you use Colima: colima start"
echo "  - If you use nerdctl / moby: ensure socket at /var/run/docker.sock is available"
echo
echo "Run these checks for debugging:"
echo "  docker version || true"
echo "  docker ps --all || true"
exit 1
#!/usr/bin/env bash
set -euo pipefail

echo "== check_docker.sh =="

if command -v docker >/dev/null 2>&1; then
  if docker info >/dev/null 2>&1; then
    echo "Docker daemon is reachable."
    docker info --format 'Server: {{.ServerVersion}}' || true
    exit 0
  fi
fi

echo "Docker daemon is NOT reachable."
echo "Common fixes:"
echo "  - If you use Docker Desktop: open -a Docker  # wait until it's running"
echo "  - If you use Colima: colima start"
echo "  - If you use nerdctl / moby: ensure socket at /var/run/docker.sock is available"
echo
echo "Run these checks for debugging:"
echo "  docker version || true"
echo "  docker ps --all || true"
exit 1
