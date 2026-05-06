#!/bin/bash
# Usage: ./restart.sh strategy-core
SERVICE=${1:-strategy-core}
DIR=~/projects/$SERVICE

echo "=== Stopping $SERVICE ==="
docker ps -aq --filter name=$SERVICE | xargs -r docker rm -f
docker ps -aq --filter name=caveman-$SERVICE | xargs -r docker rm -f

echo "=== Starting $SERVICE ==="
cd $DIR && infisical run --env=dev -- docker-compose up --build -d

echo "=== Logs ==="
sleep 3
docker logs caveman-$SERVICE --tail=20
