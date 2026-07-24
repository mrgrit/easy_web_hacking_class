"""
MediForum — 의도적 취약 의료 커뮤니티 (mini-CTF 표적)
================================================================
22 취약점. Stored XSS / CSRF / PII 노출 / API 인증 우회 강조.

⚠️ 교육용. 격리된 네트워크에서만 실행.

V01  Stored XSS — post body                       (A03)
V02  Stored XSS — comment                          (A03)
V03  Stored XSS — profile bio + display_name       (A03)
V04  CSRF — post create                            (A08)
V05  CSRF — comment create                         (A08)
V06  CSRF — profile update                         (A08)
V07  PII leak — /api/users 전체 (이름/email/주민번호 일부) (A02)
V08  PII leak — /api/medical-records 누구나 조회   (A01/A02)
V09  IDOR — 다른 환자 medical record               (A01)
V10  Broken API auth — /api/admin/* · /admin/* 인증 0 (A07)
V11  API key in URL query — log 노출               (A09/A02)
V12  Session cookie HttpOnly/Secure 미설정         (A05)
V13  CORS allow * with credentials                 (A05)
V14  Predictable session_id (counter)              (A02)
V15  Email enumeration — 가입 시 "이미 사용중" 노출 (A07)
V16  PII overshare — search 결과에 SSN/phone 포함  (A02)
V17  Mass assignment — /api/profile (role/verified) (A01)
V18  Stored XSS in DM (private message)            (A03)
V19  XSS via SVG upload (avatar)                   (A03/A09)
V20  Open redirect — /go?to=                       (A10)
V21  Verbose error — Python stack trace            (A09)
V22  Hardcoded admin token                          (A07)

────────────────────────────────────────────────────────────────
🏁 mini-CTF 설계 메모 (강사용)
  학생은 curl 없이 **브라우저만으로** 6문제를 전부 풀 수 있어야 한다.
  그래서 "숨은 주소를 찍어서 맞히기"가 아니라 **화면에서 발견되는 경로**를 깔아 두었다.

    · /robots.txt          → 관리자/기록/API 경로가 그대로 적힌 정찰 출발점
    · /search (회원 찾기)  → 화면이 fetch('/api/users') 를 호출 → F12 Network 로 API 발견
    · /records             → 진료기록 '목록'은 누구나, '상세'는 소유 검증 0 → IDOR 을 주소창으로
    · /admin               → 인증 없이 열리는 관리자 콘솔(쪽지 감사·신고 검토·금고 링크)
    · /posts/<id>/report   → 신고 버튼 → 관리자 봇이 검토(/admin/review) 하는 서사 완성
    · ensure_ctf_flags()   → 부팅마다 깃발 값을 강제로 다시 심어, 사이트에서 본 깃발과
                             ctf/challenges.yml 의 정답이 **항상 일치**하도록 보장

Run: python app.py  (port 3003)
"""
import os, sqlite3, re, time, hashlib, traceback
from flask import Flask, request, jsonify, render_template, redirect, g, make_response
from werkzeug.utils import secure_filename  # 일부러 미사용 (V19 우회)

app = Flask(__name__)
app.secret_key = "mediforum-not-secret-2026"  # V14

DB_PATH = os.environ.get("DB_PATH", "mediforum.db")
UPLOAD = os.environ.get("UPLOAD_DIR", "uploads")
os.makedirs(UPLOAD, exist_ok=True)

ADMIN_TOKEN = "MEDIFORUM-ADMIN-2026-DEV"  # V22 hardcoded

# =============================================================================
#  CTF 깃발 — 이 값이 '유일한 진실'이다.
#  ctf/challenges.yml 과 solutions/SOLUTIONS.md 의 값과 반드시 같아야 하며,
#  ensure_ctf_flags() 가 부팅할 때마다 DB 에 다시 심는다(오래된 DB 로 인한 불일치 방지).
# =============================================================================
FLAGS = {
    "recon":   "flag{v13w_s0urc3_r3con}",       # 1. 페이지 소스 주석
    "api":     "flag{n0_4uth_us3r_ap1}",        # 2. 인증 없는 회원 API 의 admin api_key
    "idor":    "flag{1d0r_m3d_r3c0rds}",        # 3. 남의 진료기록 처방란
    "dm":      "flag{4dm1n_dm_l34k}",           # 4. 관리자 쪽지
    "session": "flag{pr3d1ct4bl3_s3ss10n}",     # 5. 관리자 전용 금고
    "xss":     "flag{st0r3d_xss_4dm1n_b0t}",    # 6. 저장형 XSS + 관리자 봇
}

ADMIN_SESSION_ID = "sess-1001"   # 관리자(uid=1)의 고정 세션 — 5번 문제
SESSION_BASE     = 2000          # 일반 사용자 세션은 sess-2001 부터


# ----------- DB 헬퍼 -----------
def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(_):
    d = g.pop("db", None)
    if d: d.close()

def init_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      email TEXT UNIQUE,
      password TEXT,
      display_name TEXT,
      role TEXT DEFAULT 'patient',  -- patient/doctor/admin
      verified INTEGER DEFAULT 0,
      bio TEXT DEFAULT '',
      ssn TEXT DEFAULT '',
      phone TEXT DEFAULT '',
      api_key TEXT,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS posts(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      author_id INTEGER, title TEXT, body TEXT,
      tag TEXT DEFAULT 'general',
      created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS comments(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      post_id INTEGER, author_id INTEGER, body TEXT,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS medical_records(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      patient_id INTEGER, doctor_id INTEGER,
      diagnosis TEXT, prescription TEXT,
      visit_date TEXT
    );
    CREATE TABLE IF NOT EXISTS dms(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      from_id INTEGER, to_id INTEGER, body TEXT,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS sessions(
      sid TEXT PRIMARY KEY, user_id INTEGER, created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS reports(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      kind TEXT,           -- 'post' | 'comment'
      target_id INTEGER,
      reporter_id INTEGER,
      reason TEXT,
      status TEXT DEFAULT 'pending',
      created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cur.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] == 0:
        seed = [
            ("admin@medi.kr",   "admin123",  "관리자",       "admin",   1, "MediForum 관리자",        "800101-1******", "010-0000-0000", FLAGS["api"]),
            ("dr.kim@medi.kr",  "doctor123", "김의사 (내과)","doctor",  1, "내과 전문의 · 진료 12년", "750515-1******", "010-1111-1111", "ak-doc-2222"),
            ("dr.lee@medi.kr",  "doctor123", "이의사 (외과)","doctor",  1, "외과 전문의 · 외상 외과", "780303-2******", "010-2222-2222", "ak-doc-3333"),
            ("alice@user.kr",   "alice123",  "앨리스",       "patient", 1, "당뇨 관리 중",            "920722-2******", "010-3333-3333", "ak-pat-4444"),
            ("bob@user.kr",     "bob123",    "밥",           "patient", 0, "어깨 통증",               "880909-1******", "010-4444-4444", "ak-pat-5555"),
            ("carol@user.kr",   "carol123",  "캐롤",         "patient", 1, "혈압 관리",               "950611-2******", "010-5555-5555", "ak-pat-6666"),
        ]
        cur.executemany("INSERT INTO users(email,password,display_name,role,verified,bio,ssn,phone,api_key) VALUES(?,?,?,?,?,?,?,?,?)", seed)

        cur.executemany("INSERT INTO posts(author_id,title,body,tag) VALUES(?,?,?,?)", [
            (2, "감기 예방법 5가지", "손 자주 씻기, 충분한 수면 등...", "tip"),
            (3, "어깨 통증 자가 진단", "팔을 들 때 통증이 있다면...", "tip"),
            (4, "당뇨 식단 공유", "현미, 견과류 추천드려요!", "share"),
            (1, "[공지] 의료정보 무단 전송 금지",
                "본 포럼은 익명입니다. 진료기록·주민번호를 게시글에 적지 마세요.\n"
                "<!-- TODO(admin): 배포 전에 이 메모 꼭 지우기! 임시 관리자 인수인계 코드 = "
                + FLAGS["recon"] + " -->", "notice"),
        ])
        cur.executemany("INSERT INTO comments(post_id,author_id,body) VALUES(?,?,?)", [
            (1,4,"감사합니다 도움돼요"),
            (1,5,"좋은 글이네요"),
            (3,2,"식단 좋네요. 운동도 같이 추천드립니다."),
        ])
        cur.executemany("INSERT INTO medical_records(patient_id,doctor_id,diagnosis,prescription,visit_date) VALUES(?,?,?,?,?)", [
            (4,2,"제2형 당뇨 의심","메트포민 500mg 1일 2회","2026-04-10"),
            (5,3,"좌측 회전근개 부분 파열","조영제 MRI 권고, NSAIDs 처방","2026-04-12"),
            (6,2,"본태성 고혈압","암로디핀 5mg 1일 1회","2026-04-15"),
            (4,3,"발목 염좌 (자전거)","압박 + 부목, 7일 후 재진","2026-04-18"),
            (1,2,"[VIP 비공개] 원장 종합검진","특이소견 없음 — 기밀코드 " + FLAGS["idor"],"2026-04-20"),
        ])
        cur.executemany("INSERT INTO dms(from_id,to_id,body) VALUES(?,?,?)", [
            (4,2,"선생님 처방 감사합니다."),
            (2,4,"증상 변화 있으면 바로 알려주세요."),
            (1,3,"[관리자] 서버 백업 비밀번호 공유합니다: " + FLAGS["dm"]),
        ])
    con.commit(); con.close()


def ensure_ctf_flags():
    """부팅할 때마다 깃발이 든 레코드를 '강제로' 최신 값으로 되돌린다.

    학생이 사이트에서 눈으로 본 깃발과 CTFd 정답이 달라지는 사고(오래된 DB, 학생의
    프로필 수정으로 admin api_key 변조 등)를 원천 차단한다. 매 기동 시 실행된다.
    """
    con = sqlite3.connect(DB_PATH); cur = con.cursor()
    try:
        # ① 2번 문제 — 관리자 api_key
        cur.execute("UPDATE users SET api_key=? WHERE role='admin'", (FLAGS["api"],))

        # ② 1번 문제 — 공지 글 소스 주석
        notice_body = ("본 포럼은 익명입니다. 진료기록·주민번호를 게시글에 적지 마세요.\n"
                       "<!-- TODO(admin): 배포 전에 이 메모 꼭 지우기! 임시 관리자 인수인계 코드 = "
                       + FLAGS["recon"] + " -->")
        cur.execute("UPDATE posts SET body=? WHERE tag='notice'", (notice_body,))

        # ③ 3번 문제 — VIP 진료기록 처방란
        cur.execute("UPDATE medical_records SET prescription=? WHERE diagnosis LIKE '%VIP%'",
                    ("특이소견 없음 — 기밀코드 " + FLAGS["idor"],))

        # ④ 4번 문제 — 관리자 쪽지
        cur.execute("UPDATE dms SET body=? WHERE body LIKE '%백업 비밀번호%'",
                    ("[관리자] 서버 백업 비밀번호 공유합니다: " + FLAGS["dm"],))

        # ⑤ 5번 문제 — 관리자 고정 세션(sess-1001)이 항상 살아 있게
        cur.execute("SELECT id FROM users WHERE role='admin' ORDER BY id LIMIT 1")
        row = cur.fetchone()
        admin_id = row[0] if row else 1
        cur.execute("DELETE FROM sessions WHERE sid=?", (ADMIN_SESSION_ID,))
        cur.execute("INSERT INTO sessions(sid,user_id,created_at) VALUES(?,?,datetime('now'))",
                    (ADMIN_SESSION_ID, admin_id))
        con.commit()
    finally:
        con.close()


# ----------- 세션 (V14 predictable) -----------
def _next_session_no():
    """sess-2001, 2002 … 순차 증가. 재기동해도 겹치지 않게 DB 최댓값에서 이어 간다."""
    cur = db().cursor()
    cur.execute("SELECT sid FROM sessions WHERE sid LIKE 'sess-%'")
    mx = SESSION_BASE
    for (sid,) in cur.fetchall():
        try:
            n = int(str(sid).split("-")[1])
        except (IndexError, ValueError):
            continue
        if n > mx:            # 관리자 고정 세션(sess-1001)은 SESSION_BASE 아래라 자연히 제외됨
            mx = n
    return mx + 1

def issue_session(uid):
    sid = f"sess-{_next_session_no()}"  # V14 — 예측 가능한 순차 세션
    cur = db().cursor()
    cur.execute("INSERT INTO sessions(sid,user_id,created_at) VALUES(?,?,datetime('now'))", (sid, uid))
    db().commit()
    return sid

def current_user():
    sid = request.cookies.get("MFSID")
    # V22 admin token 우회
    if request.headers.get("X-Admin-Token") == ADMIN_TOKEN:
        cur = db().cursor()
        cur.execute("SELECT * FROM users WHERE role='admin' LIMIT 1")
        return cur.fetchone()
    if not sid: return None
    cur = db().cursor()
    cur.execute("SELECT u.* FROM users u JOIN sessions s ON s.user_id=u.id WHERE s.sid=?", (sid,))
    return cur.fetchone()

# ----------- 보안 헤더 (V12/V13 불완전) -----------
@app.after_request
def headers(resp):
    resp.headers["Server"] = "nginx/1.18.0"
    # V13 CORS
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Credentials"] = "true"
    resp.headers["Access-Control-Allow-Headers"] = "*"
    return resp

# ----------- 정찰 표면: robots.txt -----------
@app.route("/robots.txt")
def robots():
    """'검색엔진아 여기는 긁지 마' 파일. 역설적으로 숨기고 싶은 경로 목록이 된다.

    CTF 학생의 정찰 출발점 — 주소를 '찍어서 맞히는' 게 아니라 여기서 '읽어서' 알아낸다.
    """
    body = (
        "# MediForum robots.txt\n"
        "# 검색엔진 수집 금지 목록입니다. (내부 전용 경로가 포함되어 있으니 취급 주의)\n"
        "User-agent: *\n"
        "Disallow: /admin\n"
        "Disallow: /admin/secret\n"
        "Disallow: /admin/review\n"
        "Disallow: /records\n"
        "Disallow: /api/users\n"
        "Disallow: /api/medical-records\n"
        "Disallow: /api/admin/\n"
        "Disallow: /uploads/\n"
    )
    return app.response_class(body, mimetype="text/plain")

# ----------- 페이지 -----------
@app.route("/")
def index():
    cur = db().cursor()
    cur.execute("""SELECT p.*, u.display_name, (SELECT COUNT(*) FROM comments c WHERE c.post_id=p.id) AS cmt
                   FROM posts p LEFT JOIN users u ON u.id=p.author_id ORDER BY p.id DESC LIMIT 30""")
    posts = cur.fetchall()
    return render_template("index.html", posts=posts, me=current_user())

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")
    email = request.form.get("email","").strip()
    pw = request.form.get("password","").strip()
    cur = db().cursor()
    cur.execute("SELECT id,password FROM users WHERE email=?", (email,))
    row = cur.fetchone()
    if not row or row["password"] != pw:
        return render_template("login.html", error="이메일/비밀번호 확인"), 401
    sid = issue_session(row["id"])
    resp = make_response(redirect("/"))
    # V12: HttpOnly/Secure 미설정 → JS 로도 읽히고, 개발자도구로 손쉽게 바꿔 끼울 수 있다
    resp.set_cookie("MFSID", sid)
    return resp

@app.route("/logout")
def logout():
    resp = make_response(redirect("/"))
    resp.set_cookie("MFSID", "", expires=0)
    return resp

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")
    email = request.form.get("email","").strip()
    pw = request.form.get("password","x")
    name = request.form.get("display_name","익명")
    cur = db().cursor()
    cur.execute("SELECT id FROM users WHERE email=?", (email,))
    # V15 email enumeration
    if cur.fetchone():
        return render_template("register.html", error=f"{email} 는 이미 사용 중입니다."), 409
    api_key = "ak-" + hashlib.md5(email.encode()).hexdigest()[:10]
    cur.execute("INSERT INTO users(email,password,display_name,role,api_key) VALUES(?,?,?,'patient',?)",
                (email, pw, name, api_key))
    db().commit()
    return redirect("/login")

# ----------- Posts (V01 stored XSS) -----------
@app.route("/posts/new", methods=["GET","POST"])
def post_new():
    me = current_user()
    if not me: return redirect("/login")
    if request.method == "GET":
        return render_template("post_new.html", me=me)
    # V04 CSRF: 토큰 0
    title = request.form.get("title","")
    body  = request.form.get("body","")  # V01 raw 저장
    tag   = request.form.get("tag","general")
    cur = db().cursor()
    cur.execute("INSERT INTO posts(author_id,title,body,tag) VALUES(?,?,?,?)",
                (me["id"], title, body, tag))
    db().commit()
    return redirect(f"/posts/{cur.lastrowid}")

@app.route("/posts/<int:pid>")
def post_detail(pid):
    cur = db().cursor()
    cur.execute("SELECT p.*, u.display_name FROM posts p LEFT JOIN users u ON u.id=p.author_id WHERE p.id=?", (pid,))
    p = cur.fetchone()
    if not p: return "not found", 404
    cur.execute("""SELECT c.*, u.display_name FROM comments c LEFT JOIN users u ON u.id=c.author_id
                   WHERE c.post_id=? ORDER BY c.id""", (pid,))
    cmts = cur.fetchall()
    reported = request.args.get("reported") == "1"
    return render_template("post_detail.html", p=p, cmts=cmts, me=current_user(), reported=reported)

@app.route("/posts/<int:pid>/comment", methods=["POST"])
def comment_new(pid):
    me = current_user()
    if not me: return redirect("/login")
    body = request.form.get("body","")  # V02 stored XSS
    # V05 CSRF
    cur = db().cursor()
    cur.execute("INSERT INTO comments(post_id,author_id,body) VALUES(?,?,?)", (pid, me["id"], body))
    db().commit()
    return redirect(f"/posts/{pid}")

@app.route("/posts/<int:pid>/report", methods=["POST"])
def post_report(pid):
    """신고 버튼 — 누구나(로그인 없이도) 신고할 수 있다.

    신고된 글은 '관리자 검토 대기열'에 쌓이고, 관리자 콘솔(/admin)의 '신고 검토'에서
    관리자(봇)가 열어 본다. 6번 문제(저장형 XSS)의 '사람이 하는' 흐름을 만들어 준다.
    """
    me = current_user()
    reason = request.form.get("reason", "부적절한 내용")
    cur = db().cursor()
    cur.execute("INSERT INTO reports(kind,target_id,reporter_id,reason) VALUES('post',?,?,?)",
                (pid, me["id"] if me else 0, reason))
    db().commit()
    return redirect(f"/posts/{pid}?reported=1")

# ----------- Profile (V03/V06 + V17 mass assign) -----------
@app.route("/profile/<int:uid>")
def profile(uid):
    cur = db().cursor()
    cur.execute("SELECT * FROM users WHERE id=?", (uid,))
    u = cur.fetchone()
    if not u: return "not found", 404
    return render_template("profile.html", u=u, me=current_user())

@app.route("/profile/edit", methods=["GET","POST"])
def profile_edit():
    me = current_user()
    if not me: return redirect("/login")
    if request.method == "GET":
        return render_template("profile_edit.html", me=me)
    # V06 CSRF + V17 mass assign — form 필드 그대로 update
    fields = ["display_name","bio","phone","ssn","email","role","verified","api_key"]
    sets, vals = [], []
    for f in fields:
        if f in request.form:
            sets.append(f"{f}=?"); vals.append(request.form.get(f))
    if sets:
        vals.append(me["id"])
        cur = db().cursor()
        cur.execute(f"UPDATE users SET {','.join(sets)} WHERE id=?", vals)
        db().commit()
    return redirect(f"/profile/{me['id']}")

# ----------- Avatar upload (V19 SVG XSS) -----------
@app.route("/profile/avatar", methods=["POST"])
def avatar():
    me = current_user()
    if not me: return redirect("/login")
    f = request.files.get("file")
    if not f: return "no file", 400
    # V19: 확장자 검증 0, secure_filename 미사용
    fname = f"u{me['id']}_{int(time.time())}_{f.filename}"
    f.save(os.path.join(UPLOAD, fname))
    return jsonify({"ok": True, "url": f"/uploads/{fname}"})

@app.route("/uploads/<path:fn>")
def uploads(fn):
    # 직접 파일 반환 (Content-Type 추론)
    safe = os.path.join(UPLOAD, fn)
    if not os.path.isfile(safe):
        return "not found", 404
    with open(safe, "rb") as fp: data = fp.read()
    ext = fn.rsplit(".",1)[-1].lower()
    ct = {"png":"image/png","jpg":"image/jpeg","jpeg":"image/jpeg",
          "gif":"image/gif","svg":"image/svg+xml"}.get(ext,"application/octet-stream")
    resp = make_response(data); resp.headers["Content-Type"] = ct
    return resp

# ----------- DM (V18 stored XSS in private msg) -----------
@app.route("/dm")
def dm_inbox():
    me = current_user()
    if not me: return redirect("/login")
    cur = db().cursor()
    cur.execute("""SELECT d.*, u.display_name AS from_name FROM dms d LEFT JOIN users u ON u.id=d.from_id
                   WHERE d.to_id=? ORDER BY d.id DESC""", (me["id"],))
    return render_template("dm.html", msgs=cur.fetchall(), me=me)

@app.route("/dm/send", methods=["POST"])
def dm_send():
    me = current_user()
    if not me: return redirect("/login")
    to = int(request.form.get("to_id","0"))
    body = request.form.get("body","")  # V18 raw 저장
    cur = db().cursor()
    cur.execute("INSERT INTO dms(from_id,to_id,body) VALUES(?,?,?)", (me["id"], to, body))
    db().commit()
    return redirect("/dm")

# ----------- 회원 찾기 (V16 PII overshare) -----------
@app.route("/search")
def search():
    """화면은 껍데기고, 실제 데이터는 브라우저가 /api/users 를 호출해 가져온다.

    → 학생이 F12 → Network 탭만 열면 '이 페이지가 어떤 API 를 부르는지' 가 그대로 보인다.
      주소를 찍어서 맞히는 게 아니라, 눈으로 발견하는 정찰이다. (2번 문제의 정공법)
    """
    return render_template("search.html", q=request.args.get("q","").strip(), me=current_user())

# ----------- 진료기록 (V08/V09 IDOR) -----------
@app.route("/records")
def records_list():
    """진료기록 '목록' — 번호·날짜·담당의만 공개. (내용은 상세 페이지에서)

    목록이 공개인 것 자체는 설계 실수지만, 진짜 사고는 상세 페이지에 소유 검증이
    없다는 것이다(V09 IDOR). 학생은 목록에서 번호를 보고 상세로 들어간다.
    """
    cur = db().cursor()
    cur.execute("""SELECT m.id, m.visit_date, m.patient_id,
                          p.display_name AS patient_name, d.display_name AS doctor_name
                   FROM medical_records m
                   LEFT JOIN users p ON p.id=m.patient_id
                   LEFT JOIN users d ON d.id=m.doctor_id ORDER BY m.id""")
    return render_template("records.html", records=cur.fetchall(), me=current_user())

@app.route("/records/<int:rid>")
def record_detail(rid):
    # V09 IDOR: 이 기록이 '요청한 사람의 것인지' 를 전혀 확인하지 않는다.
    cur = db().cursor()
    cur.execute("""SELECT m.*, p.display_name AS patient_name, p.ssn AS patient_ssn,
                          d.display_name AS doctor_name FROM medical_records m
                   LEFT JOIN users p ON p.id=m.patient_id
                   LEFT JOIN users d ON d.id=m.doctor_id WHERE m.id=?""", (rid,))
    r = cur.fetchone()
    if not r:
        return render_template("record_detail.html", r=None, rid=rid, me=current_user()), 404
    return render_template("record_detail.html", r=r, rid=rid, me=current_user())

# ----------- Open redirect (V20) -----------
@app.route("/go")
def go():
    to = request.args.get("to","/")
    return redirect(to)  # V20: 검증 0

# ----------- API: PII / IDOR / Broken auth -----------
@app.route("/api/users")
def api_users():
    # V07: 인증 없이 전체 PII(email/ssn/phone/api_key) 노출. q 로 필터만 가능.
    q = request.args.get("q","").strip()
    cur = db().cursor()
    if q:
        like = f"%{q}%"
        cur.execute("""SELECT id,email,display_name,role,verified,phone,ssn,api_key,bio FROM users
                       WHERE display_name LIKE ? OR email LIKE ? OR bio LIKE ? OR role LIKE ?""",
                    (like, like, like, like))
    else:
        cur.execute("SELECT id,email,display_name,role,verified,phone,ssn,api_key,bio FROM users")
    return jsonify([dict(r) for r in cur.fetchall()])

@app.route("/api/users/<int:uid>")
def api_user_one(uid):
    # V11: api_key 를 query 로 받아도 통과
    key = request.args.get("api_key") or request.headers.get("X-API-Key")
    cur = db().cursor()
    cur.execute("SELECT * FROM users WHERE id=?", (uid,))
    u = cur.fetchone()
    if not u: return jsonify({"error":"not found"}), 404
    if key and key != u["api_key"]:
        # 그래도 IDOR 가능: api_key 만 맞추면 자기 것 아니어도 ok (V09 IDOR 변형)
        cur.execute("SELECT id FROM users WHERE api_key=?", (key,))
        if not cur.fetchone():
            return jsonify({"error":"bad key"}), 401
    return jsonify(dict(u))

@app.route("/api/medical-records")
def api_med_all():
    # V08 PII leak — 전체 환자 기록 인증 0
    cur = db().cursor()
    cur.execute("""SELECT m.*, p.display_name AS patient_name, p.ssn AS patient_ssn,
                          d.display_name AS doctor_name FROM medical_records m
                   LEFT JOIN users p ON p.id=m.patient_id
                   LEFT JOIN users d ON d.id=m.doctor_id ORDER BY m.id DESC""")
    return jsonify([dict(r) for r in cur.fetchall()])

@app.route("/api/medical-records/<int:rid>")
def api_med_one(rid):
    # V09 IDOR: 어떤 사용자도 다른 사람 기록 조회
    cur = db().cursor()
    cur.execute("SELECT * FROM medical_records WHERE id=?", (rid,))
    r = cur.fetchone()
    if not r: return jsonify({"error":"not found"}), 404
    # 의도적으로 patient_id 검증 0
    return jsonify(dict(r))

@app.route("/api/admin/users")
def api_admin_users():
    # V10 broken admin auth — 인증 0
    cur = db().cursor()
    cur.execute("SELECT * FROM users")
    return jsonify([dict(r) for r in cur.fetchall()])

@app.route("/api/admin/dms")
def api_admin_dms():
    # V10: 모든 DM 인증 0 — privacy leak
    cur = db().cursor()
    cur.execute("""SELECT d.*, f.display_name AS from_name, t.display_name AS to_name
                   FROM dms d LEFT JOIN users f ON f.id=d.from_id
                   LEFT JOIN users t ON t.id=d.to_id ORDER BY d.id DESC""")
    return jsonify([dict(r) for r in cur.fetchall()])

@app.route("/api/admin/reports")
def api_admin_reports():
    # V10: 신고 목록도 인증 0
    cur = db().cursor()
    cur.execute("""SELECT r.*, p.title AS post_title FROM reports r
                   LEFT JOIN posts p ON p.id=r.target_id ORDER BY r.id DESC""")
    return jsonify([dict(x) for x in cur.fetchall()])

@app.route("/api/profile", methods=["POST"])
def api_profile_update():
    # V17 mass assignment via JSON
    me = current_user()
    if not me:
        # V22 admin token 통과
        if request.headers.get("X-Admin-Token") != ADMIN_TOKEN:
            return jsonify({"error":"auth"}), 401
        me_id = 1
    else:
        me_id = me["id"]
    payload = request.get_json(silent=True) or {}
    fields = ["display_name","bio","phone","ssn","email","role","verified","api_key"]
    sets, vals = [], []
    for f in fields:
        if f in payload:
            sets.append(f"{f}=?"); vals.append(payload[f])
    if not sets:
        return jsonify({"error":"no fields"}), 400
    vals.append(me_id)
    cur = db().cursor()
    cur.execute(f"UPDATE users SET {','.join(sets)} WHERE id=?", vals)
    db().commit()
    cur.execute("SELECT * FROM users WHERE id=?", (me_id,))
    return jsonify(dict(cur.fetchone()))

# ----------- Verbose error (V21) -----------
@app.errorhandler(500)
def err500(e):
    tb = traceback.format_exc()
    return f"<h1>500 Internal Error</h1><pre>{tb}</pre>", 500

@app.route("/api/debug/echo")
def api_debug_echo():
    # V21: 의도적 raise — request 파라미터 stack에 노출
    raise RuntimeError(f"debug echo: q={request.args.get('q','')}")

# =============================================================================
#  관리자 영역 — 전부 '인증 0' (V10). CTF 4·5·6번의 무대.
# =============================================================================
@app.route("/admin")
def admin_console():
    """관리자 콘솔. 로그인 검사가 통째로 빠져 있어 누구나 열린다.

    robots.txt 에 적힌 /admin 을 보고 들어온 학생이 여기서
      · 쪽지 감사(4번)  · 관리자 전용 금고 링크(5번)  · 신고 검토(6번)
    로 자연스럽게 이어지도록 설계했다.
    """
    return render_template("admin.html", me=current_user())

@app.route("/admin/secret")
def admin_secret():
    """관리자 전용 금고. role=admin 인 세션만 통과한다(여기는 '제대로' 막혀 있다).

    막는 방법이 틀린 게 아니라, 세션 값이 예측 가능한 게 문제다(V14).
    MFSID 를 sess-1001 로 바꾸면 관리자로 인식된다 → 5번 문제.
    """
    me = current_user()
    want_json = "application/json" in (request.headers.get("Accept") or "") \
                or request.args.get("format") == "json"
    if me and me["role"] == "admin":
        if want_json:
            return jsonify({"area": "admin-only",
                            "msg": "관리자 전용 영역 진입 성공!",
                            "flag": FLAGS["session"]})
        return render_template("admin_secret.html", ok=True, flag=FLAGS["session"], me=me)
    if want_json:
        return jsonify({"error": "admin only — 관리자만 접근할 수 있습니다."}), 403
    return render_template("admin_secret.html", ok=False, flag=None, me=me), 403

@app.route("/admin/review")
def admin_review():
    """관리자(봇)의 신고 검토 화면.

    관리자 봇은 신고된 글을 '자기 브라우저로 열어 본다'. 글 본문에 <script> 가 심겨
    있으면 봇의 브라우저에서 그 스크립트가 실행된 것으로 간주하고(=저장형 XSS 성공)
    봇이 들고 있던 깃발이 화면에 노출된다 → 6번 문제.
    """
    cur = db().cursor()
    # 신고 대기열 (없으면 최근 글 3개를 '자동 순찰' 대상으로 본다)
    cur.execute("""SELECT r.id AS report_id, r.reason, r.created_at AS reported_at,
                          p.id AS post_id, p.title, p.body
                   FROM reports r LEFT JOIN posts p ON p.id=r.target_id
                   WHERE r.kind='post' ORDER BY r.id DESC LIMIT 20""")
    queue = [dict(x) for x in cur.fetchall()]
    if not queue:
        cur.execute("SELECT id AS post_id, title, body FROM posts ORDER BY id DESC LIMIT 3")
        queue = [dict(x, report_id=None, reason="(신고 없음 · 정기 순찰)", reported_at="") for x in cur.fetchall()]

    # 봇이 열어 본 모든 글·댓글에서 스크립트 흔적을 찾는다
    cur.execute("SELECT id, title, body FROM posts")
    scanned = [("post", r["id"], r["title"], r["body"] or "") for r in cur.fetchall()]
    cur.execute("SELECT id, body FROM comments")
    scanned += [("comment", r["id"], "(댓글)", r["body"] or "") for r in cur.fetchall()]

    pat = re.compile(r"<\s*script|onerror\s*=|onload\s*=|javascript:", re.I)
    hits = [{"kind": k, "id": i, "title": t, "snippet": (b or "")[:160]}
            for (k, i, t, b) in scanned if pat.search(b or "")]

    return render_template("admin_review.html", queue=queue, hits=hits,
                           flag=FLAGS["xss"] if hits else None, me=current_user())

# ----------- 헬스 -----------
@app.route("/_health")
def health():
    return {"ok": True, "service": "mediforum", "vulns": 22}

if __name__ == "__main__":
    init_db()
    ensure_ctf_flags()   # 사이트의 깃발 == challenges.yml 의 정답 (항상)
    port = int(os.environ.get("PORT","3003"))
    print(f"[mediforum] listening on :{port} (22 vulns, theme=medical, CTF flags re-seeded)")
    app.run(host="0.0.0.0", port=port, debug=False)
