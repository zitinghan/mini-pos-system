#!/usr/bin/env bash
# Run from a normal terminal with Docker access; does not start the POS or mount production data.
set -euo pipefail
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"
if ! docker info >/dev/null 2>&1; then
  printf '%s\n' 'Docker daemon unavailable or permission denied.' 'From a normal host terminal run: sudo bash scripts/verify-in-docker.sh' >&2
  exit 1
fi
mkdir -p artifacts/checks
# pipefail makes build/test failures fail this script while preserving their logs.
docker compose config --quiet
docker build --target test -t keke-pos/backend-check ./backend 2>&1 | tee artifacts/checks/backend-build.log
docker run --rm --network none keke-pos/backend-check 2>&1 | tee artifacts/checks/backend-tests.log
docker build --target test -t keke-pos/frontend-check ./frontend 2>&1 | tee artifacts/checks/frontend-build.log
docker run --rm --network none keke-pos/frontend-check 2>&1 | tee artifacts/checks/frontend-tests.log
# Preserve resolved dependencies for review before committing a release lockfile.
docker run --rm --network none --entrypoint cat keke-pos/frontend-check /app/package-lock.json > artifacts/checks/package-lock.json
docker run --rm --network none keke-pos/backend-check python -m pip freeze > artifacts/checks/python-test-environment.txt
docker compose build 2>&1 | tee artifacts/checks/production-build.log
printf '%s\n' 'Backend tests, frontend unit tests, TypeScript/Vite and production images passed.' 'Browser acceptance and real-printer compatibility still require separate checks.'
