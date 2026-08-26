#!/usr/bin/env bash
# Build Plane self-host images from source
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose build --progress=plain
