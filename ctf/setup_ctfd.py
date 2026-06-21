#!/usr/bin/env python3
"""
CTFd 최초 셋업(관리자 생성) + Access Token 발급 자동화.
이미 셋업돼 있으면 관리자 로그인으로 전환해 토큰만 발급한다.

사용:
  python3 setup_ctfd.py --ctfd http://localhost:8000 \
      --admin admin --password ezweb-admin-2026 --email admin@ezweb.local
출력 마지막 줄: TOKEN=<발급된 토큰>
"""
import argparse, re, sys
try:
    import requests
except ImportError:
    sys.exit("pip install requests")


def nonce_from(html, field="nonce"):
    m = re.search(r'name="%s"[^>]*value="([^"]+)"' % field, html) or \
        re.search(r'value="([^"]+)"[^>]*name="%s"' % field, html)
    return m.group(1) if m else None


def csrf_from(html):
    m = re.search(r"csrfNonce['\"]?\s*[:=]\s*['\"]([a-f0-9]+)['\"]", html)
    return m.group(1) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ctfd", required=True)
    ap.add_argument("--admin", default="admin")
    ap.add_argument("--password", required=True)
    ap.add_argument("--email", default="admin@ezweb.local")
    ap.add_argument("--ctf-name", default="AI 웹 해킹 특강 mini-CTF")
    a = ap.parse_args()
    base = a.ctfd.rstrip("/")
    s = requests.Session()

    r = s.get(base + "/setup", allow_redirects=True)
    if "/setup" in r.url and nonce_from(r.text):
        # 신규 셋업
        nonce = nonce_from(r.text)
        data = {
            "ctf_name": a.ctf_name,
            "ctf_description": "배운 기법으로 깃발을 찾는 mini-CTF (표적: MediForum)",
            "user_mode": "users",
            "name": a.admin, "email": a.email, "password": a.password,
            "ctf_theme": "core-beta", "theme_color": "",
            "start": "", "end": "", "nonce": nonce,
        }
        rr = s.post(base + "/setup", data=data, allow_redirects=True)
        if rr.status_code not in (200, 302) or "/setup" in rr.url:
            print("[!] 셋업 실패, 상태", rr.status_code, rr.url, file=sys.stderr)
            sys.exit(1)
        print(f"[+] 관리자 생성 완료: {a.admin} / {a.password}")
    else:
        # 이미 셋업됨 → 로그인
        lp = s.get(base + "/login")
        nonce = nonce_from(lp.text)
        s.post(base + "/login", data={"name": a.admin, "password": a.password, "nonce": nonce})
        print("[+] 기존 관리자로 로그인")

    # CSRF 확보 후 토큰 발급
    page = s.get(base + "/settings")
    csrf = csrf_from(page.text) or csrf_from(s.get(base + "/").text)
    if not csrf:
        print("[!] csrfNonce 를 찾지 못함", file=sys.stderr); sys.exit(1)
    tr = s.post(base + "/api/v1/tokens",
                headers={"CSRF-Token": csrf, "Content-Type": "application/json"},
                json={"description": "challenge import"})
    if tr.status_code != 200:
        print("[!] 토큰 발급 실패:", tr.status_code, tr.text[:200], file=sys.stderr); sys.exit(1)
    token = tr.json()["data"]["value"]
    print(f"TOKEN={token}")


if __name__ == "__main__":
    main()
