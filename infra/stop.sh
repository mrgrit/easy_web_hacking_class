#!/usr/bin/env bash
# 희생자 인프라 전부 내리기 (데이터 볼륨은 보존). 완전 삭제는 ./stop.sh purge
set -euo pipefail
cd "$(dirname "$0")"
COMPOSE="docker compose"; $COMPOSE version >/dev/null 2>&1 || COMPOSE="docker-compose"
if [ "${1:-}" = "purge" ]; then
  echo "[*] 컨테이너 + 볼륨까지 완전 삭제합니다..."
  $COMPOSE --profile extras down -v
else
  echo "[*] 컨테이너를 내립니다(볼륨/데이터 보존)..."
  $COMPOSE --profile extras down
fi
