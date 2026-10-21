# Madtech Radar
Twice-weekly agent that researches MCP, audience data, partnerships, M&A and product news in madtech, and publishes a static page.

## Run locally
    pip install -r requirements.txt
    export ANTHROPIC_API_KEY=...
    python run.py            # writes docs/index.html and docs/<date>.html

## Schedule + host (GitHub)
1. Push this folder to a repo; add secret ANTHROPIC_API_KEY.
2. Settings > Pages > deploy from branch, folder /docs.
3. .github/workflows/digest.yml runs Tue and Fri at 12:00 UTC and commits the new issue.

## Tune it
- watchlist.txt: companies to search by name.
- run.py: subagent prompts, trusted sources, RADAR_MODEL env var for model choice.
- data/state.json: delete to reset dedup history.

## Email
After each run with new stories, the digest is emailed to therran@hand-raiser.com (override with EMAIL_TO).
Set these as repo secrets (or env vars locally): SMTP_HOST, SMTP_PORT (587 STARTTLS or 465 SSL), SMTP_USER, SMTP_PASSWORD, EMAIL_FROM.
Optionally set repo variable PAGE_URL to your Pages URL to add an "Open the full page" link.
If SMTP_HOST is unset, email is skipped. A failed email exits non-zero but the page and dedup state are still saved.
Providers: Gmail (smtp.gmail.com, app password), Resend (smtp.resend.com, user "resend"), SendGrid (smtp.sendgrid.net, user "apikey").
