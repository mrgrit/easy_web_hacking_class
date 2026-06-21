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
          "dir": "화면에 안 보이는 정보는 '페이지 소스'에 있다. 브라우저에서 Ctrl+U(소스 보기)를 누르고, "
                 "게시판의 '공지' 글을 연 뒤 HTML 주석 <!-- ... --> 안을 살펴봐."},
    "2": {"name": "인증 없는 회원 API (PII)",
          "dir": "로그인 없이 열리는 API 주소를 추측해봐(예: /api/users). 응답(JSON)에서 role 이 admin 인 "
                 "사용자의 비밀 키(api_key) 필드를 확인해."},
    "3": {"name": "남의 진료기록 (IDOR)",
          "dir": "진료기록 API(/api/medical-records, /api/medical-records/<번호>)에서 번호를 1부터 바꿔가며 "
                 "남의 기록까지 열어봐. 처방/소견 칸을 잘 읽어."},
    "4": {"name": "관리자 쪽지 도청",
          "dir": "'관리자 전용'인데 인증을 안 거는 API 를 추측해봐(예: /api/admin/dms). 쪽지 본문을 전부 읽어."},
    "5": {"name": "예측 가능한 세션",
          "dir": "로그인 후 쿠키 MFSID 값의 규칙을 관찰해(예: sess-2001). 관리자는 더 일찍 로그인했어 — 더 낮은 "
                 "번호를 시도해보고, 관리자 전용 경로(/admin/secret)에 들어가 봐."},
    "6": {"name": "저장형 XSS — 관리자 봇",
          "dir": "게시글/댓글 본문에 <script>alert(1)</script> 처럼 스크립트를 저장해봐. 그 다음 관리자가 글을 "
                 "검토하는 경로(/admin/review)를 호출하면 봇이 반응해."},
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

    answer = ask_anthropic(question, ch) or ask_ollama(question, ch) or offline_hint(question, ch)
    backend = ("anthropic" if ANTHROPIC_API_KEY else "ollama" if OLLAMA_URL else "offline")
    return jsonify({"answer": redact(answer), "backend": backend})


@app.route("/_health")
def health():
    return {"ok": True, "service": "ctf-ai-helper",
            "backend": ("anthropic" if ANTHROPIC_API_KEY else "ollama" if OLLAMA_URL else "offline")}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8001"))
    print(f"[ai-helper] listening on :{port} "
          f"(backend={'anthropic' if ANTHROPIC_API_KEY else 'ollama' if OLLAMA_URL else 'offline'})")
    app.run(host="0.0.0.0", port=port)
