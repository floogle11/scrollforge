# ScrollForge

Open **https://floogle11.github.io/scrollforge/**. The site is a native scrolling feed of engineering challenges, Broncos/NFL headlines, and stories. GitHub Pages serves plain HTML/CSS/JavaScript; no build or server is required.

## Reading and questions

Scroll with the wheel or your finger. Cards stay in the document, so revealing an answer or posting a question preserves your place. **j/k** move to the next/previous card, **Space** reveals the active challenge solution, and **c** opens its thread. Cards are marked seen when they enter view. At the end, review engineering cards without replaying old headlines. The Inbox opens the card associated with each reply, including archived threads.

Settings holds the repository slug and an optional fine-grained GitHub token with Issues write access. Posting a question creates a `pending-codex` Issue. The token stays in that browser and is sent only to GitHub; it is never committed. The desktop worker uses the GitHub CLI's existing login independently of browser settings.

## Local Codex loop

Generation and replies run through **Codex CLI on your computer using its saved ChatGPT login**. No OpenAI API key or OpenAI SDK is used. Codex still uses the online Codex service and your account's usage limits; it is not an offline model running on your GPU.

The Windows task **ScrollForge Local Codex Loop** checks questions every five minutes while you are logged in. An idle check makes no model call. New questions are answered in one bounded terminal batch; up to six engineering cards are generated twice per day. Questions wait while the computer is asleep, offline, or signed out.

The task operates in an isolated checkout under `.cache/local-agent/checkout`, keeping the working project separate. GitHub credentials are read into memory through `gh`; Codex uses its own login. Validated replies enter `feed.json` and are pushed before the worker posts an answer to and closes the Issue. Private state and logs remain under `.cache/`.

For manual operation, run `scripts/run_local_loop.ps1`. `scripts/install_local_loop.ps1` installs the current-user scheduled task without a password. Both use this checkout's `.venv`, Git, GitHub CLI, and the installed Codex CLI. The installer is intended to be run once; the task handles subsequent checks. The repository contains no credentials.

GitHub Actions independently fetches RSS at **00:00 and 12:00 UTC**, preserving fresh headlines even when the desktop is off. It does not generate challenges or answer questions. Optional `ICS_CALENDAR_URL` enables exam weighting. New Markdown, text, and PDF notes belong in `notes_raw/`; the deterministic slicer indexes them without using Codex. The existing local `notes raw/` library is ignored by Git and is not published.

## Content lifecycle

- Sports and news leave the reading feed after **seven days from publication**; stories after **30 days**.
- Re-fetching a headline does not renew its publication date. Tracking URLs and changed source IDs do not create a new article identity. Items without a known publication date are skipped.
- Seen news and stories are not automatically recycled as spacers or replayed at the end. Engineering material stays available for review.
- Old cards with conversations or queued questions are retained for the Inbox rather than resurfaced as fresh headlines. The JSON archive is capped at 300 cards.

The original 15-card demonstration feed is preserved as a test fixture; the live feed is refreshed and expires normally.

## Development checks

```sh
python -m pip install -r requirements-dev.txt
python scripts/slice_notes.py
python -m worker.run_pipeline --dry-run
python -m worker.local_loop --dry-run
python -m pytest tests
```

Serve `docs/` with a static HTTP server for local previews. Browser checks use Playwright Chromium. JSON contracts live in `contracts/`. The original product specification is `scrollforge_master_spec.md`; its API-based generation section is superseded by the local CLI loop above.
