"""
AI 웹 해킹 특강 — 강좌 포털 웹사이트.

학생이 한 곳에서 커리큘럼을 보고, 교과서(lecture)·실습(lab)을 브라우저에서 바로 읽고,
실습 워크북·해킹 서약서를 다운로드한다.

⚠️ 보안: 이 서버는 '학생에게 보여도 되는 것'만 화이트리스트로 노출한다.
   - 교과서 lecture_weekNN.md, 실습 lab_weekNN.yaml, downloads/ 의 배부 자료만 제공.
   - solutions/(정답 풀이), ctf/challenges.yml(flag), seed/vulnerabilities.md 등은 절대 서빙하지 않는다.

실행: PORT(기본 8090). docker-compose 의 course-site 서비스로 기동하거나,
      로컬에서 `python3 app.py` (레포 루트 기준 경로 자동 탐색).
"""
from __future__ import annotations
import os, re, html
from pathlib import Path
from flask import Flask, render_template, abort, send_from_directory

BASE = Path(__file__).resolve().parent


def _find(*cands: str) -> Path:
    for c in cands:
        if c and Path(c).exists():
            return Path(c)
    return Path(cands[-1])


# 컨텐츠 경로 — 도커(이미지 내 복사본)와 로컬(레포 구조) 모두 지원
CONTENT = _find(os.environ.get("CONTENT_DIR", ""),
                str(BASE.parent / "content" / "training"),   # 도커: COPY contents/training → /app/content/training
                str(BASE.parent / "contents" / "training"),  # 혹시 모를 배치
                str(BASE.parent.parent / "contents" / "training"),  # 로컬: 레포/contents/training
                "/app/content/training")
DOWNLOADS = _find(os.environ.get("DOWNLOADS_DIR", ""),
                  str(BASE.parent / "downloads"),
                  str(BASE.parent.parent / "downloads"),
                  "/app/downloads")

WEEKS = {
    "01": {"title": "AI와 AI 에이전트, 그리고 윤리",
           "hook": "AI·에이전트를 만져보고, 해도 되는 것과 안 되는 것을 약속한다.",
           "hours": "4시간", "emoji": "🤖"},
    "02": {"title": "리눅스·Claude Code 첫걸음 + 내 첫 웹사이트 + GitHub",
           "hook": "터미널과 친해지고, AI와 함께 심리테스트 사이트를 만들어 GitHub에 올린다.",
           "hours": "4시간", "emoji": "🐧"},
    "03": {"title": "웹의 작동 원리 + 직접 해보는 웹 해킹 (DVWA)",
           "hook": "웹이 어떻게 움직이는지 보고, SQLi·XSS·CSRF·웹셸을 내 손으로 뚫는다.",
           "hours": "7시간", "emoji": "🕸️"},
    "04": {"title": "AI 에이전트와 함께하는 모의해킹 (NeoBank)",
           "hook": "프롬프트만 복사해 붙이면 AI가 가상 은행을 점검한다.",
           "hours": "6시간", "emoji": "🏦"},
    "05": {"title": "mini-CTF (MediForum + CTFd)",
           "hook": "배운 걸로 깃발을 찾아 친구들과 실시간 리더보드 대결!",
           "hours": "4시간+", "emoji": "🏁"},
}

# 주차별 실습 페이지에서 내려받게 할 배부 자료(.docx). Week01 엔 보안서약서도 함께.
WEEK_DOWNLOADS = {
    "01": ["보안서약서.docx", "실습워크북_Week01.docx"],
    "02": ["실습워크북_Week02.docx"],
    "03": ["실습워크북_Week03.docx"],
    "04": ["실습워크북_Week04.docx"],
    "05": ["실습워크북_Week05.docx"],
}

app = Flask(__name__)


def render_markdown(text: str) -> str:
    import markdown
    md = markdown.Markdown(extensions=["tables", "fenced_code", "toc", "sane_lists", "attr_list"])
    body = md.convert(text)
    # ```mermaid 코드블록 → <div class="mermaid"> 로 변환(클라이언트에서 다이어그램 렌더)
    def to_mermaid(m):
        return '<div class="mermaid">' + html.unescape(m.group(1)) + '</div>'
    body = re.sub(r'<pre><code class="language-mermaid">(.*?)</code></pre>',
                  to_mermaid, body, flags=re.S)
    return body


@app.route("/")
def index():
    return render_template("index.html", weeks=WEEKS, downloads=_list_downloads())


@app.route("/lecture/<week>")
def lecture(week):
    if week not in WEEKS:
        abort(404)
    f = CONTENT / f"lecture_week{week}.md"
    if not f.exists():
        abort(404)
    body = render_markdown(f.read_text(encoding="utf-8"))
    return render_template("doc.html", body=body, week=week, kind="교과서",
                           weeks=WEEKS, has_mermaid=True)


@app.route("/lab/<week>")
def lab(week):
    if week not in WEEKS:
        abort(404)
    f = CONTENT / f"lab_week{week}.yaml"
    if not f.exists():
        abort(404)
    import yaml
    data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    p = []
    p.append(f"<h1>실습 {week} — {html.escape(str(data.get('title','')))}</h1>")
    try:
        thr = int(float(data.get("pass_threshold", 0)) * 100)
    except Exception:
        thr = 0
    p.append(f"<blockquote>난이도 <b>{html.escape(str(data.get('difficulty','')))}</b> · "
             f"약 {data.get('duration_minutes','?')}분 · 통과 기준 {thr}%</blockquote>")
    # 이 주차 배부 자료(.docx) 다운로드 링크
    dls = [f for f in WEEK_DOWNLOADS.get(week, []) if (DOWNLOADS / f).is_file()]
    if dls:
        links = " · ".join(f'<a href="/download/{f}">📄 {f}</a>' for f in dls)
        p.append(f'<div class="dlbox">⬇️ <b>이 주차 자료</b> (다운로드): {links}</div>')
    if data.get("description"):
        p.append(render_markdown(str(data["description"])))
    objs = data.get("objectives") or []
    if objs:
        p.append("<h2>학습 목표</h2>")
        p.append(render_markdown("\n".join(f"{i+1}. {o}" for i, o in enumerate(objs))))
    p.append("<hr>")
    for st in data.get("steps", []):
        p.append(f'<h2>단계 {st.get("order","")} '
                 f'<span class="stepmeta">{html.escape(str(st.get("category","")))} · '
                 f'{st.get("points","")}점</span></h2>')
        p.append(render_markdown(str(st.get("instruction", ""))))
        if st.get("hint"):
            p.append(f'<p class="hint">💡 <b>힌트:</b> {html.escape(str(st["hint"]))}</p>')
        ans = str(st.get("answer", "") or "").strip()
        ad = str(st.get("answer_detail", "") or "").strip()
        if ans or ad:
            det = "<details class='ans'><summary>정답·해설 보기 (강사·복습용)</summary>"
            if ans:
                det += render_markdown("```\n" + ans + "\n```")
            if ad:
                det += render_markdown(ad)
            det += "</details>"
            p.append(det)
        p.append("<hr>")
    return render_template("doc.html", body="\n".join(p), week=week, kind="실습",
                           weeks=WEEKS, has_mermaid=False)


def _list_downloads():
    if not DOWNLOADS.exists():
        return []
    out = []
    for p in sorted(DOWNLOADS.iterdir()):
        if p.is_file() and p.suffix.lower() in (".md", ".html", ".pdf", ".docx"):
            out.append(p.name)
    return out


@app.route("/download/<path:fn>")
def download(fn):
    # 화이트리스트: downloads/ 안의 파일만, 경로 이탈 차단
    safe = os.path.basename(fn)
    if safe != fn or not (DOWNLOADS / safe).is_file():
        abort(404)
    return send_from_directory(DOWNLOADS, safe, as_attachment=True)


@app.route("/_health")
def health():
    return {"ok": True, "service": "course-site",
            "content": str(CONTENT), "downloads": str(DOWNLOADS)}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8090"))
    print(f"[course-site] listening on :{port}  content={CONTENT}  downloads={DOWNLOADS}")
    app.run(host="0.0.0.0", port=port)
