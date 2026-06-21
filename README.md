# 🕵️ AI로 배우는 웹 해킹 특강 (Easy Web Hacking Class)

> **"코드 한 줄 몰라도, AI 에이전트와 함께라면 진짜 해커가 하는 일을 직접 해볼 수 있다."**

컴퓨터를 잘 모르는 **고등학생(비전공)** 을 위한 체험형 웹 해킹 특강입니다. 어려운 기술은
**AI 에이전트(Claude Code)** 가 대신 해주고, 학생은 **"이거 해보고 → 다음은 이거"** 절차만
따라가며 "우와!" 하는 결과를 직접 만들어 냅니다.

- 🎯 **대상**: 컴퓨터/코딩을 몰라도 됨. 호기심만 있으면 OK
- 🤖 **방법**: 세세한 건 AI 에이전트가 해주고, 학생은 안전한 절차만 따라감
- 🧪 **결과**: 직접 만든 사이트, 직접 뚫는 웹, 친구들과 겨루는 미니 CTF

---

## 📚 전체 커리큘럼 (5개 섹터)

| 섹터 | 제목 | 시간 | 무엇을 하나 |
|------|------|------|-------------|
| **Week 01** | AI와 AI 에이전트, 그리고 윤리 | 4h | AI·에이전트가 뭔지 체험 + "해도 되는 것 / 안 되는 것" |
| **Week 02** | 리눅스·Claude Code 첫걸음 + 내 첫 웹사이트 + GitHub | 4h | 리눅스/CC 설치, **심리테스트 사이트** 직접 제작, GitHub 올리기 |
| **Week 03** | 웹의 작동 원리 + 직접 해보는 웹 해킹 (DVWA) | 7h | 웹 기초 → SQLi·XSS·CSRF·인증우회·파일업로드 직접 체험 |
| **Week 04** | AI 에이전트와 함께하는 모의해킹 (NeoBank) | 6h | 프롬프트로 step-by-step 가상 은행 모의해킹 |
| **Week 05** | 🏁 mini-CTF (MediForum + CTFd) | 4h+ | 배운 걸로 깃발(flag) 찾기, 실시간 리더보드 대결 |

> 9개 원래 모듈 ↔ 5개 섹터 매핑은 [`contents/training/_CURRICULUM.md`](contents/training/_CURRICULUM.md) 참고.

각 섹터는 **교과서(`lecture_weekNN.md`)** 와 **실습(`lab_weekNN.yaml`)** 한 쌍으로 구성됩니다.

```
contents/training/
  _CURRICULUM.md          # 5섹터 ↔ 9모듈 매핑 + 시간표
  _LECTURE_RUBRIC.md      # 집필 기준(골드 스탠다드)
  lecture_week01.md ~ 05  # 학생이 읽는 교과서
  lab_week01.yaml   ~ 05  # 따라하는 실습(스텝별 명령/정답/판정)
```

---

## 🖥️ 실습 환경 (희생자 / 공격자)

복잡한 인프라 없이 **VM 두 대**(또는 노트북 한 대)면 됩니다. 자세한 건 [`infra/README.md`](infra/README.md).

```bash
cd infra
./start.sh        # DVWA + NeoBank + MediForum + CTFd 한 번에 기동
```

| 사이트 | 주소 | 쓰는 곳 |
|--------|------|---------|
| DVWA | `:8080` | Week 03 웹 해킹 |
| NeoBank | `:3001` | Week 04 AI 모의해킹 |
| MediForum | `:3003` | Week 05 CTF 표적 |
| CTFd | `:8000` | Week 05 CTF 플랫폼 |

---

## 🏁 mini-CTF (Week 05)

- CTFd 기반: **회원가입 / 실시간 리더보드 / AI 질문·답변 연동**
- 문제·정답 일괄 등록: [`ctf/`](ctf/)
- **강사(admin) 전용 상세 풀이**: [`solutions/`](solutions/) — flag 획득법을 한 단계도 빠짐없이 설명 (※ 학생 배부 전 비공개 유지)

---

## ⚠️ 안전·윤리 고지

이 자료의 모든 사이트는 **교육용으로 일부러 취약하게** 만든 것입니다.

- 반드시 **본인 소유 / 허가된 폐쇄망 실습 환경**에서만 사용하세요.
- 실제 타인의 웹사이트를 허락 없이 공격하는 것은 **범죄**입니다 (정보통신망법).
- 자세한 윤리 가이드는 **Week 01** 에서 다룹니다.

커스텀 취약 사이트는 [mrgrit/ccc](https://github.com/mrgrit/ccc/tree/main/contents/vuln-sites) 에서 가져왔습니다.
