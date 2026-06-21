#!/usr/bin/env python3
"""
주차별 실습 워크북(.docx) 생성기.
contents/training/lab_weekNN.yaml 을 읽어 각 주차의 단계 수에 맞춘 기록표가 든
실습워크북_WeekNN.docx 를 downloads/ 에 만든다. flag·정답은 넣지 않는다(빈 양식).

실행:
    pip install python-docx pyyaml
    python3 downloads/build_docx.py        # 레포 루트에서
"""
from pathlib import Path
import yaml
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

ROOT = Path(__file__).resolve().parent.parent
LABS = ROOT / "contents" / "training"
OUT = ROOT / "downloads"

WEEK_TITLES = {
    "01": "AI와 AI 에이전트, 그리고 윤리",
    "02": "리눅스·Claude Code 첫걸음 + 내 첫 웹사이트 + GitHub",
    "03": "웹의 작동 원리 + 직접 해보는 웹 해킹 (DVWA)",
    "04": "AI 에이전트와 함께하는 모의해킹 (NeoBank)",
    "05": "mini-CTF (MediForum + CTFd)",
}


def blank_line(doc, label):
    p = doc.add_paragraph()
    run = p.add_run(label + "  ")
    run.bold = True
    p.add_run("________________________________________________")


def build(week):
    lab = yaml.safe_load((LABS / f"lab_week{week}.yaml").read_text(encoding="utf-8"))
    steps = lab.get("steps", [])

    doc = Document()
    # 제목
    h = doc.add_heading(f"AI 웹 해킹 특강 — 실습 워크북", level=0)
    sub = doc.add_heading(f"Week {week} · {WEEK_TITLES.get(week,'')}", level=1)

    # 표지 정보
    doc.add_paragraph()
    for lbl in ["이름", "학교 / 반", "날짜"]:
        blank_line(doc, lbl)
    doc.add_paragraph("☐ 나는 ‘해킹 윤리 서약서’에 서명했다.")

    # 오늘의 목표
    doc.add_heading("1. 오늘의 목표 (읽고 한 줄로 옮겨 적기)", level=2)
    blank_line(doc, "→")

    # 새로 배운 용어
    doc.add_heading("2. 새로 배운 용어 3개", level=2)
    t = doc.add_table(rows=4, cols=2)
    t.style = "Table Grid"
    t.rows[0].cells[0].text = "용어"
    t.rows[0].cells[1].text = "내가 이해한 뜻 (한 줄)"
    for i in range(1, 4):
        t.rows[i].cells[0].text = ""
        t.rows[i].cells[1].text = ""

    # 실습 기록표
    doc.add_heading("3. 실습 기록표", level=2)
    doc.add_paragraph("각 단계를 해보고 결과를 적으세요. (정확한 명령·정답은 교과서를 보고 직접 채웁니다)")
    tbl = doc.add_table(rows=len(steps) + 1, cols=5)
    tbl.style = "Table Grid"
    hdr = ["단계", "무엇을 했나", "결과", "화면에서 본 것 / 메모", "막힌 점"]
    for j, htext in enumerate(hdr):
        c = tbl.rows[0].cells[j]
        c.text = htext
        for r in c.paragraphs[0].runs:
            r.bold = True
    for i, st in enumerate(steps, start=1):
        row = tbl.rows[i].cells
        cat = st.get("category", "")
        row[0].text = f"{st.get('order', i)}\n({cat})"
        row[1].text = ""
        row[2].text = "성공 ☐\n실패 ☐"
        row[3].text = ""
        row[4].text = ""

    # 우와 포인트 / 회고 / 윤리
    doc.add_heading("4. 오늘의 ‘우와!’ 포인트", level=2)
    blank_line(doc, "→")
    doc.add_heading("5. 한 줄 회고", level=2)
    blank_line(doc, "→")
    doc.add_heading("6. 윤리 체크", level=2)
    doc.add_paragraph("☐ 나는 허락된 표적(실습 환경)에서만 공격/점검을 했다.")

    out = OUT / f"실습워크북_Week{week}.docx"
    doc.save(str(out))
    print(f"  생성: {out.name}  (단계 {len(steps)}개)")


if __name__ == "__main__":
    print("주차별 워크북(.docx) 생성 중...")
    for wk in WEEK_TITLES:
        build(wk)
    print("완료.")
