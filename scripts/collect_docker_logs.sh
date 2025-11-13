#!/usr/bin/env bash
set -euo pipefail

# collect_docker_logs.sh
# Collect diagnostics into logs/docker-diagnostics-<ts> and produce a tar.gz
# Keeps only the last $RETAIN archives (default 10)

RETAIN=${RETAIN:-10}
OUT_DIR="logs/docker-diagnostics-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT_DIR"

echo "Collecting Docker diagnostics into $OUT_DIR"

echo "== docker version ==" > "$OUT_DIR/docker-version.txt" 2>&1 || true
docker version 2>&1 | tee "$OUT_DIR/docker-version.txt"

echo "== docker info ==" > "$OUT_DIR/docker-info.txt" 2>&1 || true
docker info 2>&1 | tee "$OUT_DIR/docker-info.txt"

echo "== docker ps --all ==" > "$OUT_DIR/docker-ps.txt" 2>&1 || true
docker ps --all 2>&1 | tee "$OUT_DIR/docker-ps.txt"

COMPOSE_FILE=".devcontainer/compose.yml"
if [ -f "$COMPOSE_FILE" ]; then
  echo "== docker compose (core) logs ==" > "$OUT_DIR/compose-core-logs.txt" 2>&1 || true
  docker compose -f "$COMPOSE_FILE" --profile core logs --no-color 2>&1 | tee "$OUT_DIR/compose-core-logs.txt" || true
fi

echo "== DNS checks for registry-1.docker.io ==" > "$OUT_DIR/dns-registry.txt" 2>&1 || true
if command -v dig >/dev/null 2>&1; then
  dig registry-1.docker.io +short 2>&1 | tee -a "$OUT_DIR/dns-registry.txt"
fi
if command -v nslookup >/dev/null 2>&1; then
  nslookup registry-1.docker.io 2>&1 | tee -a "$OUT_DIR/dns-registry.txt"
fi

echo "== curl registry API (may 401 but should resolve) ==" > "$OUT_DIR/curl-registry.txt" 2>&1 || true
curl -sS -D - https://registry-1.docker.io/v2/ 2>&1 | tee "$OUT_DIR/curl-registry.txt" || true

echo "Collected files:"
ls -la "$OUT_DIR"

ARCHIVE="${OUT_DIR}.tar.gz"
echo "Creating archive: ${ARCHIVE}"
tar -czf "$ARCHIVE" -C "$(dirname "$OUT_DIR")" "$(basename "$OUT_DIR")"

echo "Pruning older archives, keeping last $RETAIN"
# collect archives newest first
mapfile -t ARCHIVES < <(ls -1t logs/docker-diagnostics-*.tar.gz 2>/dev/null || true)
if [ ${#ARCHIVES[@]} -gt $RETAIN ]; then
  for ((i=RETAIN; i<${#ARCHIVES[@]}; i++)); do
    old=${ARCHIVES[$i]}
    echo "Removing old archive: $old"
    rm -f "$old" || true
    # remove corresponding directory if present
    dir="${old%.tar.gz}"
    if [ -d "$dir" ]; then
      echo "Also removing directory: $dir"
      rm -rf "$dir" || true
    fi
  done
fi

echo "Done. Archive: ${ARCHIVE}"
#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="logs/docker-diagnostics-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT_DIR"

echo "Collecting Docker diagnostics into $OUT_DIR"

echo "== docker version ==" > "$OUT_DIR/docker-version.txt" 2>&1 || true
docker version 2>&1 | tee "$OUT_DIR/docker-version.txt"

echo "== docker info ==" > "$OUT_DIR/docker-info.txt" 2>&1 || true
docker info 2>&1 | tee "$OUT_DIR/docker-info.txt"

echo "== docker ps --all ==" > "$OUT_DIR/docker-ps.txt" 2>&1 || true
docker ps --all 2>&1 | tee "$OUT_DIR/docker-ps.txt"

COMPOSE_FILE=".devcontainer/compose.yml"
if [ -f "$COMPOSE_FILE" ]; then
  echo "== docker compose (core) logs ==" > "$OUT_DIR/compose-core-logs.txt" 2>&1 || true
  docker compose -f "$COMPOSE_FILE" --profile core logs --no-color 2>&1 | tee "$OUT_DIR/compose-core-logs.txt" || true
fi

echo "== DNS checks for registry-1.docker.io ==" > "$OUT_DIR/dns-registry.txt" 2>&1 || true
if command -v dig >/dev/null 2>&1; then
  dig registry-1.docker.io +short 2>&1 | tee -a "$OUT_DIR/dns-registry.txt"
fi
if command -v nslookup >/dev/null 2>&1; then
  nslookup registry-1.docker.io 2>&1 | tee -a "$OUT_DIR/dns-registry.txt"
fi

echo "== curl registry API (may 401 but should resolve) ==" > "$OUT_DIR/curl-registry.txt" 2>&1 || true
curl -sS -D - https://registry-1.docker.io/v2/ 2>&1 | tee "$OUT_DIR/curl-registry.txt" || true

echo "Collected files:"
ls -la "$OUT_DIR"

echo "Archive: ${OUT_DIR}.tar.gz"
tar -czf "${OUT_DIR}.tar.gz" -C "$(dirname "$OUT_DIR")" "$(basename "$OUT_DIR")"

echo "Done. Upload or attach ${OUT_DIR}.tar.gz when reporting an issue."
