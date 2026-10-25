# Change log

Dates below use America/Denver. The evening releases on October 24, 2026 correspond to October 25 UTC. Automated feed-refresh commits are omitted except where needed to explain deployment state.

## 2026-10-24 — Feed diversity, learned interests, foundational review and hosting budgets

Feature commit **`98dc01c`**, followed by automatic feed refresh **`2942e1b`**. Both Pages deployments succeeded; live mobile verification passed. Earlier published release evidence remains below for history.

- Reworked For you mixing to avoid adjacent broad groups while alternatives remain, and seek different publishers, teams and subjects inside a group. Retained randomized weighting, calendar profiles, seen-source exclusion and chronological New sorting. A single-category tail remains possible after other inventory is exhausted.
- Added More like this / Less like this to every post. Signals learn recurring recognized topics, favorite teams, courses, publishers and subreddits. Votes toggle off or switch direction; Settings summarizes trends and resets feed preferences independently of credentials. Browser-only storage retains up to 500 signals with a 45-day half-life, no backend/model calls or remote vote writes. Reading is not counted as liking. Preference weights retain exploration.
- Voting remixes only unmounted content. Existing posts, drafts, quiz state and reading position remain in place.
- Added 192 original calculated foundation questions: 32 each for Calculus I/II/III and Physics I/II, plus 16 each for linear algebra and differential equations. These are 48 concepts with four numerical variants apiece. The total reproducible bank is now 392 quizzes and 20 topic posts. Stable IDs preserve existing conversations. Added math/physics vector schematics and an Engineering subject selector.
- Regenerated the local feed: 731 posts, including 392 quizzes. No AI generation, private-source publication or new source fetching was required.
- Added 5 MiB feed/per-file and 20 MiB site budgets, enforced by CI, content refresh and Pages deployment. Atomic writers reject oversized feed data before replacement. Size report verifies the marker and estimates gzip/transfer capacity. GitHub's documented limits were checked against the official Pages documentation.
- Added a tiny feed-meta.json version marker. Visible/online polling checks every five minutes and skips the full archive when unchanged; explicit refresh and marker-failure fallback remain available. Updated both RSS and desktop publication paths, including cached-outbox crash/push-race recovery, to include the marker.
- Bumped the deployed offline cache to scrollforge-shell-v8. Total published data after refresh is 742,395 bytes, including a 610,839-byte feed (~97,926 bytes gzip estimate). Actual monthly traffic and remote Git history are not measured by the size guard.
- Validation: **126 tests passed locally**, including mobile/desktop preference persistence, reversal/reset, retained drafts/DOM, group diversity, trend decay, all foundation subjects/diagrams, offline feed loading, unchanged-marker transfer avoidance, independent reference answers for all 48 new numerical templates, budget rejection with original-data preservation, and desktop feed/marker crash/push-race recovery. JavaScript syntax, the offline pipeline dry run and `git diff --check` also passed.
- Deployment: [feature deployment](https://github.com/floogle11/scrollforge/actions/runs/40166162971), [post-refresh deployment](https://github.com/floogle11/scrollforge/actions/runs/40166188075), and [content refresh](https://github.com/floogle11/scrollforge/actions/runs/40166162877) succeeded. Published snapshot: **730 posts, 392 quizzes and 20 topic posts**, last updated 2026-10-25T05:37:00Z. Live mobile browser checks confirmed preference controls, Calc III filtering, quiz feedback, rendered math, no horizontal overflow and no JavaScript errors; feed/marker timestamps and byte counts match.
- [Independent GitHub checks](https://github.com/floogle11/scrollforge/actions/runs/40166162923) also succeeded for the feature commit.

## 2026-10-24 — Conversation continuity documentation

- Added `MEMORY.md` with the user's preferences, current implementation, content and generation settings, deployment evidence, regression lessons, and Windows workflow details.
- Added `AGENTS.md` as the repository entry point for future agents and linked the memory and change history from `README.md`.
- Recorded the feature-release history below, distinguishing fixed initial failures from the successful final validation. These documentation changes do not change the running site.

## 2026-10-24 — Final browser regression fix

Commit: **`4fb5f41`** — Keep short final posts reachable and stabilize saved-answer browser checks.

- Added sufficient space at the end of the feed for a short final post to align beneath the sticky header. This fixes keyboard/active-post tracking near the document bottom.
- Added a tall-viewport regression test that scrolls every displayed post into position.
- Corrected quiz persistence tests to reopen engineering review after reload, rather than racing asynchronous seen-state writes by manually clearing storage.
- Bumped the offline shell cache to **`scrollforge-shell-v7`**.
- Validation: final GitHub run passed all **69 tests**, including real-browser checks. Pages deployment and the published CSS/cache version were verified.
- [Successful checks](https://github.com/floogle11/scrollforge/actions/runs/40162194551), [successful deployment](https://github.com/floogle11/scrollforge/actions/runs/40162194635).

## 2026-10-24 — Illustrated reviews, larger inventory, hockey, and Reddit previews

Commit: **`6abd389`** — Add illustrated review bank, continuous scrolling, hockey and Reddit previews.

The user wanted the approved Reddit feel with substantially more content, illustrated school questions, optional multiple choice, favorite-team hockey, occasional drama, and direct Reddit posts to reduce AI generation work.

- Added **200 original multiple-choice questions and 20 short topic posts** across fluids, thermodynamics, statics, machine design, and system dynamics. The bank includes concept questions and computed numerical variants with stable IDs and deterministic answer ordering.
- Added original vector diagrams with accessible descriptions and givens. Different diagrams cover physical setups such as turbines, heat engines, refrigerators, springs in series/parallel, beam loads, stress elements, Mohr circles, and two-force members. Older challenge posts also received diagrams.
- Added four-to-eight-option quiz support, correctness feedback, worked solutions, retry, and persistent answer selections. The starter bank uses four options. Answers are invalidated if their option set changes.
- Added optional quiz, diagram, sports/team/topic, and image fields to the feed contract. Generated challenges now require a quiz and illustration; semantic validation checks the answer index against actual option count.
- Added **24-post automatic pagination** with a load-more fallback. Preserved mounted DOM and drafts. Filters and search include unloaded content; newest sorting works with appended pages.
- Added NHL, Utah Mammoth, Colorado Avalanche, and drama filtering. Added favorite-team chips and hockey navigation to desktop and mobile layouts.
- Added ESPN NHL/team feeds and official NHL team-page metadata ingestion. Utah's official team path is `/utah/`; verified team IDs are Utah 129764 and Colorado 17. Official imports use real publication dates, short descriptions, and article images.
- Added more Reddit communities, including active `r/Utah_Hockey` and story/drama sources. `r/pettyrevenge` supplied drama posts during verification; several other Reddit feeds were rate-limited.
- Added on-demand original Reddit previews through a sandboxed official embed iframe, with original-post links and validated resize messages. No AI rewrite is needed for imported posts.
- Expanded refresh intake to up to 180 sports, 180 news, and 100 story posts. Raised archive capacity from 300 to **1,500**, prioritizing pending parents and the original review bank.
- Changed baseline browser mixing to football 25%, hockey 20%, news 25%, other stories 11%, drama 4%, and school 15%, while all pools have unread content. Exam profiles still adjust the mix.
- Increased recurring local generation from at most six to **20 cards per batch**, up to twice daily, with a 300-second timeout. Added quiz/diagram instructions and recent review titles to generation context.
- Added original committed machine-design/system-dynamics note outlines; the public sliced note index grew from six to eight chunks. The private library remained ignored.
- Added review-bank calculations/contract checks and browser coverage for quizzes, saved answers, pagination, team filtering, and original Reddit previews.
- Initial local suite passed 68 tests. Independent Linux browser testing found the two issues corrected by `4fb5f41`; that final fix added the 69th test.
- Published content after the accompanying refresh reached **541 posts**, with 200 quizzes, 20 topic posts, 75 hockey posts, and 41 drama posts. Counts are a snapshot, not a fixed target.

## 2026-10-24 — Reddit-style redesign and expanded news

Commit: **`0b88953`** — Redesign feed with Reddit styling and expand NFL and news sources.

- Replaced oversized, technical-looking cards with compact Reddit-style dark posts, clearer source attribution, a sticky searchable header, topic sidebar, community rail, mobile topic tabs, rounded controls, and responsive spacing.
- Added topic filtering, search, and mixed/newest sorting while preserving answers and comment drafts.
- Reduced baseline coursework emphasis from half the feed to **15%** and increased the leisure/news share.
- Fixed a headline bottleneck that kept only three or four posts per refresh. Introduced separate 40-sports, 40-news, and 20-story intake pools; these were enlarged in the next release.
- Added ESPN, BBC, NPR, The Guardian, NASA, Smithsonian, and more public Reddit feeds. Corrected NFL/Reddit sports categorization and bounded imported excerpts.
- Increased public-source refresh frequency from twice daily to **every three hours**. Isolated feed failures and used concurrent source fetching.
- Updated PWA metadata and bumped the shell cache to v5.
- Fixed JSON CLI output on legacy Windows consoles by escaping non-ASCII output while preserving UTF-8 stored content.
- Validated with **54 passing tests**, successful GitHub checks, and a verified GitHub Pages deployment. The user explicitly approved the resulting look and feel.

## 2026-10-24 — Earlier foundation retained by these releases

Reference commit: **`1b03b2d`** — Use local Codex loop and native scrolling feed.

- Established native document scrolling with persistent cards, engineering review, keyboard navigation, comments, and a reply inbox including archived threads.
- Replaced the historical API-generation proposal with a local Codex CLI workflow using the saved ChatGPT login and an isolated desktop checkout.
- Added scheduled question handling, bounded generation, durable outbox recovery, and reply publication before GitHub Issue closure.
- Retained independent public-source refresh, calendar weighting, deterministic note slicing, publication-age expiry, source deduplication, JSON validation, and offline support.
- These behaviors remain part of the current implementation. See `README.md` and `MEMORY.md` for operational details rather than relying on the old master specification.
