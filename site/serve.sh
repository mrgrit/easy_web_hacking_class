#!/usr/bin/env bash
# 강좌 웹사이트 로컬 실행(도커 없이). 레포 구조에서 교과서·다운로드를 자동으로 찾는다.
#   pip install flask markdown
#   ./serve.sh           → http://localhost:8090
set -euo pipefail
cd "$(dirname "$0")"
export PORT="${PORT:-8090}"
python3 app.py
