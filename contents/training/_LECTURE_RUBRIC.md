# 집필 기준 — 고등학생 특강 골드 스탠다드

> tw2 트레이닝 기준서를 **비전공 고등학생** 대상에 맞게 조정한 버전.
> 모든 `lecture_weekNN.md` / `lab_weekNN.yaml` 는 이 기준을 따른다.

## 0. 절대 원칙
- **컴퓨터를 처음 만지는 고등학생** 이 독자다. 처음 나오는 모든 용어는 **그 자리에서 비유로** 설명한다.
- **노잼 금지.** 매 섹터는 "그래서 이걸 하면 뭐가 되는데?"에 즉시 답하고, 가능한 빨리 "우와!" 결과를 보여준다.
- **변수 금지.** 실습은 한 글자도 안 틀리게 따라하면 똑같은 결과가 나오도록 짠다. (DVWA는 Security Low 고정 등)
- **AI가 운전, 학생은 절차.** 어려운 건 Claude Code(AI 에이전트)가 하고, 학생은 "이거 → 다음 이거" 절차만 따른다.
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

## 4. 우리 인프라 사실 (지어내지 말 것)
- VM 2대: **공격자**(학생 Ubuntu + Claude Code + 브라우저/curl) ↔ **희생자**(Docker 호스트).
- 희생자 포트: DVWA `:8080`(admin/password, Security **Low**), NeoBank `:3001`, MediForum `:3003`,
  CTFd `:8000`. 보너스: govportal `:3002`, aicompanion `:3005`, adminconsole `:3004`, juiceshop `:3000`.
- 기동: `cd infra && ./start.sh`. sudo 비번이 필요하면 환경에 따름.
- 커스텀 사이트 출처: github.com/mrgrit/ccc/contents/vuln-sites.

## 5. 자가 점검
- [ ] ASCII 박스아트 0개, 모든 그림 mermaid 세로.
- [ ] 처음 나오는 용어·도구가 비유와 함께 설명됨.
- [ ] 실습을 그대로 따라하면 변수 없이 같은 결과.
- [ ] 한 줄 bullet 나열이 아니라 문장 설명.
- [ ] 인프라 사실(포트·로그인·경로)이 정확.
