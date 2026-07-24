# 집필 기준 — 고등학생 특강 골드 스탠다드

> tw2 트레이닝 기준서를 **비전공 고등학생** 대상에 맞게 조정한 버전.
> 모든 `lecture_weekNN.md` / `lab_weekNN.yaml` 와 특별 세션 `lecture_aiNN.md` / `lab_aiNN.yaml` 는
> 이 기준을 따른다.

## 0. 절대 원칙
- **컴퓨터를 처음 만지는 고등학생** 이 독자다. 처음 나오는 모든 용어는 **그 자리에서 비유로** 설명한다.
- **노잼 금지.** 매 섹터는 "그래서 이걸 하면 뭐가 되는데?"에 즉시 답하고, 가능한 빨리 "우와!" 결과를 보여준다.
- **변수 금지.** 실습은 한 글자도 안 틀리게 따라하면 똑같은 결과가 나오도록 짠다. (DVWA는 Security Low 고정 등)
- **AI가 운전, 학생은 절차.** 어려운 건 Hermes Agent(AI 에이전트 + DGX Spark 의 오픈 모델)가 하고, 학생은 "이거 → 다음 이거" 절차만 따른다.
- **브라우저 우선.** 모든 실습은 크롬/엣지 + F12 만으로 완주 가능해야 한다. `curl` 은 "같은 일을 기계가 하는 방식"으로 **병기**만 하고, 유일한 경로로 쓰지 않는다.
- 뒤 섹터로 갈수록 부실해지지 않게, 모든 주차가 같은 깊이를 유지한다.

## 1. 다이어그램 = mermaid 세로 그래픽 (ASCII 박스아트 금지)
- 모든 그림은 ```mermaid (graph TD/TB). 노드 라벨은 `<br/>` 로 줄바꿈.
- 색: 공격/위험 `#f85149`(빨강), 방어/정상 `#3fb950`(초록)·`#1f6feb`(파랑), 데이터/경고 `#d29922`(주황), 특수 `#bc8cff`(보라).

## 2. 교과서(lecture) 필수 구조
1. `# Week NN — <제목>`
2. `> 한 줄 요약` (인용블록, 2~3문장: 이번에 뭘·왜 하는지)
3. `## 학습 목표` : "학생은 ~을 직접 할 수 있다" 4~6개
4. `## 시간 배분` 표
5. `## 0. 용어 해설` : 표(용어|영문|뜻|비유) + 헷갈리는 핵심어는 일상 비유로 한 단락
6. 본문 `## 1, 2 …` : 개념마다 (한 줄 정의 → 왜 중요 → 어떻게 해보나 → 주의), mermaid 세로 그림
7. `## 실습 안내` : 각 실습마다 4축(왜 하나 / 무엇을 알게 되나 / 결과 해석 / 실전 의미)
8. `## 다음 주차 예고`
- 분량보다 **완결성**. 한 줄 bullet 나열 금지, 문장으로 설명.

## 3. 실습(lab.yaml) 구조
- 메타: `lab_id, title, course, week, description, difficulty, duration_minutes, prerequisites[], objectives[], pass_threshold, steps[]`
- step 마다: `order, instruction(🎯목표/개념 한 줄/💻실행/✅합격기준/🧰풀이), hint, category, points, answer, answer_detail, verify(type/expect/field), target`
- 고등학생용이므로 `instruction` 에 **클릭 위치·화면에 보일 것**까지 친절히 적는다.
- 에이전트를 쓰는 단계에는 **`## 🖱️ 브라우저로 직접 확인`** 절을 반드시 둔다.
  에이전트의 보고를 학생이 눈으로 교차 검증하게 하고, 재현되지 않으면 **환각**임을 가르친다.
- `answer` / `answer_detail` 은 **관리자 등급에게만** 렌더링된다(강좌 사이트 `site/app.py`).
  학생이 볼 화면을 기준으로 `instruction` 과 `hint` 만으로 풀 수 있어야 한다.

## 3.5 CTF·정답 관리 (사고 방지)
- **깃발의 단일 진실은 표적 코드**다. MediForum `app.py` 의 `FLAGS` 딕셔너리가 기준이고,
  부팅마다 `ensure_ctf_flags()` 가 DB 에 다시 심는다. `ctf/challenges.yml` 은 그 값과 같아야 한다.
- 문제 설명에 **"주소를 추측해 보세요"** 류를 쓰지 않는다. 화면에서 **발견 가능한 출발점**
  (robots.txt / F12 Network / 화면의 버튼)을 반드시 제시한다.
- 힌트는 3단계(0점 방향 → 저비용 위치 → 고비용 거의 정답)로 만든다.
- 수업 전 `ctf/verify_ctf.py --submit` 으로 표적↔정답표↔CTFd 3자 일치를 반드시 확인한다.

## 4. 우리 인프라 사실 (지어내지 말 것)
- 공격자 = 학생 리눅스(**Hermes Agent** + 브라우저). 희생자 = **학생 PC 각자**의 Docker 표적.
- 두뇌(LLM)는 외부 **DGX Spark** 의 Ollama(`http://<dgx>:11434/v1`)를 빌려 쓴다. Hermes 는 학생 PC 에 깐다.
- 강사 서버(hub) 1대: 강좌 사이트 `:8090` · CTFd `:8000` · AI 도우미 `:8001`.
- 표적 포트(학생 PC): DVWA `:8088`(admin/password, Security **Low**), NeoBank `:3001`,
  MediForum `:3003`, **AICompanion `:3005`**(특별 세션, 기본 mock 모드).
  보너스(extras): govportal `:3002`, adminconsole `:3004`, juiceshop `:3000`.
- 기동: `cd infra && ./start.sh hub|victim`. sudo 비번이 필요하면 환경에 따름.
- Hermes Agent 설치: `curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash`
  → `hermes setup` 에서 Custom Endpoint + `http://<dgx>:11434/v1` (**`/v1` 필수**).
- ⚠️ **도구 호출(tool calling)을 지원하는 모델만** 에이전트로 쓸 수 있다. 강사가 미리 검증한
  모델명을 지정한다(추론 특화 모델은 버전에 따라 도구 호출 불가).
- 커스텀 사이트 출처: github.com/mrgrit/ccc/contents/vuln-sites,
  github.com/mrgrit/el34/vuln-sites (AICompanion).

## 5. 자가 점검
- [ ] ASCII 박스아트 0개, 모든 그림 mermaid 세로.
- [ ] 처음 나오는 용어·도구가 비유와 함께 설명됨.
- [ ] 실습을 그대로 따라하면 변수 없이 같은 결과.
- [ ] 한 줄 bullet 나열이 아니라 문장 설명.
- [ ] 인프라 사실(포트·로그인·경로)이 정확.
- [ ] 모든 실습 단계가 **브라우저만으로** 완주 가능. curl 은 병기이지 유일 경로가 아님.
- [ ] 에이전트 단계에 브라우저 교차 검증 절이 있음.
- [ ] CTF 문제에 "추측하세요"가 없고, 발견 가능한 출발점이 명시됨.
