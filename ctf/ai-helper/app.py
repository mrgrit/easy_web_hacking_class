"""
mini-CTF AI 도우미 — 학생이 막혔을 때 '방향'만 알려주는 힌트 챗봇.

설계(요청 출처: tw2 의 드래그-질문 AI 튜터 패턴):
  - 학생이 현재 문제 + 질문을 보내면, 시스템 프롬프트로 'flag 는 절대 알려주지 말고 방향만'
    이라고 강제한 뒤 LLM 에 물어 답을 돌려준다.
  - LLM 백엔드 우선순위:
      1) Anthropic API  (환경변수 ANTHROPIC_API_KEY 있으면)        — 모델 ANTHROPIC_MODEL(기본 claude-haiku-4-5)
      2) Ollama         (환경변수 OLLAMA_URL 있으면, 예: http://gpu:11434) — 모델 OLLAMA_MODEL(기본 llama3)
      3) 오프라인 폴백   (LLM 미설정 시) — 문제별 미리 준비한 단계 힌트를 규칙 기반으로 제공
  - 어떤 경우에도 응답에서 'flag{...}' 패턴은 가려서(레다크션) 내보낸다(안전망).

실행: PORT(기본 8001). docker-compose 의 ai-helper 서비스로 기동.
"""
from __future__ import annotations
import os, re, json
import urllib.request
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5").strip()
OLLAMA_URL = os.environ.get("OLLAMA_URL", "").strip().rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3").strip()

FLAG_RE = re.compile(r"flag\{[^}]*\}", re.IGNORECASE)

# 문제별 '방향' 힌트(절대 flag 미포함). 오프라인 폴백 + LLM 시스템 프롬프트 양쪽에 쓰인다.
CHALLENGES = {
    "1": {"name": "페이지 속 깃발 (Recon)",
          "dir": "화면에 안 보이는 정보는 '페이지 소스'에 있어. 게시판에서 [공지] 글을 연 다음 Ctrl+U "
                 "(소스 보기)를 누르고, 소스 창에서 Ctrl+F 로 'TODO' 나 '<!--' 를 찾아봐. "
                 "HTML 주석은 화면에 안 그려지지만 원본에는 그대로 남아 있어."},
    "2": {"name": "인증 없는 회원 API (PII)",
          "dir": "주소를 찍어서 맞히지 마. 상단 메뉴 '회원 찾기'로 가서 F12 → Network 탭을 켠 채로 검색을 "
                 "눌러 봐. 이 화면이 뒤에서 어떤 주소를 부르는지 그대로 보여. 그 응답에서 role 이 admin 인 "
                 "사람의 비밀 키(api_key) 칸을 확인해. /robots.txt 에도 그 주소가 적혀 있어."},
    "3": {"name": "남의 진료기록 (IDOR)",
          "dir": "상단 메뉴 '진료기록'에서 아무 기록이나 [상세 보기]를 눌러 봐. 주소창 끝의 숫자가 '몇 번 "
                 "기록'인지를 뜻해. 그 숫자를 1부터 5까지 바꿔 가며(또는 [다음 기록 ▶] 버튼으로) 열어 보고, "
                 "'처방 / 소견' 칸을 잘 읽어. 남의 기록이 막힘 없이 열리는 것 자체가 취약점이야."},
    "4": {"name": "관리자 쪽지 도청",
          "dir": "먼저 /robots.txt 를 열어 봐. '검색엔진 수집 금지' 목록이 사실은 '숨기고 싶은 주소' 목록이야. "
                 "거기 적힌 관리자 콘솔로 들어가면 로그인 없이 그냥 열려. 메뉴에서 '쪽지 감사'를 눌러 "
                 "본문(body) 칸을 훑어봐."},
    "5": {"name": "예측 가능한 세션",
          "dir": "회원가입·로그인한 뒤 F12 → Application(저장소) → Cookies 에서 MFSID 값을 봐. 값이 "
                 "sess-숫자 모양이면 그 숫자는 '몇 번째 손님'이라는 뜻이야. 계정을 하나 더 만들어 보면 "
                 "규칙이 확실해져. 관리자는 서비스 첫날 로그인했으니 훨씬 이른 번호를 쓰겠지? "
                 "쿠키 값을 고친 뒤 관리자 전용 금고 페이지를 F5 로 새로고침해."},
    "6": {"name": "저장형 XSS — 관리자 봇",
          "dir": "회원가입·로그인 후 새 글을 쓰는데, 본문에 <script>alert('xss')</script> 를 그대로 적어 저장해 봐. "
                 "그다음 그 글 아래의 [🚨 신고하기] 버튼을 눌러 관리자를 부르고, 관리자 콘솔(/admin)의 "
                 "'신고 검토(관리자 봇)' 메뉴로 가 봐. 봇이 네 글을 열어 보면 무슨 일이 생길까?"},
}

SYSTEM_RULES = (
    "너는 고등학생 대상 웹 해킹 특강의 mini-CTF AI 도우미다. 역할은 '코치'다.\n"
    "절대 규칙: 1) flag(정답 문자열)를 절대 직접 알려주지 마라. 2) 정확한 최종 페이로드를 통째로 "
    "주지 말고, '어디를 보고 무엇을 시도할지' 방향과 개념만 쉽게 설명하라. 3) 한국어로, 비전공 "
    "고등학생도 이해하게 친절하고 짧게(2~4문장) 답하라. 4) 학생이 스스로 찾는 재미를 남겨라."
)


def redact(text: str) -> str:
    return FLAG_RE.sub("flag{■■■ 직접 찾아보세요 ■■■}", text or "")


def ask_anthropic(question: str, ch: dict) -> str | None:
    if not ANTHROPIC_API_KEY:
        return None
    sys_prompt = (f"{SYSTEM_RULES}\n\n[현재 문제] {ch['name']}\n"
                  f"[코치 참고 방향(학생에게 직접 베껴주지 말 것)] {ch['dir']}")
    body = json.dumps({
        "model": ANTHROPIC_MODEL,
        "max_tokens": 400,
        "system": sys_prompt,
        "messages": [{"role": "user", "content": question}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body,
        headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        return "".join(b.get("text", "") for b in data.get("content", []))
    except Exception as e:
        return f"(Anthropic 호출 실패: {type(e).__name__}) " + ch["dir"]


def ask_ollama(question: str, ch: dict) -> str | None:
    if not OLLAMA_URL:
        return None
    sys_prompt = (f"{SYSTEM_RULES}\n\n[현재 문제] {ch['name']}\n[코치 참고 방향] {ch['dir']}")
    body = json.dumps({
        "model": OLLAMA_MODEL, "stream": False,
        "messages": [{"role": "system", "content": sys_prompt},
                     {"role": "user", "content": question}],
    }).encode()
    req = urllib.request.Request(f"{OLLAMA_URL}/api/chat", data=body,
                                 headers={"content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
        return data.get("message", {}).get("content", "") or ch["dir"]
    except Exception as e:
        return f"(Ollama 호출 실패: {type(e).__name__}) " + ch["dir"]


def offline_hint(question: str, ch: dict) -> str:
    # LLM 미설정 시 — 문제별 방향 힌트를 그대로 제공(항상 동작).
    q = question.lower()
    lead = "직접 깃발은 알려줄 수 없어! 하지만 방향은 줄게 🙂\n"
    if any(w in q for w in ["flag", "깃발", "정답", "답 알려", "답좀"]):
        lead = "깃발은 직접 찾아야 점수가 의미 있지! 대신 방향을 줄게 🙂\n"
    return lead + ch["dir"]


@app.route("/")
def index():
    return render_template("index.html", challenges=CHALLENGES)


@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    cid = str(data.get("challenge") or "1")
    ch = CHALLENGES.get(cid, CHALLENGES["1"])
    if not question:
        return jsonify({"answer": "무엇이 막혔는지 적어줘! 예: '이 문제 어디부터 봐야 해?'"})

    # 이 특강은 오픈 모델(DGX Spark 의 Ollama)을 우선 쓴다. 없으면 Anthropic, 그것도 없으면 오프라인.
    answer = ask_ollama(question, ch) or ask_anthropic(question, ch) or offline_hint(question, ch)
    backend = ("ollama" if OLLAMA_URL else "anthropic" if ANTHROPIC_API_KEY else "offline")
    return jsonify({"answer": redact(answer), "backend": backend})


@app.route("/_health")
def health():
    return {"ok": True, "service": "ctf-ai-helper",
            "backend": ("ollama" if OLLAMA_URL else "anthropic" if ANTHROPIC_API_KEY else "offline")}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8001"))
    print(f"[ai-helper] listening on :{port} "
          f"(backend={'ollama' if OLLAMA_URL else 'anthropic' if ANTHROPIC_API_KEY else 'offline'})")
    app.run(host="0.0.0.0", port=port)
