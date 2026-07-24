#!/usr/bin/env python3
"""
mini-CTF 문제 일괄 등록기 — challenges.yml 을 읽어 CTFd 에 문제/깃발/힌트를 만든다.

사용법:
  1) CTFd(:8000) 최초 관리자 셋업을 끝낸다. (setup_ctfd.py 가 자동으로 해 준다)
  2) CTFd → Settings → Access Tokens 에서 토큰을 발급한다.
  3) 실행:
       pip install requests pyyaml
       python3 import_challenges.py \
         --ctfd http://localhost:8000 \
         --token <ACCESS_TOKEN> \
         --victim <희생자IP 또는 호스트>   # 예: 192.168.0.50 / localhost

  이미 등록된 문제를 싹 지우고 다시 넣으려면:
       python3 import_challenges.py ... --replace

문제 설명의 {VICTIM} 자리는 --victim 값으로 치환된다.

────────────────────────────────────────────────────────────────────────
⚠️ 과거 버그 메모 (같은 실수 반복 금지)
   예전 버전은 깃발을 만들 때 {"challenge": <id>} 를 보냈는데, CTFd 의 Flag/Hint
   스키마가 기대하는 필드명은 **challenge_id** 다. 알 수 없는 필드는 조용히 버려지고
   challenge_id 가 비어 있는(= 어떤 문제에도 연결되지 않은) 깃발이 만들어졌다.
   결과: 문제에 깃발이 0개 → 학생이 정답을 넣어도 전부 "Incorrect".
   그래서 이 스크립트는 등록 후 **반드시 재조회로 연결 상태를 검증**한다.
────────────────────────────────────────────────────────────────────────
"""
import argparse, re, sys
try:
    import requests, yaml
except ImportError:
    sys.exit("먼저: pip install requests pyyaml")


def api(sess, base, method, path, **kw):
    r = sess.request(method, f"{base}{path}", **kw)
    try:
        body = r.json()
    except Exception:
        body = {"raw": r.text[:300]}
    return r.status_code, body


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ctfd", required=True, help="CTFd 주소 (예: http://localhost:8000)")
    ap.add_argument("--token", required=True, help="CTFd Access Token")
    ap.add_argument("--victim", required=True, help="희생자 IP/호스트 (문제의 {VICTIM} 치환)")
    ap.add_argument("--file", default="challenges.yml")
    ap.add_argument("--replace", action="store_true",
                    help="기존에 등록된 문제를 모두 삭제한 뒤 새로 등록")
    args = ap.parse_args()

    base = args.ctfd.rstrip("/")
    s = requests.Session()
    s.headers.update({
        "Authorization": f"Token {args.token}",
        "Content-Type": "application/json",
    })

    with open(args.file, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    def sub(text):
        return (text or "").replace("{VICTIM}", args.victim)

    # ---- 0) 기존 문제 정리 (--replace) -------------------------------------
    code, body = api(s, base, "GET", "/api/v1/challenges?view=admin")
    if code != 200:
        sys.exit(f"[!] CTFd API 접속 실패({code}). 토큰/주소를 확인하세요: {body}")
    existing = body.get("data", [])
    if existing and args.replace:
        for ch in existing:
            api(s, base, "DELETE", f"/api/v1/challenges/{ch['id']}")
        print(f"[i] 기존 문제 {len(existing)}개 삭제 (--replace)")
    elif existing:
        print(f"[!] 이미 문제 {len(existing)}개가 등록돼 있습니다. "
              f"다시 넣으려면 --replace 를 붙이세요.")
        sys.exit(1)

    created, cids = 0, []
    for ch in data["challenges"]:
        # ---- 1) 문제 생성 --------------------------------------------------
        payload = {
            "name": ch["name"],
            "category": ch["category"],
            "description": sub(ch["description"]),
            "value": ch["value"],
            "type": "standard",
            "state": "visible",
            "connection_info": f"http://{args.victim}:3003",
        }
        code, body = api(s, base, "POST", "/api/v1/challenges", json=payload)
        if code != 200 or not body.get("success"):
            print(f"[!] 문제 생성 실패: {ch['name']} -> {code} {body}")
            continue
        cid = body["data"]["id"]
        cids.append((cid, ch))
        print(f"[+] 문제 생성: #{cid} {ch['name']} ({ch['value']}점)")

        # ---- 2) 깃발 등록 --------------------------------------------------
        flag = ch["flag"]
        inner = flag[len("flag{"):-1] if flag.startswith("flag{") and flag.endswith("}") else flag
        # (a) 정적 깃발 — 정확히 일치(대소문자 무시)
        code, body = api(s, base, "POST", "/api/v1/flags", json={
            "challenge_id": cid, "content": flag,
            "type": "static", "data": "case_insensitive"})
        if code != 200 or not body.get("success"):
            print(f"    [!] 정적 깃발 등록 실패: {code} {body}")
        # (b) 정규식 깃발 — 관용 채점.
        #     실제 수업에서 관측된 오답 7건 중 5건이 **중괄호를 빼고 제출**한 경우였다
        #     (예: flag{v13w_s0urc3_r3con} 대신 v13w_s0urc3_r3con).
        #     비전공 고등학생 대상이므로, 앞뒤 공백·대소문자·중괄호 누락까지 정답 처리한다.
        #     (교재에서는 "중괄호까지 통째로" 가 원칙이라고 계속 가르친다)
        tolerant = rf"^\s*(flag\{{)?{re.escape(inner)}(\}})?\s*$"
        code, body = api(s, base, "POST", "/api/v1/flags", json={
            "challenge_id": cid, "content": tolerant,
            "type": "regex", "data": "case_insensitive"})
        if code != 200 or not body.get("success"):
            print(f"    [!] 정규식(관용) 깃발 등록 실패: {code} {body}")

        # ---- 3) 힌트 등록 --------------------------------------------------
        for h in ch.get("hints", []):
            code, body = api(s, base, "POST", "/api/v1/hints", json={
                "challenge_id": cid, "content": sub(h["content"]), "cost": h.get("cost", 0)})
            if code != 200 or not body.get("success"):
                print(f"    [!] 힌트 등록 실패: {code} {body}")

        created += 1

    # ---- 4) 검증: 깃발이 정말 그 문제에 붙었는가 ---------------------------
    print("\n── 등록 검증 ──────────────────────────────────────────")
    problems = 0
    for cid, ch in cids:
        code, body = api(s, base, "GET", f"/api/v1/challenges/{cid}/flags")
        flags = body.get("data", []) if code == 200 else []
        linked = [f for f in flags if f.get("challenge_id") == cid]
        static_ok = any(f.get("type") == "static" and f.get("content") == ch["flag"] for f in linked)
        code_h, body_h = api(s, base, "GET", f"/api/v1/challenges/{cid}/hints")
        hints = body_h.get("data", []) if code_h == 200 else []
        mark = "✓" if (static_ok and len(linked) >= 1) else "✗"
        if mark == "✗":
            problems += 1
        print(f"  {mark} #{cid} {ch['name']:<24} 깃발 {len(linked)}개 · 힌트 {len(hints)}개")

    print("─────────────────────────────────────────────────────")
    print(f"완료: {created}/{len(data['challenges'])} 문제 등록.")
    if problems:
        print(f"[!] {problems}개 문제의 깃발 연결이 확인되지 않았습니다 — 학생이 정답을 넣어도 오답 처리됩니다.")
        print("    CTFd 버전/토큰 권한을 확인하고 --replace 로 다시 시도하세요.")
    else:
        print("모든 문제에 깃발이 정상 연결되었습니다.")
    print(f"\n리더보드: {base}/scoreboard   문제: {base}/challenges")
    print(f"실제 정답 처리까지 확인하려면:  python3 verify_ctf.py --ctfd {base} "
          f"--victim {args.victim} --token <TOKEN>")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
