"""
AI 웹 해킹 특강 — 강좌 포털 웹사이트.

학생이 한 곳에서 커리큘럼을 보고, 교과서(lecture)·실습(lab)을 브라우저에서 바로 읽고,
실습 워크북·보안 서약서를 다운로드하고, 담벼락(게시판)에 메모를 붙인다.

⚠️ 보안·권한 모델
   - 회원가입/로그인이 있고, 등급은 **student** 와 **admin** 두 가지다.
   - **정답·해설(answer / answer_detail)과 강사용 풀이(solutions/)는 admin 만 볼 수 있다.**
     student 로 로그인하면 실습 페이지에서 정답 블록이 아예 렌더링되지 않는다(HTML 에도 없음).
   - ctf/challenges.yml(flag), seed/vulnerabilities.md 등은 어떤 등급에게도 서빙하지 않는다.
   - 회원가입 시 **CTFd 계정도 함께 생성**한다(CTFD_URL + CTFD_ADMIN_TOKEN 설정 시).

환경변수
   PORT                기본 8090
   SECRET_KEY          세션 서명 키 (운영 시 반드시 지정)
   USER_DB             사용자 DB 경로 (기본 site/users.db, 도커에서는 /data/users.db 권장)
   ADMIN_SIGNUP_CODE   가입 시 이 코드를 넣으면 admin 등급 (기본 ezweb-admin-2026)
   CTFD_URL            예: http://ctfd:8000  — 설정 시 가입과 동시에 CTFd 계정 생성
   CTFD_ADMIN_TOKEN    CTFd Access Token (Settings → Access Tokens)
   CTFD_PUBLIC_URL     학생에게 안내할 CTFd 주소(없으면 CTFD_URL)
"""
from __future__ import annotations
import os, re, html, json, sqlite3, secrets, hashlib, urllib.request, urllib.error
from functools import wraps
from pathlib import Path
from flask import (Flask, render_template, abort, send_from_directory,
                   request, redirect, url_for, session, flash, g)

BASE = Path(__file__).resolve().parent


def _find(*cands: str) -> Path:
    for c in cands:
        if c and Path(c).exists():
            return Path(c)
    return Path(cands[-1])


# 컨텐츠 경로 — 도커(이미지 내 복사본)와 로컬(레포 구조) 모두 지원
CONTENT = _find(os.environ.get("CONTENT_DIR", ""),
                str(BASE.parent / "content" / "training"),   # 도커: COPY contents/training → /app/content/training
                str(BASE.parent / "contents" / "training"),  # 혹시 모를 배치
                str(BASE.parent.parent / "contents" / "training"),  # 로컬: 레포/contents/training
                "/app/content/training")
DOWNLOADS = _find(os.environ.get("DOWNLOADS_DIR", ""),
                  str(BASE.parent / "downloads"),
                  str(BASE.parent.parent / "downloads"),
                  "/app/downloads")
SOLUTIONS = _find(os.environ.get("SOLUTIONS_DIR", ""),
                  str(BASE.parent / "solutions"),
                  str(BASE.parent.parent / "solutions"),
                  "/app/solutions")

WEEKS = {
    "01": {"title": "AI와 AI 에이전트, 그리고 윤리",
           "hook": "AI·에이전트를 만져보고, 요즘 터미널 에이전트 지도를 그린 뒤, 해도 되는 것과 안 되는 것을 약속한다.",
           "hours": "5시간", "emoji": "🤖"},
    "02": {"title": "리눅스 · DGX Spark 접속 · Hermes Agent + 오픈 모델 · 내 첫 웹사이트",
           "hook": "ssh 로 AI 서버에 들어가 보고, 내 컴퓨터에 에이전트를 깔아 오픈 모델과 연결한 뒤 사이트를 만든다.",
           "hours": "6시간", "emoji": "🐧"},
    "03": {"title": "웹의 작동 원리 + 직접 해보는 웹 해킹 (DVWA)",
           "hook": "웹이 어떻게 움직이는지 보고, SQLi·XSS·CSRF·웹셸을 브라우저만으로 내 손으로 뚫는다.",
           "hours": "7시간", "emoji": "🕸️"},
    "04": {"title": "AI 에이전트(Hermes)와 함께하는 모의해킹 (NeoBank)",
           "hook": "프롬프트만 복사해 붙이면 에이전트가 가상 은행을 점검한다. 그리고 브라우저로 직접 교차 검증한다.",
           "hours": "6시간", "emoji": "🏦"},
    "05": {"title": "mini-CTF (MediForum + CTFd)",
           "hook": "배운 걸로 깃발을 찾아 친구들과 실시간 리더보드 대결! 6문제 전부 브라우저로 풀린다.",
           "hours": "4시간+", "emoji": "🏁"},
}

# 특별 세션 — AI 서비스 모의해킹 3주
SPECIALS = {
    "ai01": {"title": "AI 서비스는 어디가 약할까? (공격 표면 · OWASP LLM Top 10 · 정찰)",
             "hook": "공격도 하기 전에 새는 비밀 3건을 브라우저로 직접 찾아낸다.",
             "hours": "5시간", "emoji": "🔎"},
    "ai02": {"title": "프롬프트 인젝션 3종 + 챗봇의 답이 흉기가 될 때",
             "hook": "말 한 줄로 챗봇을 조종하고, 남이 읽을 문서에 함정을 미리 심는다.",
             "hours": "5시간", "emoji": "💉"},
    "ai03": {"title": "도구를 쥔 챗봇 · 모델 절취 · 그리고 방어 설계",
             "hook": "챗봇의 손발을 잡아 서버를 흔들어 보고, 마지막엔 방어자로 전환해 설계도를 그린다.",
             "hours": "5시간", "emoji": "🛡️"},
}

ALL_UNITS = {**WEEKS, **SPECIALS}

# 주차별 실습 페이지에서 내려받게 할 배부 자료(.docx). Week01 엔 보안서약서도 함께.
WEEK_DOWNLOADS = {
    "01": ["보안서약서.docx", "실습워크북_Week01.docx"],
    "02": ["실습워크북_Week02.docx"],
    "03": ["실습워크북_Week03.docx"],
    "04": ["실습워크북_Week04.docx"],
    "05": ["실습워크북_Week05.docx"],
    "ai01": ["실습워크북_AI01.docx"],
    "ai02": ["실습워크북_AI02.docx"],
    "ai03": ["실습워크북_AI03.docx"],
}

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or "ezweb-course-site-change-me"

USER_DB = os.environ.get("USER_DB") or str(BASE / "users.db")
ADMIN_SIGNUP_CODE = os.environ.get("ADMIN_SIGNUP_CODE", "ezweb-admin-2026")
CTFD_URL = (os.environ.get("CTFD_URL", "") or "").rstrip("/")
CTFD_ADMIN_TOKEN = os.environ.get("CTFD_ADMIN_TOKEN", "")
CTFD_PUBLIC_URL = (os.environ.get("CTFD_PUBLIC_URL", "") or CTFD_URL).rstrip("/")

NOTE_COLORS = ["yellow", "green", "blue", "pink", "purple", "orange"]


# =============================================================================
#  사용자 · 담벼락 저장소 (SQLite)
# =============================================================================
def db():
    if "db" not in g:
        g.db = sqlite3.connect(USER_DB)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def _close_db(_):
    d = g.pop("db", None)
    if d:
        d.close()


def init_db():
    Path(USER_DB).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(USER_DB)
    con.executescript("""
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT UNIQUE NOT NULL,
      email TEXT,
      pw_hash TEXT NOT NULL,
      role TEXT NOT NULL DEFAULT 'student',   -- student | admin
      ctfd_status TEXT DEFAULT '',            -- created | exists | skipped | error:...
      created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS notes(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      author TEXT NOT NULL,
      title TEXT,
      body TEXT NOT NULL,
      color TEXT DEFAULT 'yellow',
      link TEXT DEFAULT '',
      created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS note_likes(
      note_id INTEGER, username TEXT,
      PRIMARY KEY (note_id, username)
    );
    CREATE TABLE IF NOT EXISTS note_comments(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      note_id INTEGER NOT NULL,
      author TEXT NOT NULL,
      body TEXT NOT NULL,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)
    con.commit()
    con.close()


def hash_pw(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(8)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000)
    return f"pbkdf2${salt}${dk.hex()}"


def check_pw(password: str, stored: str) -> bool:
    try:
        _, salt, _ = stored.split("$", 2)
    except ValueError:
        return False
    return secrets.compare_digest(hash_pw(password, salt), stored)


def current_user():
    uname = session.get("u")
    if not uname:
        return None
    cur = db().execute("SELECT * FROM users WHERE username=?", (uname,))
    return cur.fetchone()


def is_admin() -> bool:
    u = current_user()
    return bool(u and u["role"] == "admin")


def login_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if not current_user():
            return redirect(url_for("login", next=request.path))
        return fn(*a, **kw)
    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if not current_user():
            return redirect(url_for("login", next=request.path))
        if not is_admin():
            abort(403)
        return fn(*a, **kw)
    return wrapper


@app.context_processor
def inject_globals():
    return {"me": current_user(), "is_admin": is_admin(),
            "weeks": WEEKS, "specials": SPECIALS,
            "ctfd_url": CTFD_PUBLIC_URL}


# =============================================================================
#  CTFd 계정 연동
# =============================================================================
def ctfd_create_user(username: str, email: str, password: str) -> str:
    """CTFd 에 같은 계정을 만든다. 반환값은 상태 문자열(로그·화면 표시용)."""
    if not (CTFD_URL and CTFD_ADMIN_TOKEN):
        return "skipped"          # 연동 미설정 — 학생이 CTFd 에서 직접 가입하면 된다
    payload = json.dumps({
        "name": username,
        "email": email or f"{username}@ezweb.local",
        "password": password,
        "type": "user",
        "verified": True,
        "hidden": False,
        "banned": False,
    }).encode()
    req = urllib.request.Request(
        f"{CTFD_URL}/api/v1/users", data=payload, method="POST",
        headers={"Authorization": f"Token {CTFD_ADMIN_TOKEN}",
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            body = json.loads(r.read().decode("utf-8", "replace"))
        return "created" if body.get("success") else f"error:{str(body)[:80]}"
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:120]
        # 이미 있는 계정이면 그대로 쓰면 된다
        if "already" in detail or "taken" in detail or e.code == 400:
            return "exists"
        return f"error:{e.code}"
    except Exception as e:                                   # 네트워크 실패 등
        return f"error:{type(e).__name__}"


# =============================================================================
#  마크다운 렌더
# =============================================================================
def render_markdown(text: str) -> str:
    import markdown
    md = markdown.Markdown(extensions=["tables", "fenced_code", "toc", "sane_lists", "attr_list"])
    body = md.convert(text)

    # ```mermaid 코드블록 → <div class="mermaid"> 로 변환(클라이언트에서 다이어그램 렌더)
    def to_mermaid(m):
        return '<div class="mermaid">' + html.unescape(m.group(1)) + '</div>'
    body = re.sub(r'<pre><code class="language-mermaid">(.*?)</code></pre>',
                  to_mermaid, body, flags=re.S)
    return body


# =============================================================================
#  인증 라우트
# =============================================================================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")
    username = (request.form.get("username") or "").strip()
    email = (request.form.get("email") or "").strip()
    pw = request.form.get("password") or ""
    pw2 = request.form.get("password2") or ""
    code = (request.form.get("admin_code") or "").strip()

    if not re.fullmatch(r"[A-Za-z0-9._-]{3,24}", username):
        return render_template("register.html", error="아이디는 영문/숫자/._- 3~24자로 만들어주세요."), 400
    if len(pw) < 6:
        return render_template("register.html", error="비밀번호는 6자 이상으로 해주세요."), 400
    if pw != pw2:
        return render_template("register.html", error="비밀번호 확인이 일치하지 않습니다."), 400
    if db().execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
        return render_template("register.html", error="이미 사용 중인 아이디입니다."), 409

    # 등급 결정: 관리자 코드가 맞거나, 아직 사용자가 한 명도 없으면(최초 1인) admin
    first_user = db().execute("SELECT COUNT(*) c FROM users").fetchone()["c"] == 0
    role = "admin" if (first_user or (code and code == ADMIN_SIGNUP_CODE)) else "student"

    ctfd_status = ctfd_create_user(username, email, pw)
    db().execute("INSERT INTO users(username,email,pw_hash,role,ctfd_status) VALUES(?,?,?,?,?)",
                 (username, email, hash_pw(pw), role, ctfd_status))
    db().commit()

    session["u"] = username
    msgs = {"created": "CTFd 계정도 같은 아이디·비밀번호로 만들어졌습니다.",
            "exists": "CTFd 에 같은 아이디가 이미 있어 그대로 사용합니다.",
            "skipped": "CTFd 연동이 설정되지 않아, CTF 는 따로 가입해야 합니다."}
    flash(f"환영합니다, {username} 님! ({'관리자' if role == 'admin' else '학생'} 등급) "
          + msgs.get(ctfd_status, f"CTFd 연동 중 문제가 있었습니다({ctfd_status}). 강사에게 알려주세요."))
    return redirect(url_for("index"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html", next=request.args.get("next", ""))
    username = (request.form.get("username") or "").strip()
    pw = request.form.get("password") or ""
    row = db().execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if not row or not check_pw(pw, row["pw_hash"]):
        return render_template("login.html", error="아이디 또는 비밀번호가 올바르지 않습니다."), 401
    session["u"] = row["username"]
    nxt = request.form.get("next") or url_for("index")
    return redirect(nxt if nxt.startswith("/") else url_for("index"))


@app.route("/logout")
def logout():
    session.pop("u", None)
    return redirect(url_for("index"))


# =============================================================================
#  콘텐츠 라우트
# =============================================================================
@app.route("/")
def index():
    return render_template("index.html", downloads=_list_downloads())


@app.route("/lecture/<unit>")
def lecture(unit):
    if unit not in ALL_UNITS:
        abort(404)
    f = CONTENT / f"lecture_{'week' if unit in WEEKS else ''}{unit}.md"
    if not f.exists():
        abort(404)
    body = render_markdown(f.read_text(encoding="utf-8"))
    return render_template("doc.html", body=body, unit=unit, kind="교과서", has_mermaid=True)


@app.route("/lab/<unit>")
def lab(unit):
    if unit not in ALL_UNITS:
        abort(404)
    f = CONTENT / f"lab_{'week' if unit in WEEKS else ''}{unit}.yaml"
    if not f.exists():
        abort(404)
    import yaml
    data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    admin = is_admin()
    p = []
    label = f"Week {unit}" if unit in WEEKS else f"특별 세션 {unit[-1]}"
    p.append(f"<h1>실습 {label} — {html.escape(str(data.get('title','')))}</h1>")
    try:
        thr = int(float(data.get("pass_threshold", 0)) * 100)
    except Exception:
        thr = 0
    p.append(f"<blockquote>난이도 <b>{html.escape(str(data.get('difficulty','')))}</b> · "
             f"약 {data.get('duration_minutes','?')}분 · 통과 기준 {thr}%</blockquote>")
    # 이 주차 배부 자료(.docx) 다운로드 링크
    dls = [f for f in WEEK_DOWNLOADS.get(unit, []) if (DOWNLOADS / f).is_file()]
    if dls:
        links = " · ".join(f'<a href="/download/{f}">📄 {f}</a>' for f in dls)
        p.append(f'<div class="dlbox">⬇️ <b>이 주차 자료</b> (다운로드): {links}</div>')
    if data.get("description"):
        p.append(render_markdown(str(data["description"])))
    objs = data.get("objectives") or []
    if objs:
        p.append("<h2>학습 목표</h2>")
        p.append(render_markdown("\n".join(f"{i+1}. {o}" for i, o in enumerate(objs))))
    p.append("<hr>")
    for st in data.get("steps", []):
        p.append(f'<h2>단계 {st.get("order","")} '
                 f'<span class="stepmeta">{html.escape(str(st.get("category","")))} · '
                 f'{st.get("points","")}점</span></h2>')
        p.append(render_markdown(str(st.get("instruction", ""))))
        if st.get("hint"):
            p.append(f'<p class="hint">💡 <b>힌트:</b> {html.escape(str(st["hint"]))}</p>')
        # ⚠️ 정답·해설은 admin 에게만. student 응답에는 HTML 자체가 포함되지 않는다.
        if admin:
            ans = str(st.get("answer", "") or "").strip()
            ad = str(st.get("answer_detail", "") or "").strip()
            if ans or ad:
                det = "<details class='ans'><summary>정답·해설 보기 (관리자 전용)</summary>"
                if ans:
                    det += render_markdown("```\n" + ans + "\n```")
                if ad:
                    det += render_markdown(ad)
                det += "</details>"
                p.append(det)
        p.append("<hr>")
    if not admin:
        p.append('<div class="info warn">🔒 <b>정답·해설은 관리자(강사) 등급만</b> 볼 수 있습니다. '
                 '먼저 스스로 끝까지 시도해 보세요. 막히면 힌트와 AI 도우미를 활용하세요.</div>')
    return render_template("doc.html", body="\n".join(p), unit=unit, kind="실습", has_mermaid=False)


@app.route("/solutions")
@admin_required
def solutions():
    f = SOLUTIONS / "SOLUTIONS.md"
    if not f.exists():
        abort(404)
    body = render_markdown(f.read_text(encoding="utf-8"))
    return render_template("doc.html", body=body, unit=None, kind="강사용 풀이", has_mermaid=True)


# =============================================================================
#  담벼락 (Padlet 스타일 메모판)
# =============================================================================
@app.route("/board")
def board():
    rows = db().execute("""
        SELECT n.*, (SELECT COUNT(*) FROM note_likes l WHERE l.note_id=n.id) AS likes,
               (SELECT COUNT(*) FROM note_comments c WHERE c.note_id=n.id) AS cmts
        FROM notes n ORDER BY n.id DESC LIMIT 300""").fetchall()
    me = current_user()
    liked = set()
    if me:
        liked = {r["note_id"] for r in db().execute(
            "SELECT note_id FROM note_likes WHERE username=?", (me["username"],)).fetchall()}
    return render_template("board.html", notes=rows, liked=liked, colors=NOTE_COLORS)


@app.route("/board/new", methods=["POST"])
@login_required
def board_new():
    me = current_user()
    title = (request.form.get("title") or "").strip()[:80]
    body = (request.form.get("body") or "").strip()[:2000]
    color = request.form.get("color") or "yellow"
    link = (request.form.get("link") or "").strip()[:300]
    if color not in NOTE_COLORS:
        color = "yellow"
    if link and not link.startswith(("http://", "https://", "/")):
        link = ""                       # 자바스크립트 URL 등 차단
    if not body:
        flash("내용을 입력해 주세요.")
        return redirect(url_for("board"))
    db().execute("INSERT INTO notes(author,title,body,color,link) VALUES(?,?,?,?,?)",
                 (me["username"], title, body, color, link))
    db().commit()
    return redirect(url_for("board"))


@app.route("/board/<int:nid>/like", methods=["POST"])
@login_required
def board_like(nid):
    me = current_user()
    row = db().execute("SELECT 1 FROM note_likes WHERE note_id=? AND username=?",
                       (nid, me["username"])).fetchone()
    if row:
        db().execute("DELETE FROM note_likes WHERE note_id=? AND username=?", (nid, me["username"]))
    else:
        db().execute("INSERT INTO note_likes(note_id,username) VALUES(?,?)", (nid, me["username"]))
    db().commit()
    return redirect(url_for("board"))


@app.route("/board/<int:nid>/comment", methods=["POST"])
@login_required
def board_comment(nid):
    me = current_user()
    body = (request.form.get("body") or "").strip()[:500]
    if body:
        db().execute("INSERT INTO note_comments(note_id,author,body) VALUES(?,?,?)",
                     (nid, me["username"], body))
        db().commit()
    return redirect(url_for("board_detail", nid=nid))


@app.route("/board/<int:nid>")
def board_detail(nid):
    n = db().execute("SELECT * FROM notes WHERE id=?", (nid,)).fetchone()
    if not n:
        abort(404)
    cmts = db().execute("SELECT * FROM note_comments WHERE note_id=? ORDER BY id", (nid,)).fetchall()
    return render_template("board_detail.html", n=n, cmts=cmts)


@app.route("/board/<int:nid>/delete", methods=["POST"])
@login_required
def board_delete(nid):
    me = current_user()
    n = db().execute("SELECT * FROM notes WHERE id=?", (nid,)).fetchone()
    if not n:
        abort(404)
    if n["author"] != me["username"] and not is_admin():
        abort(403)                                  # 내 글이거나 관리자만 삭제
    db().execute("DELETE FROM notes WHERE id=?", (nid,))
    db().execute("DELETE FROM note_likes WHERE note_id=?", (nid,))
    db().execute("DELETE FROM note_comments WHERE note_id=?", (nid,))
    db().commit()
    return redirect(url_for("board"))


# =============================================================================
#  관리자 — 수강생 관리
# =============================================================================
@app.route("/admin/users")
@admin_required
def admin_users():
    rows = db().execute("SELECT * FROM users ORDER BY id").fetchall()
    return render_template("admin_users.html", users=rows,
                           ctfd_linked=bool(CTFD_URL and CTFD_ADMIN_TOKEN))


@app.route("/admin/users/<int:uid>/role", methods=["POST"])
@admin_required
def admin_set_role(uid):
    role = request.form.get("role")
    if role in ("student", "admin"):
        db().execute("UPDATE users SET role=? WHERE id=?", (role, uid))
        db().commit()
    return redirect(url_for("admin_users"))


@app.route("/admin/users/<int:uid>/ctfd-sync", methods=["POST"])
@admin_required
def admin_ctfd_sync(uid):
    """CTFd 계정이 없던 학생을 나중에 연동한다(임시 비밀번호 발급)."""
    row = db().execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    if not row:
        abort(404)
    temp_pw = "ctf-" + secrets.token_urlsafe(6)
    status = ctfd_create_user(row["username"], row["email"], temp_pw)
    db().execute("UPDATE users SET ctfd_status=? WHERE id=?", (status, uid))
    db().commit()
    if status == "created":
        flash(f"{row['username']} 의 CTFd 계정을 만들었습니다. 임시 비밀번호: {temp_pw}")
    else:
        flash(f"{row['username']} CTFd 연동 결과: {status}")
    return redirect(url_for("admin_users"))


# =============================================================================
#  다운로드 · 헬스
# =============================================================================
def _list_downloads():
    if not DOWNLOADS.exists():
        return []
    out = []
    for p in sorted(DOWNLOADS.iterdir()):
        if p.is_file() and p.suffix.lower() in (".md", ".html", ".pdf", ".docx"):
            out.append(p.name)
    return out


@app.route("/download/<path:fn>")
def download(fn):
    # 화이트리스트: downloads/ 안의 파일만, 경로 이탈 차단
    safe = os.path.basename(fn)
    if safe != fn or not (DOWNLOADS / safe).is_file():
        abort(404)
    return send_from_directory(DOWNLOADS, safe, as_attachment=True)


@app.route("/_health")
def health():
    return {"ok": True, "service": "course-site",
            "content": str(CONTENT), "downloads": str(DOWNLOADS),
            "ctfd_linked": bool(CTFD_URL and CTFD_ADMIN_TOKEN)}


@app.errorhandler(403)
def forbidden(_):
    return render_template("error.html", code=403,
                           msg="이 페이지는 관리자(강사)만 볼 수 있습니다."), 403


@app.errorhandler(404)
def notfound(_):
    return render_template("error.html", code=404, msg="페이지를 찾을 수 없습니다."), 404


init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8090"))
    print(f"[course-site] listening on :{port}  content={CONTENT}  downloads={DOWNLOADS}")
    print(f"[course-site] users db={USER_DB}  ctfd_linked={bool(CTFD_URL and CTFD_ADMIN_TOKEN)}")
    app.run(host="0.0.0.0", port=port)
