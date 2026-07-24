#!/usr/bin/env bash
# =============================================================================
#  AI 웹 해킹 특강 — 인프라 기동
#
#  사용법
#    ./start.sh hub       강사 서버(중앙 1대): 강좌 사이트 · CTFd · AI 도우미
#    ./start.sh victim    학생 PC(각자)     : DVWA · NeoBank · MediForum · AICompanion
#    ./start.sh           한 대에서 전부(혼자 테스트할 때)
#    ./start.sh extras    위 전부 + 보너스 표적(govportal/adminconsole/juiceshop)
#
#  교실에서는 hub 를 강사 PC 1대에, victim 을 학생 PC 마다 띄웁니다.
#  이유·자세한 배치는 ../docs/DEPLOYMENT.md 참고.
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")"

COMPOSE="docker compose"
$COMPOSE version >/dev/null 2>&1 || COMPOSE="docker-compose"

MODE="${1:-all}"
case "$MODE" in
  hub)    PROFILES=(--profile hub);                                    LABEL="강사 서버(hub)" ;;
  victim) PROFILES=(--profile victim);                                 LABEL="학생 PC 표적(victim)" ;;
  all)    PROFILES=(--profile hub --profile victim);                   LABEL="전부(hub + victim)" ;;
  extras) PROFILES=(--profile hub --profile victim --profile extras);  LABEL="전부 + 보너스" ;;
  *)      echo "사용법: ./start.sh [hub|victim|extras]  (인자 없으면 전부)"; exit 1 ;;
esac

echo "[*] ${LABEL} 를 기동합니다..."
$COMPOSE "${PROFILES[@]}" up -d --build

IP=$(hostname -I 2>/dev/null | awk '{print $1}')
IP="${IP:-<this-ip>}"
echo
echo "================ 접속 주소 (이 컴퓨터 IP = ${IP}) ================"
if [ "$MODE" != "victim" ]; then
  echo "  [hub]  강좌 사이트 : http://${IP}:8090   ← 커리큘럼·교과서·담벼락·회원가입"
  echo "  [hub]  CTFd        : http://${IP}:8000   ← mini-CTF 리더보드"
  echo "  [hub]  AI 도우미   : http://${IP}:8001   ← CTF 힌트 챗봇"
fi
if [ "$MODE" != "hub" ]; then
  echo "  [victim] DVWA        : http://${IP}:8088  (admin / password, Security=Low)"
  echo "  [victim] NeoBank     : http://${IP}:3001  (alice@example.com / alice123)"
  echo "  [victim] MediForum   : http://${IP}:3003  (사이트 내 회원가입)"
  echo "  [victim] AICompanion : http://${IP}:3005  (alice / alice123, 기본 mock 모드)"
fi
if [ "$MODE" = "extras" ]; then
  echo "  [extras] govportal :3002 · adminconsole :3004 · juiceshop :3000"
fi
echo "=================================================================="
echo
if [ "$MODE" != "victim" ]; then
  cat <<'NEXT'
다음 단계 (강사 서버, 최초 1회):
  cd ../ctf
  python3 setup_ctfd.py --ctfd http://127.0.0.1:8000 --admin admin --password '원하는비번' --email admin@ezweb.local
  python3 import_challenges.py --ctfd http://127.0.0.1:8000 --token <TOKEN> --victim <표적IP> --replace
  python3 verify_ctf.py --victim <표적IP> --ctfd http://127.0.0.1:8000 --token <TOKEN> --submit   # ★ 반드시 확인

  CTFd 계정 자동 연동을 쓰려면 infra/.env 에 아래를 넣고 course-site 를 재기동:
     CTFD_ADMIN_TOKEN=<TOKEN>
     CTFD_PUBLIC_URL=http://<hub-ip>:8000

NEXT
fi
echo "상태 확인:  cd infra && $COMPOSE ps        내리기: ./stop.sh"
