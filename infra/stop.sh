#!/usr/bin/env bash
# 인프라 내리기.
#   ./stop.sh          컨테이너만 내림 (데이터 볼륨 보존 — 회원·CTFd 점수 유지)
#   ./stop.sh purge    볼륨까지 완전 삭제 (계정·점수·표적 DB 전부 초기화)
set -euo pipefail
cd "$(dirname "$0")"
COMPOSE="docker compose"; $COMPOSE version >/dev/null 2>&1 || COMPOSE="docker-compose"
ALL=(--profile hub --profile victim --profile extras)
if [ "${1:-}" = "purge" ]; then
  echo "[*] 컨테이너 + 볼륨까지 완전 삭제합니다 (회원·CTF 점수도 사라집니다)..."
  $COMPOSE "${ALL[@]}" down -v
else
  echo "[*] 컨테이너를 내립니다(볼륨/데이터 보존)..."
  $COMPOSE "${ALL[@]}" down
fi
