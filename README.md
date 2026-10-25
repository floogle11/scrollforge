# ScrollForge

For future conversations and project handoffs, start with [MEMORY.md](MEMORY.md) and [CHANGELOG.md](CHANGELOG.md). [AGENTS.md](AGENTS.md) points repository agents to that context.

Open **https://floogle11.github.io/scrollforge/**. The site is a compact, Reddit-style feed of Broncos/NFL headlines, world and US news, stories, and engineering challenges. GitHub Pages serves plain HTML/CSS/JavaScript; no build or server is required. Use the topic tabs, search, and For you / New sorting to browse. Filtering preserves open answers and comment drafts.

## Reading and questions

Scroll with the wheel or your finger. Posts load automatically in batches of 24 as you approach the bottom. Mounted posts stay in the document, so revealing an answer or posting a question preserves your place. Search and topic filters include unloaded posts and preserve drafts. **j/k** move to the next/previous card, **Space** reveals the active challenge solution, and **c** opens its thread. Cards are marked seen when they enter view. At the end, review engineering cards without replaying old headlines. The Inbox opens the card associated with each reply, including archived threads.

The review bank contains **452 original multiple-choice questions and 20 short topic posts** across fluids, thermodynamics, statics, machine design, system dynamics, **Calculus I–III, linear algebra, differential equations, and Physics I–II**. Each calculus and physics subject has 37 questions; linear algebra and differential equations have 21 each. The bank combines numerical variants with 60 additional distinct questions, five per subject. Choose an answer for immediate feedback and a worked solution; retry whenever you like. Answers persist on this device and reset when the question, choices, or correct answer changes. The format supports 4–8 choices; the bank uses four.

Mental review keeps exponentials, logarithms, radicals and multiples of π in exact form: for example, `e² + 1` for the integral of `xeˣ` from 0 to 2. Distractors target boundary, sign, chain-rule and setup mistakes. Decimal approximation remains appropriate for estimation questions and ordinary numerical engineering quantities. Figures are optional: reviewed vector schematics show the relevant forces, supports and components, while integral plots use the actual function and bounds. Questions without a useful matching figure stay text-only. The Engineering subject selector opens focused practice. Regenerate offline with `python -m worker.study_bank` without resetting existing conversations; the bank, exact choices, extra questions and diagram assignments live in `worker/study_bank.py`, `worker/foundations_bank.py`, `worker/review_choices.py`, `worker/extra_review_bank.py` and `worker/review_diagrams.py`.

**More like this / Less like this** on each post shapes upcoming posts and future visits. Signals recognize recurring subjects, teams, broad topics (such as space, history, technology and politics), and publishers or subreddits. Multiple related votes strengthen the trend. Click the same arrow to undo, or the opposite arrow to change it. Settings shows learned interests and resets them independently of your repository settings. Preferences stay in this browser, keep at most 500 signals, and fade with a 45-day half-life. No account, model call, analytics service, or per-vote GitHub write is needed. Reading a post is not counted as liking it.

For you combines weighted random sampling with topic spacing and source/subject variety; it avoids consecutive broad groups while alternatives remain. Within a group, it prefers an alternative publisher, team or subject when available. Inventory can still run down to one group. Preferences influence both groups and posts, while every item retains a chance to appear. The default leisure-first weights remain; these are sampling weights, not exact percentages after diversity rules, personalization, and pool exhaustion. Voting reorders only posts that have not been mounted, preserving your reading position, drafts and quiz state. New sorting remains chronological.

The Hockey feed includes dedicated **Utah Mammoth** and **Colorado Avalanche** filters. Reddit drama comes from public story communities and gets a small share of the home mix. **Show Reddit post** loads the original through Reddit's embed service on demand, including its supported media. The original link remains available if a preview is unavailable. Public news and Reddit posts do not need AI-written cards.

Settings holds the repository slug and an optional fine-grained GitHub token with Issues write access. Posting a question creates a `pending-codex` Issue. The token stays in that browser and is sent only to GitHub; it is never committed. The desktop worker uses the GitHub CLI's existing login independently of browser settings.

## Local Codex loop

Generation and replies run through **Codex CLI on your computer using its saved ChatGPT login**. No OpenAI API key or OpenAI SDK is used. Codex still uses the online Codex service and your account's usage limits; it is not an offline model running on your GPU.

The Windows task **ScrollForge Local Codex Loop** checks questions every five minutes while you are logged in. An idle check makes no model call. New questions are answered in one bounded terminal batch; up to **20 engineering cards per batch**, twice per day, use one bounded prompt with a five-minute timeout. Generated challenges must include a quiz with 4–8 options and a concise solution. Generation guidance requests exact mental-math choices and a diagram only when its documented setup matches; otherwise the diagram is null. Questions wait while the computer is asleep, offline, or signed out.

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

## Hosting budgets

GitHub documents a **1 GB maximum published site**, **1 GB recommended source repository size**, and **100 GB/month soft bandwidth limit**. The normal 10-builds/hour soft limit does not apply to this project's custom Actions publishing workflow. See [GitHub Pages limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits).

Project limits are deliberately smaller: **5 MiB for feed.json or any individual published file; 20 MiB for docs/**. `python scripts/check_pages_budget.py` reports sizes, gzip estimates, and a conservative full-feed transfer estimate. CI, content refresh, and Pages publishing check these budgets. Atomic feed writes also reject an oversized payload before replacing existing data. The archive remains capped at 1,500 posts; there is no hosted video, copied photo library, or external personalization database.

The browser polls a tiny `data/feed-meta.json` marker every five minutes while visible and online, and downloads the archive only when its version changes (or the marker is unavailable). Explicit refresh still fetches the current feed. Feed writers publish both files together, including the desktop loop's retry/recovery paths. Actual monthly traffic and accumulated Git history are not measured by these static size checks; gzip and transfer counts are estimates, not a bandwidth quota guarantee.

## Development checks

```sh
python -m pip install -r requirements-dev.txt
python scripts/slice_notes.py
python -m worker.run_pipeline --dry-run
python -m worker.local_loop --dry-run
python -m pytest tests
python scripts/check_pages_budget.py
```

Serve `docs/` with a static HTTP server for local previews. Browser checks use Playwright Chromium. JSON contracts live in `contracts/`. The original product specification is `scrollforge_master_spec.md`; its API-based generation section is superseded by the local CLI loop above.
