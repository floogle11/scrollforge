# ScrollForge

Open **https://floogle11.github.io/scrollforge/**. The site is a compact, Reddit-style feed of Broncos/NFL headlines, world and US news, stories, and engineering challenges. GitHub Pages serves plain HTML/CSS/JavaScript; no build or server is required. Use the topic tabs, search, and For you / New sorting to browse. Filtering preserves open answers and comment drafts.

## Reading and questions

Scroll with the wheel or your finger. Posts load automatically in batches of 24 as you approach the bottom. Mounted posts stay in the document, so revealing an answer or posting a question preserves your place. Search and topic filters include unloaded posts and preserve drafts. **j/k** move to the next/previous card, **Space** reveals the active challenge solution, and **c** opens its thread. Cards are marked seen when they enter view. At the end, review engineering cards without replaying old headlines. The Inbox opens the card associated with each reply, including archived threads.

The starter review bank contains **200 original illustrated multiple-choice questions and 20 short topic posts** across fluids, thermodynamics, statics, machine design, and system dynamics. It includes conceptual questions and numerical variants whose answers are calculated in `worker/study_bank.py`. Choose an answer for immediate feedback and the worked solution; retry whenever you like. Answer choices and feedback persist on this device. The format supports 4–8 choices; the starter bank uses four. Diagrams are original vector schematics with the givens alongside them. Regenerate the bank offline with `python -m worker.study_bank` without resetting existing conversations.

The Hockey feed includes dedicated **Utah Mammoth** and **Colorado Avalanche** filters. Reddit drama comes from public story communities and gets a small share of the home mix. **Show Reddit post** loads the original through Reddit's embed service on demand, including its supported media. The original link remains available if a preview is unavailable. Public news and Reddit posts do not need AI-written cards.

Settings holds the repository slug and an optional fine-grained GitHub token with Issues write access. Posting a question creates a `pending-codex` Issue. The token stays in that browser and is sent only to GitHub; it is never committed. The desktop worker uses the GitHub CLI's existing login independently of browser settings.

## Local Codex loop

Generation and replies run through **Codex CLI on your computer using its saved ChatGPT login**. No OpenAI API key or OpenAI SDK is used. Codex still uses the online Codex service and your account's usage limits; it is not an offline model running on your GPU.

The Windows task **ScrollForge Local Codex Loop** checks questions every five minutes while you are logged in. An idle check makes no model call. New questions are answered in one bounded terminal batch; up to **20 engineering cards per batch**, twice per day, use one bounded prompt with a five-minute timeout. Generated challenges must include a quiz with 4–8 options, a supported diagram, and a concise solution. Questions wait while the computer is asleep, offline, or signed out.

The task operates in an isolated checkout under `.cache/local-agent/checkout`, keeping the working project separate. GitHub credentials are read into memory through `gh`; Codex uses its own login. Validated replies enter `feed.json` and are pushed before the worker posts an answer to and closes the Issue. Private state and logs remain under `.cache/`.

For manual operation, run `scripts/run_local_loop.ps1`. `scripts/install_local_loop.ps1` installs the current-user scheduled task without a password. Both use this checkout's `.venv`, Git, GitHub CLI, and the installed Codex CLI. The installer is intended to be run once; the task handles subsequent checks. The repository contains no credentials.

GitHub Actions independently fetches public sources **every three hours**, preserving fresh headlines even when the desktop is off. Sources include ESPN, official Mammoth and Avalanche NHL sites, the Broncos, BBC, NPR, The Guardian, NASA, Smithsonian, and public Reddit feeds for football, hockey, news, history, space, and drama. Reddit sometimes rate-limits feeds; each source can fail independently, with publisher feeds keeping the mix stocked. Only short excerpts and article metadata are imported, with links to the original article or Reddit discussion. Each refresh keeps up to **180 sports posts, 180 news posts, and 100 stories**, selected across sources. Default home mixing weights are football 25%, hockey 20%, news 25%, other stories 11%, drama 4%, and coursework 15% while each pool has unread posts. Remaining posts are still available after a pool runs out. There is no synthetic recycling of already-read headlines to simulate an endless feed.

RSS refresh does not generate challenges or answer questions. Optional `ICS_CALENDAR_URL` enables exam weighting. New Markdown, text, and PDF notes belong in `notes_raw/`; the deterministic slicer indexes them without using Codex. The existing local `notes raw/` library is ignored by Git and is not published.

## Content lifecycle

- Sports and news leave the reading feed after **seven days from publication**; stories after **30 days**.
- Re-fetching a headline does not renew its publication date. Tracking URLs and changed source IDs do not create a new article identity. Items without a known publication date are skipped.
- Seen news and stories are not automatically recycled as spacers or replayed at the end. Engineering material stays available for review.
- Old cards with conversations or queued questions are retained for the Inbox rather than resurfaced as fresh headlines. The JSON archive is capped at **1,500 cards**, prioritizing queued parents and the original review bank. Other cards are selected by recent activity.

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
