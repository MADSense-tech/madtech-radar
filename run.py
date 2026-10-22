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


def pick(s, *keys):
    for k in keys:
        v = s.get(k)
        if v:
            return v
    return None


def norm_topic(t):
    t = str(t or "").lower()
    if "mcp" in t: return "mcp"
    if "audience" in t or "identity" in t or "data" in t: return "audience_data"
    if "partner" in t: return "partnerships"
    if "m&a" in t or "mna" in t or "acqui" in t or "merger" in t: return "mna"
    return "product"


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
                   "and write a JSON list of stories to data/raw.json using the Write tool. "
                   "Use exactly these keys for every story: headline, url, source, published, topic, companies, "
                   "summary, why_it_matters, confidence. Do not write anything else."),
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
    try:
        stories = json.loads(m.group(0)) if m else []
    except Exception as exc:
        print(f"Could not parse stories: {exc}")
        stories = []
    print(f"raw.json written: {raw.exists()}, parsed {len(stories)} stories")
    if stories:
        print(f"first story keys: {sorted(stories[0].keys()) if isinstance(stories[0], dict) else type(stories[0])}")

    seen, clean = set(state["seen"]), []
    for s in stories:
        if not isinstance(s, dict):
            print("dropped: not an object")
            continue
        headline = pick(s, "headline", "title", "name")
        url = pick(s, "url", "link", "source_url", "href")
        if not headline or not url:
            print(f"dropped (missing headline or url): keys={sorted(s.keys())}")
            continue
        u = norm(url)
        if u in seen:
            print(f"dropped (already reported): {u}")
            continue
        seen.add(u)
        companies = s.get("companies") or []
        if isinstance(companies, str):
            companies = [companies]
        clean.append({
            "headline": headline,
            "url": url,
            "source": pick(s, "source", "publication", "outlet") or "",
            "published": pick(s, "published", "date", "published_date") or "",
            "topic": norm_topic(pick(s, "topic", "category", "type")),
            "companies": companies,
            "summary": s.get("summary") or "",
            "why_it_matters": pick(s, "why_it_matters", "why", "significance") or "",
            "confidence": s.get("confidence") or "medium",
        })
    print(f"kept {len(clean)} stories after validation and dedup")

    issue = {"date": TODAY, "window_start": since, "stories": clean}
    ISSUES.mkdir(parents=True, exist_ok=True)
    (ISSUES / f"{TODAY}.json").write_text(json.dumps(issue, indent=2))
    if stories:  # only advance the window when the agents actually returned something
        STATE_F.write_text(json.dumps({"last_run": TODAY, "seen": sorted(seen)[-2000:]}, indent=2))
    else:
        print("Agents returned nothing; leaving state.json unchanged")
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
