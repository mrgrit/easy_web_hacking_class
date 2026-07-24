#!/usr/bin/env bash
# =============================================================================
#  🚀 AI 웹 해킹 특강 — 한 방(bootstrap) 설치 & 기동 스크립트
# =============================================================================
#  "리눅스만 설치된 맨바닥" 에서 이 한 줄이면 끝:
#
#        ./setup.sh              # 한 대에 전부 (hub + victim)
#        ./setup.sh hub          # 강사 서버만: 강좌 사이트 · CTFd · AI 도우미
#        ./setup.sh victim       # 학생 PC만: DVWA · NeoBank · MediForum · AICompanion
#
#  교실에서는 강사 PC 에 hub, 학생 PC 마다 victim 을 씁니다 (docs/DEPLOYMENT.md 참고).
#
#  하는 일 (순서대로):
#    1) 패키지 매니저 감지 (apt / dnf / pacman)
#    2) 기본 도구 설치        : curl, git, python3, venv, pip
#    3) Docker Engine + compose 설치 (없으면) + 서비스 기동 + 그룹 등록
#    4) CTFd 자동화용 파이썬 패키지(venv) : requests, pyyaml
#    5) 희생자 서버 전부 빌드 & 기동      : docker compose up -d --build
#    6) CTFd 가 뜰 때까지 대기 → 관리자 자동 생성 → 6문제 자동 등록
#    7) DVWA DB 자동 생성 + Security=Low (best-effort)
#    8) 접속 주소 / 계정 안내 출력
#
#  옵션:
#    ./setup.sh extras          # 보너스 사이트(govportal/juiceshop 등)까지 기동
#    VICTIM_IP=192.168.0.50 ./setup.sh   # 다른 PC에서 접속할 희생자 IP 지정
#    CTFD_PASSWORD='내비번' ./setup.sh    # CTFd 관리자 비번 지정(기본 ezweb-admin-2026)
#    SKIP_CTFD=1 ./setup.sh     # CTFd 자동 셋업/문제등록 건너뛰기
#    SKIP_DVWA=1 ./setup.sh     # DVWA 자동 초기화 건너뛰기
# =============================================================================
set -euo pipefail

# ---- 0. 공통 준비 -----------------------------------------------------------
REPO="$(cd "$(dirname "$0")" && pwd)"
MODE="${1:-all}"                             # all | hub | victim | extras
case "$MODE" in all|hub|victim|extras) ;; *) echo "사용법: ./setup.sh [hub|victim|extras]"; exit 1;; esac
CTFD_ADMIN="${CTFD_ADMIN:-admin}"
CTFD_PASSWORD="${CTFD_PASSWORD:-ezweb-admin-2026}"
CTFD_EMAIL="${CTFD_EMAIL:-admin@ezweb.local}"

# 색상/로그 헬퍼
if [ -t 1 ]; then B=$'\033[1m'; G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[31m'; C=$'\033[36m'; N=$'\033[0m'; else B=''; G=''; Y=''; R=''; C=''; N=''; fi
step(){ echo; echo "${B}${C}▶ $*${N}"; }
ok(){   echo "  ${G}✓${N} $*"; }
warn(){ echo "  ${Y}!${N} $*"; }
die(){  echo "${R}✗ $*${N}" >&2; exit 1; }

# root 여부에 따라 sudo 준비
if [ "$(id -u)" -eq 0 ]; then SUDO=""; else
  command -v sudo >/dev/null 2>&1 || die "root 가 아니고 sudo 도 없습니다. root 로 실행하거나 sudo 를 설치하세요."
  SUDO="sudo"
fi

# 패키지 매니저 감지
if   command -v apt-get >/dev/null 2>&1; then PKG=apt
elif command -v dnf     >/dev/null 2>&1; then PKG=dnf
elif command -v yum     >/dev/null 2>&1; then PKG=yum
elif command -v pacman  >/dev/null 2>&1; then PKG=pacman
else PKG=unknown; fi

pkg_install(){ # 인자로 받은 패키지들을 배포판에 맞게 설치
  case "$PKG" in
    apt)    $SUDO apt-get install -y "$@" ;;
    dnf)    $SUDO dnf install -y "$@" ;;
    yum)    $SUDO yum install -y "$@" ;;
    pacman) $SUDO pacman -S --noconfirm --needed "$@" ;;
    *)      warn "알 수 없는 배포판 — 수동 설치 필요: $*" ; return 1 ;;
  esac
}

echo "${B}=======================================================${N}"
echo "${B}  AI 웹 해킹 특강 — 한 방 설치 & 기동${N}"
echo "${B}=======================================================${N}"
echo "  레포     : $REPO"
echo "  배포판   : $(. /etc/os-release 2>/dev/null && echo "${PRETTY_NAME:-unknown}") (pkg=$PKG)"
echo "  실행권한 : $( [ -n "$SUDO" ] && echo '일반 사용자(sudo 사용)' || echo 'root' )"

# ---- 1. 기본 도구 설치 ------------------------------------------------------
step "1/8  기본 도구 설치 (curl, git, python3, venv, pip)"
if [ "$PKG" = apt ]; then
  $SUDO apt-get update -y
  pkg_install ca-certificates curl git python3 python3-venv python3-pip
elif [ "$PKG" = pacman ]; then
  pkg_install ca-certificates curl git python python-pip
else
  pkg_install ca-certificates curl git python3 python3-pip || true
fi
ok "기본 도구 준비 완료"

# ---- 2. Docker Engine + compose 설치 ---------------------------------------
step "2/8  Docker 설치 확인/설치"
need_docker_install=1
if command -v docker >/dev/null 2>&1; then
  need_docker_install=0
  ok "docker 이미 설치됨 ($(docker --version 2>/dev/null | head -1))"
fi

if [ "$need_docker_install" -eq 1 ]; then
  warn "docker 가 없습니다. 설치를 시작합니다..."
  if curl -fsSL https://get.docker.com -o /tmp/ezweb-get-docker.sh 2>/dev/null; then
    # Docker 공식 편의 스크립트 — 대부분의 배포판에서 최신 engine + compose plugin 설치
    $SUDO sh /tmp/ezweb-get-docker.sh || warn "공식 스크립트 실패 — 배포판 패키지로 재시도"
    rm -f /tmp/ezweb-get-docker.sh
  fi
  if ! command -v docker >/dev/null 2>&1; then
    # 폴백: 배포판 기본 패키지
    case "$PKG" in
      apt)    pkg_install docker.io docker-compose-v2 || pkg_install docker.io ;;
      dnf|yum) pkg_install docker docker-compose-plugin || pkg_install docker ;;
      pacman) pkg_install docker docker-compose ;;
      *) die "docker 자동 설치 실패 — 수동으로 Docker + compose 를 설치한 뒤 다시 실행하세요." ;;
    esac
  fi
  command -v docker >/dev/null 2>&1 || die "docker 설치에 실패했습니다."
  ok "docker 설치 완료"
fi

# docker 데몬(systemd) 기동/활성화
if command -v systemctl >/dev/null 2>&1; then
  $SUDO systemctl enable --now docker 2>/dev/null && ok "docker 서비스 활성화" || warn "systemctl 로 docker 기동 실패(이미 떠 있으면 무시)"
fi

# 현재 사용자를 docker 그룹에 등록 (다음 로그인부터 sudo 없이 사용 가능)
if [ -n "$SUDO" ] && ! id -nG "$USER" | tr ' ' '\n' | grep -qx docker; then
  $SUDO usermod -aG docker "$USER" && ok "사용자 '$USER' 를 docker 그룹에 추가(재로그인 후 sudo 없이 docker 사용)"
fi

# 이번 실행에서 docker 를 어떻게 부를지 결정 (그룹이 아직 현재 셸에 적용 안 됐을 수 있음)
if docker info >/dev/null 2>&1; then
  DK="docker"
elif [ -n "$SUDO" ] && $SUDO docker info >/dev/null 2>&1; then
  DK="$SUDO docker"
  warn "현재 셸엔 docker 그룹이 아직 적용 안 됨 → 이번엔 sudo 로 docker 실행"
else
  die "docker 데몬에 접속할 수 없습니다. 'sudo systemctl start docker' 후 다시 실행하세요."
fi

# compose 명령 결정 (v2 플러그인 우선, 없으면 docker-compose v1)
if $DK compose version >/dev/null 2>&1; then
  COMPOSE="$DK compose"
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE="${SUDO:+$SUDO }docker-compose"
else
  die "docker compose 를 찾을 수 없습니다. compose plugin 을 설치하세요."
fi
ok "compose 명령: $COMPOSE"

# ---- 3. CTFd 자동화용 파이썬 환경(venv) ------------------------------------
step "3/8  CTFd 자동화용 파이썬 venv 준비 (requests, pyyaml)"
VENV="$REPO/infra/.ctf-venv"
PY="$VENV/bin/python"
if [ ! -x "$PY" ]; then
  python3 -m venv "$VENV" || die "python venv 생성 실패 (python3-venv 설치 확인)"
fi
"$PY" -m pip install --quiet --upgrade pip >/dev/null 2>&1 || true
"$PY" -m pip install --quiet requests pyyaml || die "requests/pyyaml 설치 실패"
ok "venv 준비 완료: $VENV"

# ---- 4. 희생자 서버 전부 빌드 & 기동 ---------------------------------------
step "4/8  서버 빌드 & 기동 (mode=$MODE)"
cd "$REPO/infra"
case "$MODE" in
  hub)    PROFILES=(--profile hub) ;;
  victim) PROFILES=(--profile victim) ;;
  all)    PROFILES=(--profile hub --profile victim) ;;
  extras) PROFILES=(--profile hub --profile victim --profile extras) ;;
esac
$COMPOSE "${PROFILES[@]}" up -d --build
ok "컨테이너 기동 완료"

# 희생자 IP 결정 (다른 PC에서 접속할 주소). 지정 없으면 첫 번째 로컬 IP
VICTIM_IP="${VICTIM_IP:-$(hostname -I 2>/dev/null | awk '{print $1}')}"
VICTIM_IP="${VICTIM_IP:-localhost}"

# 서비스 하나가 200 응답할 때까지 대기하는 헬퍼
wait_http(){ # $1=url  $2=최대초  $3=이름
  local url="$1" max="${2:-120}" name="${3:-service}" i=0 code
  printf "  %s 준비 대기" "$name"
  while [ "$i" -lt "$max" ]; do
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 "$url" 2>/dev/null || echo 000)
    case "$code" in 200|301|302) echo " ${G}(ready)${N}"; return 0;; esac
    printf "."; i=$((i+1)); sleep 1
  done
  echo " ${Y}(timeout)${N}"; return 1
}

# ---- 5·6. CTFd 자동 셋업 + 문제 등록 ---------------------------------------
if [ "${SKIP_CTFD:-0}" != "1" ] && [ "$MODE" != "victim" ]; then
  step "5/8  CTFd 자동 셋업 (관리자 생성 + 토큰)"
  if wait_http "http://127.0.0.1:8000/setup" 150 "CTFd(:8000)"; then
    cd "$REPO/ctf"
    set +e
    SETUP_OUT="$("$PY" setup_ctfd.py --ctfd http://127.0.0.1:8000 \
                  --admin "$CTFD_ADMIN" --password "$CTFD_PASSWORD" --email "$CTFD_EMAIL" 2>&1)"
    set -e
    echo "$SETUP_OUT" | sed 's/^/     /'
    TOKEN="$(printf '%s\n' "$SETUP_OUT" | sed -n 's/^TOKEN=//p' | tail -1)"

    if [ -n "$TOKEN" ]; then
      ok "관리자 준비 완료 ($CTFD_ADMIN / $CTFD_PASSWORD)"
      step "6/8  CTFd 문제 등록 (challenges.yml → 6문제)"
      # 이미 문제가 등록돼 있으면(재실행) 중복 방지로 건너뜀
      # (문제 0개면 grep 이 exit 1 → pipefail+set -e 로 죽으므로 반드시 '|| true')
      # (CTFd 토큰 인증은 'Content-Type: application/json' 이 없으면 /login 으로 302 → 반드시 헤더 지정)
      EXISTING="$(curl -s -H "Authorization: Token $TOKEN" -H "Content-Type: application/json" \
                   "http://127.0.0.1:8000/api/v1/challenges" 2>/dev/null | grep -o '"id":' | wc -l | tr -d ' ' || true)"
      EXISTING="${EXISTING:-0}"
      if [ "$EXISTING" -gt 0 ] 2>/dev/null; then
        warn "이미 문제 ${EXISTING}개가 등록돼 있어 import 를 건너뜁니다."
      else
        "$PY" import_challenges.py --ctfd http://127.0.0.1:8000 \
              --token "$TOKEN" --victim "$VICTIM_IP" | sed 's/^/     /' \
          && ok "문제 등록 완료" || warn "문제 등록 중 일부 실패 — 위 로그 확인"
      fi
    else
      warn "CTFd 토큰 발급 실패 — 나중에 수동 셋업: ctf/README.md 참고"
    fi
  else
    warn "CTFd 가 제때 안 떴습니다. 잠시 후 'docker compose logs ctfd' 확인 후 ctf/README.md 로 수동 셋업하세요."
  fi
else
  warn "SKIP_CTFD=1 — CTFd 자동 셋업 건너뜀"
fi

# ---- 7. DVWA 자동 초기화 (DB 생성 + Security=Low) ---------------------------
if [ "${SKIP_DVWA:-0}" != "1" ] && [ "$MODE" != "hub" ]; then
  step "7/8  DVWA 자동 초기화 (DB 생성 + 교재 페이로드 실측)"
  if wait_http "http://127.0.0.1:8088/login.php" 120 "DVWA(:8088)"; then
    if "$PY" - <<'PYDVWA'
import re, sys
try:
    import requests
except Exception:
    sys.exit(2)
base = "http://127.0.0.1:8088"
s = requests.Session()

def tok(html):
    m = re.search(r"name=['\"]user_token['\"]\s+value=['\"]([0-9a-fA-F]+)['\"]", html)
    return m.group(1) if m else None

def login():
    r = s.get(base + "/login.php", timeout=10)
    return s.post(base + "/login.php",
                  data={"username": "admin", "password": "password",
                        "Login": "Login", "user_token": tok(r.text)}, timeout=10)

try:
    login()
    # ① DB 생성/초기화
    r = s.get(base + "/setup.php", timeout=10)
    s.post(base + "/setup.php",
           data={"create_db": "Create / Reset Database", "user_token": tok(r.text)}, timeout=120)
    # ② ⚠️ DB 를 다시 만들면 users 테이블이 초기화되며 세션이 풀린다. 반드시 재로그인.
    login()
    # ③ 실습이 실제로 통하는지 교재 페이로드로 확인 (조용한 실패 방지)
    #    보안등급 Low 는 compose 의 DEFAULT_SECURITY_LEVEL=low 로 브라우저마다 자동 적용된다.
    r = s.get(base + "/vulnerabilities/sqli/",
              params={"id": "1' UNION SELECT user, password FROM users #", "Submit": "Submit"}, timeout=15)
    if "5f4dcc3b5aa765d61d8327deb882cf99" not in r.text:
        print("     DVWA: DB 는 만들었지만 교재 페이로드가 통하지 않습니다 "
              "(security 쿠키 =", s.cookies.get("security"), ")")
        sys.exit(1)
    print("     DVWA: DB 생성 완료 + SQLi 실측 통과 (admin/password, Security=Low 자동)")
except Exception as e:
    print("     DVWA 자동설정 실패(브라우저에서 admin/password 로그인 후 "
          "Create/Reset Database 1회 클릭):", e)
    sys.exit(1)
PYDVWA
    then ok "DVWA 초기화 완료"
    else warn "DVWA 자동 초기화 실패 — 브라우저에서 admin/password 로그인 후 'Create/Reset Database' 1회 클릭하세요."
    fi
  else
    warn "DVWA 가 제때 안 떴습니다. 잠시 후 http://$VICTIM_IP:8088 에서 admin/password 로그인 → Create/Reset Database."
  fi
else
  warn "SKIP_DVWA=1 — DVWA 자동 초기화 건너뜀"
fi

# ---- 8. 안내 ----------------------------------------------------------------
step "8/8  완료 — 접속 주소"
cat <<EOF
${B}================ 접속 주소 (이 컴퓨터 IP = ${VICTIM_IP}) ================${N}
$( [ "$MODE" != victim ] && printf '  %s[hub] 강좌 사이트%s : http://%s:8090    ← 교과서·실습·담벼락·회원가입\n' "$C" "$N" "$VICTIM_IP" )
$( [ "$MODE" != victim ] && printf '  %s[hub] CTFd%s        : http://%s:8000    (%s / %s)\n' "$C" "$N" "$VICTIM_IP" "$CTFD_ADMIN" "$CTFD_PASSWORD" )
$( [ "$MODE" != victim ] && printf '  %s[hub] AI 도우미%s   : http://%s:8001\n' "$C" "$N" "$VICTIM_IP" )
$( [ "$MODE" != hub ] && printf '  %s[victim] DVWA%s        : http://%s:8088    (admin / password, Security=Low)\n' "$C" "$N" "$VICTIM_IP" )
$( [ "$MODE" != hub ] && printf '  %s[victim] NeoBank%s     : http://%s:3001    (alice@example.com / alice123)\n' "$C" "$N" "$VICTIM_IP" )
$( [ "$MODE" != hub ] && printf '  %s[victim] MediForum%s   : http://%s:3003    (사이트 내 회원가입)\n' "$C" "$N" "$VICTIM_IP" )
$( [ "$MODE" != hub ] && printf '  %s[victim] AICompanion%s : http://%s:3005    (alice / alice123, mock 모드)\n' "$C" "$N" "$VICTIM_IP" )
$( [ "$MODE" = extras ] && printf '  %sgovportal%s   : http://%s:3002   %sjuiceshop%s: http://%s:3000\n' "$C" "$N" "$VICTIM_IP" "$C" "$N" "$VICTIM_IP" )
${B}=====================================================================${N}
$( [ "$MODE" != victim ] && printf '  ★ 수업 전 필수:  cd ctf && python3 verify_ctf.py --victim <표적IP> --ctfd http://127.0.0.1:8000 --token <TOKEN> --submit\n' )

  상태 확인 :  cd infra && $COMPOSE ps
  로그 보기 :  cd infra && $COMPOSE logs -f ctfd
  내리기    :  cd infra && ./stop.sh         (볼륨까지: ./stop.sh purge)
EOF

# docker 그룹이 이번 셸엔 아직 적용 안 됐다면 재로그인 안내
if [ -n "$SUDO" ] && ! id -nG "$USER" 2>/dev/null | tr ' ' '\n' | grep -qx docker; then
  echo
  warn "다음부터 sudo 없이 docker 를 쓰려면 재로그인 하거나: ${B}newgrp docker${N}"
fi
echo
ok "끝! 브라우저로 위 주소에 접속해 보세요."
