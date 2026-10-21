"""Turns issue JSON into static HTML pages (docs/ is served by GitHub Pages)."""
import html, json
from pathlib import Path

TOPICS = {
    "mcp": ("MCP", "#2F5BEA"),
    "audience_data": ("Audience data", "#0E8F7E"),
    "partnerships": ("Partnerships", "#B7791F"),
    "mna": ("M&A", "#8E3B8C"),
    "product": ("New products", "#C2410C"),
}

CSS = """
:root{--bg:#F6F8FA;--ink:#14202B;--mute:#5B6875;--rule:#D9DEE4;--card:#fff}
@media(prefers-color-scheme:dark){:root{--bg:#10161C;--ink:#E7ECF1;--mute:#97A4B1;--rule:#26313B;--card:#161E26}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.55 "Instrument Sans",system-ui,sans-serif}
main{max-width:46rem;margin:0 auto;padding:3rem 1.25rem 5rem}
h1{font:600 2.4rem/1.1 Newsreader,Georgia,serif;margin:0 0 .4rem;letter-spacing:-.01em}
.sub{color:var(--mute);margin:0 0 2rem}
.chips{display:flex;flex-wrap:wrap;gap:.5rem;margin-bottom:2rem}
.chips button{font:inherit;font-size:.9rem;border:1px solid var(--rule);background:var(--card);color:var(--ink);
 padding:.35rem .8rem;border-radius:99px;cursor:pointer}
.chips button[aria-pressed=true]{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.chips button:focus-visible,a:focus-visible{outline:3px solid #2F5BEA;outline-offset:2px}
article{background:var(--card);border-left:6px solid var(--c);padding:1.1rem 1.3rem;margin:0 0 1rem;border-radius:4px}
article[hidden]{display:none}
article h2{font:600 1.3rem/1.25 Newsreader,Georgia,serif;margin:0 0 .35rem}
article h2 a{color:inherit;text-decoration:none}article h2 a:hover{text-decoration:underline}
.meta{font-size:.85rem;color:var(--mute);margin:0 0 .6rem}
article p{margin:.3rem 0;max-width:68ch}.why{color:var(--mute)}
.past{margin-top:3rem;border-top:1px solid var(--rule);padding-top:1rem;font-size:.95rem}
.past a{color:var(--ink);margin-right:1rem}
"""

JS = """
const chips=[...document.querySelectorAll('.chips button')];
chips.forEach(b=>b.addEventListener('click',()=>{
 chips.forEach(x=>x.setAttribute('aria-pressed',x===b));
 const t=b.dataset.t;
 document.querySelectorAll('article').forEach(a=>a.hidden=t!=='all'&&a.dataset.t!==t);
}));
"""

def _e(s): return html.escape(str(s or ""))

def render_issue(issue, past_dates):
    stories = issue["stories"]
    counts = {k: sum(s["topic"] == k for s in stories) for k in TOPICS}
    chips = f'<button data-t="all" aria-pressed="true">All ({len(stories)})</button>' + "".join(
        f'<button data-t="{k}" aria-pressed="false">{TOPICS[k][0]} ({n})</button>' for k, n in counts.items() if n)
    cards = ""
    for s in stories:
        label, color = TOPICS.get(s["topic"], ("Other", "#5B6875"))
        co = ", ".join(s.get("companies", []))
        cards += (f'<article data-t="{_e(s["topic"])}" style="--c:{color}">'
                  f'<h2><a href="{_e(s["url"])}" rel="noopener">{_e(s["headline"])}</a></h2>'
                  f'<p class="meta">{label}, {_e(s.get("source"))}, {_e(s.get("published"))}'
                  f'{", " + _e(co) if co else ""}{", confidence: " + _e(s["confidence"]) if s.get("confidence") not in (None, "high") else ""}</p>'
                  f'<p>{_e(s.get("summary"))}</p><p class="why">{_e(s.get("why_it_matters"))}</p></article>')
    if not stories:
        cards = "<p>No new stories found in this window.</p>"
    past = "".join(f'<a href="{d}.html">{d}</a>' for d in past_dates)
    past_html = f'<nav class="past" aria-label="Past issues">Past issues: {past}</nav>' if past else ""
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>Madtech Radar, {issue["date"]}</title>'
            f'<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;600&family=Newsreader:wght@600&display=swap">'
            f'<style>{CSS}</style></head><body><main>'
            f'<h1>Madtech Radar</h1><p class="sub">{_e(issue["window_start"])} to {_e(issue["date"])}. '
            f'{len(stories)} stories on MCP, audience data, partnerships, M&amp;A and product launches.</p>'
            f'<div class="chips">{chips}</div>{cards}{past_html}</main><script>{JS}</script></body></html>')

def build_site(issues_dir: Path, site_dir: Path):
    site_dir.mkdir(exist_ok=True)
    files = sorted(issues_dir.glob("*.json"), reverse=True)
    dates = [f.stem for f in files]
    for f in files:
        (site_dir / f"{f.stem}.html").write_text(
            render_issue(json.loads(f.read_text()), dates), encoding="utf-8")
    if files:
        (site_dir / "index.html").write_text(
            render_issue(json.loads(files[0].read_text()), dates[1:]), encoding="utf-8")
