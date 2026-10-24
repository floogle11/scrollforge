# ScrollForge: Master Product Requirements & Multi-Agent Orchestration Plan (Zero-Ops Serverless Edition)

---

# PART 1: Product Requirements Document (PRD)

## 1. Executive Summary & Vision
* **Objective:** Build a zero-maintenance, mobile-first Progressive Web App (PWA) and automated daily content pipeline hosted entirely on GitHub (GitHub Pages + GitHub Actions). ScrollForge harnesses the psychological mechanics of social media doomscrolling (variable-ratio reinforcement and zero-friction skipping) to deliver a personalized stream of NFL/Denver Broncos news, curated Reddit narratives, and active-recall Mechanical Engineering problems.
* **Core Philosophy:** Traditional flashcard apps (e.g., Anki) fail to capture casual downtime because they introduce high cognitive friction, performance guilt, and monotonous predictability. Furthermore, complex self-hosted web stacks create setup and maintenance fatigue. ScrollForge eliminates all server management, `npm` build steps, and token bloat by using a **Git-Backed Static JSON Architecture** paired with a **Single-Shot Pre-Sliced LLM Batch Loop**.

---

## 2. Psychological & Engagement Mechanics (The "Addiction" Engine)
To compete with native social apps, the feed must obey strict behavioral design rules:

### 2.1 Variable-Ratio Reinforcement
* **Unpredictable Ordering:** The user never chooses the next card category. Swiping past a Denver Broncos injury report might reveal a quick Statics truss puzzle, followed by an `r/AskHistorians` story, followed by a Materials Science phase-diagram trap.
* **Cognitive Contrast (Interleaving):** Mixing high-engagement leisure with technical problem-solving prevents academic fatigue. The mixer enforces an interleaving rule: never display more than two `CHALLENGE_*` cards back-to-back.

### 2.2 Zero-Friction Skipping & Zero Guilt
* **Never Block the Scroll:** There are no mandatory multiple-choice buttons, required text inputs, or "Did you get this right?" grading gates before advancing. If the user is tired and skips five engineering cards in a row, the app imposes zero friction or visual penalty.
* **Single-Viewport Density:** Every card (excluding expandable full-text stories) must fit within a single mobile screen (`390x844` viewport). Problems must be framed as punchy puzzles, "spot-the-error" snippets, or intuitive gut-checks under 75 words.

### 2.3 Micro-Dopamine Triggers
* **Instant Verification:** Technical cards feature a single-tap expandable drawer (`[ Tap to Reveal Solution ]`) that snaps open with a concise 2-to-4 line derivation or intuitive explanation.
* **Asynchronous Dialogue Reward:** Leaving a comment or question on a card creates a `pending-codex` GitHub Issue via REST API. On the next scheduled run, the pipeline answers the question, embeds the thread into `feed.json`, and lights up the `[ Inbox: N Replies ]` badge in the top bar.

---

## 3. Content Taxonomy & Dynamic Calendar Weighting

### 3.1 Card Archetypes
1. **Sports & Headlines (`SPORTS` / `NEWS`) — [0 LLM Tokens]:**
   * Automated RSS/JSON pulls covering the Denver Broncos, broader NFL news, and general tech/world headlines via Python `feedparser`.
2. **Curated Reddit Narratives (`STORY`) — [0 LLM Tokens]:**
   * High-engagement text posts or technical anecdotes pulled from selected subreddits via JSON/RSS feeds.
3. **Active Engineering Challenges (`CHALLENGE_CURRENT`):**
   * Drawn from pre-sliced active semester coursework chunks in `data/notes_index.json` (e.g., Fluid Mechanics, Thermodynamics, Machine Design, Heat Transfer).
   * Formats include:
     * *Spot the Flaw:* A 3-line derivation or Free Body Diagram description containing a subtle sign error, missing assumption, or wrong boundary condition.
     * *Order-of-Magnitude / Intuition Check:* "If pipe diameter doubles at constant flow rate $Q$, how does head loss $h_L$ scale?"
     * *Quick Calculation:* Clean numbers designed for mental math or back-of-the-napkin solving in under 60 seconds.
4. **Foundational Refresher (`CHALLENGE_PAST`):**
   * Spaced-repetition pulls from prior semesters (Statics, Dynamics, Mechanics of Materials, Calculus/Differential Equations).
5. **Real-World Engineering Deep-Cuts (`DEEP_CUT`):**
   * Bite-sized breakdowns connecting classroom theory to real hardware (e.g., polycrystalline diamond cutter thermal stress, airfoil stall characteristics, or hybrid planetary gearset kinematics).

### 3.2 Calendar-Driven Proximity Weighting
During each scheduled GitHub Action run, plain Python fetches the next 10 days of events from the user's `.ics` calendar URL, scanning for keywords (`Exam`, `Midterm`, `Final`, `Quiz`, `Project`) and matching course codes.

| Calendar State | Sports & News | Reddit Stories | Current Coursework (Targeted) | Past Course Refresher |
| :--- | :--- | :--- | :--- | :--- |
| **Baseline (Clear Calendar)** | 30% | 20% | 30% | 20% |
| **Exam Window (3–6 Days Out)** | 20% | 15% | 55% (Heavily weighted to exam topic) | 10% |
| **Crunch Window (1–2 Days Out)** | 25% | 15% | 55% (High-yield formulas & pitfalls) | 5% |
| **Exam Day (Decompression)** | 50% | 35% | 15% (Light warmup only) | 0% |

---

## 4. Token-Conserving Pipeline & Asynchronous Comment Loop

### 4.1 Strict Token Budget (~98% Reduction vs. Agentic Browsing)
To prevent the twice-daily schedule from blowing out API usage limits:
1. **Local Note Pre-Slicer (`scripts/slice_notes.py`):** Whenever raw PDFs or Markdown files are added to `/notes_raw`, this deterministic Python script extracts text (via `PyMuPDF`) and slices it into 250–350 word concept chunks inside `/docs/data/notes_index.json`. **Zero LLM tokens are used to index files.**
2. **Python Sampler (`worker/sampler.py`):** During the scheduled cron job, plain Python reads the calendar weights and randomly selects **only 5 to 6 text chunks** (~1,500 tokens total) from `notes_index.json`.
3. **Single-Shot Structured LLM Call (`worker/generate_batch.py`):** Instead of running an unbounded multi-turn agent loop, the worker makes **one single structured JSON API request** per run containing:
   * Open user comments fetched from GitHub Issues tagged `pending-codex`.
   * The 5–6 sampled note chunks.
   * System instructions to return a strict JSON object with `comment_replies[]` and `new_cards[]`.

### 4.2 Serverless Mobile Commenting via GitHub Issues Bridge
Because there is no backend server to maintain:
* **One-Time Token Entry:** The user pastes a fine-grained GitHub Personal Access Token (scoped only to this repository's Issues/Contents) into the PWA's `[ Settings ]` modal, which stores it in browser `localStorage`.
* **Posting a Comment:** Tapping `[ Comment / Ask Follow-up ]` on any card sends a `POST https://api.github.com/repos/{owner}/{repo}/issues` request with:
  * `title`: `"Comment on Card: {card_id}"`
  * `labels`: `["pending-codex"]`
  * `body`: JSON payload containing `card_id`, `course_tag`, and `user_comment`.
* **Optimistic UI:** The mobile app immediately shows the user's comment on the card as `Queued for Next Codex Run` using `localStorage` until the next GitHub Action run merges the official reply into `/docs/data/feed.json` and closes the GitHub Issue.

---

## 5. Visual Design & Styling Guide (Anti-Default-Codex)
**Strict Directive:** Avoid the generic "AI / SaaS boilerplate" aesthetic—no pastel purple/blue gradients, no oversized bubbly rounded corners (`border-radius: 24px`), no floating glassmorphism blobs, and no sterile corporate typography.

### 5.1 Design Aesthetic: "Industrial Dark-Mode Technical HUD"
Inspired by high-density engineering schematics, factory telemetry interfaces, and classic dark-mode terminal readers. Tactile, high-contrast, scannable, and utilitarian.

### 5.2 Color Palette
* **Primary Canvas Background:** Deep Obsidian (`#0D0F12`)
* **Card Surface Background:** Gunmetal Slate (`#16191E`)
* **Card Border / Dividers:** Machined Hairline (`1px solid #282D37`)
* **Primary Text:** Crisp Off-White (`#ECEFF4`) — prevents halation during night scrolling
* **Secondary / Metadata Text:** Muted Steel (`#8A94A6`)
* **Category Accent Tags (Left-Border `3px` Stripe + Pill Badge):**
  * **Broncos / NFL News:** Victory Orange (`#FB4F14`) with Navy subtle fill (`#0A2342`)
  * **Engineering Challenge:** Amber Gold / Brass (`#E5A93C`)
  * **Reddit / Narrative:** Cyan Telemetry (`#38BDF8`)
  * **Codex Reply / Active Thread:** Phosphor Green (`#10B981`)

### 5.3 Typography & Layout Rules
* **Body & Headings:** Clean, compact geometric sans-serif (`IBM Plex Sans` or `Inter` loaded via Google Fonts), tight line-height (`1.45`) for rapid scanning.
* **Equations, Numbers & Metadata:** Crisp monospace (`JetBrains Mono` or `IBM Plex Mono`) for all timestamps, category tags, problem parameters, and code/math blocks.
* **Math Rendering:** Native KaTeX CDN integration for instant, zero-layout-shift rendering of inline ($...$) and block ($$...$$) equations.
* **Geometry:** Sharp, mechanical corners (`border-radius: 4px`), compact padding (`14px 16px`), and exposed `1px` structural borders.

---

## 6. Zero-Ops System Architecture & JSON Contracts

### 6.1 Repository Layout
```text
/
├── .github/workflows/
│   └── scrollforge_cron.yml   # Runs at 06:00 & 18:00 daily + manual workflow_dispatch
├── contracts/
│   ├── feed_schema.json       # Immutable JSON schema for /docs/data/feed.json
│   └── llm_output_schema.json # Strict schema for the single-shot OpenAI/Codex API call
├── notes_raw/                 # Drop raw course PDFs, syllabi, and .md notes here
├── scripts/
│   └── slice_notes.py         # Deterministic PDF/MD chunker -> /docs/data/notes_index.json
├── worker/
│   ├── calendar_weights.py    # Parses ICS_CALENDAR_URL -> category ratio dict
│   ├── ingest_rss.py          # Zero-token RSS/Reddit fetcher
│   ├── generate_batch.py      # Resolves pending GitHub Issues + generates 6 cards in 1 call
│   └── run_pipeline.py        # Merges cards, trims archive to 300 cards, writes feed.json
└── docs/                      # Served directly by GitHub Pages (Zero npm build step!)
    ├── index.html             # Single-page entry point + KaTeX CDN
    ├── manifest.json          # Mobile PWA install manifest
    ├── tokens.css             # Industrial Technical HUD stylesheet
    ├── app.js                 # Vanilla ES6 feed mixer, swipe handler, GitHub Issue bridge
    └── data/
        ├── feed.json          # Active cards + resolved comment threads
        └── notes_index.json   # Pre-sliced 300-word course note chunks
```

### 6.2 Core JSON Contract (`contracts/feed_schema.json`)
```json
{
  "last_updated": "2026-10-24T12:00:00Z",
  "calendar_mode": "EXAM_WINDOW",
  "active_exam_course": "ME-3050",
  "cards": [
    {
      "id": "card_20261024_001",
      "created_at": "2026-10-24T12:00:00Z",
      "category": "CHALLENGE_CURRENT",
      "course_tag": "ME-3050",
      "title": "Moody Diagram Fully Rough Zone",
      "body_markdown": "Pipe flow enters the **fully rough turbulent zone** at high $Re$. If you double the flow velocity while keeping fluid properties and pipe geometry constant, how does the Darcy friction factor $f$ change?",
      "solution_markdown": "**Intuition:** In the fully rough regime, viscous sublayer thickness is negligible compared to roughness height $\\epsilon$, so $f$ becomes completely independent of $Re$.\n\n$$f = \\text{constant} \\implies \\Delta f = 0\\%$$\n*(Note: Head loss $h_L \\propto V^2$ still quadruples!)*",
      "source_url": null,
      "parent_card_id": null,
      "comments": [
        {
          "id": "comm_101",
          "author": "USER",
          "body_markdown": "Wait, does that mean viscosity drops out of the head loss calculation entirely here?",
          "created_at": "2026-10-24T13:10:00Z"
        },
        {
          "id": "comm_102",
          "author": "CODEX",
          "body_markdown": "Spot on. Once you're to the right of the dashed transition line on the Moody chart, inertial form drag on the roughness elements dominates skin friction. Dynamic viscosity $\\mu$ no longer affects $f$ or $h_L$.",
          "created_at": "2026-10-24T18:00:00Z",
          "unread": true
        }
      ]
    }
  ]
}
```

---
---

# PART 2: Multi-Agent Work Breakdown (GPT 6.1-Sol Orchestrating Codex Luna Agents)

## 1. Execution Dependency DAG

```text
                      ┌─────────────────────────────────────────┐
                      │       PHASE 0: GPT 6.1-Sol (Lead)       │
                      │  Lock JSON Contracts, Folder Tree, &    │
                      │  Seed Sample Note + Initial feed.json   │
                      └────────────────────┬────────────────────┘
                                           │
            ┌──────────────────────────────┼──────────────────────────────┐
            ▼                              ▼                              ▼
┌───────────────────────┐      ┌───────────────────────┐      ┌───────────────────────┐
│      LUNA-ALPHA       │      │       LUNA-BETA       │      │      LUNA-GAMMA       │
│  Note Pre-Slicer &    │      │  Calendar, RSS & 1-   │      │  Zero-Build Vanilla   │
│  Indexer (`/scripts`) │      │  Shot LLM (`/worker`) │      │  HUD PWA (`/docs`)    │
└───────────┬───────────┘      └───────────┬───────────┘      └───────────┬───────────┘
            │                              │                              │
            └──────────────────────────────┼──────────────────────────────┘
                                           ▼
                      ┌─────────────────────────────────────────┐
                      │            LUNA-DELTA (QA)              │
                      │   GitHub Actions Workflow, E2E Dry-Run  │
                      │         & Automated Git Push            │
                      └─────────────────────────────────────────┘
```

---

## 2. Codex Luna Agent Workstreams

### Agent 1: `Luna-Alpha` — Deterministic Note Slicer & Local Indexer
* **Exclusive Workspace:** `/scripts` and `/notes_raw`
* **Deliverables:**
  * `slice_notes.py`: Scans `/notes_raw` for `.md`, `.txt`, and `.pdf` files (using `pymupdf` / `fitz`), splits content into clean 250–350 word conceptual blocks tagged by course folder name (e.g., `/notes_raw/ME-3050_Fluids/`), and writes `/docs/data/notes_index.json` using deterministic content hashes so unchanged files are never re-processed.
* **Acceptance Criteria:** Processes sample notes in `<1 second` with zero LLM API calls.

### Agent 2: `Luna-Beta` — Calendar Engine, Zero-Token RSS & Single-Shot Batch Worker
* **Exclusive Workspace:** `/worker`
* **Deliverables:**
  * `calendar_weights.py`: Fetches `ICS_CALENDAR_URL` env var (falling back gracefully to `Baseline` weights if empty), detects upcoming exams within 10 days, and outputs the target card counts.
  * `ingest_rss.py`: Pulls Denver Broncos, NFL, and curated Reddit RSS feeds into normalized `SPORTS`, `NEWS`, and `STORY` card dictionaries without invoking any LLM.
  * `generate_batch.py`: Queries GitHub Issues labeled `pending-codex`, samples 5–6 chunks from `/docs/data/notes_index.json`, and executes **one single structured LLM call** (`OPENAI_API_KEY`) to generate all comment replies, follow-up cards, and new engineering challenge cards at once. Closes resolved GitHub Issues via REST API.
  * `run_pipeline.py`: Combines RSS cards + LLM cards, updates `/docs/data/feed.json`, and caps total stored cards at 300.

### Agent 3: `Luna-Gamma` — Zero-Build "Industrial Technical HUD" PWA
* **Exclusive Workspace:** `/docs`
* **Deliverables:**
  * `tokens.css` & `index.html`: Zero-build Vanilla HTML/CSS/JS app with KaTeX CDN and `manifest.json` for iOS/Android home-screen installation. Strictly enforces the `#0D0F12` Obsidian / `#16191E` Gunmetal / `#FB4F14` Broncos Orange / `#E5A93C` Brass HUD aesthetic.
  * `app.js`:
    * Loads `/docs/data/feed.json`, tracks `seen_card_ids` and `read_comment_ids` in `localStorage`.
    * Interleaves unseen cards so no more than two `CHALLENGE_*` cards appear consecutively.
    * Supports touch-swipe on mobile and `j`/`k`/`Space`/`c` hotkeys on desktop.
    * Implements the `[ Settings ]` modal (to store the user's GitHub Repo Token & Repo Slug in `localStorage`) and the GitHub Issues `fetch()` POST bridge for instant inline commenting.

### Agent 4: `Luna-Delta` — GitHub Actions Automation & E2E Verification
* **Exclusive Workspace:** `/.github/workflows`, `/tests`, and root `requirements.txt`
* **Deliverables:**
  * `.github/workflows/scrollforge_cron.yml`: Runs on `schedule: [{cron: '0 12,0 * * *'}]` (6 AM / 6 PM MDT) and `workflow_dispatch`. Installs `requirements.txt`, runs `python scripts/slice_notes.py` and `python worker/run_pipeline.py`, and commits/pushes updated `/docs/data/feed.json` back to `main`.
  * `tests/test_e2e.py`: Verifies the entire pipeline offline/dry-run, ensuring `feed.json` validates against `contracts/feed_schema.json`, then stages and commits the initial working repository.

---

## 3. Copy-Paste Master Prompt for GPT 6.1-Sol

```text
# ROLE: Lead System Orchestrator (GPT 6.1-Sol)
You are orchestrating a fleet of Codex Luna agents to build and deploy "ScrollForge" (Zero-Ops Serverless Edition) as defined in `scrollforge_master_spec.md`.

## CRITICAL ZERO-SETUP DIRECTIVE
The user wants ZERO manual build steps, ZERO server maintenance, and minimal token usage. You and your sub-agents must build the complete system, populate `/docs/data/feed.json` with a rich initial batch of 15 realistic sample cards (Broncos news, Reddit stories, and ME problems with KaTeX equations) so the app works the second it is pushed, pass all E2E tests, and commit/push the finished code to the git remote.

## EXECUTION SEQUENCE
1. **Phase 0 (You):** Create the directory tree, write `/contracts/feed_schema.json` and `/contracts/llm_output_schema.json`, and seed `/notes_raw/ME_Sample_Notes.md` with sample Fluids, Thermo, and Statics concepts.
2. **Parallel Agent Spawn:**
   - **Luna-Alpha (`/scripts`):** Build `slice_notes.py` and generate `/docs/data/notes_index.json`.
   - **Luna-Beta (`/worker`):** Build the `.ics` calendar parser, zero-token RSS fetcher, and single-shot LLM batch generator + GitHub Issue comment resolver.
   - **Luna-Gamma (`/docs`):** Build the zero-build Vanilla JS/CSS/KaTeX Industrial HUD PWA (`#0D0F12` canvas, `#16191E` cards, `4px` corners, `#FB4F14` Broncos stripe, `#E5A93C` Brass challenge stripe, mobile swipe + `j/k/Space/c` hotkeys, Inbox Drawer, and GitHub Issues comment bridge).
3. **Phase 2 (`Luna-Delta`):** Write `requirements.txt`, `.github/workflows/scrollforge_cron.yml`, run `tests/test_e2e.py`, seed `/docs/data/feed.json` with 15 realistic initial cards, and run `git add . && git commit -m "Initialize ScrollForge Zero-Ops PWA" && git push`.
```