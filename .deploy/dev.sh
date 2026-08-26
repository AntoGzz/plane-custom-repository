#!/usr/bin/env bash
# Plane local-dev helpers (ports from 8700)
# Usage: .deploy/dev.sh {up|down|logs|ps|frontend}
set -euo pipefail
cd "$(dirname "$0")/.."

export PATH="${HOME}/.local/bin:${PATH}"
if command -v mise >/dev/null 2>&1; then
  eval "$(mise activate bash)"
fi

# Docker Desktop on WSL2
if [ -S /mnt/wsl/docker-desktop-bind-mounts/Ubuntu-24.04/docker.sock ]; then
  export DOCKER_HOST="unix:///mnt/wsl/docker-desktop-bind-mounts/Ubuntu-24.04/docker.sock"
elif [ -S /var/run/docker.sock ]; then
  export DOCKER_HOST="unix:///var/run/docker.sock"
fi

COMPOSE=(docker compose -f docker-compose-local.yml)

case "${1:-up}" in
  up)
    "${COMPOSE[@]}" up -d --build
    ;;
  down)
    "${COMPOSE[@]}" down
    ;;
  logs)
    shift || true
    "${COMPOSE[@]}" logs -f --tail=100 "$@"
    ;;
  ps|status)
    "${COMPOSE[@]}" ps
    ;;
  frontend|dev)
    pnpm dev
    ;;
  *)
    echo "Uso: $0 {up|down|logs|ps|frontend}"
    echo "Puertos: web=8700 admin=8701 space=8702 live=8703 api=8704"
    exit 1
    ;;
esac
