#!/usr/bin/env python3
"""
mini-CTF 문제 일괄 등록기 — challenges.yml 을 읽어 CTFd 에 문제/깃발/힌트를 만든다.

사용법:
  1) CTFd(:8000) 최초 관리자 셋업을 끝낸다.
  2) CTFd → Settings → Access Tokens 에서 토큰을 발급한다.
  3) 실행:
       pip install requests pyyaml
       python3 import_challenges.py \
         --ctfd http://localhost:8000 \
         --token <ACCESS_TOKEN> \
         --victim <희생자IP 또는 호스트>   # 예: 192.168.0.50 / localhost

문제 설명의 {VICTIM} 자리는 --victim 값으로 치환된다.
"""
import argparse, sys
try:
    import requests, yaml
except ImportError:
    sys.exit("먼저: pip install requests pyyaml")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ctfd", required=True, help="CTFd 주소 (예: http://localhost:8000)")
    ap.add_argument("--token", required=True, help="CTFd Access Token")
    ap.add_argument("--victim", required=True, help="희생자 IP/호스트 (문제의 {VICTIM} 치환)")
    ap.add_argument("--file", default="challenges.yml")
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

    created = 0
    for ch in data["challenges"]:
        # 1) 문제 생성
        payload = {
            "name": ch["name"],
            "category": ch["category"],
            "description": sub(ch["description"]),
            "value": ch["value"],
            "type": "standard",
            "state": "visible",
            "connection_info": f"http://{args.victim}:3003",
        }
        r = s.post(f"{base}/api/v1/challenges", json=payload)
        if r.status_code != 200 or not r.json().get("success"):
            print(f"[!] 문제 생성 실패: {ch['name']} -> {r.status_code} {r.text[:200]}")
            continue
        cid = r.json()["data"]["id"]
        print(f"[+] 문제 생성: #{cid} {ch['name']} ({ch['value']}점)")

        # 2) 깃발 등록 (정적, 정확히 일치)
        r = s.post(f"{base}/api/v1/flags", json={
            "challenge": cid, "content": ch["flag"], "type": "static", "data": ""})
        if r.status_code != 200:
            print(f"    [!] 깃발 등록 실패: {r.text[:160]}")

        # 3) 힌트 등록
        for h in ch.get("hints", []):
            r = s.post(f"{base}/api/v1/hints", json={
                "challenge": cid, "content": h["content"], "cost": h.get("cost", 0)})
            if r.status_code != 200:
                print(f"    [!] 힌트 등록 실패: {r.text[:160]}")

        created += 1

    print(f"\n완료: {created}/{len(data['challenges'])} 문제 등록.")
    print(f"리더보드: {base}/scoreboard   문제: {base}/challenges")


if __name__ == "__main__":
    main()
