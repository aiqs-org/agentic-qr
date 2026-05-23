#!/usr/bin/env bash
set -e
COMPOSE_FILE=/home/gram/projects/infisical/docker-compose.yml
LOG=/home/gram/projects/infisical/startup.log

echo "[$(date)] Pulling images..." | tee -a "$LOG"
docker compose -f "$COMPOSE_FILE" pull 2>&1 | tee -a "$LOG"

echo "[$(date)] Starting stack..." | tee -a "$LOG"
docker compose -f "$COMPOSE_FILE" up -d 2>&1 | tee -a "$LOG"

echo "[$(date)] Done. Containers:" | tee -a "$LOG"
docker compose -f "$COMPOSE_FILE" ps 2>&1 | tee -a "$LOG"
