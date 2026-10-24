# ScrollForge

A zero-build, mobile-first feed for Broncos headlines, Reddit narratives, and mechanical engineering recall. Plain HTML, CSS, JavaScript, and JSON run on GitHub Pages; scheduled GitHub Actions refresh the feed. No server or Node build is required.

Open **https://floogle11.github.io/scrollforge/**. The committed feed contains 15 clearly marked sample cards, including source-linked historical headlines, original Reddit-style sample narratives, and engineering challenges with worked equations. Samples are not presented as breaking news or attributed to real Reddit users.

## Everyday use

Swipe up/down or press **j/k** to move. **Space** reveals a solution and **c** opens the comment composer. Skip freely. The Inbox collects replies; reading a thread clears its unread badge. Install from your browser's home-screen/install menu for a standalone PWA.

Settings accepts a GitHub repository slug and an optional fine-grained token with Issues write access to this repository. The token remains in that browser's local storage and is sent only to GitHub. Posting creates an Issue labeled `pending-codex`; the feed shows the queued question until an automated run publishes a reply. No token is needed to browse, solve, install, or read the feed.

## Automation

The content job runs at **00:00 and 12:00 UTC** (6 PM and 6 AM during Denver daylight time; 5 PM and 5 AM during standard time), on manual dispatch, and when raw notes change. RSS ingestion and note indexing use no LLM tokens. The job works without optional secrets and preserves the seeded feed when sources are unavailable.

To enable newly generated challenges and comment answers, set the repository Actions secret `OPENAI_API_KEY`. The pipeline makes at most one structured API request per content run, with SDK retries disabled. Optional `ICS_CALENDAR_URL` enables exam weighting; optional repository variable `OPENAI_MODEL` selects the model. Neither secret is required for the initial app or RSS updates. The calendar URL and API key stay in Actions and are never included in browser assets.

New Markdown, text, or PDF notes belong in `notes_raw/`, ideally in folders named for course codes. The deterministic slicer creates 250–350 word chunks and reuses cached extraction. The existing local `notes raw/` library is ignored by Git; it is not part of the public website or repository.

Resolved questions are written to the feed and pushed before the resolver comments on and closes Issues. If publication fails, Issues remain open for a subsequent run. The archive retains at most 300 cards, and feed data is validated before replacing the previous file.

## Local verification (optional)

```sh
python -m pip install -r requirements.txt -r requirements-dev.txt
python scripts/slice_notes.py
python worker/run_pipeline.py --dry-run
python -m pytest tests/test_e2e.py
```

Serve `docs/` with any static HTTP server for local browser testing. Production serves it directly; there is no build step. Browser checks use Playwright Chromium. JSON contracts are in `contracts/`; the complete product specification is `scrollforge_master_spec.md`.
