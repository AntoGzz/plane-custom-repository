#!/usr/bin/env bash
# Plane self-host - operaciones
# Uso: ./start.sh | ./stop.sh | ./restart.sh | ./logs.sh [servicio] | ./status.sh | ./backup.sh

set -euo pipefail
cd "$(dirname "$0")/.."
export DOCKER_HOST="unix:///var/run/docker.sock"
COMPOSE=(docker compose)

case "${1:-start}" in
  start)
    "${COMPOSE[@]}" up -d
    ;;
  stop)
    "${COMPOSE[@]}" down
    ;;
  restart)
    "${COMPOSE[@]}" down
    "${COMPOSE[@]}" up -d
    ;;
  logs)
    if [ $# -gt 1 ]; then
      "${COMPOSE[@]}" logs -f --tail=100 "$2"
    else
      "${COMPOSE[@]}" logs -f --tail=100
    fi
    ;;
  status)
    "${COMPOSE[@]}" ps
    ;;
  backup)
    ts=$(date +%Y%m%d-%H%M%S)
    out=".deploy/backups/$ts"
    mkdir -p "$out"
    docker exec plane-db pg_dump -U "${POSTGRES_USER:-plane}" "${POSTGRES_DB:-plane}" -F c -f /tmp/plane.dump
    docker cp plane-db:/tmp/plane.dump "$out/plane.dump"
    docker cp plane-minio:/export "$out/uploads" 2>/dev/null || true
    cp .env "$out/root.env"
    cp apps/api/.env "$out/api.env"
    echo "Backup completado en .deploy/backups/$ts"
    ;;
  *)
    echo "Uso: $0 {start|stop|restart|logs [servicio]|status|backup}"
    exit 1
    ;;
esac
