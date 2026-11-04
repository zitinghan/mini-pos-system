#!/usr/bin/env bash
# Run from a normal development-machine terminal, not a restricted agent sandbox.
# Prompts through sudo; never put a password in this file or its arguments.
set -euo pipefail
sudo -v
sudo apt-get update
sudo apt-get install -y ca-certificates curl fonts-noto-cjk python3-venv python3-pip docker.io docker-compose-v2
sudo systemctl enable --now docker
sudo docker version
sudo docker compose version
# Keep production-compatible Python and Node available without changing system Python.
sudo docker pull python:3.12-slim
sudo docker pull node:22-alpine
printf '%s\n' 'Development tools ready. See docs/validation.md for build and test commands.'
