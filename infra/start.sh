#!/usr/bin/env bash
# =============================================================================
#  희생자 인프라 한 방에 띄우기
#  사용법:   ./start.sh           (특강 기본 4종: dvwa neobank mediforum ctfd)
#            ./start.sh extras    (보너스까지 전부)
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")"

# CTFd 가 마운트할 빈 DB 파일이 없으면 만들어 둔다(첫 기동 시 CTFd 가 채움).
mkdir -p ctfd
[ -f ctfd/ctfd.db ] || : > ctfd/ctfd.db

COMPOSE="docker compose"
$COMPOSE version >/dev/null 2>&1 || COMPOSE="docker-compose"

if [ "${1:-}" = "extras" ]; then
  echo "[*] 기본 4종 + 보너스 사이트까지 모두 기동합니다..."
  $COMPOSE --profile extras up -d --build
else
  echo "[*] 특강 기본 4종(dvwa / neobank / mediforum / ctfd)을 기동합니다..."
  $COMPOSE up -d --build
fi

echo
IP=$(hostname -I 2>/dev/null | awk '{print $1}')
echo "================ 접속 주소 (희생자 IP = ${IP:-<victim-ip>}) ================"
echo "  강좌 사이트 : http://${IP:-<victim-ip>}:8090    ← 커리큘럼·교과서·다운로드"
echo "  DVWA        : http://${IP:-<victim-ip>}:8080    (admin / password, Security=Low)"
echo "  NeoBank     : http://${IP:-<victim-ip>}:3001    (alice@example.com / alice123)"
echo "  MediForum   : http://${IP:-<victim-ip>}:3003"
echo "  CTFd        : http://${IP:-<victim-ip>}:8000"
echo "  AI 도우미   : http://${IP:-<victim-ip>}:8001"
echo "==========================================================================="
echo "상태 확인:  docker compose ps"
