"""Email delivery via SMTP (stdlib only). Configure with environment variables."""
import html
import os
import smtplib
import ssl
from email.message import EmailMessage

from render import TOPICS

DEFAULT_TO = "therran@hand-raiser.com"


def _e(s):
    return html.escape(str(s or ""))


def build(issue, page_url=""):
    """Return (subject, plain_text, html). Email clients ignore <style>, so styles are inline."""
    stories = issue["stories"]
    subject = f"Madtech Radar {issue['date']}: {len(stories)} new stories"
    text = [f"Madtech Radar, {issue['window_start']} to {issue['date']}", ""]
    body = ""
    for key, (label, color) in TOPICS.items():
        group = [s for s in stories if s["topic"] == key]
        if not group:
            continue
        body += (f'<h2 style="font:600 18px Georgia,serif;margin:28px 0 10px;'
                 f'color:{color}">{label}</h2>')
        text.append(label.upper())
        for s in group:
            meta = ", ".join(x for x in (s.get("source"), s.get("published")) if x)
            body += (
                f'<div style="border-left:4px solid {color};padding:2px 0 2px 12px;margin:0 0 16px">'
                f'<a href="{_e(s["url"])}" style="font:600 16px Georgia,serif;color:#14202B;'
                f'text-decoration:none">{_e(s["headline"])}</a>'
                f'<div style="font:13px Arial,sans-serif;color:#5B6875;margin:3px 0">{_e(meta)}</div>'
                f'<div style="font:15px/1.5 Arial,sans-serif;color:#14202B">{_e(s.get("summary"))}</div>'
                f'<div style="font:14px/1.5 Arial,sans-serif;color:#5B6875;margin-top:4px">'
                f'{_e(s.get("why_it_matters"))}</div></div>'
            )
            text += [s["headline"], s["url"], s.get("summary", ""), s.get("why_it_matters", ""), ""]

    link = ""
    if page_url:
        link = (f'<p style="margin:0 0 20px;font:14px Arial,sans-serif">'
                f'<a href="{_e(page_url)}" style="color:#2F5BEA">Open the full page</a></p>')
        text.append(f"Full page: {page_url}")

    page = (
        '<div style="max-width:600px;margin:0 auto;padding:24px 16px;background:#ffffff">'
        '<h1 style="font:600 26px Georgia,serif;margin:0 0 4px;color:#14202B">Madtech Radar</h1>'
        f'<p style="font:14px Arial,sans-serif;color:#5B6875;margin:0 0 20px">'
        f'{_e(issue["window_start"])} to {_e(issue["date"])}</p>{link}{body}</div>'
    )
    return subject, "\n".join(text), page


def send(issue):
    host = os.environ["SMTP_HOST"]
    port = int(os.getenv("SMTP_PORT") or "587")
    user, pw = os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD")
    to = os.getenv("EMAIL_TO") or DEFAULT_TO
    subject, text, page = build(issue, os.getenv("PAGE_URL", ""))

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.getenv("EMAIL_FROM") or user or to
    msg["To"] = to
    msg.set_content(text)
    msg.add_alternative(page, subtype="html")

    ctx = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=ctx, timeout=30) as s:
            if user:
                s.login(user, pw)
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=30) as s:
            s.starttls(context=ctx)
            if user:
                s.login(user, pw)
            s.send_message(msg)
    print(f"Emailed digest to {to}")
