# ScrollForge conversation memory

Last recorded: **2026-10-28, America/Denver**.

This file is the handoff for future conversations. Read it together with `CHANGELOG.md` and `README.md`. Counts and deployment identifiers below are dated snapshots; inspect the current repository and feed before treating them as live values.

**October 25 update deployed and verified:** feature commit `93ac88a` adds exact mental-review answer choices, reviewed diagrams and 60 new questions, bringing the bank to 452 quizzes plus 20 topic posts. Automatic refresh `dc885e2` followed it. Both Pages deployments and independent GitHub checks succeeded; a real live mobile preview verified rendered math, diagrams and quiz retry with no page errors. Prior feature `98dc01c` added feed diversity, browser-local preferences and publication budgets.

## October 28 current-state update

- User now wants editable current interests shared with automated generation and is deeply studying the Italian Game in chess. Preserve the leisure-first feed and add chess alongside it.
- Settings > Current interests syncs an owner-authored public configuration issue titled `ScrollForge current interests`, JSON kind `scrollforge-interests-v1`, using the existing Issues token. One line per interest, maximum twelve, 160 characters each. Empty list pauses interest generation; keep the issue open. No issue means defaults in `docs/data/interests.json`; failed fetches do not restore removed interests. Do not log credentials.
- `worker/interests.py` loads shared interests before generation. Up to six of the existing twenty slots become INTEREST cards, with no additional model call and the same twice-daily schedule. Removed interests affect subsequent batches, not existing content.
- `worker/chess_content.py` reproducibly builds six Italian Game posts (three lessons, three quizzes). python-chess builds boards, validates FEN/SAN and check/mate notation, and regenerates SVG; the browser isolates SVG in images. This validates legality, not engine evaluations. Chess/Interests filters can revisit read posts; Home does not recycle them.
- New INTEREST category is evergreen and separate from coursework. Retention keeps six starters plus 54 unthreaded generated interest posts; threads and pending parents remain protected. Existing publication budgets still apply. Offline shell is v11; early topic selection waits for the feed to load.
- Local checks: 106 final worker/offline checks pass; browser/interest suite 37 passed before final additions, with final retention/revisit/update/error checks passing separately. Feed 900,088 bytes and site 1,039,664 bytes, within budgets.
- Live generator smoke attempts on October 28 failed before content was returned: Codex service reported `Incomplete response returned, reason: max_output_tokens`, zero reported tokens. No live batch was verified or published; do not claim live generation success.
- Updated python-chess dependency is installed in the workspace virtualenv also used by the existing scheduled launcher. Feature `bfa7273`, merged with automated feed updates in `01f7dbb`, is deployed: initial Pages run `40789037369`, independent checks `40789037387`, content refresh `40789037358`, and post-refresh deployment `40789096445` all succeeded. Live mobile verification confirmed six chess posts, board images, quiz feedback and the interests editor. Follow-up validation records below distinguish the final loading-race fix from this first deployment.
- Final deployed code: loading fix `2fd90e9`, merged with refresh `c182f14` in `88ac85d`. Pages deployment `40789317148` and independent checks `40789317046` succeeded; all 141 local tests passed. Live mobile and desktop verification showed zero page errors, loaded SVG boards, working quiz feedback, and the Italian Game interest in Settings. Published snapshot: 1,315 posts including six chess starters, feed 1,232,083 bytes, site 1,371,752 bytes; feed and marker match. The unrelated pre-existing hidden-launcher script/installer changes remain uncommitted locally and were not part of this deployment.

## User intent and preferences

- The user wants the feeling of scrolling Reddit, with a little review or class content woven between interesting posts.
- They explicitly loved the deployed Reddit-style redesign: "It looks amazing. Just what I want honestly." Preserve that visual direction when extending the site.
- They disliked the earlier oversized cards, artificial post presentation, limited inventory, and feed dominated by school material.
- They want a large, varied pool and automatic loading as they scroll. Do not satisfy this by replaying already-read headlines or inventing news.
- Main interests: NFL and Broncos, general/world/US/technology news, hockey, **Utah Mammoth (favorite team)**, **Colorado Avalanche**, discoveries/history/space, and occasional Reddit drama stories.
- School material should include useful illustrations, more topics, short explanations, and multiple-choice questions. Four to eight choices were requested; the starter questions use four and the format supports up to eight.
- October 25 feedback: questions should be solvable mentally without evaluating decimal exponentials or other transcendental constants. Keep expressions such as `e² + 1`, `ln(4/3)`, `π/5`, fractions and radicals exact. Distractors should represent plausible mistakes. Misleading diagrams made the user misinterpret questions: use accurate, labeled figures only when they match the stated setup, and omit unrelated artwork.
- They welcomed importing real Reddit posts so AI does not have to write the entire feed.
- Earlier feature releases and the final navigation fix were published and verified. The latest follow-up requested better randomization, learning from likes/dislikes and recurring interests, Calc I–III/linear algebra/differential equations/Physics I–II, and attention to GitHub hosting limits.
- Keep the feed leisure-first; the expanded bank should not turn Home into a coursework dashboard. New default sampling weights remain 85% leisure / 15% review before diversity and personalization adjustments.

## Current product

- Public site: **https://floogle11.github.io/scrollforge/**.
- GitHub repository: **floogle11/scrollforge**, branch **main**.
- Static HTML, CSS, JavaScript, and JSON served from `docs/` on GitHub Pages. There is no frontend build step or application server.
- Dark Reddit-style layout: sticky header, search, compact posts, source attribution, rounded action buttons, desktop topic sidebar and community rail, mobile topic tabs, favorite-team chips.
- Topics: home, NFL, hockey, Mammoth, Avalanche, news, stories, drama, and engineering. Sort by mixed "For you" order or newest.
- For you avoids consecutive broad groups when alternatives remain, then seeks a different publisher/team/subject inside a group. Shuffled weighted selection still varies each visit. Exhausting diverse inventory can leave a single-category tail.
- Each post has **More like this / Less like this**, with toggle-to-undo and switchable signals. Recognized topics, favorite teams, course tags, publishers and subreddits contribute to future ranking. Repeated signals strengthen trends; half-life is 45 days. Weights retain exploration. Reading alone does not imply approval.
- Preferences use `scrollforge.preferences.v1` in browser local storage, capped at 500 signals. Settings summarizes learned interests and resets them separately from repository credentials. No votes leave the device; no cloud database, analytics or per-vote publication exists. Only unmounted posts are remixed after voting so mounted DOM, scroll, drafts and answers remain intact. New sorting stays chronological.
- Engineering now has a subject selector for all twelve course tags. Foundation tags are descriptive labels, not claimed university catalog numbers.
- The feed mounts **24 posts per batch**, appends more near the bottom through IntersectionObserver, and offers a load-more fallback. A caught-up state remains when available content is exhausted; the inventory is large, not mathematically infinite.
- Existing post DOM is preserved when loading more or filtering. Search finds matching posts that have not yet been mounted. Answers, expanded sections, drafts, and reading position must survive routine interactions.
- Keyboard: `j/k` next/previous post, Space reveals a challenge solution, `c` opens comments. Native wheel and touch scrolling remain native.
- "Show Reddit post" opens an on-demand original-post preview using `https://embed.reddit.com/`. The original Reddit link stays available if the embed fails. There are no invented Reddit votes or comment counts.
- Reddit iframes use a restricted sandbox. Resize messages are accepted only from the embed origin and the matching iframe window, with bounded heights. Imported text is escaped/sanitized.
- Browser local storage tracks read posts and source URLs, read replies, pending comments, selected quiz answers, repository settings, and the optional Issues token. Quiz signatures now include the body, options and correct index so edited questions cannot reuse incompatible selections. Older options-only answer records expire once.

## Content and review bank

- `worker/study_bank.py` with `worker/foundations_bank.py` and `worker/extra_review_bank.py` reproducibly builds **452 multiple-choice questions plus 20 short topic posts**. The original foundation bank has **192 questions: 48 concepts with four calculated variants each**. The original 200 engineering questions remain; October 25 adds 60 distinct questions, five per subject.
- `worker/review_choices.py` preserves exact expressions for exponentials, logarithms, π, fractions and radicals, with misconception-based choices for foundational math and selected engineering topics. Numerical engineering approximations still use closest-value choices where applicable. All 368 original numerical variants are checked against their calculated values and for numerically equivalent distractors. Answer order remains deterministically shuffled.
- Illustrations are optional. `worker/review_diagrams.py` assigns only matching figures; unsupported or unrelated legacy artwork is omitted. This intentionally supersedes the earlier requirement that every challenge have an image.
- `docs/diagrams.js` renders 42 reviewed vector types with readable labels, accessible descriptions and captioned givens. Integral plots sample the actual integrand over the given bounds; physical figures distinguish open/sealed tanks, damped/undamped springs, separate dampers, pin/roller supports, collision carts and coils. Lens rays intersect at the correct real image. Figures are original inline vectors, not copied textbook images or generated bitmaps.
- Courses represented:

| Course | Subject | Current classification |
| --- | --- | --- |
| ME-3310 | Fluid Mechanics | Current |
| ENGR-2300 | Thermodynamics | Current |
| ME-3140 | Machine Design | Current |
| ME-3010 | System Dynamics | Current |
| ME-2010 | Statics | Foundational/past |
| CALC-I, CALC-II, CALC-III | Calculus I, II, III; 37 questions each | Foundational/past |
| LINEAR-ALG | Linear algebra; 21 questions | Foundational/past |
| DIFF-EQ | Differential equations; 21 questions | Foundational/past |
| PHYS-I, PHYS-II | Mechanics/waves and electricity/magnetism/optics; 37 questions each | Foundational/past |

- `notes raw/` is the private, ignored local library. It contains coursework folders including Mechatronics (ME-3050), but that folder had no content at inspection. Do not imply that the new bank covers mechatronics or publish private library files.
- `notes_raw/` is the committed input to the deterministic slicer. It contains the original sample notes and `Review_Topics.md`, an original outline supporting machine-design and system-dynamics generation. The last index had eight chunks from two source files; it is not a complete index of the private library.
- Regenerate/merge the original review bank with `python -m worker.study_bank`. IDs are stable; existing conversations are preserved. This command updates the feed locally and does not itself deploy.

## Feed sources, balance, and retention

- `worker/ingest_rss.py`: independent public-source ingestion, up to 50 entries per source, bounded concurrency, sanitized excerpts of at most 600 characters, original publication dates, stable IDs, and source-failure isolation.
- Sources include ESPN NFL/NHL, Broncos, BBC, NPR, The Guardian, NASA, Smithsonian, and multiple Reddit news, football, hockey, discovery, and drama communities.
- **Utah's official NHL site path is `/utah/`**, not `/mammoth/`. Its active Reddit community `r/Utah_Hockey` successfully supplied posts. `r/UtahMammoth` was configured but rate-limited during verification.
- `worker/ingest_nhl.py` imports official Mammoth and Avalanche article headlines, short descriptions, dates, and image metadata. It handles NHL's escaped JSON publication metadata; no full article bodies are copied.
- ESPN team identifiers verified in this session: Utah **129764**, Colorado **17**. Team-specific ESPN feeds can include unrelated league articles, so the importer checks team keywords before applying team labels.
- Reddit feeds often return 429/403. Several drama communities were unavailable during initial import; **r/pettyrevenge** supplied real drama posts. This is an external source limitation, not a reason to fabricate content or retry aggressively. Publisher/team sources keep the feed useful when Reddit fails.
- GitHub Actions refreshes public sources **every three hours**, independently of the desktop and without model generation.
- Refresh intake targets: up to **180 sports**, **180 news**, and **100 story** posts, selected across source buckets.
- Default browser mixer weights when all pools are available: football 25%, hockey 20%, news 25%, other stories 11%, drama 4%, current review 10%, past review 5%. These are selection weights; once pools empty, remaining categories can have a larger share.
- Browser exam profiles differ from baseline. Backend calendar weights guide generation quotas separately; do not assume the frontend and backend tables are identical.
- Sports/news expire after seven days from publication; stories after 30 days. Engineering is evergreen. Unknown publication dates are skipped, and fetching an article again does not make it new.
- Canonical source URLs and stable IDs prevent tracking links or edited titles from resurfacing read stories. Seen headlines are not recycled at the end. Explicit engineering review can revisit school material.
- Archive cap: **1,500 posts**. Queued question parents and the original `study_` bank receive priority; other posts are ordered by activity. Preserve comments and parent identities when merging.

## Hosting/data budgets (deployed October 24 follow-up)

- Verified GitHub documentation: published Pages site maximum 1 GB, source repository recommended 1 GB, soft bandwidth 100 GB/month. The usual 10-builds/hour soft limit does not apply to custom Actions publishing: https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits.
- Project checks deliberately restrict **feed.json and each published file to 5 MiB; total docs/ to 20 MiB**. `scripts/check_pages_budget.py` runs in CI, content refresh and Pages deployment. Oversized atomic feed writes fail before replacing existing data; the script checks marker consistency too.
- Browser reply polling uses a tiny `data/feed-meta.json` marker every five minutes while visible/online; full JSON is fetched only when changed or when the marker is unavailable. Explicit refresh still fetches feed.json. SW v9 adds the separate diagram renderer to the offline shell.
- Feed atomic writes produce both JSON and marker. The local loop publishes and recovers only these two generated paths; cached outbox and publication-before-Issue-resolution guarantees remain. RSS automation stages the marker too. Do not add marker generation without preserving both writers and recovery.
- Published-size snapshot after refresh `2942e1b`: **742,395 bytes total published files**, **610,839-byte feed**, roughly **97,926 bytes gzip** (estimate only). This is roughly 163,709 uncompressed complete-feed transfers per 100 decimal GB, excluding other traffic. Static checks do not measure actual monthly bandwidth or accumulated remote Git history.
- October 25 size snapshot after refresh `dc885e2`: **827,193 bytes total published files**, **696,083-byte feed**, about **120,076 bytes gzip**. All file/feed/site budgets pass.
- No hosted video or copied image library was added. Diagrams remain inline vector markup; imported publisher images load lazily from their original hosts and Reddit embeds remain on demand.

## AI generation, questions, and desktop automation

- Generation uses the local **Codex CLI with the user's saved ChatGPT login**. It is not a GPU/offline model, and it does not use an OpenAI API key or SDK. Do not restore the old API-based master-spec design without a new request.
- Default configured generator model at this handoff: `gpt-6-luna`; environment overrides exist. This is project configuration, not a recommendation to change the conversation model.
- Practical batch guidance given to the user: **20–30 carefully checked AI-written questions per prompt**. Implemented recurring cap: **20 cards per batch**, at most twice per day, with a **300-second** model timeout. This is a chosen quality/usage bound, not a hard model capability limit.
- Model prompts use supplied note context, ask for 4–8 plausible choices, constrain course tags/categories, and discourage repeated recent titles. Mental-review guidance requests exact expressions and common-error distractors. Diagrams may be null; choose one only when its documented geometry and assumptions match. Generated challenges require concise solutions and a question body of at most 75 words.
- `contracts/feed_schema.json` and `contracts/llm_output_schema.json` describe the formats. Python also rejects a correct-answer index outside the actual option array. Legacy non-quiz posts remain supported.
- Windows scheduled task: **ScrollForge Local Codex Loop**. It checks every five minutes while the user is logged in, prioritizes pending questions, and makes no model call for an idle check. October 26: the user found recurring terminal popups annoying. The installed task now starts `scripts/run_local_loop_hidden.vbs` via `wscript.exe`; the installer uses the same action. The wrapper starts PowerShell hidden before its console appears, waits for completion, and propagates the exit code. The five-minute/logon triggers and other existing task settings were preserved. An offline hidden-launcher test passed with zero external calls; logs remain in `.cache/local-agent/run.log`. The previous task definition is backed up privately under `.cache/local-agent/task-before-hidden-launch.xml`.
- The worker owns an isolated checkout at `.cache/local-agent/checkout`; private state and cached publication outbox live under `.cache/`. Do not casually reset this checkout or delete its state: the outbox supports crash and push-race recovery.
- October 26 operational verification: the first automatic run through the hidden launcher started at 17:52:10 America/Denver and completed with Task Scheduler result 0; the log recorded an idle check with no pending questions or generated cards.
- Browser comments create `pending-codex` GitHub Issues. Optional browser credentials stay on that device. Desktop credentials come from the existing `gh` login, independently.
- Replies are validated, merged into `feed.json`, and pushed before the worker posts answers to and closes represented Issues. Preserve this publication ordering and retry behavior.

## Important files

| Path | Purpose |
| --- | --- |
| `docs/index.html` | Page shell, topic navigation, dialogs |
| `docs/tokens.css` | Approved design, responsive layout, quizzes and diagrams |
| `docs/app.js` | Mixing, pagination, search/filtering, diagrams, quizzes, embeds, comments/inbox |
| `docs/sw.js` | Offline shell/feed/marker caching; v9 includes diagrams.js |
| `docs/diagrams.js` | Reviewed SVG figures and function-specific integral plots |
| `docs/data/feed.json` | Live content and conversations; also written by automation |
| `docs/data/feed-meta.json` | Tiny update marker, generated together with feed.json |
| `docs/data/notes_index.json` | Committed, sliced note context |
| `worker/study_bank.py` | Reproducible review bank and merge command |
| `worker/foundations_bank.py` | 192 original calculated math/physics variants |
| `worker/review_choices.py` | Exact expressions and misconception distractors |
| `worker/extra_review_bank.py` | 60 distinct additional questions across twelve subjects |
| `worker/review_diagrams.py` | Question-to-figure assignments and integral plot parameters |
| `scripts/check_pages_budget.py` | Published-file/feed/site budgets and marker validation |
| `worker/ingest_rss.py`, `worker/ingest_nhl.py` | Public source importers |
| `worker/run_pipeline.py`, `worker/retention.py` | Validation, merging, publication, expiry/deduplication |
| `worker/generate_batch.py`, `worker/local_loop.py` | Local AI generation and durable question/reply loop |
| `.github/workflows/` | Checks, content refresh, GitHub Pages deployment |
| `tests/test_browser.py`, `tests/test_study_bank.py` | Browser behavior and review-bank checks |

## Development and deployment notes

- Workspace: `C:\Users\user\Documents\MISC\scrollforge`, PowerShell, existing `.venv`.
- Use `.venv/Scripts/python.exe` for this Windows checkout. `git` and `gh` were not on PATH; installed executables were `C:/Program Files/Git/cmd/git.exe` and `C:/Program Files/GitHub CLI/gh.exe`.
- Useful checks: `python -m pytest -q tests`, `python -m worker.run_pipeline --dry-run`, `git diff --check`. Dry run must remain offline and must not overwrite its input feed.
- Serve `docs/` with a static server for previews. Browser tests exercise a `/scrollforge/` subpath and use installed Chrome or Playwright Chromium. Do not assume the Playwright headless-shell executable is installed merely because Chromium is available.
- PowerShell/legacy console encodings can corrupt non-ASCII text piped into Python. Prefer `apply_patch` for Unicode source edits and use explicit UTF-8 for file I/O. The pipeline's CLI JSON output uses ASCII escapes to avoid Windows console failures; stored feed JSON remains UTF-8.
- Pushes changing `docs/**` on `main` trigger Pages. The content refresh may create a second feed commit and subsequent deployment. Before pushing, fetch and merge automated feed updates without discarding local content or conversations. Never force-push to bypass this race.
- Bump the service-worker shell version when changing cached assets so installed/offline clients receive the change.
- Public source network access, Git metadata writes, and deployment required tool-level sandbox escalation in this session. No credentials were printed or committed.
- Original `scrollforge_master_spec.md` and duplicate orchestration plan describe an earlier design. The current code, README, memory, and change log reflect the deployed implementation.

## Last published state and regression lessons

- Last feature commit: **`93ac88a`**, followed by automatic feed refresh **`dc885e2`**. Earlier releases: `98dc01c`, `4fb5f41`, `6abd389` and `0b88953`.
- October 25 Pages deployments succeeded: https://github.com/floogle11/scrollforge/actions/runs/40216856179 and the post-refresh deployment https://github.com/floogle11/scrollforge/actions/runs/40216886871.
- Independent GitHub checks for this feature release succeeded: https://github.com/floogle11/scrollforge/actions/runs/40216856160. Local full-suite run passed 132 tests; one additional generation-contract test and focused final checks also passed. GitHub checks include the added test (133 total).
- Latest verified live snapshot (`last_updated` **2026-10-25T17:31:25Z**): **867 posts**, **452 quizzes**, **60 added questions**, and **20 topic posts**. Live mobile checks verified exact integration-by-parts answers, rendered KaTeX, function-specific plots, quiz feedback/retry, no horizontal overflow and no JavaScript errors. Feed/marker timestamps and byte counts match. All 2,164 bank math expressions also rendered without KaTeX errors in local browser verification.
- The first expansion run exposed issues on Linux Chromium that local Windows checks had missed. They were fixed and the successful final run supersedes that failure.
- **Short final posts need scroll space below them.** `.feed-end` has `min-height: calc(100svh - 160px)` so `scrollIntoView({block:'start'})` can align a final short post under the sticky header. Do not remove this without preserving that behavior; a tall-viewport regression test covers it.
- **Read-tracking is asynchronous.** Clearing seen storage immediately before reload races IntersectionObserver. Saved-answer tests now reload and explicitly reopen engineering review, matching intended product behavior.
- A real-data mobile preview verified rendered KaTeX math, the illustrated multiple-choice layout, Mammoth filtering, official Reddit iframe creation, no horizontal overflow, and no JavaScript errors.
- Verified published content snapshot (`last_updated` **2026-10-25T04:27:03Z**): **541 posts**, **200 quizzes**, **20 topic posts**, **75 hockey posts**, including **57 Mammoth**, **7 Avalanche**, and **41 drama posts**. Counts overlap and change as sources refresh/expire.
- Prior October 24 live snapshot (`last_updated` **2026-10-25T05:37:00Z**) had **730 posts**, **392 quizzes**, and **20 topic posts**. Its automatic refresh and both deployments passed. A real live mobile browser verified saved preference-button state, Calc III subject filtering, quiz feedback, rendered math, no horizontal overflow, and no JavaScript errors. Published feed and marker timestamps/byte counts matched.
- Latest local verification: **126 tests passed**, with real mobile/desktop Chromium checks, 48 new independent calculation references, subject rendering/filtering, local preference reversal/reset/persistence, unchanged-marker request avoidance, feed budget rejection and feed/marker publication recovery. Offline pipeline dry run, JS syntax and diff whitespace checks also passed.
- The user explicitly requested deployment of this follow-up. It is published and verified; no deployment step remains outstanding.
