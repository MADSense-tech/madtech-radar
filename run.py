"""Madtech Radar: run twice a week. Usage: python run.py"""
import asyncio, datetime as dt, json, os, re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from claude_agent_sdk import query, ClaudeAgentOptions, AgentDefinition, ResultMessage
from render import build_site
import mailer

ROOT = Path(__file__).parent
DATA, ISSUES, SITE = ROOT / "data", ROOT / "data/issues", ROOT / "docs"
STATE_F = DATA / "state.json"
TODAY = dt.date.today().isoformat()

try:
    state = json.loads(STATE_F.read_text())
    state.setdefault("last_run", None)
    state.setdefault("seen", [])
except Exception:
    state = {"last_run": None, "seen": []}
since = state["last_run"] or (dt.date.today() - dt.timedelta(days=4)).isoformat()
watch = [l.strip() for l in (ROOT / "watchlist.txt").read_text().splitlines() if l.strip() and not l.startswith("#")]

def norm(url):  # drop tracking params/fragments so the same story dedupes
    p = urlsplit(url)
    return urlunsplit((p.scheme, p.netloc.lower().removeprefix("www."), p.path.rstrip("/"), "", ""))

SCHEMA = """Each story: {"headline","url","source","published":"YYYY-MM-DD","topic":"mcp|audience_data|partnerships|mna|product",
"companies":[...],"summary":"1-2 sentences, your own words","why_it_matters":"1 sentence for a madtech strategist","confidence":"high|medium|low"}"""

def sub(focus):
    return AgentDefinition(
        description=f"Finds new madtech stories about {focus}.",
        prompt=(f"Find stories about {focus} in marketing and advertising technology, published {since} or later. "
                f"Search broadly, then search these companies by name: {', '.join(watch)}. "
                "Prefer primary sources (press releases, company blogs) and trade press (AdExchanger, Digiday, Adweek, "
                "Campaign, MediaPost, Ad Age, The Drum). Fetch each page and confirm the publish date and key facts. "
                "Drop anything unverifiable or older than the window. "
                f"Return a JSON list using this schema. {SCHEMA}"),
        tools=["WebSearch", "WebFetch"])

OPTIONS = ClaudeAgentOptions(
    cwd=str(ROOT),
    system_prompt=("You are a madtech research analyst. Delegate to every topic subagent in parallel, merge results, "
                   "remove duplicate stories about the same event (keep the best source), rank by significance, "
                   "and write a JSON list of stories to data/raw.json using the Write tool. Do not write anything else."),
    allowed_tools=["Task", "WebSearch", "WebFetch", "Write", "Read"],
    agents={
        "mcp": sub("Model Context Protocol (MCP) servers, clients and agentic integrations launched by ad tech, martech, measurement or data companies"),
        "audience_data": sub("audience data, identity, clean rooms, data collaboration and targeting/signal changes"),
        "partnerships": sub("partnerships and integrations between madtech vendors, platforms, publishers, agencies and AI companies"),
        "mna": sub("acquisitions, mergers, divestitures and major funding rounds in madtech"),
        "product": sub("new product and feature launches from madtech vendors and platforms"),
    },
    permission_mode="acceptEdits",
    max_turns=80,
    model=os.getenv("RADAR_MODEL") or None,
)

async def main():
    raw = ROOT / "data/raw.json"
    raw.unlink(missing_ok=True)
    final = ""
    async for msg in query(prompt=f"Build the digest for {since} to {TODAY}. Topics: MCP, audience data, partnerships, M&A, product releases.", options=OPTIONS):
        if isinstance(msg, ResultMessage):
            final = msg.result or ""
            print(f"agent finished: error={getattr(msg, 'is_error', None)}, turns={getattr(msg, 'num_turns', None)}, cost={getattr(msg, 'total_cost_usd', None)}")
            print(f"agent said: {final[:600]}")
    text = raw.read_text() if raw.exists() else final
    m = re.search(r"\[.*\]", text, re.S)  # tolerate fences or chatter
    stories = json.loads(m.group(0)) if m else []
        print(f"raw.json written: {raw.exists()}, parsed {len(stories)} stories") 
    seen, clean = set(state["seen"]), []
    for s in stories:
        if not all(s.get(k) for k in ("headline", "url", "topic")): continue
        u = norm(s["url"])
        if u in seen: continue
        seen.add(u); clean.append(s)

    issue = {"date": TODAY, "window_start": since, "stories": clean}
    ISSUES.mkdir(parents=True, exist_ok=True)
    (ISSUES / f"{TODAY}.json").write_text(json.dumps(issue, indent=2))
    STATE_F.write_text(json.dumps({"last_run": TODAY, "seen": sorted(seen)[-2000:]}, indent=2))
    build_site(ISSUES, SITE)
    print(f"{len(clean)} new stories -> docs/index.html")
    if not clean:
        print("No new stories; skipping email")
    elif not os.getenv("SMTP_HOST"):
        print("SMTP_HOST not set; skipping email")
    else:
        try:
            mailer.send(issue)
        except Exception as exc:  # page and state are already saved
            print(f"Email failed: {exc}")
            raise SystemExit(1)

asyncio.run(main())
