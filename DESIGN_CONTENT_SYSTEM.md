# FlatFeed — Design & Content System

**Status:** Normative. Single source of truth for UI, layout, components, copy, terminology, and case-study content.
**Date:** 2026-07-07 (landing sections updated for the "Swiss International" redesign; see §34).
**Basis:** source code inspection (`main.py`, `flatfeed/`, `synthetic/`, `eval/`), the rendered case-study page (`docs/case-study.html` + `docs/styles.css`), and the project docs (`README.md`, `docs/PROJECT_CONTEXT.md`, `CASE_STUDY.md`). No formal UX/content audits have been run yet; rules marked CURRENT describe today's implementation and were confirmed by reading the code, not by audit findings.

**Rule keywords.** MUST = mandatory project rule. SHOULD = default; deviate only for a stated reason. MAY = permitted option. MUST NOT = prohibited. Rules without a keyword are descriptive context.

**Decision statuses.** Where a rule required judgment, it is tagged:
- **CURRENT** — how the implementation behaves today (not automatically the standard).
- **ADOPT** — current behavior confirmed as the standard.
- **UNRESOLVED** — no rule yet; see §30 for the temporary default.

---

## 0. Quick Start for Agents

Before making a change, identify the touched surface and read the relevant route below. Then apply the verification matrix in §31; do not default to the heaviest checks when the change is documentation-only.

| Change surface | Read first | Non-negotiable invariants |
|---|---|---|
| Bot UI or renter/admin copy | §§7, 10, 17–20, 31 | One message = one purpose; sanctioned emoji only; listing-card field order unchanged; destructive/costly actions confirm with consequence-named buttons |
| Parser, matching, WBS, transit, or eval | §§2–3, 10–13, 20, 23, 27, 31 | Deterministic matching owns user-facing decisions; fail closed; WBS semantics live in `flatfeed/wbs_rules.py`; eval numbers update everywhere together |
| AI QA | §§2–3, 11–12, 21, 23, 31 | Admin-only, budgeted, versioned, non-mutating; ground truth and case tags never enter prompts |
| Case-study landing page | §§4–6, 13–15, 22–27, 32–34 | Synthetic/mock qualifiers stay at reading depth; ownership language preserved; 7-part structure and mockup honesty preserved |
| Public docs | §§16–27, 31, 33 | Evidence labels, terminology, and ownership stay meaning-identical across surfaces |
| Deployment or public URL claims | README + §§23, 27, 29, 35 | Verify before stating as FACT; do not guess canonical GitHub/Page URLs |

**Rule levels.**
- **Invariants** are product/legal/trust boundaries: AI never mutates, ground truth is eval-only, privacy copy is safe, listing-card contract and WBS semantics stay canonical, synthetic evidence is labeled at the same reading depth.
- **Current implementation rules** describe today's selectors, breakpoints, token names, layout components, and mockup structure. Follow them when editing the current surface; change them only with §34 governance.
- **Review gates** are the checklists and verification commands in §§31–33. Choose the gate by risk and surface, then record any skipped high-cost check in the handoff.

---

## 1. System Purpose

This document answers: *exactly how should interface elements and texts in this project look, be positioned, be named, and behave?*

**Who uses it:** AI coding agents (Claude/Fable, Codex), human developers, and anyone doing design, code, or content review on FlatFeed.

**Surfaces covered:**
1. **Telegram bot UI** — `main.py` (aiogram): commands, persistent reply keyboard, inline keyboards, the 4-step filter wizard, listing cards (formatted in `flatfeed/matching.py`), admin panel, AI QA triage.
2. **Streamlit admin dashboard** — `flatfeed/dashboard/streamlit_app.py`: AI QA coverage, feedback quality, cost, parser risk patterns.
3. **Case-study landing page** — `docs/case-study.html` + `docs/styles.css`: the public AI PM portfolio page.
4. **Public repo docs** — `README.md`, `CASE_STUDY.md`, `docs/PROJECT_CONTEXT.md`: reader-facing evidence; they follow the content rules in §§16–26.

**Not covered:** `LOCAL_CONTEXT.md` (local-only, git-ignored — operational server/bot details MUST NOT leak into any covered surface); test internals; build tooling; future live source adapters (out of current demo scope).

**Source-of-truth order:** this file → `docs/PROJECT_CONTEXT.md` (product semantics detail) → `README.md` (commands and setup). For behavior, code constants win over any document: `flatfeed/wbs_rules.py` (WBS semantics), `flatfeed/matching.py` (card format), `flatfeed/ai_qa.py` (`CURRENT_AI_QA_PROMPT_VERSION`, risk thresholds), `eval/run_eval.py` (metrics). If this file is silent, follow the closest approved pattern in §28.

---

## 2. Product Context

Confirmed by `README.md`, `docs/PROJECT_CONTEXT.md`, `CASE_STUDY.md`:

- **Category:** Telegram bot + admin dashboard prototype for collecting Berlin WBS apartment listings through source adapters and matching them to saved user filters. The current demo uses a synthetic catalog with hidden ground truth instead of scraping real housing companies.
- **Primary users:** (a) a renter setting a filter and receiving matching listings in Telegram; (b) an admin reviewing AI QA findings and the dashboard; (c) case-study readers — recruiters, hiring managers, AI PMs. The target portfolio role is **AI Product Manager in a corporate environment**: reliability, explainability, privacy, defensibility, measurable AI quality, and cost control matter more than feature count.
- **Unit of work:** the *listing*. It flows through: source adapter → deterministic parsing → local transit enrichment → optional AI QA → deterministic matching → one-time notification.
- **Role of AI:** AI QA is the **only** AI surface. Listing parsing and matching are fully deterministic and make no LLM calls. Canonical boundary (from `docs/PROJECT_CONTEXT.md` and `README.md`): *AI QA may challenge the parser but cannot replace or mutate parsing rules, listing data, matching, or user-facing cards automatically. Findings are admin-only and require human feedback.*
- **Role of the human:** the admin triages every alerted finding as `Parser error` / `Parser correct` / `Borderline / unsure`; parser improvements are made by a human editing `flatfeed/parser.py` / `flatfeed/wbs_rules.py`.
- **Honesty constraint (product-level):** everything measurable is a *synthetic/demo* result unless a real production measurement exists. Demo metrics MUST be visibly labeled as synthetic evaluation metrics, never as production user-impact numbers.
- **Privacy constraint:** the bot stores only the Telegram ID, the saved filter, and notification-dedupe history; `/delete` and the `🗑 Delete my data` button remove them after an explicit confirmation. No real listings are scraped or redistributed; listing photos are licensed Wikimedia Commons demo assets (`assets/listing_photos/LICENSES.md`).

---

## 3. System Principles

Derived from the product's actual behavior — not imported from external systems.

**P1 — Determinism owns the user-facing decision.**
*Why:* eligibility (WBS, rent, rooms) must be predictable and explainable to be trusted.
*Implications:* parsing and matching stay rule-based; every match/no-match is traceable to a rule; unknown values fail closed (unknown Kaltmiete or rooms never match a specific filter).
*Anti-pattern:* letting an LLM decide, adjust, or "fix" any field that affects matching or cards.

**P2 — AI reviews; it never mutates.**
*Why:* the product's thesis is AI as a controlled QA layer with a hard boundary.
*Implications:* AI QA output lands in `ai_qa_reviews` and admin alerts only; risk at/above the configured threshold (default 75) alerts the admin; the admin's triage label is the decision of record.
*Anti-pattern:* auto-applying `suggested_values`; letting QA output touch `listings`, matching, or cards.

**P3 — Every number carries its provenance.**
*Why:* the portfolio credibility rests on never implying live systems or production impact.
*Implications:* eval metrics are labeled "synthetic golden-set eval"; QA cost shows the provider (mock = $0); transit minutes are geometric estimates with the `not calculated` fallback; demo photos are disclosed as not depicting the actual address.
*Anti-pattern:* quoting "100% accuracy" anywhere without "synthetic" at the same reading depth.

**P4 — Ground truth is eval-only.**
*Why:* the eval is only meaningful if the parser and AI QA cannot see the answers.
*Implications:* synthetic case tags and hidden truth fields MUST never appear in listing text, listing URLs, parser input, or AI QA prompts. They live in `synthetic/case_catalog.py` / `synthetic/golden_set.py` and are read only by `eval/run_eval.py`.
*Anti-pattern:* "helpfully" enriching a prompt with golden-set metadata.

**P5 — The user's cost of a wrong send is high; fail quiet, fail closed.**
*Why:* a notification about a dead or mismatched listing burns trust in one message.
*Implications:* activity is re-checked through the source adapter before delivery; failed checks mark the listing inactive and exclude it; notifications are deduplicated (`sent_listing_notifications`); at most 10 cards per action; partial collection never mass-marks unseen listings removed.
*Anti-pattern:* sending unverified candidates to hit a count.

**P6 — Domain terms are kept, glossed, never translated away.**
*Why:* WBS, Kaltmiete, Bezirk are the domain; removing them removes correctness.
*Implications:* the product is English-facing; WBS (Wohnberechtigungsschein) and Kaltmiete keep short plain-language explainers at the point of use (wizard hints); the visible filter label is `District` while the semantic unit is the Bezirk (12 Berlin Bezirke; Ortsteil/Kiez names normalize to a Bezirk).
*Anti-pattern:* renaming WBS to "housing certificate"; translating Kaltmiete to "cold rent" in UI.

**P7 — Destructive actions confirm; everything else flows.**
*Why:* the bot holds personal filter data; deletion is a privacy feature and must be both discoverable and safe.
*Implications:* `Reset filter` and `🗑 Delete my data` always ask an explicit Yes/No with unambiguous labels ("Yes, delete everything" / "No, keep my data"); the wizard always offers `⬅ Back` / `✖ Cancel`; the wizard is never forced on the user (`/start` shows the filter card with a `Set up filter` button instead).
*Anti-pattern:* one-tap destructive actions; trapping the user in a setup flow.

**P8 — Two audiences, two panels: user surface vs admin surface.**
*Why:* renters and the QA reviewer have different jobs and different vocabularies.
*Implications:* admin functions live behind the `🛠 Admin` button (shown only to `ADMIN_TELEGRAM_USER_IDS`) and the dashboard; user-facing copy never mentions parser internals, risk scores, or prompt versions; admin copy may be technical but stays plain.
*Anti-pattern:* leaking QA jargon into renter-facing messages; hiding admin diagnostics behind user flows.

---

## 4. Benchmark Map

References inform rules; they are never templates. Deviation from a reference is not itself a defect.

| Area | Primary reference | Project-specific rule |
|---|---|---|
| Bot conversation UX | Telegram Bot API / official bot design conventions | Persistent reply keyboard for the main story; inline keyboards for choices; commands published in the menu (§7) |
| Wizard flows | GOV.UK "one thing per page" | 4 fixed steps, `Step N/4` prefix, Back/Cancel on every step, hint at the point of the question (§7.3) |
| Listing card | Project (`flatfeed/matching.py`) | Fixed field order, bold HTML labels, canonical fallback strings (§10) |
| Dashboard | Streamlit defaults; question-driven headings | Title + question subheaders + caption provenance; no custom theming (§8) |
| Case-study page | Repo-local "Swiss International" rules in §5; the sibling Opsqora landing is a comparison example when available, not a required dependency | Hand-written HTML/CSS, token palette in `docs/styles.css`, 7-part case framework (§6.3, §22); accent split: FlatFeed teal, Opsqora ultramarine |
| Product copy | GOV.UK/GDS principles | §§16–19 |
| AI language | Project boundary (§2) + Microsoft AI wording guidance | §21 |
| Evidence integrity | AI PM portfolio evidence standards | Measured-on-synthetic beats claimed; label everything (§23) |
| Accessibility (web page only) | WCAG 2.2 AA | §15 |

**Conflict resolution order.**
*Product:* correctness of matching/eligibility → privacy/defensibility → real user task → existing validated behavior → project consistency → external references → visual preference.
*Copy:* correct meaning → clear action → comprehension → project terminology (§20) → GDS → style preference.
*Case study:* factual integrity → ownership clarity → fast comprehension → evidence → product judgment → AI PM relevance → persuasiveness.
Never choose "more impressive" over "more accurate".

---

## 5. Design Foundations (case-study page)

These tokens apply to `docs/case-study.html` / `docs/styles.css` only. The bot has no visual tokens (§7) and the dashboard uses stock Streamlit (§8).

The page uses the repo-local **"Swiss International" system** documented in this section: flat 1px-bordered panels, square corners, mono uppercase kickers, numbered sections, a browser-chrome demo frame, and a dark final CTA. The sibling Opsqora project is a useful comparison implementation when it is available, but this file is the source of truth for FlatFeed. The deliberate difference between the two sites is the accent: FlatFeed is teal, Opsqora is ultramarine. When one landing's system evolves, consider whether the other should receive the same pattern, but preserve the accent split and product-specific evidence.

### 5.1 Color — ADOPT

All colors come from `:root` in `docs/styles.css`. New page styles MUST use these tokens; new hex literals MUST NOT be introduced without updating this section.

| Token | Value | Role | Allowed usage | Prohibited usage |
|---|---|---|---|---|
| `--bg` | `#fbfcfb` | Page ground | Body background, sticky header backdrop (via `color-mix`) | — |
| `--surface` | `#ffffff` | Panels, cards | Panels, evidence cards, buttons, table backgrounds | — |
| `--wash` | `#f2f5f4` | Quiet plane | Demo-frame body, figcaption strip, quiet fills | Text |
| `--ink` | `#121a1b` | Primary | Headings, body, solid buttons, dark CTA background, `--rule` | — |
| `--ink-2` | `#4e5c5e` | Secondary text | Ledes, prose paragraphs, nav links | — |
| `--ink-3` | `#657473` | Tertiary text | Mono kickers, captions, labels, table headers | Long body text blocks |
| `--line` | `#e1e7e5` | Hairlines | 1px dividers, card borders, grid rules | Text |
| `--rule` | `#121a1b` | Structural rule | 2px section top rules, panel header underlines, table head rules | — |
| `--accent` | `#02776f` | Single accent — FlatFeed teal | Kicker numbers, step numbers, live-demo dot, health-list dots, "real" scope bullet, button hovers, selection, focus rings | Results values (amber's slot); long text |
| `--accent-deep` | `#045953` | Accent text/links | Link hovers, demo-live label, product-shot status column | — |
| `--accent-wash` | `#e7f4f1` | Accent wash | Quiet accent fills | Text backgrounds needing contrast |
| `--amber` | `#c86b05` | Measured/provenance emphasis | **Only** the Results table values (`.case-results-value`) and the "Synthetic on purpose" scope bullet | Anywhere else; small text |
| `--inverted` | `#ffffff` | Inverted text/surface | Text and hover fills inside the dark CTA, dark buttons, dark user-message bubble, selection text | New light panels; use `--surface` there |
| `--inverted-muted` | `rgba(255,255,255,0.62)` | Muted inverted text | Dark CTA body copy | Anything outside inverted zones |
| `--inverted-line` | `rgba(255,255,255,0.45)` | Inverted hairline | Secondary button border inside the dark CTA | Anything outside inverted zones |
| `--demo-shadow` | `0 36px 72px -48px rgba(18,26,27,0.45)` | Single elevation token | `.demo-frame` only | Any other shadow |

Rules:
- **Two-accent system (unchanged in spirit):** teal is the brand/structure accent; amber has exactly two permitted jobs: measured Results values and the synthetic/provenance scope bullet. A third accent MUST NOT be added, and amber MUST NOT spread beyond those slots.
- The page has no error/warning/success status colors — it is editorial, not operational. Do not import status palettes from the bot, the dashboard, or Opsqora's status set (`--ok`/`--warn`/`--bad` were deliberately not ported).
- The dark CTA and footer use `--ink` as ground with `--inverted` / `--inverted-muted` / `--inverted-line` — the only inverted zone on the page, except for dark buttons and the Telegram user-message mockup.

### 5.2 Typography — ADOPT roles

Three families, loaded via Google Fonts from the HTML head (this webfont import is a deliberate 2026-07-07 change; see §34):
- `--font-ui` **Inter** — body, buttons, nav, meta values.
- `--font-display` **Inter Tight** (600–700) — H1, section H2s, step titles, figure/metric values, boundary quote, wordmark.
- `--font-mono` **IBM Plex Mono** (500–600, uppercase + letter-spacing) — kickers, labels, captions, table headers, chips, listing-card fields.

The page must remain readable and structurally stable if Google Fonts are blocked or slow. Keep system-font fallbacks in every font token, do not make layout correctness depend on exact webfont metrics, and update §34 if fonts are removed, self-hosted, or changed. The rationale for external fonts is portfolio presentation consistency, not product functionality.

| Role | Font / weight | Size | Notes |
|---|---|---|---|
| Hero h1 | display 600 | clamp(38px → 76px), lh 1.02, ls −0.035em | first-person outcome statement |
| Section h2 | display 600 | clamp(28px → 48px), lh 1.06 | takeaway statements |
| Boundary quote | display 500 | clamp(24px → 42px), lh 1.18 | the AI-boundary sentence |
| Hero lede | ui 400 | clamp(16px → 20px) / 1.6 | `--ink-2` |
| Body prose (`.case-prose p`) | ui 400 | 16px / 1.7, max-width 680px | `--ink-2` |
| Kicker (`.kicker`) | mono 500 | 11px uppercase, ls 0.08em | `--ink-3`; index number span in `--accent` 600 |
| Figure/metric value | display 600 | 36px (figures), 26px (panel metrics), clamp(22–30px) (results) | tabular-nums; results values amber |
| Buttons (`.btn`) | ui 600 | 13px, padding 11×18 | square corners |
| Table headers / dt labels | mono 500 | 11–11.5px uppercase | `--ink-3` |
| Listing-card fields | mono 400 | 12px / 1.7 | mockup only |

Rules:
- Base body is 15px/1.5 `--font-ui`; long-form prose measure stays ≤680px.
- Display sizes use `clamp()` — do not add per-breakpoint font overrides.
- New text styles SHOULD reuse a role above rather than introduce a new size; do not add weights above 700.

### 5.3 Borders, Radius, Elevation — ADOPT

- **Square corners everywhere: border-radius 0.** No exceptions — dots and squares (7–8px `<i>` elements) are literal squares. Do not reintroduce radii.
- 1px `--line` hairlines divide and border; **2px `--rule` top rules** open every numbered section, the hero meta grid, and panel/table headers — this rule-line motif is the page's structure signal.
- Elevation: one shadow only — `--demo-shadow` on `.demo-frame`. Everything else is flat; `product-shot` inside the narrative is deliberately shadowless.
- No gradients anywhere. The sticky header uses `color-mix` transparency + `backdrop-filter: blur(10px)`, not a gradient.

### 5.4 Grid and Width — ADOPT

- One centered column: `.case` max-width **1140px** + 24px side padding.
- Sections are single-column: kicker + H2 head, then content blocks. The numbered mono kicker (`01`–`07`) is the page's navigation motif — keep it.
- Tiled bands are bordered grids with internal 1px `--line` dividers (no gaps): `case-figures` 4-up, `case-meta` 5-up. Open grids with gaps: `case-steps--five` 5-up (workflow), `case-points` 3-up, `case-scope-columns` 2-up, `case-built` prose+shot 2-up, `demo-frame-body` 2-up. All collapse per §14.
- The demo frame is full-width under the hero; the dark CTA is a full-width `--ink` block.

### 5.5 Icons and Imagery — ADOPT

- Icons are inline hand-written SVG strokes, stroke `currentColor`, width 2: 14px inside buttons (arrows, git-branch), 16px in panel headers. No icon library at runtime, no emoji on the page.
- Brand: `assets/flatfeed-logo-mark.png` at 26px in the header/footer wordmark, `alt=""` (decorative next to the visible name).
- Imagery: `assets/berlin-wbs-building.jpg` (demo listing photo) inside the listing-card mockup. The decorative CSS mini-map was removed in the 2026-07-07 redesign — do not resurrect it. Product "screenshots" are HTML mockups (`phone-panel`, `dashboard-panel`, `product-shot`) presented inside the labeled demo frame — CURRENT. If real screenshots are ever added (a stated next step in CASE_STUDY.md §7), they replace mockups only with captions stating they come from a real demo session.
- Any photo of a building MUST keep alt text disclosing it is a demo image, and licensing stays documented in `assets/listing_photos/LICENSES.md`.

---

## 6. Layout Systems per Surface

### 6.1 Telegram bot shell — ADOPT
**Purpose:** keep the main story reachable in one tap at all times.
**Anatomy:** persistent reply keyboard —

```text
🔎 Show matches
⚙ Filter    📂 All listings
🛠 Admin        (admins only)
```

— plus the published command menu: `/start`, `/filter`, `/matches`, `/help`, `/delete`. Inline keyboards carry contextual choices under the message they belong to.
**Rules:** the reply keyboard is the main navigation and MUST keep `Show matches` alone on the top row (it is the primary action). New global entries need a §34 justification; admin entries go into the admin inline panel, not the reply keyboard.

### 6.2 Filter card — ADOPT
`/start` and `/filter` show the user's filter card (`<b>Your filter</b>` + current values) with contextual inline actions: `Set up filter` (empty filter) or `Show matches` / `Edit filter` / `Reset filter` / `🗑 Delete my data` (saved filter). The privacy action stays on the card — discoverable, not buried in `/help`.

### 6.3 Case-study page shell — ADOPT
Skip link → sticky top bar (logo mark + "FlatFeed" + mono "Case study" sub-label; nav: Problem · Why AI · Approach · Results · Learned; `View repository` button) → hero (kicker "AI product management — case study · 2026", first-person H1, lede, CTAs `Read the case study` / `View repository`, 5-column meta `dl`: Role / Domain / Type / Data / Year) → **demo frame** (browser-chrome figure labeled "Demo · synthetic data" holding the phone panel + dashboard panel mockups, with a figcaption stating they are mockups, not screenshots) → the numbered **7-part case framework**: 01 The Problem (+ 4-up scope figures) · 02 Why AI? (+ 3-up points) · 03 My Role · 04 The Approach (+ 5-step workflow band) · 05 What I Built (+ dashboard product-shot, real-vs-synthetic scope columns, stack chips) → *unnumbered* AI-boundary pull quote → 06 Results (+ results table) · 07 What I Learned (+ 3-up points) → dark CTA block (`View repository` / `Read the Markdown version`) → footer (wordmark, provenance line, Repository + Markdown links).
The 7-part structure mirrors `CASE_STUDY.md` section-for-section — keep them in sync (§27); the boundary pull quote is deliberately outside the numbering. ≤920px the header wraps; the nav MUST stay reachable (horizontal scroll row), never `display:none` without replacement.

### 6.4 Dashboard composition — ADOPT
Order in `streamlit_app.py`: title `FlatFeed parser AI QA` + provenance caption → **Is AI QA running well now?** (coverage, current prompt-version caption) → **How useful is AI QA?** (feedback quality, false positives vs confirmed errors) → **How much does AI QA cost?** (tokens, dollars, budgets) → **Demo: parser made a mistake, AI checked it** (parser snapshot + raw listing text side by side) → **Where the parser is most at risk** (field-level patterns) → **How AI QA quality changed by version**.
The order is a narrative: health → value → cost → concrete example → risk map → history. New sections join this narrative; meta-text about data provenance lives in `st.caption` directly under the heading it qualifies.

---

## 7. Telegram UI System

The bot's "design system" is message structure, keyboards, and formatting discipline — there is no CSS.

### 7.1 Message formatting — ADOPT
- Parse mode is HTML. Allowed tags: `<b>` for labels and step prefixes, `<i>` for hints/explainers, `<a>` for the single `Open listing` link. No other markup, no code blocks in user-facing messages.
- One message = one purpose. A question message contains: optional `<b>Step N/4</b>` prefix → the question → optional one `<i>` hint. Listing cards are separate messages, one per listing, at most 10 per action.
- Emoji policy: emoji appear **only** as button-label prefixes from the existing set — 🔎 ⚙ 📂 🛠 📊 🗑 ⬅ ✖ — never inside message prose, never decoratively. Inline choice buttons (WBS values, districts, triage labels) are plain text. New emoji require a §34 entry.

### 7.2 Keyboards — ADOPT
- **Reply keyboard** = global navigation (§6.1). **Inline keyboards** = choices about the message above them.
- Choice grids: options flow in rows (districts 2–3 per row); mutually exclusive values are separate buttons, not toggles.
- Rent step: four `≤ N EUR` presets + `No limit` + free-text entry accepted.
- Every wizard step's last row is the nav row: `⬅ Back` (steps 2+) + `✖ Cancel`.
- Confirmation keyboards state the consequence in the label: `Yes, reset filter` / `No, keep it`; `Yes, delete everything` / `No, keep my data`; `Yes, run catalog QA` / `Cancel`. A bare `Yes`/`No` pair MUST NOT be used for destructive or costly actions.

### 7.3 Filter wizard — ADOPT
Four fixed steps, always in this order: **1 WBS → 2 District → 3 Max Kaltmiete → 4 Rooms.** Each shows `Step N/4`. Steps 1 and 3 carry the plain-language explainers (`WBS_HINT`, `KALTMIETE_HINT` in `main.py`) — the gloss lives at the point of the question, not in `/help`. The wizard is entered only by explicit user action (`Set up filter`, `Edit filter`, `/filter`); `/start` never forces it. If the bot restarted mid-setup, `SETUP_EXPIRED_TEXT` states what happened and restarts cleanly — never silently resume with lost state.

### 7.4 Admin panel — ADOPT
Behind `🛠 Admin` (admin IDs only). Actions: `Run QA demo`, `Review flagged issues`, `View QA metrics`, `Refresh catalog`, `Run catalog QA`, `📊 Effectiveness dashboard` (URL button when `DASHBOARD_URL` is set). QA triage on a flagged report offers exactly three labels: `Parser error` / `Parser correct` / `Borderline / unsure` — this vocabulary is load-bearing (it feeds the dashboard's feedback-quality metrics) and MUST NOT drift.

### 7.5 Failure and timeout messages — ADOPT principle
Manual refresh and listing actions have timeouts (`MANUAL_REFRESH_TIMEOUT_SECONDS`) and user-facing failure messages. A failure message states what failed and, for admins, where to look next ("Catalog QA failed. Check the logs."). Renter-facing failures never expose internals; they state the outcome and that the user can retry. Apologies, exclamation marks, and blame are out of register (§17).

---

## 8. Dashboard System

- Stock Streamlit components and theme — CURRENT/ADOPT. No custom CSS injection; the dashboard's credibility is its data, not its chrome.
- **Headings are the admin's questions** ("Is AI QA running well now?", "How much does AI QA cost?") — new sections keep this question form; the content answers it.
- Every metric block carries an `st.caption` with provenance and definitions; the current prompt version is always shown from `CURRENT_AI_QA_PROMPT_VERSION` (never hard-coded as a string).
- The worked example ("Demo: parser made a mistake, AI checked it") renders the parser snapshot and the raw listing text side by side — source data and AI output visually separated (§12.6).
- Charts: Streamlit-native (dataframe/altair defaults). Do not add a charting stack; label axes and state units in the caption when the chart cannot.
- The dashboard reads production-shaped tables (`ai_qa_reviews`, `api_logs`, `ingestion_runs`) — it is real measurement of the demo pipeline, not a mockup. Keep it that way: no hand-typed numbers.

---

## 9. Action Hierarchy

| Level | Treatment | Placement | Wording |
|---|---|---|---|
| Global primary | Top row of the reply keyboard, alone | `🔎 Show matches` | Verb + object |
| Global secondary | Second reply-keyboard row | `⚙ Filter`, `📂 All listings` | Noun or verb + object |
| Contextual | Inline buttons under the message they affect | `Set up filter`, `Edit filter`, choice values | The choice itself |
| Destructive | Inline + mandatory confirmation step | `Reset filter`, `🗑 Delete my data` | Consequence named in the confirm labels |
| Admin | Inside the admin panel only | `Run QA demo`, `Run catalog QA`, … | Verb + object |
| Case-study CTAs | `.btn--primary` (ink, teal hover) / `.btn--ghost` (outline); dark CTA block: `.btn--accent` (teal) / `.btn--inverse` | Top bar + hero + final CTA | `Read the case study`, `View repository`, `Read the Markdown version` |

Rules:
- One primary action per surface: the bot's is `Show matches`; the case page's is `Read the case study`.
- `📂 All listings` / `Browse all listings` is a secondary demo action and **ignores the saved filter** — copy around it must never imply filtering.
- Actions that do not exist (subscribe/unsubscribe toggles, listing bookmarking, export, language switch) MUST NOT be referenced in copy as if they did.

---

## 10. Listing Card Contract

The Telegram listing card is the product's core artifact. Format lives in `flatfeed/matching.py` and MUST NOT be changed casually.

Fixed field order, bold labels, one field per line:

```text
District: <Bezirk>
Address: <street and house number, postal code Berlin>
Floor: <floor>
Rooms: <rooms>
S-Bahn: <minutes or "not calculated">
U-Bahn: <minutes or "not calculated">
WBS: <allowed values / generic requirement / "No WBS required">
Source: <source company>

Kalt: <price>
Warm: <price>

Open listing
```

Rules:
- **Canonical unknown-value strings:** `not specified` (fields), `not calculated` (transit). Do not invent variants ("n/a", "—", "unknown").
- **Prices:** display preserves cents; German-style decimal comma in display amounts; currency renders as `EUR` after the amount ("610 EUR"). Matching compares Kaltmiete in cents. Cards show both Kalt and Warm when available; matching uses **Kaltmiete only**.
- **WBS line:** rendered through `display_wbs_requirement` from `flatfeed/wbs_rules.py` — allowed percentage list, `WBS required, type unknown` for generic requirements, `No WBS required` otherwise. Never re-implement WBS display logic elsewhere.
- **Rooms:** integer when whole, decimal comma otherwise; filter value 5 means "5 or more".
- The blank-line grouping (facts / prices / link) is part of the contract; `Open listing` is always the last line and the only link.
- The photo (when present) is a deterministic demo asset; captions or docs referencing photos MUST NOT imply they depict the listing address.

---

## 11. Status and Semantic Vocabulary

One concept = one canonical vocabulary. Do not merge concepts because they sound similar.

| Concept | Canonical values | Where | Notes |
|---|---|---|---|
| **Listing activity** | active / inactive (removed listings stay in history, excluded from delivery) | DB + delivery logic | A failed activity check marks inactive; partial collection never mass-marks removals |
| **Admin QA triage** | `Parser error` / `Parser correct` / `Borderline / unsure` | Bot triage buttons, dashboard feedback metrics | The decision of record; exactly three values |
| **AI risk** | `risk_score` 0–100 + alert threshold (default 75) | AI QA reviews, alerts | A number with a threshold, never "the AI is worried" |
| **Parser eval outcome** | field accuracy / exact listing accuracy vs golden set | `eval/run_eval.py`, docs | Always "synthetic golden-set" scoped |
| **WBS requirement** | 100 / 140 / 160 / 180 / 220 / `WBS required, type unknown` / `No WBS required` / `Any WBS` (filter) | Cards, wizard, matching | Semantics in `flatfeed/wbs_rules.py`; e.g. `WBS 141-220` excludes 140 |
| **Location** | `District` (visible label) = one of the 12 Berlin Bezirke (semantic) | Wizard, cards | Ortsteil/Kiez normalize to a Bezirk |
| **Rent** | Kaltmiete (matching basis) / Warmmiete (display) — `Kalt:` / `Warm:` on cards | Cards, wizard | Unknown Kaltmiete ≠ match |
| **Transit** | `S-Bahn` / `U-Bahn` walking minutes, or `not calculated` | Cards | Geometric estimate: straight-line × 1.25 at 80 m/min — an estimate, label it as such in prose |
| **Source health** | ingestion run success/failure; 3 consecutive failures → admin alert (with cooldown) | `ingestion_runs`, admin alerts | Empty synthetic results count as failure |
| **Data provenance** | synthetic / demo / mock (provider) / golden set / hidden ground truth | All surfaces | Load-bearing honesty vocabulary (§23) |

Rules:
- User-facing copy never shows `risk_score`, prompt versions, or QA internals (P8).
- Qualifiers ("demo-only", "synthetic") attach to the value they qualify, at the same reading depth.

---

## 12. AI Interface Rules

The enforcement of the FlatFeed AI boundary in product behavior and copy:

1. **AI reviews parser snapshots; it never mutates data.** No AI output may alter `listings`, matching results, or user-facing cards automatically. `suggested_values` are advisory input for a human editing the parser.
2. **Admin-only.** AI QA findings, alerts, and triage exist only in the admin panel and dashboard. Renters never see AI output.
3. **Budgeted and optional.** `AI_QA_PROVIDER=mock` is the default (local, deterministic, free). `openai` is opt-in, requires an API key and explicit budget settings; daily count and dollar budgets stop excessive usage. Copy MUST NOT present AI QA as required for matching — it isn't.
4. **Versioned and deduplicated.** Each listing gets at most one review per prompt version; the version constant lives in `flatfeed/ai_qa.py` and is displayed, not duplicated, elsewhere.
5. **Risk is a thresholded number.** `risk_score` 0–100; alert at ≥ the configured threshold (default 75); an alerting review must contain at least one concrete issue. Never render risk without its threshold context in admin surfaces.
6. **Source data vs AI output separated.** Raw listing text and the parser snapshot render as distinct blocks next to AI findings (dashboard demo section, triage reports). Never blend them into one paragraph.
7. **Prompt hygiene.** Ground-truth fields and synthetic case tags MUST NOT enter prompts (P4). The prompt is also product policy — e.g. it encodes that "no WBS mention → No WBS required" is *correct*; prompt changes are product changes and bump the version.
8. Hard prohibitions: anthropomorphism ("the AI thinks/wants"); presenting the mock provider as a live model; "AI-powered" as a feature adjective; implying AI does the matching; any capability claim not traceable to `flatfeed/` behavior.

---

## 13. Data Visualization (dashboard + case page)

- Dashboard charts confirm the adjacent metric blocks (coverage over time, cost, version comparison). If a metric answers the question, don't add a chart.
- Case-page "charts" are static metric displays, not plots — CURRENT/ADOPT. Two forms: bordered figure/metric grids (big display value + short mono caption, ink values) and the Results table (amber values + detail column). Amber stays confined to Results values (§5.1).
- Every metric card value on the case page MUST be reproducible: golden-set size ↔ `SYNTHETIC_LISTING_COUNT`/catalog, accuracy ↔ `python -m eval.run_eval` output, QA cost ↔ the run's logged cost. No hand-invented numbers, no rounding a 99.x up to 100.
- Units and denominators stay with the number ("15 golden listings", "$0.000000 mock QA cost", "% of reviewed listings").

---

## 14. Responsive System (case-study page)

Breakpoints in use: **1080** (hero meta → 3-up, workflow steps → 2-up), **920** (header wraps and nav becomes a horizontal scroll row, demo-frame panels and the built/scope/points grids stack to one column, scope figures → 2-up, the Results detail column hides — the caption and prose keep the qualifier visible), **620** (meta → 2-up, steps → 1-up, brand sub-label and demo-frame URL hide).

- Desktop is the primary reading surface; mobile is a supported viewing mode, not a separately designed product.
- Nothing needed for the 10-second scan (§22) may disappear at any width: kicker, H1, CTAs, meta grid, at least one evidence panel; the synthetic qualifier for the Results numbers must survive every width (it lives in the table caption and the adjacent prose, not only in the hidden detail column).
- The Telegram bot and Streamlit dashboard handle their own responsiveness — do not add custom viewport logic there.

---

## 15. Accessibility Baseline (case-study page) — WCAG 2.2 AA target

- Landmarks and labels exist and MUST be preserved: the skip link, `aria-label` on nav ("Case study sections"), evidence panels, the workflow band, and the scope-figures list; decorative SVGs carry `aria-hidden` and the brand image an empty alt; the demo photo has a descriptive alt disclosing it is a demo image.
- Contrast: `--ink-2` #4e5c5e on white ≈ 7.0:1 and `--ink-3` #657473 ≈ 4.9:1 (used for small mono captions — keep it ≥4.5:1 if retinted); `--accent` #02776f ≈ 5.4:1 — AA-safe for text; verify any new pair instrumentally before use. `--amber` #c86b05 appears only at 22–30px semibold (large-text scale) — do not use it for small text without checking.
- Keyboard: a global `:focus-visible` outline (2px `--accent`) covers all interactive elements — any new interactive element MUST keep a visible focus state.
- `scroll-behavior: smooth` and the demo-frame live-dot blink exist only inside `prefers-reduced-motion: no-preference`; the reduced-motion block keeps animation and scroll behavior neutral. New animation MUST be added inside the same gating pattern.
- Tables (`product-shot`) keep real `th` headers.
- Telegram and Streamlit accessibility ride on their platforms; the project's obligation there is text clarity (§16) and never encoding meaning in emoji alone.

---

## 16. Content Principles

1. **Frontload the point.** The first clause carries the message ("Finding WBS-eligible apartments in Berlin is fragmented and time-sensitive: …").
2. **Concrete over abstract.** "sends at most 10 valid cards", "three consecutive failures trigger an admin alert" — numbers with units and denominators, mechanisms over adjectives.
3. **State facts, not self-praise.** Surfaces never grade themselves ("robust", "seamless" do not appear — protect this). Quality is demonstrated by the eval, the boundary, and the confirmations.
4. **Precision is credibility.** WBS semantics are exact (`WBS 141-220` excludes 140); "estimates" stay estimates ("walking-time estimates", "not calculated"); one imprecise claim taxes every accurate one.
5. **Explain domain terms at first use, keep the term.** "WBS (Wohnberechtigungsschein) is a Berlin eligibility certificate…", "Kaltmiete is the base rent without utilities (Nebenkosten)." Don't translate the term away; gloss it (P6).
6. **Every claim carries its evidence status.** "These are synthetic evaluation metrics, not production user-impact numbers" — the qualifier is part of the sentence, not a footnote (§23).
7. **Write for the working reader.** The renter wants the next apartment; the admin wants the next parser fix; the recruiter wants the judgment. No filler serving the author.

---

## 17. Voice and Tone

**Bot voice (ADOPT):** a competent first-person assistant — plain, brief, helpful, never cute. The bot says "I" about its own actions ("I found active listings that match your saved WBS filter.", "Which district should I search in?") and "you/your" for the user's data ("Your filter"). No exclamation marks, no small talk, no personality bits.

**Dashboard voice (ADOPT):** neutral admin register; headings are the admin's questions; captions define terms and provenance; no first person.

**Case study / docs voice (ADOPT):** professional, evidence-led, first person where ownership is claimed ("I defined the product scope…"), never salesy. Judgment is shown by trade-offs ("I deliberately limited live source coverage to make the demo privacy-safe, defensible, and measurable"), not by adjectives.

Voice is stable; tone flexes by context:

| Context | Tone | Example / rule |
|---|---|---|
| Normal bot flow | Plain, task-forward | "Which WBS should match?" |
| Success | Plain confirmation, no celebration | "I found active listings that match your saved WBS filter." |
| No results | Honest + what the filter was | State that nothing active matches; never pad with near-misses |
| Destructive confirm | Consequence named, neutral | "Yes, delete everything" / "No, keep my data" |
| Session loss | Own the cause, restart cleanly | "Your setup session expired (the bot restarted), so I lost the earlier answers. Let's start again." |
| Renter-facing failure | Outcome + retry, no internals | "One or more sources may have returned an error or timed out." |
| Admin failure | What failed + where to look | "Catalog QA failed. Check the logs." |
| Dashboard | Question → answer → definition | "Is AI QA running well now?" + caption |
| Case-study limitation | Matter-of-fact, unhedged | "These are synthetic evaluation metrics, not production user-impact numbers." |

---

## 18. Product Copy System

| Category | Pattern | Length | Examples (current, approved) | Anti-pattern |
|---|---|---|---|---|
| Reply-keyboard buttons | Emoji + verb/noun | ≤3 words | `🔎 Show matches`, `⚙ Filter` | Emoji-only; clever names |
| Inline action buttons | Verb + object, plain text | 2–4 words | `Set up filter`, `Edit filter`, `Run QA demo` | "OK", "Click here" |
| Confirmation buttons | Consequence in the label | ≤4 words | `Yes, delete everything` / `No, keep my data` | Bare Yes/No for destructive actions |
| Wizard questions | Direct question, one thing | 1 sentence | "How many rooms do you need?" | Multi-question messages |
| Wizard hints | `<i>` gloss at the point of use | 1–2 sentences | the WBS and Kaltmiete explainers | Glossary dumps in /help |
| Card labels | `<b>Label:</b>` fixed vocabulary | 1 word | `District:`, `Kalt:`, `Warm:` | Renaming card fields |
| Unknowns | Canonical fallback strings | — | `not specified`, `not calculated` | "n/a", "—", "unknown" |
| Bot statements | First-person, one purpose | 1–2 sentences | "I found active listings that match your saved WBS filter." | Paragraph messages |
| Failure copy | Cause (admin) / outcome + retry (renter) | 1–2 clauses | "Catalog QA failed. Check the logs." | Apologies, exclamations, stack traces |
| Dashboard headings | The admin's question | 1 question | "How much does AI QA cost?" | Vague ("Overview") |
| Dashboard captions | Provenance + definition | 1–2 sentences | "Current AI QA version: v8." (from the constant) | Hard-coded versions/numbers |
| Commands | Single lowercase words | 1 word | `/start /filter /matches /help /delete` | Compound commands |

Capitalization: sentence case everywhere; card labels and proper/domain nouns (WBS, Kaltmiete, S-Bahn, U-Bahn, Bezirk names) keep their canonical forms. Terminal periods on sentences, none on button labels.

---

## 19. Action Language

| Action | Canonical wording | Prohibited alternatives | Scope |
|---|---|---|---|
| Get matching listings | **🔎 Show matches** / `Show matches` (inline) / `/matches` | "Find flats", "Search" | Reply keyboard, filter card, command |
| Open filter | **⚙ Filter** / `/filter` | "Settings", "Preferences" | Reply keyboard, command |
| Start setup | **Set up filter** | "Start wizard", "Configure" | Empty filter card |
| Change one field | **Edit filter** → `WBS` / `District` / `Rent` / `Rooms` | "Modify", "Update settings" | Filter card |
| Clear the filter | **Reset filter** (+ confirm pair) | "Clear", "Delete filter" | Filter card |
| Remove personal data | **🗑 Delete my data** / `/delete` (+ confirm pair) | "Unsubscribe", "Forget me" | Filter card, command |
| Browse without filter | **📂 All listings** (keyboard) / **📂 Browse all listings** (inline) | Implying it respects the filter | Reply keyboard / no-filter card |
| Wizard navigation | **⬅ Back** / **✖ Cancel** | "Previous", "Abort" | Every wizard step |
| Admin: demo QA run | **Run QA demo** | "Test AI" | Admin panel |
| Admin: full backfill | **Run catalog QA** (+ confirm: `Yes, run catalog QA` / `Cancel`) | — | Admin panel |
| Admin: triage a finding | **Parser error** / **Parser correct** / **Borderline / unsure** | Any fourth label; abbreviations | QA reports |
| Admin: open metrics | **View QA metrics** / **📊 Effectiveness dashboard** | — | Admin panel |
| Open a listing | **Open listing** (the card's only link) | "More", "Details" | Listing card |
| Case-study CTAs | **Read the case study** / **View repository** | "Try it", "GitHub" (as a button label) | Hero; header nav item `GitHub` is a nav link, not a CTA |

Actions that have no product function (subscribe, bookmark, share, export, language switch, pause notifications) MUST NOT appear in UI or copy as if they did. If a phase adds one, define its canonical verb here first.

---

## 20. Terminology System

| Concept | Canonical term | Definition | User-facing form | Case study / docs form | Avoid |
|---|---|---|---|---|---|
| Unit of work | listing | One apartment offer normalized into the catalog | listing | listing | "ad", "flat" (as the entity), "object" |
| Eligibility certificate | WBS | Wohnberechtigungsschein; tiers 100/140/160/180/220 | WBS (+ wizard gloss) | WBS (glossed at first use) | Translating it; removing tiers |
| Rent basis | Kaltmiete | Base rent without utilities; the only matching basis | Kaltmiete / card `Kalt:` | Kaltmiete (glossed) | "cold rent", matching on Warmmiete |
| Total rent | Warmmiete | Rent incl. utilities; display only | card `Warm:` | Warmmiete | Using it for matching |
| Location unit | Bezirk | One of the 12 Berlin Bezirke | label `District` | Bezirk / district | Treating Ortsteil/Kiez as the unit |
| Saved criteria | filter | The fixed 4-field user filter (WBS, district, max Kaltmiete, rooms) | Your filter | user filter | "preferences", "profile", "subscription" |
| Getting results | matches / matching | Deterministic rule comparison of listings vs filter | Show matches | deterministic matching | "recommendations", "AI matching" |
| Collection layer | source adapter | Per-source ingestion module with activity checks and health | Source (card field) | source-adapter architecture | "scraper" (the demo doesn't scrape) |
| Demo source | FlatFeed Synthetic | The synthetic catalog adapter | Source: FlatFeed Synthetic | synthetic source adapter | Implying live sources exist |
| Parsing | deterministic parsing | Rule-based field extraction at ingestion; no LLM | — (internal) | deterministic parsing | "AI parsing" |
| AI surface | AI QA | Admin-only review of parser snapshots by a model | — (admin panel only) | AI QA | "AI assistant", "autopilot" |
| AI QA input | parser snapshot | The parsed-field record a review evaluates | parser snapshot (admin) | parser snapshot | "the data" |
| AI QA output | finding / review | Versioned review with risk score and issues | flagged report | finding, review | "verdict", "decision" |
| Risk number | risk score | 0–100 likelihood the parser result is materially wrong | risk (admin surfaces) | risk score + threshold | "confidence" (inverted meaning) |
| Human QA label | triage label | Parser error / Parser correct / Borderline / unsure | the three buttons | admin feedback | "rating" |
| Eval dataset | golden set | Synthetic cases with hidden ground truth | — | golden set / synthetic golden-set eval | "test data" (vague) |
| Hidden answers | ground truth | Eval-only truth fields and case tags | — | hidden ground truth | Putting it anywhere near prompts |
| Quality numbers | field accuracy / exact listing accuracy | Parser vs golden set | — | with "synthetic" scope attached | Unscoped "accuracy" |
| Transit estimate | walking-time estimate | Geometric estimate from bundled station CSV | `S-Bahn:`/`U-Bahn:` minutes, `not calculated` | local walking-time estimates | Implying routing/geocoding services |
| Notifications | one-time notification | Deduplicated delivery of a new match | — | notification deduplication | "alerts" (reserved for admin) |
| Admin alerts | admin alert | Source-health or high-risk QA alert to admins | — | admin alert | Mixing with user notifications |
| Provenance | synthetic / demo / mock / estimated | Not from live systems or production | demo catalog | synthetic, demo-only, mock provider | "sample data" (vague), unlabeled values |

Audience adaptation is allowed (gloss depth, sentence length) — mechanical word-for-word identity between surfaces is not required. Meaning identity is (§27).

---

## 21. AI Language System

- **"AI" is useful** when attributing origin or boundary: "AI QA", "AI reviews parser snapshots", "AI never mutates listings". **"AI" is redundant** as a quality adjective. "AI-powered" MUST NOT appear (currently appears nowhere — protect this).
- **Review, not decision:** the model *reviews*, *flags*, *suggests*; the admin *labels*, *decides*, *fixes the parser*. Verbs giving the model agency over data ("AI corrected the listing") MUST NOT appear.
- **Risk is a number with a threshold** ("risk score 85, alert threshold 75") — never "the AI is confident/worried that…".
- **The mock provider is named as mock** wherever its numbers appear ($0 cost is a mock-provider fact, not an efficiency claim).
- **Determinism is stated positively:** "listing parsing itself is fully deterministic and makes no LLM calls" — this sentence pattern is the product's differentiator; keep it verbatim-close in docs.
- **Prompt versions** are referenced via `CURRENT_AI_QA_PROMPT_VERSION`, with docs pointing at the constant rather than freezing a value ("inspect the constant rather than trusting this document").
- Prohibited: anthropomorphism; unsupported capability claims; "intelligent/smart" as adjectives; presenting optional budgeted QA as core infrastructure; any claim not traceable to `flatfeed/` behavior.

---

## 22. Case Study Content System

The page serves three reading depths; every depth must independently answer its questions.

**10-second scan** (kicker + H1 + lede + meta grid + demo frame) must answer: What is this? What domain? What did the candidate do? Why AI-PM-relevant?
Mechanics: kicker names the genre ("AI product management — case study · 2026"); H1 is a first-person outcome statement ("I built FlatFeed to turn fragmented Berlin WBS apartment listings into a trusted, measurable matching workflow."); the lede names collection, normalization, matching, and the AI boundary in one breath; the demo frame's phone/dashboard panels prove the product's shape and its chrome label says "Demo · synthetic data".

**30-second scan** (+ section headings, workflow band, boundary pull quote, results table) must answer: why AI is bounded, what was built, whether results are honest.
Mechanics: section H2s state takeaways, not topics; the boundary pull quote is the mechanism statement ("AI QA may challenge the parser, but it cannot replace or mutate … automatically."); the scope columns separate "Real in this prototype" from "Synthetic on purpose"; the Results table caption and prose carry the synthetic qualifier at the same depth as the numbers.

**Deep read** must answer: decisions, trade-offs, ownership, limitations, next steps — the 7-part framework (§6.3) covers exactly these; keep the parts and their order.

Element rules:
- **Hero:** kicker → first-person outcome H1 → lede (what it does + AI stance) → CTAs → meta `dl` (Role / Domain / Type / Data / Year). Every meta value must be decodable without insider context.
- **Section 02 (Why AI?)** always leads with the *negative* decision ("I did not make AI responsible for matching because…") before the positive use — this inversion is the page's strongest judgment signal; keep it.
- **Workflow band:** exactly the pipeline the code implements (Collect → Normalize → Match → Review → Notify); if the pipeline changes, the band changes with it.
- **Boundary pull quote:** the canonical AI-boundary sentence (§2), rendered as the page's only blockquote, outside the 7-part numbering. It restates the boundary, never a softened paraphrase.
- **Scope columns:** "Real in this prototype" vs "Synthetic on purpose" — every line must be a FACT or MOCK/SYNTHETIC claim per §23; this is where the honesty inventory lives.
- **Results:** numbers come from a real `python -m eval.run_eval` run; the qualifier "synthetic evaluation metrics, not production user-impact numbers" sits in the same paragraph; the amber table values restate the same numbers, nothing more, with the qualifier repeated in the table caption.
- **Limitations and next steps** live in section 07, stated unhedged ("If I continued the project, I would…").
- Mockup panels (phone/dashboard) depict only states the real product produces and stay inside the labeled demo frame; a listing card mockup MUST follow the §10 field vocabulary; the figcaption MUST keep stating they are mockups, not screenshots.

---

## 23. Evidence Rules

Every claim on the case study, README, and CASE_STUDY.md carries one of these statuses, labeled as shown:

| Status | Definition | Required labeling |
|---|---|---|
| FACT | Verifiable in the repo or by running the demo | None beyond the claim ("the canonical implementation is `flatfeed/wbs_rules.py`") |
| MEASURED (SYNTHETIC) | Computed by an actual eval or logged run on synthetic data | "synthetic golden-set eval" / "mock AI QA provider" at the same reading depth as the number. This is the *only* measured-result class that exists — production impact numbers do not exist; do not fabricate them |
| TARGET | A goal, not an achievement | "target", "should"; never bare |
| HYPOTHESIS | Believed, untested | "would", "If I continued the project, I would…" |
| SYNTHETIC DATA | The deterministic demo catalog | "synthetic", "demo catalog", seed disclosed in env docs |
| ESTIMATE | Illustrative computed value | Named method ("straight-line distance × 1.25 at 80 m/min") or "estimate" in the sentence |
| MOCK | Behavior imitating an unbuilt/optional system | "mock provider", "no network request is made" |
| IMPLEMENTED | Actually built and runnable | Plain description; demo script proves it |
| PLANNED | Future phase | "future multi-source collection", "where terms allow it" |
| LIMITATION | Known gap | Stated in Results/Learned or PROJECT_CONTEXT, unhedged |

Hard constraints (non-negotiable):
- Synthetic eval numbers MUST NOT read as production evidence at any reading depth.
- Eval numbers MUST come from an actual run and update **all** their occurrences together (§27); never round 99.x to 100, never keep stale numbers because they look better.
- Capabilities exercised only through the synthetic adapter (multi-source collection, source health) MUST be described as architecture exercised by the synthetic adapter — the README's phrasing is the model.
- $0 QA cost MUST stay attributed to the mock provider.
- Hiring signal MUST NOT be improved by inventing evidence. Ever.

---

## 24. Candidate Ownership Language

- The canonical ownership statement lives in CASE_STUDY.md §3 / case-study.html section 03 ("I defined the product scope, shaped the portfolio positioning, designed the source-collection and matching flow, implemented the prototype, created the synthetic evaluation dataset, wrote deterministic parsing rules, added AI QA with budget controls, and built the admin dashboard…"). Keep the HTML and Markdown versions in sync in *meaning*.
- Verb discipline: **defined/designed/scoped/chose** = candidate judgment; **implemented/built/wrote** = delivery; **the bot/the parser/the eval does X** = system behavior; **demo/mock/synthetic** = illustrative outcome. Do not swap categories.
- If AI coding agents contributed to implementation and the author wants that disclosed, the disclosure is added by the author — an agent MUST NOT add or remove ownership or collaboration claims on its own.
- First person ("I", "my") is correct on the case study and in CASE_STUDY.md. In the bot, "I" is the *bot* speaking about bot actions (§17) — never the candidate. The dashboard and README use no first person for ownership except CASE_STUDY-quoted material.

---

## 25. Professional Language Rules

**Prefer:** concrete mechanisms tied to artifacts — "source-adapter registry, ingestion history, per-source activity checks", "daily count and dollar budgets", "one review per prompt version"; named thresholds ("alert at risk ≥ 75", "three consecutive failures"); verifiable statements ("no network request is made"); earned judgments ("eligibility decisions need to be predictable and explainable").

**Buzzword register.** Current status: *leverage, seamless, robust, cutting-edge, intelligent, actionable insights, AI-powered, end-to-end (as a boast), scalable, production-ready, enterprise-grade* appear on no surface as self-praise. Protect this. Rules rather than blanket bans:
- *production-ready / enterprise-grade*: MUST NOT appear — the demo explicitly is neither.
- *end-to-end*: acceptable only in the literal sense already used ("an end-to-end AI PM case: problem framing, trade-off definition, prototype delivery, evaluation, and honest documentation") — a scoped list, not a boast.
- *scalable*: only about a specific mechanism with its limit stated (e.g. "SQLite is appropriate for this local portfolio prototype" is the model — a fitness claim, not a scale claim).
- Self-praise adjectives about our own output ("reliable", "trusted", "honest" as feature labels) are acceptable only where the artifact proving them is shown or named at the same spot (e.g. "trusted, measurable matching workflow" is anchored by the eval and boundary sections).

---

## 26. Scannability Rules

- Headings state the takeaway or the question; a heading-only read of the case page or dashboard must be coherent.
- Case-study paragraphs ≤5 sentences, one idea each; bot messages are 1–2 sentences; dashboard captions 1–2 sentences.
- Lists for parallel mechanisms (README "What It Shows", the case page's point grids and scope columns); tables only for enumerable facts.
- Key metrics render as metric cards with their qualifier in the adjacent prose (§22); the Telegram card's blank-line grouping (§10) is the bot's scannability mechanism.
- Technical explanations follow "term (plain gloss)" on first use — the WBS and Kaltmiete hints are the models.
- Review gates: the 10s/30s scan tests (§22) for any case-page change; for the bot, "can a new user reach a listing card in ≤5 taps from /start?"; for the dashboard, "does each section answer its own heading?"

---

## 27. Cross-Surface Consistency

**MUST remain consistent (meaning-identical) across bot, dashboard, case page, and docs:**
- The meaning of listing, filter, WBS tiers, Kaltmiete-only matching, district/Bezirk, golden set, risk score, triage labels (§20).
- The AI boundary sentence pattern: parsing/matching deterministic; AI QA admin-only, budgeted, never mutating (§2, §12).
- **Eval result numbers.** They currently appear in: `CASE_STUDY.md` §6, `docs/case-study.html` (demo-frame dashboard panel + Results table + Results prose), and any README mention. When an eval run changes them, update every occurrence in the same change — a stale number on one surface is a factual error.
- **Eval sync search.** When touching eval numbers or adjacent prose, run a targeted text search before editing and before final review:
  `rg -n "golden-set|field accuracy|exact listing accuracy|Parser misses by tag|false alert fields|\\$0\\.000000|100\\.0%" CASE_STUDY.md README.md docs/case-study.html`.
- The 7-part case structure between `CASE_STUDY.md` and `docs/case-study.html`.
- WBS semantics: `flatfeed/wbs_rules.py` is the single source; documents give examples, the module defines truth.
- The card field contract (§10) between `flatfeed/matching.py`, README's card sketch, PROJECT_CONTEXT's card sketch, and any case-page mockup.
- Copy changes propagate across bot UI, dashboard UI, tests, and documentation together (a stated Known Constraint in PROJECT_CONTEXT).

**MAY adapt by audience:**
- Gloss depth (case page glosses WBS for recruiters; the bot glosses it for renters; the dashboard doesn't need to).
- Register (bot conversational first person; docs technical; case page editorial).
- German domain-term density (cards say `Kalt:`/`Warm:`; prose says Kaltmiete/Warmmiete).

---

## 28. Approved Patterns

Working well; reuse as-is; do not "improve" for uniformity's sake.

| Pattern | Location | Why approved | Reuse guidance |
|---|---|---|---|
| Deterministic core + AI-as-QA boundary | whole product | The portfolio thesis, implemented | Any new AI use starts admin-only, budgeted, non-mutating |
| Persistent keyboard with one primary action | bot shell | Main story always one tap away | Keep `Show matches` alone on top |
| `Step N/4` wizard with Back/Cancel and point-of-use hints | filter setup | One thing per page, glossed domain terms | Template for any future multi-step flow |
| Consequence-named confirmation pairs | reset / delete / catalog QA | Destructive safety without friction elsewhere | Mandatory for destructive or costly actions |
| Filter card as home (wizard never forced) | `/start` | Respects returning users | Any future "home" message |
| Fixed listing-card contract with canonical fallbacks | `flatfeed/matching.py` | Predictable, scannable, honest about unknowns | Never fork per-context card variants |
| Fail-closed matching on unknown values | matching rules | Wrong sends are the costliest error | Default for any new matching field |
| Activity re-check before delivery + notification dedupe | delivery pipeline | Trust preservation | Any new delivery path |
| Source-health alerting with cooldown | ingestion | Detects silent failure without alert spam | Any new background job |
| Question-form dashboard sections with caption provenance | `streamlit_app.py` | Admin reads answers, not charts | All new dashboard sections |
| Worked example on the dashboard ("parser made a mistake, AI checked it") | dashboard | Shows the loop, not just aggregates | Keep one concrete example per new metric family |
| Ground-truth quarantine | `synthetic/` ↔ prompts | Makes the eval meaningful | Absolute; no exceptions |
| Version-stamped QA reviews (one per listing per version) | `flatfeed/ai_qa.py` | Enables version comparison, caps cost | Any new AI artifact gets a version field |
| Negative-decision-first "Why AI?" framing | case study §02 | Strongest judgment signal on the page | Keep in any rewrite |
| Synthetic qualifier inside the results sentence | case study §06 | Honesty at every reading depth | Every future results claim |
| Teal structure / amber results split | case page | Measured outcomes read as a distinct zone | Don't dilute amber elsewhere |
| Licensed demo photos with attribution file | `assets/listing_photos/` | Defensibility | Any new third-party asset gets the same treatment |

---

## 29. Deprecated / Do-Not-Copy

Exists in the codebase today; MUST NOT be reused in new work; migrate when touching the area. (No formal audits exist yet — this list comes from direct inspection and is expected to grow when audits run.)

| Pattern | Current location | Reason | Replacement | Priority |
|---|---|---|---|---|
| Two labels for the same catalog action (`📂 All listings` vs `📂 Browse all listings`) | reply keyboard vs inline card | One action, one name (§19) — inline long form tolerated only until touched | Converge on one form when editing either | Low |
| Case-page GitHub links hard-coded to `github.com/mich-mayer/flatfeed` | `docs/case-study.html`, footer + hero + nav | Must match the actual public repo location; verify before publishing changes | Confirm canonical public URL, then treat as FACT | Medium |

---

## 30. Unresolved Decisions

Insufficient evidence for a rule — do not invent one; use the temporary default.

| Decision | Why unresolved | Evidence needed | Temporary default |
|---|---|---|---|
| Real screenshots vs HTML mockups on the case page | CASE_STUDY §7 names real screenshots as a next step | An actual demo session capture the author approves | Keep HTML mockups; keep them state-accurate |
| Dashboard theming/branding | Stock Streamlit is deliberate for now | A decision that dashboard chrome matters for the portfolio | No custom CSS injection |
| Localization (German or Russian bot copy) | Product is English-facing by decision (PROJECT_CONTEXT Known Constraints) | An explicit product decision to localize | English only; keep German domain terms glossed |
| Live source adapters | Legal/terms review pending; demo is synthetic-only | Author's go-ahead + terms-compatible sources | Synthetic adapter only; describe others as PLANNED |
| Renter-facing "why did this match?" explanations | Match reasons exist internally (`MatchDecision.reasons`) but aren't user-facing | A decision that renters need explanation UI | Keep reasons internal; don't expose ad hoc |
| Eval-metrics automation into docs | Numbers are updated by hand across three surfaces | A decision to generate result blocks from `run_eval --json` | Manual sync per §27, all occurrences in one change |

---

## 31. Agent Instructions

For Claude/Fable, Codex, and other coding agents.

**Before changing bot UI or copy, an agent MUST:**
1. Read §§7, 17–19 and match the existing register (bot first person, HTML tags `<b>/<i>/<a>` only, emoji only in the sanctioned button set).
2. Keep the listing-card contract (§10) and canonical fallback strings intact.
3. Add a consequence-named confirmation to anything destructive or costly (§7.2).
4. Propagate copy changes across bot, dashboard, tests, and docs together (§27).

**Before changing parsing, matching, or WBS logic, an agent MUST:**
1. Treat `flatfeed/wbs_rules.py` as the single source of WBS semantics; never re-implement display or ranges elsewhere.
2. Preserve fail-closed matching for unknown values and Kaltmiete-only matching.
3. Run the eval and the tests; if golden-set numbers change, update every documented occurrence (§27) in the same change.

**Before touching AI QA, an agent MUST:**
1. Keep it admin-only, budgeted, versioned, and non-mutating (§12).
2. Keep ground truth and case tags out of prompts, listing text, and URLs (P4).
3. Bump `CURRENT_AI_QA_PROMPT_VERSION` for any prompt change; never hard-code the version in copy.

**Before changing the case study or public docs, an agent MUST:**
1. Preserve factual integrity and evidence labels (§23) — the synthetic qualifier stays in the same sentence/level as the numbers.
2. Preserve candidate ownership language (§24); never alter ownership claims without the author.
3. Keep `CASE_STUDY.md` and `docs/case-study.html` synchronized in structure and meaning.
4. Run the 10s/30s scan tests (§22) on the changed section.

**Verification matrix.** Choose the required row by the riskiest touched surface; run broader checks when uncertain or when a change crosses surfaces.

| Change type | Required checks | Add when |
|---|---|---|
| Documentation-only, no claims or numbers changed | `git diff --check`; targeted `rg` for changed terminology/evidence labels | Run tests/eval only if docs assert behavior that may have drifted |
| Case-study HTML/CSS only | `git diff --check`; 10s/30s scan review (§22); browser/render check for the touched viewport(s); `rg` for non-token colors when CSS changes | Run unit tests if code examples, eval numbers, or generated artifacts are touched |
| Eval numbers or result prose | `PYTHONPYCACHEPREFIX=/tmp/flatfeed-pycache .venv/bin/python -m eval.run_eval`; eval sync search (§27); `git diff --check` | Run full tests if parser/generator/AI QA code changed |
| Parser, matching, WBS, synthetic catalog, transit, or DB behavior | `PYTHONPYCACHEPREFIX=/tmp/flatfeed-pycache .venv/bin/python -m unittest discover -s tests`; `PYTHONPYCACHEPREFIX=/tmp/flatfeed-pycache .venv/bin/python -m eval.run_eval`; `git diff --check` | Add focused manual smoke checks for changed source adapters or delivery paths |
| Bot UI, dashboard, or AI QA behavior | Full tests; focused runtime/manual check of the changed flow; `git diff --check` | Run eval if parser snapshots, AI QA prompt policy, or documented result numbers changed |
| Deployment/public URL changes | Relevant tests from above; Pages/GitHub status check; `curl -I` and content check for the published URL | Re-check after cache delay if headers still show old content |

**Always:**
- Use the matrix above; if you skip a heavier check that the old blanket rule would have run, state why in the final/handoff.
- Keep the demo synthetic: no real scraping, no network geocoding, no image reuploading, no live-source claims.
- Operational/server details belong in `LOCAL_CONTEXT.md` (local-only) and MUST NOT enter any committed or public surface.
- Don't overwrite others' uncommitted work.

---

## 32. Design Review Checklist

- [ ] Bot: message = one purpose; HTML tags within the allowed set; emoji only in sanctioned button labels (§7.1).
- [ ] Bot: wizard steps keep `Step N/4`, Back/Cancel, and point-of-use hints (§7.3).
- [ ] Bot: destructive/costly actions have consequence-named confirmations (§7.2).
- [ ] Card: field order, labels, grouping, and fallback strings match §10 exactly.
- [ ] Delivery: activity re-check, dedupe, ≤10 cards, fail-closed matching intact (§3 P5).
- [ ] Dashboard: new sections are question-headed with caption provenance; no hand-typed metric values (§8).
- [ ] Case page: tokens only, square corners (no radius), shadow only on the demo frame; amber confined to Results values (§5).
- [ ] Case page: 7-part structure, numbered-kicker motif, boundary quote outside the numbering, and nav reachable at all widths (§6.3, §14).
- [ ] Accessibility: aria labels/alt preserved; new text colors checked ≥4.5:1; new motion gated (§15).
- [ ] Admin vs user separation intact: no QA jargon in renter-facing surfaces (§3 P8).

## 33. Content Review Checklist

- [ ] Audience identified: renter, admin, or case-study reader; register matches §17.
- [ ] Actions use canonical labels (§19); same action = same words across surfaces.
- [ ] Terminology matches §20; domain terms kept and glossed at first use, never translated away.
- [ ] AI claims: review verbs only, risk as number + threshold, mock provider named, no anthropomorphism (§21).
- [ ] Evidence: every number labeled MEASURED (SYNTHETIC)/ESTIMATE/MOCK/etc.; synthetic qualifier at the same reading depth (§23).
- [ ] Eval numbers verified against an actual run and synchronized across all occurrences (§27).
- [ ] Ownership verbs accurate; no ownership changes without the author (§24).
- [ ] No self-praise adjectives without a proving artifact at the same spot (§25).
- [ ] Ground truth and case tags nowhere near prompts, listing text, or URLs (P4).
- [ ] Nothing from `LOCAL_CONTEXT.md` (hosts, bot handles, deploy commands) appears on a committed surface (§1).

---

## 34. Change Governance

Any change to this system (new rule, changed rule, new component/message class, new terminology) MUST record:
1. **Problem** — the real user/admin/reader need or defect (not "another product does it differently").
2. **Rationale** — why this rule over alternatives, using the conflict hierarchy (§4).
3. **Affected surfaces** — bot, dashboard, case page, docs; list the files.
4. **Compatibility impact** — which existing messages/screens/copy now violate the new rule.
5. **Migration consideration** — fix now, fix-when-touched (add to §29), or explicitly grandfather.

Update this file in the same change. External references inform; project needs decide. Keep tests, the eval, and `git diff --check` green.

### 2026-07-06 case-page token and evidence-depth migration

- **Problem:** the case-study landing page had measurable demo numbers and mockup colors that were not fully governed by the design/content system: hero metrics needed synthetic provenance at scan depth, and several CSS colors bypassed tokens.
- **Rationale:** evidence provenance and token control are higher priority than visual novelty (§4, §23); promoting existing literals to named tokens preserves the current look while making future palette edits safe.
- **Affected surfaces:** case page and docs: `docs/case-study.html`, `docs/styles.css`, `DESIGN_CONTENT_SYSTEM.md`.
- **Compatibility impact:** new case-page styles must use the expanded token set; hero role metadata now includes Data when the page describes the demo catalog.
- **Migration consideration:** fixed now for the touched case-study landing page; no bot, dashboard, README, or CASE_STUDY.md changes required.

### 2026-07-07 "Swiss International" landing redesign

- **Problem:** the FlatFeed and Opsqora portfolio landings looked like two unrelated products, weakening the portfolio as a set; the FlatFeed page also carried decorative elements (mini-map, radii, panel shadows) that diluted the evidence-first register.
- **Rationale:** one shared system with a deliberate accent split (FlatFeed teal `#02776f`, Opsqora ultramarine `#2236e8`) reads as one author with consistent judgment (§4 conflict order: consistency over visual preference); the Opsqora landing served as the initial comparison example, while this document remains FlatFeed's source of truth. All copy, the 7-part framework, eval numbers, mockup panels, photo, and logo were carried over unchanged; amber stays as the measured-Results marker per the existing two-accent rule.
- **Affected surfaces:** `docs/case-study.html`, `docs/styles.css`, `DESIGN_CONTENT_SYSTEM.md` (§§4, 5, 6.3, 9, 13, 14, 15, 22, 26, 27, 32).
- **Compatibility impact:** the old token set (`--teal-soft`, `--amber-soft`/`--amber-border`, `--bubble-*`, `--header-*`, `--shadow`, `--max`, mini-map tokens) and old component classes (`.site-header`, `.section-label`, `.case-row`/`.case-number`, `.proof-strip`, `.result-cards`, `.button-primary`/`.button-secondary`) no longer exist; Google Fonts webfont loading (Inter, Inter Tight, IBM Plex Mono) replaces the local-stack-only rule; breakpoints moved from 1180/900/720 to 1080/920/620.
- **Migration consideration:** fixed now — page and this document updated in the same change; the earlier landing-audit findings that referenced old selectors were historical records and were not rewritten. No bot, dashboard, README, or CASE_STUDY.md changes required (structure and meaning preserved per §27).

### 2026-07-07 agent-usability hardening

- **Problem:** the standard was strong but too costly to apply for small changes: it lacked a fast route for agents, treated every verification as equally heavy, and made the sibling Opsqora implementation sound like a required external dependency.
- **Rationale:** keeping invariants explicit while separating current implementation details from review gates preserves correctness without slowing safe documentation/CSS edits. A risk-based verification matrix follows the conflict hierarchy (§4): factual integrity and behavior checks stay strict where behavior or evidence changes, while lightweight docs edits get lightweight checks.
- **Affected surfaces:** `DESIGN_CONTENT_SYSTEM.md` only (§§0, 4, 5.1, 5.2, 27, 31, 34).
- **Compatibility impact:** future agents should start from §0 and choose checks from the §31 matrix instead of blindly running tests and eval for every text-only edit; Opsqora remains a comparison example, not a source that must be present in this workspace.
- **Migration consideration:** fixed now in the standard. No code, bot, dashboard, case page, README, or CASE_STUDY.md migration required.

### 2026-07-07 product-copy audit (bot + dashboard)

- **Problem:** a copy audit against GOV.UK/GDS, the Microsoft Writing Style Guide, and ONS metric guidance found (a) one concept with several names across surfaces — the catalog QA run was called "Run catalog QA" / "Parser check", the QA demo was called "QA demo" / "error demo", admin-confirmed errors were "Confirmed errors" / "Real parser errors" / "Real errors", pending triage was "Pending decision" / "Pending review" / "Pending alert feedback", the source column was "Catalog" vs the card's "Source", and single-field edits confirmed with "Done, settings updated." although the object is the *filter*; (b) AI-transparency drift — `risk_score` (0–100) rendered as a percentage, alert header "AI QA: review parser" and section header "Mismatch" reading as facts, "the model believes / AI decided" anthropomorphism, and mock-provider cost shown under an "OpenAI model" label; (c) renter-flow defects — the post-save summary claimed "Checking available listings now" although no immediate check runs, the `Set up filter` entry skipped the `Step 1/4` prefix and WBS hint, "Hi!" violated the no-exclamation rule, and "I no longer save filters from free text" referenced product history new users cannot know; (d) raw enum values (`daily_cost_limit_reached`, enabled: "none") shown in admin messages.
- **Rationale:** correct meaning → clear action → comprehension → project terminology (§4 copy order). Canonical decisions: the backfill action is **catalog QA** everywhere; the demo is the **QA demo**; a single AI QA pass is a **check**, its stored artifact/coverage state is a **review**; an alerting review is a **flagged report**; admin-confirmed errors are **Confirmed errors**; awaiting triage is **Pending review**; risk renders as **"risk score N of 100"** (never `%`); the provider is named wherever its cost appears; single-field edit confirms with **"Filter updated."**; "Let us" → "Let's" (natural language per Microsoft style).
- **Affected surfaces:** `main.py` (bot copy), `flatfeed/dashboard/streamlit_app.py`, this file (§§7.5, 17, 18, 29). Listing-card contract (§10), canonical button labels (§19), triage vocabulary, and all eval numbers unchanged.
- **Compatibility impact:** the §29 "Error demo failed." row is resolved and removed; the approved admin-failure example is now "Catalog QA failed. Check the logs." (same "X failed. Check the logs." pattern). No callback data, commands, or behavior changed except that `Set up filter` now shows the same Step 1/4 text as `/filter`.
- **Migration consideration:** fixed now across bot and dashboard in one change; no README/CASE_STUDY/case-page changes needed (none of the changed strings appear there — verified by targeted search).

---

## 35. Open Issues

Questions needing a human decision before rules can be written (distinct from §30's rule-level gaps):

| Issue | Decision type | Owner |
|---|---|---|
| Confirm the canonical public GitHub URL used in `docs/case-study.html` links | Content/publishing | Author |
| Replace case-page HTML mockups with real demo-session screenshots (stated next step)? | Content | Author |
| Should renters ever see match reasons (`MatchDecision.reasons`) in cards? | Product | Author |
| Automate eval-number propagation into CASE_STUDY.md / case-study.html from `run_eval --json`? | Implementation | Author |
| Converge the `All listings` / `Browse all listings` label pair on one form | Content | Author |
| Any live source adapter rollout — requires terms review and a documented scope change before any rule here extends to it | Product/legal | Author |

---

*This document defines standards; it changes no code. Sources: `main.py`, `flatfeed/` (bot, matching, AI QA, dashboard), `synthetic/` + `eval/` (golden set and eval), `docs/case-study.html` + `docs/styles.css` (case page), `README.md`, `docs/PROJECT_CONTEXT.md`, `CASE_STUDY.md` (product intent and claims). WCAG 2.2 AA, Telegram bot conventions, GOV.UK/GDS and Microsoft writing guidance, and AI PM portfolio evidence standards serve as references only.*
