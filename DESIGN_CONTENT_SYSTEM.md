# FlatFeed — Design & Content System

**Status:** Normative. Single source of truth for UI, layout, components, copy, terminology, and case-study content.
**Date:** 2026-07-24 (durable current-status handoff added; see §34 history for earlier decisions).
**Basis:** source code inspection (`main.py`, `flatfeed/`, `synthetic/`, `eval/`), an evidence/claim audit, desktop and mobile browser renders of the case-study page, and the project docs (`README.md`, `docs/PROJECT_CONTEXT.md`, `CASE_STUDY.md`). No renter research or usability study has been run; product-value statements remain hypotheses.

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
| Case-study landing page | §§4–6, 13–15, 22–27, 32–34 | Synthetic/mock qualifiers stay at reading depth; ownership language preserved; four-question structure and preview honesty preserved |
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

- **Category:** Telegram prototype for matching Berlin WBS apartment listings against a saved four-field filter. One synthetic source adapter is implemented; the admin dashboard and QA path are supporting repository surfaces, not the primary product story.
- **Primary users:** (a) a renter setting a filter and receiving matching listings in Telegram; (b) an admin reviewing AI QA findings and the dashboard; (c) case-study readers — recruiters, hiring managers, AI PMs. The target portfolio role is **AI Product Manager in a corporate environment**: reliability, explainability, privacy, defensibility, measurable AI quality, and cost control matter more than feature count.
- **Unit of work:** the *listing*. It flows through: source adapter → deterministic parsing → local transit enrichment → deterministic matching; optional QA and optional background notification are separate branches.
- **Role of AI:** AI QA is the **only** AI surface. Listing parsing and matching are fully deterministic and make no LLM calls. Canonical boundary (from `docs/PROJECT_CONTEXT.md` and `README.md`): *AI QA may challenge the parser but cannot replace or mutate parsing rules, listing data, matching, or user-facing cards automatically. Findings are admin-only and require human feedback.*
- **Role of the human:** the admin triages every alerted finding as `Parser error` / `Parser correct` / `Borderline / unsure`; parser improvements are made by a human editing `flatfeed/parser.py` / `flatfeed/wbs_rules.py`.
- **Honesty constraint (product-level):** everything measurable is a *synthetic/demo* result unless a real production measurement exists. Demo metrics MUST be visibly labeled as synthetic evaluation metrics, never as production user-impact numbers.
- **Privacy constraint:** the renter path stores a Telegram ID, saved filter, and notification-dedupe history. `/delete` removes those FlatFeed database records after confirmation; it does not delete Telegram chat history or unrelated admin-review records. No real listings are scraped or redistributed; listing photos are licensed demo assets (`assets/listing_photos/LICENSES.md`).

---

## 3. System Principles

Derived from the product's actual behavior — not imported from external systems.

**P1 — Determinism owns the user-facing decision.**
*Why:* four-field matching must be predictable and explainable.
*Implications:* parsing and matching stay rule-based; every match/no-match is traceable to a rule; unknown values fail closed (unknown Kaltmiete or rooms never match a specific filter).
*Anti-pattern:* letting an LLM decide, adjust, or "fix" any field that affects matching or cards.

**P2 — AI reviews; it never mutates.**
*Why:* the product's thesis is AI as a controlled QA layer with a hard boundary.
*Implications:* AI QA output lands in `ai_qa_reviews` and admin alerts only; risk at/above the configured threshold (default 75) alerts the admin; the admin's triage label is the decision of record.
*Anti-pattern:* auto-applying `suggested_values`; letting QA output touch `listings`, matching, or cards.

**P3 — Public evidence stays proportional to what was tested.**
*Why:* portfolio credibility rests on never implying live systems or production impact.
*Implications:* before a frozen hosted-model validation exists, the public case quotes only the authored synthetic regression-case count and explains that it covers designed cases. After one exact frozen validation passes the predeclared engineering and Product Scorecard gates, the landing may replace that numerical result with exactly four simple AI QA metrics under the same-depth label `Synthetic frozen validation`; §13 and §23 define the narrow exception. Detailed field diagnostics remain in the case study or runnable eval artifacts; transit minutes are geometric estimates; demo photos disclose whether they are illustrative or location-aligned, while apartment terms remain synthetic.
*Anti-pattern:* turning 100% on authored cases, zero mock cost, or zero false alerts into a product result.

**P4 — Ground truth is eval-only.**
*Why:* the eval is only meaningful if the parser and AI QA cannot see the answers.
*Implications:* synthetic case tags and hidden truth fields MUST never appear in listing text, listing URLs, parser input, or AI QA prompts. They live in `synthetic/case_catalog.py` / `synthetic/golden_set.py` and are read only by `eval/run_eval.py`.
*Anti-pattern:* "helpfully" enriching a prompt with golden-set metadata.

**P5 — The user's cost of a wrong send is high; fail quiet, fail closed.**
*Why:* a notification about a stale or mismatched listing burns trust in one message.
*Implications:* candidates pass the current adapter's activity check before card delivery; the implemented synthetic adapter checks local catalog state, not a live network source. Optional background notifications are deduplicated (`sent_listing_notifications`); manual `/matches` may be requested repeatedly; at most 10 cards per action.
*Anti-pattern:* sending unverified candidates to hit a count.

**P6 — Domain terms are kept, glossed, never translated away.**
*Why:* WBS, Kaltmiete, Bezirk are the domain; removing them removes correctness.
*Implications:* the product is English-facing; WBS (Wohnberechtigungsschein) and Kaltmiete keep short plain-language explainers at the point of use (wizard hints); the visible filter label is `District` while the semantic unit is the Bezirk (12 Berlin Bezirke; Ortsteil/Kiez names normalize to a Bezirk).
*Anti-pattern:* renaming WBS to "housing certificate"; translating Kaltmiete to "cold rent" in UI.

**P7 — Destructive actions confirm; everything else flows.**
*Why:* the bot holds personal filter data; deletion is a privacy feature and must be both discoverable and safe.
*Implications:* `Reset filter` and `🗑 Delete my data` always ask an explicit Yes/No with unambiguous labels ("Yes, delete saved data" / "No, keep my data"); the wizard always offers `⬅ Back` / `✖ Cancel`.
*Anti-pattern:* one-tap destructive actions; trapping the user in a setup flow.

**P8 — Two audiences, two panels: user surface vs admin surface.**
*Why:* renters and the QA reviewer have different jobs and different vocabularies.
*Implications:* admin functions live behind the `🛠 Admin` button and the dashboard. The button itself is visible to every visitor as a demo view (§7.4, §34 2026-07-10); catalog-changing or budget-spending actions inside stay gated to `ADMIN_TELEGRAM_USER_IDS` and say so if a non-admin taps them. User-facing copy never mentions parser internals, risk scores, or prompt versions; admin copy may be technical but stays plain.
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
| Case-study page | Repo-local "Swiss International" rules in §5; the sibling Opsqora landing is a comparison example when available, not a required dependency | Hand-written HTML/CSS, token palette in `docs/styles.css`, four-question case framework (§6.3, §22); accent split: FlatFeed teal, Opsqora ultramarine |
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

The page uses the repo-local **"Swiss International" system** documented in this section: flat 1px-bordered panels, square corners, mono uppercase kickers, four numbered sections, one real Telegram product screenshot, and a dark final CTA. The sibling Opsqora project is a useful comparison implementation when it is available, but this file is the source of truth for FlatFeed. The deliberate difference between the two sites is the accent: FlatFeed is teal, Opsqora is ultramarine.

### 5.1 Color — ADOPT

All colors come from `:root` in `docs/styles.css`. New page styles MUST use these tokens; new hex literals MUST NOT be introduced without updating this section.

| Token | Value | Role | Allowed usage | Prohibited usage |
|---|---|---|---|---|
| `--bg` | `#f8faf9` | Page ground | Body background, sticky header backdrop (via `color-mix`) | — |
| `--surface` | `#ffffff` | Panels, cards | Panels, evidence cards, buttons, table backgrounds | — |
| `--wash` | `#eef3f1` | Quiet plane | Product-preview body and quiet fills | Text |
| `--ink` | `#101819` | Primary | Headings, body, solid buttons, dark CTA background | — |
| `--ink-2` | `#445254` | Secondary text | Ledes, prose paragraphs, nav links | — |
| `--ink-3` | `#687576` | Tertiary text | Mono kickers, captions, labels | Long body text blocks |
| `--line` | `#dce4e1` | Hairlines | 1px dividers, card borders, grid rules | Text |
| `--accent` | `#08766e` | Single accent — FlatFeed teal | Kicker numbers, state dots, button hovers, selection, focus rings | Long text |
| `--accent-deep` | `#055d57` | Accent text/links | Link hovers and demo-state label | — |
| `--accent-wash` | `#e3f2ee` | Accent wash | Role note and quiet accent fills | Text backgrounds needing contrast |
| `--mac-close` | `#ff5f57` | macOS-style close control | Decorative window control only | Content, status, or evidence |
| `--mac-minimize` | `#febc2e` | macOS-style minimize control | Decorative window control only | Content, status, or evidence |
| `--mac-maximize` | `#28c840` | macOS-style maximize control | Decorative window control only | Content, status, or evidence |

Rules:
- **One-accent system:** teal is the only content accent. The three macOS-style window-control tokens are a decorative chrome exception and MUST NOT encode product status or evidence. Evidence is distinguished by labels and filled/outlined square markers, not by a second result color.
- The page has no error/warning/success status colors — it is editorial, not operational. Do not import status palettes from the bot, the dashboard, or Opsqora's status set (`--ok`/`--warn`/`--bad` were deliberately not ported).
- The dark CTA uses `--ink` as ground with literal white/transparent-white values in the local component rules. It is the only inverted zone on the page except dark buttons.

### 5.2 Typography — ADOPT roles (fluid rem scale)

Type, spacing, box sizes, and container widths are authored in `rem` on a fluid root: `html { font-size: clamp(1rem, 0.96rem + 0.12vw, 1.0625rem) }`. Hairlines, focus strokes, shadows, and backdrop blur stay in px for crispness.

- New type/spacing MUST be authored in rem; px is reserved for the ≤2px strokes and effects above.
- MUST NOT reintroduce fixed-px font sizes for document-flow text.
- The sibling case may share the editorial principles, but FlatFeed's layout and evidence density follow this document and its own CSS.

Three families, loaded via Google Fonts from the HTML head (this webfont import is a deliberate 2026-07-07 change; see §34):
- `--font-ui` **Inter** — body, buttons, nav, meta values.
- `--font-display` **Inter Tight** (600–700) — H1, section H2s, step titles, figure/metric values, boundary quote, wordmark.
- `--font-mono` **IBM Plex Mono** (500–600, uppercase + letter-spacing) — kickers, labels, captions, table headers, chips, listing-card fields.

The page must remain readable and structurally stable if Google Fonts are blocked or slow. Keep system-font fallbacks in every font token, do not make layout correctness depend on exact webfont metrics, and update §34 if fonts are removed, self-hosted, or changed. The rationale for external fonts is portfolio presentation consistency, not product functionality.

Sizes below list the **reference px at a 16px root**; each is authored in `styles.css` as its rem equivalent (px ÷ 16) and scales with the fluid root:

| Role | Font / weight | Size | Notes |
|---|---|---|---|
| Hero h1 | display 600 | clamp(36px → 64px), lh 1.02, ls −0.035em | first-person outcome statement |
| Section h2 | display 600 | clamp(28px → 48px), lh 1.06 | takeaway statements |
| Hero lede | ui 400 | clamp(16px → 20px) / 1.6 | `--ink-2` |
| Body prose (`.case-prose p`) | ui 400 | 16px / 1.7, max-width 680px | `--ink-2` |
| Kicker (`.kicker`) | mono 500 | 11px uppercase, ls 0.08em | `--ink-3`; index number span in `--accent` 600 |
| Buttons (`.btn`) | ui 600 | 13px, padding 11×18 | square corners |
| Labels / dt | mono 500 | 10–11px uppercase | `--ink-3` |
| Product-preview fields | ui/mono | 9–12px | compact product evidence only |

Rules:
- Base body is 15px/1.5 `--font-ui`; long-form prose measure stays ≤680px (reference px at the 16px root; authored as 0.9375rem/42.5rem).
- Display sizes use `clamp()` — do not add per-breakpoint font overrides.
- New text styles SHOULD reuse a role above rather than introduce a new size; do not add weights above 700.

### 5.3 Borders, Radius, Elevation — ADOPT

- **Square corners by default: border-radius 0.** Status dots are literal squares. The three circular `.mac-window-dot` controls are the only sanctioned radius exception and exist solely in the screenshot frame.
- 1px `--line` hairlines divide and border; 1px `--ink` rules open sections and label groups.
- Elevation: one shadow only — on `.product-preview`. Everything else is flat.
- No gradients anywhere. The sticky header uses `color-mix` transparency + `backdrop-filter: blur(10px)`, not a gradient; the blur radius stays fixed px.

### 5.4 Grid and Width — ADOPT

- One centered column: `.case` width `min(100% - 3rem, 75rem)`.
- Hero is a two-column proposition + product preview at desktop and a single linear column below 56rem. On the two-column layout, the top of `.hero-copy` aligns with the top of `.product-preview`; do not vertically center the shorter column against a tall product image. The portrait Telegram preview is capped at `30rem` and aligned to the right on wide screens; below 56rem the existing responsive width rule takes over.
- Numbered mono kickers (`01`–`04`) are the section motif. Workflow is 5-up, decisions 3-up, evidence 2-up; each collapses per §14.
- The dark CTA spans the content width.

### 5.5 Icons and Imagery — ADOPT

- Icons are inline hand-written SVG strokes, stroke `currentColor`, width 2: 14px inside buttons (arrows, git-branch), 16px in panel headers. No icon library at runtime, no emoji on the page.
- Brand: `assets/flatfeed-logo-mark.png` at 26px in the header/footer wordmark, `alt=""` (decorative next to the visible name).
- Imagery: `assets/flatfeed-telegram-showcase.png` is the sole hero product image. It is a real Telegram demo-session screenshot whose building photo and address refer to the same location; the caption and alt text state that apartment terms remain synthetic. The surrounding macOS-style bar is presentation chrome, not a claim that Telegram was captured in macOS. Do not add dashboard mockups or decorative illustrations.
- Any photo of a building MUST keep alt text disclosing its demo context. Source, author, license, and modifications stay documented in `assets/listing_photos/LICENSES.md`; attribution for a licensed public-preview image also appears in the adjacent figcaption.

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
Skip link → sticky top bar (brand; 4-item nav: Product · Decisions · Evidence · Next test; Repository + Try the demo) → split hero (plain-language proposition, WBS/Kaltmiete gloss, role/status metadata, one real Telegram demo screenshot in a macOS-style evidence frame) → **four-question framework**: 01 Product · 02 Decisions · 03 Evidence · 04 Next test → dark CTA → sibling case cross-link → footer.

The page MUST answer in order: what is the user flow, what did the candidate decide, what is actually demonstrated, and what should be tested next. AI QA appears only as one bounded decision/limitation; dashboard mockups, mock-cost, legal analysis, and detailed eval tables do not belong in the main public narrative. At ≤56rem the nav may hide because the four sections remain a single linear scroll and the two primary header actions remain visible.

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
- Confirmation keyboards state the consequence in the label: `Yes, reset filter` / `No, keep it`; `Yes, delete saved data` / `No, keep my data`; `Yes, run catalog QA` / `Cancel`. A bare `Yes`/`No` pair MUST NOT be used for destructive or costly actions.

### 7.3 Filter wizard — ADOPT
Four fixed steps, always in this order: **1 WBS → 2 District → 3 Max Kaltmiete → 4 Rooms.** Each shows `Step N/4`. Steps 1 and 3 carry the plain-language explainers (`WBS_HINT`, `KALTMIETE_HINT` in `main.py`) — the gloss lives at the point of the question, not in `/help`. The wizard is entered only by explicit user action (`Set up filter`, `Edit filter`, `/filter`); `/start` never forces it. If the bot restarted mid-setup, `SETUP_EXPIRED_TEXT` states what happened and restarts cleanly — never silently resume with lost state.

### 7.4 Admin panel — ADOPT
Behind `🛠 Admin`, visible to every visitor as a demo view (§34 2026-07-10) — non-admins see a caption saying so. Actions: `Run QA demo`, `Review flagged issues`, `View QA metrics`, `Refresh catalog`, `Run catalog QA`, `📊 Effectiveness dashboard` (URL button when `DASHBOARD_URL` is set), `Replay the tour`. Every action except `Replay the tour` stays gated to `ADMIN_TELEGRAM_USER_IDS` and answers "This button is only available to admins." for anyone else. QA triage on a flagged report offers exactly three labels: `Parser error` / `Parser correct` / `Borderline / unsure` — this vocabulary is load-bearing (it feeds the dashboard's feedback-quality metrics) and MUST NOT drift. The guided tour (§7.6) reuses this exact triage vocabulary and the real alert formatter for its own, non-persisting fault-injection walkthrough — that is the actual open-to-all ephemeral demo path, not `Run QA demo`.

### 7.5 Failure and timeout messages — ADOPT principle
Manual refresh and listing actions have timeouts (`MANUAL_REFRESH_TIMEOUT_SECONDS`) and user-facing failure messages. A failure message states what failed and, for admins, where to look next ("Catalog QA failed. Check the logs."). Renter-facing failures never expose internals; they state the outcome and that the user can retry. Apologies, exclamation marks, and blame are out of register (§17).

### 7.6 Guided tour — ADOPT
`/start` (plain, or via the `?start=tour` deep link) leads into a 3-step, button-only tour before the regular filter/matches flow: **Step 1** shows a temporary four-field filter; **Step 2** runs `is_listing_match` over the synthetic catalog, applies the synthetic adapter's local activity check, and sends one canonical card with field-level match reasons; **Step 3** separates Implemented / Measured on synthetic data / Not validated. Nothing is written to `users` until the visitor taps `Use this demo filter` on step 3. Step 2 also offers an optional `How matching works` pipeline explainer (`tour:3`) alongside the main `See what is proven` button; it is a side branch, not a required step.

The parser-fault simulation is an optional branch after the core tour. It uses the deterministic mock provider, never calls a hosted model, and never persists tour feedback. Its copy MUST say that the fault is constructed and that admin labels do not change parsing or matching automatically. `Skip the tour` and `🛠 Admin` → `Replay the tour` remain available.

---

## 8. Dashboard System

- Stock Streamlit components and theme — CURRENT/ADOPT. No custom CSS injection; the dashboard's credibility is its data, not its chrome.
- **Product operations, not an AI-QA-only tool** (§34 2026-07-11). The page title is "FlatFeed product operations"; AI QA is one section among five, not the whole page. **Headings are the admin's questions**, in this fixed order: "Is the demo pipeline ready to deliver trusted matches?" → "Can FlatFeed trust and deliver what it collected?" → "How accurate is deterministic parsing?" → "Is AI QA useful enough to keep operating?" → "What is proven and what remains unproven?". New top-level sections keep this question form and this ordering (product/reliability before AI); the content answers the question.
- Every metric block carries an `st.caption` with provenance and definitions; the current prompt version is always shown from `CURRENT_AI_QA_PROMPT_VERSION` (never hard-coded as a string). The parsing-accuracy section calls `eval.run_eval` live on every page load — its numbers are never hand-typed, matching the README/CI harness exactly.
- Two worked examples separate source data from AI output (§12.6): "Worked example: raw text → parsed fields" (parsing section) shows the parser alone, no AI; "Try it yourself: inject a parser fault" (AI QA section, formerly "Demo: parser made a mistake, AI checked it") renders the parser snapshot and the raw listing text next to the AI finding.
- Every review query excludes any `qa_prompt_version` ending in `-demo` (the shape a non-persisting demo/tour artifact would use) — defense in depth, checked by `tests/test_dashboard.py`, even though nothing currently writes rows shaped that way (see the guided tour's Variant B, §7.6).
- `fmt_share(n, d)` renders a percentage only once `d >= 20`; below that it renders `"N of D"` and `"no data"` at `d == 0`. Every rate in the dashboard (useful signal rate, false alarm rate, per-field and per-version tables) MUST go through this helper — a precise-looking percentage on a handful of reviews reads as more certain than it is.
- Mock-provider `AI confidence` is a fixed value, not a calibrated score (`flatfeed/ai_qa.py`'s mock always returns 0.7 or 0.8). Wherever it is shown, label it `"AI confidence (illustrative mock score)"` while `AI_QA_PROVIDER=mock`; do not present it as a live model probability.
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
| Case-study CTAs | `.btn--primary` (ink, teal hover) / `.btn--ghost` (outline); dark CTA block: `.btn--accent` (teal) / `.btn--inverse` | Top bar + hero + final CTA | `Try the demo`, `View repository`, `Read the Markdown version` |

Rules:
- One primary action per surface: the bot's is `Show matches`; the case page's is `Try the demo`.
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
- The photo (when present) is a deterministic demo asset. The guided-tour showcase is the only address-aligned exception: its photo, displayed address, district, and coordinates refer to the same real location, while availability and apartment terms remain explicitly synthetic. Other catalog photos MUST NOT imply that they depict their listing address.

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
- The case page has no charts. Evidence remains a labeled Demonstrated / Not demonstrated split.
- Before frozen hosted-model validation, the only public eval number is the authored regression-case count, verified by `scripts/check_eval_numbers.py`.
- After one exact frozen validation passes both the unchanged engineering contract and the Product Scorecard contract in `eval/AI_QA_EVAL_PLAN.md` §31, the Evidence section MAY contain one compact four-item scorecard: Parser Error Detection Rate, False Alert Rate, Correct Field Detection Rate, and Successful Check Rate. Each item MUST show the percentage and absolute count under the same-depth label `Synthetic frozen validation`.
- The four-item scorecard is the only permitted landing metric block. Historical engineering metrics, field tables, confidence intervals, cost, and latency remain in the Markdown case study or eval artifacts. The scorecard sits below the renter-product story and MUST NOT turn the page into an AI QA dashboard.

---

## 14. Responsive System (case-study page)

Breakpoints are authored in rem/em-like units: **68rem** (tighter desktop grids), **56rem** (linear hero, hidden redundant section nav), and **40rem** (single-column metadata/workflow and full-width CTA buttons).

- Desktop is the primary reading surface; mobile is a supported viewing mode, not a separately designed product.
- Nothing needed for the 10-second scan (§22) may disappear at any width: kicker, H1, boundary-aware lede, CTAs, metadata, and product preview. The section nav may hide on narrow screens because the document remains a short linear flow.
- The Telegram bot and Streamlit dashboard handle their own responsiveness — do not add custom viewport logic there.

---

## 15. Accessibility Baseline (case-study page) — WCAG 2.2 AA target

- Landmarks and labels exist and MUST be preserved: the skip link, `aria-label` on nav ("Case study sections"), evidence panels, the workflow band, and the scope-figures list; decorative SVGs carry `aria-hidden` and the brand image an empty alt; the demo photo has a descriptive alt disclosing it is a demo image.
- Contrast: current `--ink-2`, `--ink-3`, and `--accent` are chosen for readable text on white; verify any retint instrumentally and keep normal text ≥4.5:1.
- Keyboard: a global `:focus-visible` outline (2px `--accent`) covers all interactive elements — any new interactive element MUST keep a visible focus state.
- `scroll-behavior: smooth` exists only inside `prefers-reduced-motion: no-preference`; the reduced-motion block keeps behavior neutral. New animation MUST be gated the same way.
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
| Destructive confirm | Consequence named, neutral | "Yes, delete saved data" / "No, keep my data" |
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
| Confirmation buttons | Consequence in the label | ≤5 words | `Yes, delete saved data` / `No, keep my data` | Bare Yes/No for destructive actions |
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
| Browse without filter | **📂 All listings** (reply keyboard and inline — converged 2026-07-09, §29/§34) | Implying it respects the filter; "Browse all listings" as a second inline-only form | Reply keyboard / no-filter card |
| Wizard navigation | **⬅ Back** / **✖ Cancel** | "Previous", "Abort" | Every wizard step |
| Admin: demo QA run | **Run QA demo** | "Test AI" | Admin panel |
| Admin: full backfill | **Run catalog QA** (+ confirm: `Yes, run catalog QA` / `Cancel`) | — | Admin panel |
| Admin: triage a finding | **Parser error** / **Parser correct** / **Borderline / unsure** | Any fourth label; abbreviations | QA reports |
| Admin: open metrics | **View QA metrics** / **📊 Effectiveness dashboard** | — | Admin panel |
| Open a listing | **Open listing** (the card's only link) | "More", "Details" | Listing card |
| Case-study CTAs | **Try the demo** / **Read the case study** / **View repository** | "Try it", "Try the guided demo", "GitHub" (as a button label) | Header, hero, and final CTA all use **Try the demo**; header nav item `Repository` is a nav link, not a CTA |

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
| Notifications | optional background notification | Newly seen match deduplicated against stored delivery history; manual matches may repeat | — | background notification deduplication | "every match once", "alerts" (reserved for admin) |
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

**10-second scan** (kicker + H1 + lede + meta + product preview) must answer: What is this, who is it for, what did the candidate own, and what is the prototype boundary?
Mechanics: the kicker states `working prototype` and `synthetic catalog` once. The H1 names one filter, Berlin WBS listings, and one consistent Telegram feed. The lede explains the save-once, normalize, and deterministic-match mechanism without repeating the prototype boundary. Metadata identifies the candidate's role, audience, status, and bounded admin-only AI QA role. Live-source and renter-outcome limitations stay in Evidence and the deeper case-study text instead of weakening the opening proposition. The product preview shows one current synthetic match in a real Telegram demo session; it does not show internal QA metrics.

**30-second scan** (+ section headings, workflow, decision cards, evidence split) must answer: what the core flow is, which three decisions matter, and what is demonstrated versus unvalidated.
Mechanics: the four H2s state Product / Decisions / Evidence / Next test as takeaway sentences. Decision cards explain the rationale and trade-off, not experiment outcomes. Evidence records implemented proof, measured synthetic results, and specific unknowns without repeating the decision rationale. Next test maps those unknowns to Learn / Measure / Decide signals. Evidence uses two labeled lists, not a results dashboard. Before frozen hosted-model validation, the only public eval number is the authored synthetic case count. After a passing frozen validation, one compact four-metric Product Scorecard may replace that numerical result under the explicit label `Synthetic frozen validation`; the surrounding evidence split and product-first hierarchy remain unchanged.

**Deep read** must answer: problem hypothesis, product flow, ownership, three trade-offs, evidence limits, and next validation. Keep the four-question framework in §6.3 and the concise Markdown equivalent in `CASE_STUDY.md`.

Element rules:
- **Hero:** boundary-aware kicker → plain proposition H1 → product-mechanism lede → term gloss → CTAs → four-item meta `dl`. Every value is decodable without insider context.
- **Product preview:** one real Telegram demo-session screenshot only, presented inside a clearly external macOS-style evidence frame. Values come from the current synthetic catalog; the caption states that apartment terms are synthetic and carries the photo attribution. Location coherence remains documented in `assets/listing_photos/LICENSES.md`. The screenshot may be cropped to exclude Telegram's empty composer, but its card content MUST NOT be edited. No fake dashboard, product-internal browser chrome, or mock metrics.
- **Workflow:** Filter → Normalize → Check → Match → Notify. "Check" is explicitly the synthetic adapter's local catalog state; "Notify" is optional background delivery with deduplication.
- **Decisions:** exactly three public decisions: four-field scope, deterministic matching/optional QA boundary, reliability controls before live-source breadth. Each card explains why the boundary exists; measured outcomes belong in Evidence.
- **Evidence:** Demonstrated now vs Not demonstrated yet. Implemented proof and synthetic results appear once; the Product Scorecard itself carries the hosted-model outcome. Do not present field accuracy, exact accuracy, mock cost, or zero-error counts as product outcomes. A passing frozen-validation Product Scorecard is the sole exception and is limited to the four metrics defined in §13.
- **Next test:** one permitted live source and a small renter observation, with Learn / Measure / Decide signals covering renter adoption, source freshness, human review of every AI alert, and a random sample of listings with no alert. It is a plan, not a claim.

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
- A hosted-model scorecard MUST come only from the one frozen validation run and MUST show `Synthetic frozen validation`, the absolute counts, and the real-world manual-audit limitation at the same reading depth. Calibration metrics and development-screen results MUST NOT appear on the landing.
- A real product limitation MUST say that human review is still required for every AI alert and for an independent random sample of listings receiving no alert. This is PLANNED, not implemented; the prototype uses no housing-provider data without permission.
- Capabilities exercised only through the synthetic adapter (multi-source collection, source health) MUST be described as architecture exercised by the synthetic adapter — the README's phrasing is the model.
- $0 QA cost MUST stay attributed to the mock provider.
- Hiring signal MUST NOT be improved by inventing evidence. Ever.

---

## 24. Candidate Ownership Language

- The canonical ownership statement says: "I defined the renter problem, product scope, matching and AI guardrails, reliability trade-offs, and evaluation contract. I implemented the bot, dashboard, and test harness with Claude Code and Codex as coding collaborators." Keep the HTML and Markdown versions in sync in *meaning*.
- Verb discipline: **defined/designed/scoped/chose** = candidate judgment; **implemented/built/wrote** = delivery; **the bot/the parser/the eval does X** = system behavior; **demo/mock/synthetic** = illustrative outcome. Do not swap categories.
- The author approved the agent-collaboration disclosure; it lives in the Decisions contribution note and `CASE_STUDY.md` §2 and MUST NOT be removed or softened without the author.
- First person ("I", "my") is correct on the case study and in CASE_STUDY.md. In the bot, "I" is the *bot* speaking about bot actions (§17) — never the candidate. The dashboard and README use no first person for ownership except CASE_STUDY-quoted material.

---

## 25. Professional Language Rules

**Prefer:** concrete mechanisms tied to artifacts — "four-field filter", "synthetic-adapter state check", "background notification deduplication", "15 authored regression cases". State whether each mechanism is in the main user path, optional, synthetic, or unvalidated.

**Buzzword register.** Current status: *leverage, seamless, robust, cutting-edge, intelligent, actionable insights, AI-powered, end-to-end (as a boast), scalable, production-ready, enterprise-grade* appear on no surface as self-praise. Protect this. Rules rather than blanket bans:
- *production-ready / enterprise-grade*: MUST NOT appear — the demo explicitly is neither.
- *end-to-end*: acceptable only in the literal sense already used ("an end-to-end AI PM case: problem framing, trade-off definition, prototype delivery, evaluation, and honest documentation") — a scoped list, not a boast.
- *scalable*: only about a specific mechanism with its limit stated (e.g. "SQLite is appropriate for this local portfolio prototype" is the model — a fitness claim, not a scale claim).
- Self-praise adjectives about our own output ("reliable", "trusted", "honest") SHOULD NOT be used as feature labels. Name the control instead: state check, fail-closed unknown value, or notification deduplication.

---

## 26. Scannability Rules

- Headings state the takeaway or the question; a heading-only read of the case page or dashboard must be coherent.
- Case-study paragraphs ≤5 sentences, one idea each; bot messages are 1–2 sentences; dashboard captions 1–2 sentences.
- Lists for parallel mechanisms (README "What It Shows", workflow, decisions, evidence); tables only for enumerable facts.
- The case page uses no public metric cards before frozen hosted-model validation. After the §13 publication gate passes, exactly one compact four-item Product Scorecard is permitted in Evidence; no other numerical AI QA block is allowed.
- Technical explanations follow "term (plain gloss)" on first use — the WBS and Kaltmiete hints are the models.
- Review gates: the 10s/30s scan tests (§22) for any case-page change; for the bot, "can a new user reach a listing card in two guided steps from /start?"; for the dashboard, "does each section answer its own heading?"

---

## 27. Cross-Surface Consistency

**MUST remain consistent (meaning-identical) across bot, dashboard, case page, and docs:**
- The meaning of listing, filter, WBS tiers, Kaltmiete-only matching, district/Bezirk, golden set, risk score, triage labels (§20).
- The AI boundary sentence pattern: parsing/matching deterministic; AI QA admin-only, budgeted, never mutating (§2, §12).
- **Public eval numbers.** Before frozen hosted-model validation, the only public result number is the authored synthetic regression-case count. After the §13 publication gate passes, the landing numerical result block contains only the four simple Product Scorecard metrics, each with its absolute count and `Synthetic frozen validation` label. Field tables, historical engineering metrics, mock cost, latency, and quiet/caught diagnostics stay in the case study or runnable engineering artifacts.
- **Eval sync check.** `scripts/check_eval_numbers.py` re-runs `eval.run_eval --json` and verifies the authored-case count in `CASE_STUDY.md`, `README.md`, and `docs/case-study.html`.
- The four-question Product / Decisions / Evidence / Next test structure and its five-part Markdown equivalent stay meaning-aligned.
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
| Adapter state check + optional background dedupe | delivery pipeline | Names the implemented boundary precisely | Do not imply live-network verification or manual-card dedupe |
| Source-health alerting with cooldown | ingestion | Detects silent failure without alert spam | Any new background job |
| Question-form dashboard sections with caption provenance | `streamlit_app.py` | Admin reads answers, not charts | All new dashboard sections |
| Worked example on the dashboard ("parser made a mistake, AI checked it") | dashboard | Shows the loop, not just aggregates | Keep one concrete example per new metric family |
| Ground-truth quarantine | `synthetic/` ↔ prompts | Makes the eval meaningful | Absolute; no exceptions |
| Version-stamped QA reviews (one per listing per version) | `flatfeed/ai_qa.py` | Enables version comparison, caps cost | Any new AI artifact gets a version field |
| Three concise decision cards | case study §02 | Shows prioritization without a separate AI essay | Keep four-field scope, deterministic boundary, reliability-before-breadth |
| Demonstrated / Not demonstrated split | case study §03 | Prevents prototype completion from reading as market validation | Every future evidence claim |
| Teal-only structure accent | case page | Keeps weak evidence from gaining visual weight | Use labels and filled/outlined markers for evidence status |
| Licensed demo photos with attribution file | `assets/listing_photos/` | Defensibility | Any new third-party asset gets the same treatment |

---

## 29. Deprecated / Do-Not-Copy

Exists in the codebase today; MUST NOT be reused in new work; migrate when touching the area. (No formal audits exist yet — this list comes from direct inspection and is expected to grow when audits run.)

| Pattern | Current location | Reason | Replacement | Priority |
|---|---|---|---|---|
| ~~Two labels for the same catalog action (`📂 All listings` vs `📂 Browse all listings`)~~ | (resolved — `main.py`) | One action, one name (§19) — inline long form tolerated only until touched | Converged on **📂 All listings** everywhere (`main.py` inline no-matches button now matches the reply keyboard and help text); no test asserted the old string (§34, 2026-07-09) | Done — don't reintroduce a second wording |
| Case-page GitHub links hard-coded to `github.com/mich-mayer/flatfeed` (×6) | `docs/case-study.html` — top-bar + hero + CTA + footer | Static page, no build step: a URL can't be single-sourced in markup without JS-only links (breaks no-JS on the page's key "view my code" CTA) or introducing a build/template; the 6 real hrefs are the correct static pattern | VERIFIED 2026-07-08 against `git origin` — canonical = `mich-mayer/flatfeed`, treat as FACT. A canonical-URL comment at `<body>` top is the documented source of truth; keep the 6 links in sync on any repo move/rename | Resolved-verified |

---

## 30. Unresolved Decisions

Insufficient evidence for a rule — do not invent one; use the temporary default.

| Decision | Why unresolved | Evidence needed | Temporary default |
|---|---|---|---|
| Dashboard theming/branding | Stock Streamlit is deliberate for now | A decision that dashboard chrome matters for the portfolio | No custom CSS injection |
| Localization (German or Russian bot copy) | Product is English-facing by decision (PROJECT_CONTEXT Known Constraints) | An explicit product decision to localize | English only; keep German domain terms glossed |
| Live source adapters | Legal/terms review pending; demo is synthetic-only | Author's go-ahead + terms-compatible sources | Synthetic adapter only; describe others as PLANNED |
| Renter-facing "why did this match?" explanations | Match reasons exist internally (`MatchDecision.reasons`) but aren't user-facing product-wide | A decision that renters need explanation UI in the main filter/matches flow | Keep reasons internal there; the guided tour's step 2 is a deliberate, scoped exception (§7.6, §34 2026-07-11) that surfaces `MatchDecision.reasons` as "Why it matched" — do not extend that exposure elsewhere without a new decision |
| Eval-metrics *generation* into docs (vs. verification) | Numbers are still written by hand; only checked automatically now (§27, `scripts/check_eval_numbers.py`, 2026-07-09) | A decision to template/generate the result blocks from `run_eval --json` instead of hand-editing them | Hand-edit numbers, then run the §27 sync check before handoff; do not build a generator without this decision |

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
- [ ] Delivery: adapter state check, optional background dedupe, ≤10 cards, fail-closed matching intact (§3 P5).
- [ ] Dashboard: new sections are question-headed with caption provenance; no hand-typed metric values (§8).
- [ ] Case page: tokens only, square corners except the three macOS-style window controls, shadow only on the product preview, one teal content accent (§5).
- [ ] Case page: four-question structure, numbered-kicker motif, one product preview, and clear mobile linear flow (§6.3, §14).
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

### 2026-07-24 durable current-status handoff

- **Problem:** stable product rules and the full evaluation plan were durable,
  but a new thread had no short mandatory artifact stating the latest
  experiment decision, consumed datasets, publication state, and next step.
  Reconstructing that state from chat or thousands of lines of experiment
  history is slow and risks reopening consumed evidence.
- **Rationale:** add one concise changing-state file beside the stable project
  context and make both Codex and Claude entry points require it. Update it only
  for material state changes, not after every prompt, so it remains a reliable
  handoff rather than a chat diary.
- **Affected surfaces:** new `docs/CURRENT_STATUS.md`, `AGENTS.md`, `CLAUDE.md`,
  `README.md`, `docs/agent-workflow.md`, and this document.
- **Compatibility impact:** future agents must read the current-status handoff
  before proposing work and must update it when a material result, decision,
  public evidence state, or recommended next step changes. Stable rules remain
  in their existing canonical files.
- **Migration consideration:** current Terra-high and product state migrated
  now. Future updates replace stale status and link to detailed artifacts
  instead of appending conversational history.

### 2026-07-24 Terra-high locked-holdout result

- **Problem:** Terra high passed the 280-case frozen validation, but the
  original 600-case locked holdout had not yet tested whether that selected
  configuration generalized to the larger predeclared synthetic sample.
- **Rationale:** run the holdout exactly once with a minimal freeze and
  one-run guard, then let every predeclared gate decide the outcome. The four
  simple aggregate metrics passed, but rooms achieved 43/50 against the 45/50
  minimum. A matching-critical failure overrides the stronger aggregate
  scorecard, so the configuration is not finally accepted.
- **Affected surfaces:** `eval/ai_qa_runner.py`,
  `eval/ai_qa_product_scorecard.py`, the locked-holdout run/freeze artifacts,
  their tests, `eval/AI_QA_EVAL_PLAN.md`, `README.md`,
  `docs/PROJECT_CONTEXT.md`, `CASE_STUDY.md`, `docs/case-study.html`, and this
  document (§34).
- **Compatibility impact:** the landing keeps the already measured four-metric
  frozen-validation scorecard but now states that the later locked holdout did
  not confirm the configuration. No holdout metrics replace the landing
  scorecard, and no product-runtime behavior changes.
- **Migration consideration:** completed once. The holdout is consumed and
  must not be rerun or used for prompt tuning. Any future hosted-model attempt
  requires a new hypothesis and fresh development/calibration/validation data;
  real-source measurement remains a future product step requiring permission.

### 2026-07-24 locked-holdout suitability and final-test gates

- **Problem:** the original 600-case locked holdout predates the four simple
  Product Scorecard metrics, the matching-critical district guardrail, and the
  later balanced WBS-family datasets. Its exact inputs were still independent,
  but the repository had no reproducible artifact proving that the old
  composition remained suitable for the selected Terra-high configuration.
- **Rationale:** audit aggregate composition without exposing case-level
  content or changing the frozen model. Keep the original cases because
  regenerating or rebalancing them after model selection would weaken the
  precommitment. Add exact 600-case Product Scorecard counts and critical-field
  gates while declaring that same-generator synthetic cases cannot establish
  live-provider accuracy or natural error prevalence.
- **Affected surfaces:** `eval/ai_qa_holdout_readiness.py`,
  `tests/test_ai_qa_holdout_readiness.py`, `eval/AI_QA_EVAL_PLAN.md` §37, and
  this document (§34).
- **Compatibility impact:** the locked holdout remains disabled and unchanged,
  but any future release must now pass the readiness audit plus the four simple
  metric gates and separate WBS, district, Kaltmiete, and rooms gates. A
  holdout result does not automatically replace the current public validation
  scorecard.
- **Migration consideration:** audit and contract implemented now without an
  API call. A holdout-specific one-run freeze, runner release guard, exact dry
  run, and hard budget remain the next implementation step.

### 2026-07-24 final hiring-manager CTA and ownership audit

- **Problem:** the contribution note listed broad ownership categories without
  naming the product and AI decisions, the final CTA pointed readers toward
  implementation instead of product evidence, and the footer repeated the
  already prominent synthetic-data qualifier rather than closing on the
  product's distinctive operating boundary.
- **Rationale:** name the renter problem, matching and AI guardrails, and
  evaluation contract as the candidate's decisions while preserving the
  approved coding-collaborator disclosure. Invite the reader to try the renter
  flow or inspect its evidence. Close with the concise positioning line `One
  saved filter. Deterministic matching. Admin-only AI QA.` Synthetic provenance
  remains visible in the hero, preview caption, Evidence, and scorecard.
- **Affected surfaces:** `docs/case-study.html`, `CASE_STUDY.md`, and this
  document (§24, §34).
- **Compatibility impact:** the ownership sentence changes meaning-identically
  across HTML and Markdown; CTA labels and URLs remain unchanged; the footer
  positioning line changes without removing any required evidence label.
- **Migration consideration:** fixed now as a copy-only change. No runtime,
  metrics, links, components, or responsive styles changed.

### 2026-07-24 decision-evidence-next-test separation

- **Problem:** the AI validation result appeared inside a decision card and
  again in Evidence, while reliability features were repeated across Product,
  Decisions, and Evidence. Next test named activities but did not map them back
  to the three unresolved product risks.
- **Rationale:** make each section do one job. Decisions explain why scope and
  boundaries exist; Evidence records what runs, what was measured, and what is
  still unknown; Next test states what to learn, measure, and use as the
  expansion decision. Keep the four-metric scorecard as the single landing
  location for the hosted-model outcome.
- **Affected surfaces:** `docs/case-study.html`, `CASE_STUDY.md`, and this
  document (§22, §34).
- **Compatibility impact:** remove the frozen-validation result from the
  deterministic-rules decision card, tighten the Evidence lists, and expand the
  Learn / Measure / Decide signals to include renter adoption, source
  freshness, human review of every AI alert, and a random sample of listings
  with no alert.
- **Migration consideration:** fixed now as a copy-only narrative change.
  Product behavior, metrics, evidence labels, and runtime boundaries remain
  unchanged.

### 2026-07-24 hero product-message tightening

- **Problem:** the hero repeated `working prototype`, `synthetic catalog`, and
  `end to end` across the kicker, H1, lede, and metadata, then ended with a
  generic list of open questions. The repetition weakened the product value
  without adding a meaningful risk control.
- **Rationale:** keep the factual `working prototype · synthetic catalog`
  boundary once in the kicker. Let the H1 state the user value — one filter and
  one consistent Telegram feed — and let the lede explain how the product
  works. Replace the repeated `Data: Synthetic by design` metadata item with
  the bounded `AI role: Admin-only parser QA`, which adds relevant AI PM
  context without turning QA into the primary product story. Detailed
  limitations remain specific and actionable in Evidence.
- **Affected surfaces:** `docs/case-study.html` and this document (§22, §34).
- **Compatibility impact:** the H1 and lede are shorter and product-led; the
  fourth metadata item now explains AI's bounded role. The hero no longer names
  live-source coverage, freshness, and renter outcomes as open questions.
  Those limitations remain explicit in the Evidence section, the next-test
  section, `CASE_STUDY.md`, `README.md`, and `docs/PROJECT_CONTEXT.md`.
- **Migration consideration:** fixed now as a copy-only change. No metrics,
  evidence labels, runtime behavior, or responsive styles changed.

### 2026-07-23 Terra-high passing frozen-validation publication

- **Problem:** the exact Terra-high configuration completed its one authorized
  frozen validation after the Product Scorecard publication contract was
  written. Public surfaces still described the earlier rejected medium
  configuration and therefore understated the current repository evidence.
- **Rationale:** publish exactly the four permitted simple metrics because the
  frozen engineering contract, Product Scorecard, and every matching-critical
  field guardrail passed. Keep the renter workflow ahead of the QA evidence,
  label the block `Synthetic frozen validation`, show absolute counts, and
  state the manual-audit limitation beside the results.
- **Affected surfaces:** `docs/case-study.html`, `docs/styles.css`,
  `CASE_STUDY.md`, `README.md`, `docs/PROJECT_CONTEXT.md`,
  `eval/AI_QA_EVAL_PLAN.md`, this document, the aggregate scorecard reporter,
  and its tests.
- **Compatibility impact:** replace the qualitative rejected-Terra wording on
  current-state surfaces. The landing removes the authored regression-case
  number and exposes only the four approved hosted-model metrics. Detailed
  field diagnostics remain in the Markdown case study and eval artifacts.
- **Migration consideration:** fixed now. The result remains synthetic offline
  feasibility evidence; the public demo continues to use the deterministic
  mock, product runtime is unchanged, and the locked holdout stays closed.

### 2026-07-23 frozen-validation Product Scorecard contract

- **Problem:** the engineering eval uses several technically correct metrics,
  but they are too detailed for a hiring-manager-facing product case. The
  existing public rule also prohibited every hosted-model metric, even after a
  new Terra configuration passed calibration and was frozen for independent
  validation. At the same time, synthetic validation cannot show whether the
  checker misses naturally occurring parser errors on permitted live data.
- **Rationale:** use four plain-language metrics tied directly to the admin QA
  job: Parser Error Detection Rate, False Alert Rate, Correct Field Detection
  Rate, and Successful Check Rate. Permit them only after one exact frozen
  validation passes both the unchanged engineering gates and the stricter
  Product Scorecard gates. Keep the product promise and renter workflow first;
  place the scorecard in Evidence and state that a real product would still
  require human review of alerts plus a random sample of silent cases. This
  preserves a simple prototype while showing that real-world measurement and
  source-coverage controls were considered.
- **Affected surfaces:** this document (§§3, 13, 22–23, 26–27, 34),
  `eval/AI_QA_EVAL_PLAN.md`, new
  `eval/ai_qa_product_scorecard.py`, and
  `tests/test_ai_qa_product_scorecard.py`. The landing and Markdown case study
  are deliberately not updated with new result numbers before validation.
- **Compatibility impact:** the prior absolute rule that only the 15-case
  regression count could ever be public is now conditional. Once the
  publication gate passes, the landing numerical result block contains only
  the four Product Scorecard metrics; detailed field and engineering metrics
  remain off the landing. Existing synthetic, mock, non-mutating, and
  real-source limitations remain mandatory.
- **Migration consideration:** contract and aggregate-only reporter implemented
  before validation. The frozen scorer, prompt, model, reasoning effort,
  dataset, retries, output limit, configuration freeze, product runtime, and
  existing run artifacts are unchanged. Landing migration is deferred until a
  real frozen-validation artifact exists and passes evidence review.

### 2026-07-23 Terra frozen-validation evidence update

- **Problem:** the latest Terra configuration completed its one authorized
  frozen validation after the public feasibility wording had been written
  around the earlier Luna failure.
- **Rationale:** the four simple aggregate Product Scorecard metrics passed,
  but the matching-critical rooms guardrail and unchanged engineering contract
  failed at 18/21. The landing therefore keeps no hosted-model metric block.
  The public case records the outcome qualitatively so it neither hides the
  completed experiment nor presents a rejected configuration as accepted.
- **Affected surfaces:** `CASE_STUDY.md`, `docs/case-study.html`, `README.md`,
  `docs/PROJECT_CONTEXT.md`, `eval/AI_QA_EVAL_PLAN.md`, and this document.
- **Compatibility impact:** replace the current-state phrase "missed a
  predeclared critical WBS gate" with the latest result: all four simple
  aggregate targets passed, but the predeclared matching-critical rooms
  guardrail failed. Historical Luna artifacts and their recorded WBS failure
  remain unchanged.
- **Migration consideration:** no runtime integration, metric cards, or locked
  holdout run. The consumed validation is not rerun or used as a new acceptance
  attempt.

### 2026-07-22 hosted-model feasibility evidence update

- **Problem:** the public case study still said hosted-model AI QA usefulness
  had not been tested, but the repository now contains a completed synthetic
  offline feasibility experiment. Leaving the old wording would understate the
  implemented evaluation work; presenting the experiment as accepted would be
  false because frozen validation missed a predeclared critical WBS gate.
- **Rationale:** factual integrity and evidence separation take priority over a
  stronger-looking result. The public story now records the completed
  experiment and its stop decision qualitatively, without publishing internal
  metric tables or turning balanced synthetic challenge-set results into
  production claims. The public demo remains on the deterministic mock.
- **Affected surfaces:** `CASE_STUDY.md`, `docs/case-study.html`, `README.md`,
  `docs/PROJECT_CONTEXT.md`, and this document.
- **Compatibility impact:** the statements "hosted-model usefulness has not
  been tested" and "Usefulness and false-alarm rate of AI QA with a real
  model" no longer describe the repository accurately. They are replaced by
  the narrower limitation: live-source and real-prevalence performance remain
  untested.
- **Migration consideration:** fixed now across the public Markdown, HTML, and
  durable context. No AI configuration was accepted, no locked holdout was
  run, no runtime integration was added, and the only public eval number
  remains the authored deterministic regression-case count.

### 2026-07-15 plain-language copy pass (landing, docs, guided tour)

- **Problem:** a copy review against the hiring-manager goals found three defect groups. (a) Rule violations and defects: workflow step 01 said `maximum cold rent` although §20 prohibits "cold rent" and the hero glosses Kaltmiete; the tour's plural suffix `"es"` would render "matching listing**es**" for any 2+ match count (latent today — the current catalog yields exactly 1 match); the meta description said "explicit renter filters" (plural) against the one-filter H1; one action carried three CTA labels (`Try the demo` / `Try the guided demo`); README said "failure controls" where CASE_STUDY.md said "reliability controls". (b) Residual specification language on reader-facing surfaces: noun chains ("synthetic-adapter state check", "background-delivery deduplication", "hosted-model AI QA" on a page that never mentions the mock provider), passive "are implemented", and `A → B · C` chains in tour step 3/3. (c) Wording a reader could challenge: H1 "tested as" reads as user-tested (which the Evidence section denies), "useful listing opens" names an undefined metric, "One matcher result" and "QA control" are insider terms.
- **Rationale:** correct meaning → clear action → comprehension (§4 copy order). Mechanisms stay named, but as verb phrases a hiring manager reads once ("re-checked as active before delivery", "skip matches already recorded as delivered"); no new claims, numbers, or evidence labels. The H1 now states "running end to end" (a fact) instead of "tested as" (implies validation). One CTA form (`Try the demo`) everywhere per §19 — "guided" is communicated by the tour intro itself. `working prototype` replaces `functional prototype` as the plainer word with identical meaning. The tour intro's /delete sentence became "FlatFeed does not save your filter until you explicitly keep it" — deletion stays discoverable at the moments data actually exists (save confirmation, filter card `🗑 Delete my data`, the `tour:3` explainer, the command menu), which serves P7 better than a deletion notice before anything is saved. Step 2 gained an optional `How matching works` button to the existing `tour:3` explainer, which was previously unreachable for new visitors (kept only for old inline keyboards) despite being the product's best plain-language pipeline walkthrough.
- **Affected surfaces:** `docs/case-study.html` (meta description, kicker, H1, lede, hero CTA, meta `dl`, brand sub, product paragraph, workflow steps 01/03/05, decisions 02/03, evidence intro and both lists, Measure/Decide rows, sibling note, footer link), `CASE_STUDY.md` (§§ intro, 1, 2, 3, 4, 5), `README.md` (intro paragraph), `docs/demo-listing.html` (showcase-photo paragraph), `docs/PROJECT_CONTEXT.md` (guided-tour step names), `main.py` (tour copy: intro, steps 1–3, QA branch, triage response; plural fix; step-2 keyboard), `tests/test_guided_tour.py`, and this document (§§7.6, 9, 19, 34).
- **Compatibility impact:** the previous wordings no longer conform: "cold rent" on any reader-facing surface, "hosted-model AI QA" on the case page without the mock contrast, "Try the guided demo", `QA control` (now `QA check`), "One matcher result" (now "One match from the demo catalog"), "functional prototype" (now "working prototype"). `scripts/check_eval_numbers.py` patterns were deliberately left untouched — both matched sentences are byte-identical. The `flatfeed/schemas.py` field description "Maximum cold rent in EUR." is internal schema metadata, not a covered surface, and was left as-is.
- **Migration consideration:** fixed now across all listed surfaces in one change; tests updated in the same change, including the 2+ listing plural and the newly reachable pipeline branch's continuation label. Product behavior, matching semantics, the card contract, WBS semantics, and eval numbers are unchanged. Amended after a Codex cross-review before commit, in the same change: the step-2 header avoids "real" next to a synthetic listing ("One match from the demo catalog"); the intro privacy sentence is scoped to the filter instead of a blanket "nothing is saved"; the dedupe claim is "skip matches already recorded as delivered" everywhere, because delivery history is written after the send and an unconditional "never repeat" overstates the guarantee.

### 2026-07-15 exact showcase entrance and CC0 asset naming

- **Problem:** the Wikimedia filename labels the CC0 photograph as Binger Straße 10, but the photographed entrance is marked `91` beside the `Schlangenbader Straße` sign; the nearby `Nauheimer Straße` sign points toward the intersecting street. Berlin's monument register confirms that these addresses belong to the same large residential block, but the filename is not the exact photographed entrance.
- **Rationale:** retaining the verified CC0 photograph is the simplest rights-safe option. The showcase address now follows the visible entrance (`Schlangenbader Str. 91`) and address-level OpenStreetMap coordinates, while the local asset name describes what the image actually shows. Attribution remains as provenance even though CC0 does not require it.
- **Affected surfaces:** `synthetic/case_catalog.py`, `synthetic/listing_photos.py`, `tests/test_synthetic_catalog.py`, `assets/listing_photos/LICENSES.md`, `README.md`, `docs/PROJECT_CONTEXT.md`, `docs/demo-listing.html`, the Telegram guided-tour card, `docs/assets/flatfeed-telegram-showcase.png`, `docs/case-study.html`, `docs/styles.css`, and this document (§§5.5, 22, 34).
- **Compatibility impact:** the first synthetic case changes from Binger Str. 10 to Schlangenbader Str. 91 and receives corrected address-level coordinates. The previous local Binger-named asset path is removed. Existing captured Telegram screenshots containing Binger Str. 10 no longer represent the current catalog and must not be presented as current evidence.
- **Migration consideration:** the catalog, tests, local asset naming, durable docs, Telegram card, and public case-study screenshot now use the corrected entrance address. The CSS crop ratio follows the replacement screenshot's 904 px source width and stops at 1435 px, after the message card and before Telegram's composer.

### 2026-07-14 hiring-manager copy and preview-density pass

- **Problem:** the tall Telegram proof still dominated the wide hero, while several reader-facing phrases used process language (`explicit, inspectable workflow`, `regression set`) where a hiring manager needed a faster product explanation. The compact term gloss also placed WBS and Kaltmiete on one line, and the metadata label `User` was less precise than the intended audience label.
- **Rationale:** the 10-second scan benefits from a slightly quieter proof image and plain, outcome-led copy. A `30rem` desktop cap reduces the screenshot by about 8% at 1440px without changing tablet/mobile readability. `Audience` avoids implying validated active users. The separate regression footnote is removed, but its live-accuracy limitation stays beside the 15-case number so evidence integrity is preserved.
- **Affected surfaces:** `docs/case-study.html`, `docs/styles.css`, `CASE_STUDY.md`, `scripts/check_eval_numbers.py`, and this document (§§5.4, 22, 23, 27, 34).
- **Compatibility impact:** the previous hero preview width, inline term gloss, `User` label, longer Product heading, two-sentence preview disclaimer, separate regression footnote, contrastive Next test introduction, and exact-string-only eval-count checker no longer conform to the current concise case-page pattern.
- **Migration consideration:** fixed now across the HTML case page and its Markdown equivalent. Product behavior, evidence values, screenshot contents, and mobile ordering do not change.

### 2026-07-14 top-aligned case-study hero

- **Problem:** after the real portrait Telegram screenshot replaced the shorter HTML mockup, the hero's centered grid alignment pushed the proposition 61–131px below the screenshot at common desktop widths. The first screen read as two unrelated blocks instead of one proposition-and-proof pair.
- **Rationale:** the existing Swiss editorial grid and 10-second-scan rules depend on a clear shared starting line. Top alignment preserves the approved type scale, column widths, whitespace, and responsive stack while restoring that relationship; resizing the headline or screenshot would solve a positioning defect by weakening content hierarchy or product evidence.
- **Affected surfaces:** `docs/styles.css` and this document (§§5.4, 22, 34).
- **Compatibility impact:** desktop `.case-hero` layouts that relied on vertical centering no longer conform. The single-column layout below 56rem keeps its existing source order and spacing.
- **Migration consideration:** fixed now with `align-items: start`; no component or content migration is required.

### 2026-07-14 address-aligned showcase photo and attribution

- **Problem:** the primary demo card and case-study preview paired a Rosenfelder Straße address in Lichtenberg with a photograph of a residential block in Wedding. The mismatch weakened the credibility of the portfolio artifact, and the public preview did not credit the photographer at the point of display.
- **Rationale:** factual coherence and license compliance outrank keeping a generic illustrative-photo rule for the main showcase. The showcase now uses one verified real location for its building photo, address, district, and coordinates. It still states that apartment availability, rent, floor, rooms, and WBS eligibility are synthetic, so location coherence does not become a housing-offer claim. Attribution sits below the public preview to keep the Telegram card contract concise; the linked demo-listing page and license register repeat the credit.
- **Affected surfaces:** `synthetic/case_catalog.py`, `synthetic/generator.py`, `assets/listing_photos/LICENSES.md`, `docs/assets/berlin-wbs-building.jpg`, `docs/case-study.html`, `docs/demo-listing.html`, `README.md`, `docs/PROJECT_CONTEXT.md`, `tests/test_synthetic_catalog.py`, and this document (§§3, 5, 10, 22, 34).
- **Compatibility impact:** the first synthetic case changes from Rosenfelder Str. 12 / 10315 to Suermondtstr. 56–64 / 13053 and uses a case-specific photo override. Its transit estimates change with the coordinates. Other synthetic cases retain the deterministic illustrative-photo pool. The listing-card fields and order do not change.
- **Migration consideration:** fixed now in the catalog and current code-native public preview. A fresh real Telegram screenshot should replace the code-native preview after the updated card is captured; the adjacent attribution must remain when that swap happens.

### 2026-07-14 real Telegram proof in a macOS-style frame

- **Problem:** the case-study hero still reconstructed the bot card in HTML after the corrected, address-aligned card had been captured from a real Telegram session. That left the strongest product proof looking illustrative, and the raw phone screenshot included an empty composer that did not help a hiring manager assess the product.
- **Rationale:** a real demo-session screenshot is more credible than a code-native reconstruction. The screenshot itself remains unedited; CSS crops only the empty Telegram composer. A minimal macOS-style bar with red, yellow, and green controls provides the requested portfolio-window context without pretending those controls belong to Telegram. The adjacent caption keeps the synthetic-data boundary and credits Bodo Kubrak at the point of display.
- **Affected surfaces:** `docs/case-study.html`, `docs/styles.css`, `docs/assets/flatfeed-telegram-showcase.png`, `docs/demo-listing.html`, `assets/listing_photos/LICENSES.md`, `README.md`, `docs/PROJECT_CONTEXT.md`, and this document (§§5, 22, 34). The underlying showcase data changes to Binger Str. 10 are recorded in `synthetic/case_catalog.py` and `tests/test_synthetic_catalog.py`.
- **Compatibility impact:** the old code-native preview classes and `docs/assets/berlin-wbs-building.jpg` no longer conform to the current one-screenshot rule. Circular red/yellow/green window controls are a narrow exception to the square-corner and one-content-accent rules; they are decorative and carry no product meaning.
- **Migration consideration:** fixed now. The obsolete preview asset and CSS are removed, and the previously open screenshot-replacement decision is closed.

### 2026-07-14 minimal prototype narrative and three-step tour

- **Problem:** the public case and guided tour gave internal parser/AI QA mechanics, mock metrics, and a seven-part strategy narrative more weight than the renter-facing product. Several phrases also exceeded the implementation boundary: four-field matching read as full eligibility, the synthetic adapter's local state check read as live-source verification, and optional background deduplication read as a guarantee for every card.
- **Rationale:** hiring-manager comprehension and factual defensibility take priority over feature count. The public story now centers on one temporary filter, one actual matcher result from the synthetic catalog, three product decisions, a Demonstrated / Not demonstrated evidence split, and one next validation. AI QA is a bounded optional branch, not the renter path. Detailed eval diagnostics remain runnable engineering evidence instead of public product outcomes.
- **Affected surfaces:** `docs/case-study.html`, `docs/styles.css`, `CASE_STUDY.md`, `README.md`, `docs/demo-listing.html`, `docs/PROJECT_CONTEXT.md`, `main.py`, `tests/test_guided_tour.py`, and `scripts/check_eval_numbers.py`. This document's current rules in §§2–7 and 22–28 were updated to match.
- **Compatibility impact:** the guided tour's required path changed from five screens to three; `tour:3` remains a compatibility explainer, while the main step-2 button now routes directly to `tour:5`, rendered as Step 3/3. The QA simulation remains available from the final keyboard. Public 100%/exact-accuracy/mock-cost blocks and the dashboard mockup were removed. The delete confirmation now names its actual database scope.
- **Migration consideration:** fixed across current public and normative surfaces. Historical §34 entries and local plan files remain historical records and are not current requirements. A live-source test and renter study remain future validation, not implementation claims.

### 2026-07-11 product-first demo rework: tour v2, dashboard restructure, case-study honesty fixes

- **Problem:** two independent audits (an internal tour walkthrough and Codex's `docs/PRODUCT_DEMO_AUDIT.md`) converged on the same diagnosis after the 2026-07-10 tour shipped: the demo told the story of "parser + AI QA" more strongly than the story of a complete product, which undersells the author as a Product Manager rather than an engineer. Specifics found and fixed: (1) the tour opened with product mechanics before the renter's problem, and AI occupied roughly 3 of 5 beats; (2) step 2 built its listing card by directly formatting a pre-selected listing (`_listing_match_from_model`) instead of running the real matching predicate, so "this is what FlatFeed found" was a stronger claim than the tour actually demonstrated; (3) step 1 saved the demo filter to `users` immediately on `Start the tour`, before the visitor made any explicit choice; (4) the tour's closing screen showed a same-session-empty AI QA funnel (`Checked by AI: 0` etc.) — worse than no screen, since it promised measurability and delivered zeros; (5) `AI confidence: 70%` in the tour alert and the dashboard's demo block read as a calibrated model probability when the mock provider always returns a fixed 0.7/0.8 (`flatfeed/ai_qa.py`); (6) the case-study hero mockup showed a listing card (`District: Wedding`, `Demo street 12`, `610 EUR`/`760 EUR`) that does not match any real synthetic catalog case — Wedding normalizes to Bezirk `Mitte`, and no case has those values — while a second mockup in "What I built" showed dashboard tabs (`Overview` / `QA Review` / `Sources`) that have never existed in the real one-scroll Streamlit page; (7) `Open listing` pointed at `https://demo.flatfeed.local/...`, a domain that has never resolved publicly, so the card's only link looked broken to an external viewer; (8) the dashboard's own heading was "FlatFeed parser AI QA" with no product-pipeline or evidence/limitations framing.
- **Rationale:** the central thesis adopted for this pass — *FlatFeed turns Berlin's chaotic WBS-flat hunt into one reliable feed: filter once, get every active match once; reliability is the product, AI is one bounded quality control inside it* — governs every change below, and was chosen over Codex's more generic "FlatFeed solves a repeated renter task" because it names the actual urgency (listings vanish within hours) and the actual mechanism (one filter, one-time delivery), which a generic phrasing loses. Two Codex recommendations were adopted with a **narrower scope** than proposed, for reasons recorded here so they are not silently re-widened: (a) Codex's "remove the fault-injection mini-game, replace with a static labeled case" was rejected — the interactive fault injection is the tour's only moment where a visitor *does* rather than reads the human-in-the-loop model, and removing it would have made "AI as a bounded control" a claim instead of a demonstration; it was compressed into one step (4/5) instead, which independently achieves Codex's stated goal (a 3-product/1-AI/1-evidence balance) without losing the interaction. (b) Codex's "any triage selection should proceed neutrally, never grade the visitor" was adopted, but the specific wording avoids both grading ("Correct —") and false neutrality that hides the ground truth: the new unified response opens with "Recorded for this demo only — nothing you tap is stored" for every label, then states as fact (not judgment) that the corrupted snapshot did contradict the listing text, so `Parser error` is the label an admin would confirm — informative without commenting on what the visitor personally chose. Screen 2's "Why it matched" reasons are a deliberate, scoped exception to the §30 default that renter-facing match reasons stay internal (recorded in §30's row) — chosen because proving the *real* `is_listing_match` predicate ran (not a hand-picked result) is the single highest-value fix Codex's audit identified for trust in the tour, and the reasons are read-only, already-computed `MatchDecision.reasons` output, not a new explanation feature. The empty funnel is not backfilled with seeded numbers (an option considered and rejected in an earlier working session): a mock-provider self-check trivially catches its own injected faults, so seeded metrics would read as circular, not measured. Screenshots replacing HTML mockups (author decision, resolves the §30 "Real screenshots vs HTML mockups" row — that row is removed from §30 as resolved) ship in two phases: this change corrects the mockup *values* to the real, current Lichtenberg tour-catalog listing (interim truthful state, since the mockups are what ships today) and removes the fabricated dashboard tabs; real screenshots replace the HTML mockups entirely once the author captures them from a live tour session and a live dashboard render (tracked as follow-up, not done here — an agent cannot drive a Telegram client to capture bot screenshots). The real OpenAI QA run (which would let the funnel return with genuine, non-circular numbers) and moving "Why AI?" after the product sections plus adding the two-path (main-flow vs. AI-QA-loop) diagrams are explicitly deferred by the author — nothing in this entry claims or depends on either.
- **Affected surfaces:**
  - `main.py` — tour rewritten step-by-step: step 1 no longer calls `save_fixed_preferences` (ephemeral filter); a new `_tour_candidate_matches()` runs `is_listing_match` over every active/parsed listing and step 2 runs it through the same `_verified_active_matches` activity-check path production delivery uses; step 3 is a new "Rules make the decision" pipeline explainer (replaces the old raw-text parsing deep-dive, which moved to the dashboard); step 4 is a new AI-framing screen whose button triggers the existing `tour:inject` fault flow (fault-note header now reads `Simulated parser fault`; `_format_ai_qa_review` gained an `include_confidence` parameter mirroring `include_cost`, both `False` for the tour); the triage response function collapsed from a graded Correct/Noted split into one neutral response for all three labels; step 5 replaced the AI QA funnel with `Working now` / `Measured on synthetic data` (a live `len(load_golden_set())` count) / `Not yet proven`, and gained `tour:save_filter` (writes the derived preferences only now, on explicit request) alongside the existing wizard entry point (`settings:filter`, reused rather than duplicated); `_load_tour_funnel`/`_tour_rate_line` were deleted (dead code, no remaining caller). A latent bug was found and fixed in the same change: `_select_tour_listing()` requires transit enrichment data that a fresh `scripts/ingest_synthetic.py` run does not populate (enrichment is normally lazy, triggered by the bot's own matches/listings handlers) — `_send_tour_screen_1` now calls `enrich_missing_transport_walk` itself so the tour is not silently broken as the very first interaction after a catalog refresh.
  - `synthetic/generator.py`, `flatfeed/ingestion/synthetic.py`, `flatfeed/db/seed.py`, `docs/demo-listing.html` (new) — the synthetic listing URL moved from the never-resolving `https://demo.flatfeed.local/listings/<id>` to `https://mich-mayer.github.io/flatfeed/demo-listing.html?id=<id>`, a real static page (linked from `case-study.html`'s hero figcaption) disclosing that the listing is synthetic and pointing back to the case study and the tour. `SYNTHETIC_BASE_URL` is now defined once in `synthetic/generator.py` (the URL's actual point of construction) and imported by `flatfeed/ingestion/synthetic.py` instead of being duplicated as a second literal — the two constants had silently matched by coincidence before this change, which is exactly the kind of drift this consolidation prevents. `check_synthetic_listing_active`'s prefix check was updated for the new query-string URL shape. The local DB was re-ingested (upsert-by-URL: old-URL rows are marked `removed_from_source` and preserved in history, matching the product's own reliability semantics; the `users` table is untouched by ingestion).
  - `flatfeed/dashboard/streamlit_app.py` — restructured into the five product-operations sections listed in §8, added `fmt_share`, added a live `eval.run_eval`-backed parsing-accuracy section with a raw-text→fields worked example (reusing the same tour-listing selection heuristic as `main.py`, duplicated locally since the dashboard cannot import `main.py` without triggering bot router registration), added the `-demo`-suffix exclusion filter to `_load_review_rows` (defense in depth, per §7.6), labeled mock `AI confidence` as illustrative, added an `if __name__ == "__main__":` guard (harmless under `streamlit run`, makes pure helpers safely importable — `tests/test_dashboard.py`, new) and fixed a pre-existing rendering bug where two unescaped `$..$` amounts in one caption made Streamlit render the text between them as LaTeX math.
  - `docs/case-study.html` — kicker changed so "AI" is not the first word (`Product case study · working prototype · synthetic data · 2026`); hero lede rewritten from pipeline-mechanics to the renter-outcome thesis above, keeping §24 verb discipline (`I scoped` = candidate judgment; `rules... decide` = system behavior); hero mockup listing-card values corrected to the real Lichtenberg tour-catalog listing (`Rosenfelder Str. 12`, `Kalt 512,40 EUR`, etc.) instead of the invented Wedding/610/760 values; hero figcaption now links `t.me/FlatFeedBot?start=tour` as "the guided tour" — the one place this deep link appears on the page, deliberately not duplicated into a competing hero CTA (§9 one-primary-action-per-surface); the "What I built" dashboard mockup's fabricated tabs were removed and its table headers changed to match the dashboard's real "Where the parser is most at risk" columns, with a new figcaption disclosing it is a stylized illustration, not tabbed navigation. The 7-part structure, the `Why AI?` section and its position, the Results table and numbers, the footer, and `CASE_STUDY.md` were **not** touched — moving `Why AI?` and adding the two-path diagrams are explicitly out of scope for this change (see Migration consideration).
  - `tests/test_guided_tour.py` (rewritten for the new steps: ephemeral-filter guarantee via a `users`-row-count assertion, real-matching step 2 against an in-memory catalog with a real `is_listing_match` check, neutral-triage-response assertions, funnel tests removed), `tests/test_dashboard.py` (new: `fmt_share` boundaries, `-demo` exclusion).
- **Compatibility impact:** the old tour's step numbering and callback semantics changed (`tour:2` now means the matching-result screen, not the parsing deep-dive; a new `tour:4` and `tour:save_filter` were added) — no external surface referenced the old callback data directly, so this is contained to `main.py` and its own tests. `send_match_to_chat` gained a `text_prefix` parameter (already existed from the 2026-07-10 change) reused unchanged. No listing-card contract, WBS semantics, or matching-rule change. No AI QA prompt, risk threshold, or persisted-review schema change. The synthetic URL change alters every `Listing.url` value on next ingestion (upsert-by-URL, non-destructive, see above) — any external bookmark to the old `demo.flatfeed.local` shape was never a working link, so nothing real breaks.
- **Migration consideration:** fixed now for everything listed above. Explicitly deferred, not started, and must not be inferred as done from this entry: (1) the real GPT-5.4-mini QA run, human triage, and the resulting funnel/caption flip (`AI_QA_HISTORY_IS_REAL_MODEL_RUN`, `AI_QA_HISTORY_SOURCE_CAPTION` in `flatfeed/ai_qa.py`) — screen 5 and the dashboard both already read live from the DB, so this is a data/ops task, not a further copy change; (2) moving `Why AI?` to after the product sections and adding the `main path` / `AI QA loop` diagrams from Codex's audit — both require a full case-study restructure review, tracked as a separate change; (3) real screenshots replacing the two HTML mockups fixed in this entry — captured by the author from a live tour session and dashboard render, not producible by an agent.

### 2026-07-10 guided tour message class + admin-panel demo visibility

- **Problem:** a hiring manager opening the bot cold has 2–5 minutes and no context. The prior `/start` led straight into the 4-step filter wizard, the admin panel (and therefore any visible AI QA finding) was invisible to anyone not in `ADMIN_TELEGRAM_USER_IDS`, and there was no way to show the AI-QA-audits-the-parser story without a live walkthrough from the author. A new 5-screen guided tour (`/start` or the `https://t.me/FlatFeedBot?start=tour` deep link) now leads every visitor through a pre-filled match, the deterministic parser behind it, a live WBS fault injected into that one listing, the resulting AI QA alert with real triage buttons attached, and the AI QA history funnel — before falling back to the existing filter/matches flow. This is a new bot message class (§7) and a change to the admin-panel visibility rule in P8/§7.4, so it requires this entry.
- **Rationale:** the tour reuses existing, already-approved primitives rather than inventing new ones — the listing card (`format_match_message`, unchanged), the demo fault-injection mechanism (`run_ai_qa_demo_check_for_listing`, already non-persisting), and the real admin alert formatter (`_format_ai_qa_review`) plus its exact canonical triage keyboard (`Parser error` / `Parser correct` / `Borderline / unsure`, unabbreviated, no emoji) — so the tour shows a visitor literally what an admin sees on a flagged finding, not a simplified mockup (§28 "reuse approved patterns"). An earlier chat-drafted script for this tour used narrative emoji (🎬 🧭 💥 🔨 🚨 ✅ ❌ 🤷) and code-block/arrow-diagram formatting for the parser-mapping and funnel screens; both were dropped during implementation because §7.1 restricts emoji to the sanctioned button-prefix set (🔎 ⚙ 📂 🛠 📊 🗑 ⬅ ✖) and prohibits emoji in message prose and code blocks entirely — the tour instead reuses the existing `Step N/4`-style bold prefix (generalized to `Step N/5`, already sanctioned in §28 as "template for any future multi-step flow") and the `<b>Label:</b> value` card idiom for the parser-mapping and funnel displays. Applying the conflict hierarchy (§4): factual/trust-boundary rules (Variant B non-persistence, canonical triage vocabulary) were treated as non-negotiable; the emoji/code-block deviation was a consistency violation the drafted copy hadn't been checked against, so compliance won over the draft's visual flourish. The admin-panel visibility change (P8, §7.4 "admin IDs only") is a deliberate, scoped exception: `send_admin_panel`'s own top-level gate is removed so any visitor can see how the panel is organized (with a caption stating this is a demo view), but every individual action inside — `Run QA demo`, `Refresh catalog`, `Run catalog QA`, `Review flagged issues` (writes real feedback), `View QA metrics`, the dashboard auto-start callback — keeps its existing `_is_admin_user` gate unchanged. Only opening the panel and the new `Replay the tour` button are open to everyone; the tour's own screen-3 walkthrough (not the admin panel) is the actual open-to-all ephemeral demo path. The tour's fault injection and triage never call `session.add`/`commit` on an `AIQAReview` (verified by a test asserting a zero row-count delta across a full inject-plus-all-three-triage-outcomes traversal); screen 5's funnel query only counts reviews whose `qa_prompt_version` exactly equals `CURRENT_AI_QA_PROMPT_VERSION`, so dashboard metrics stay a curated evaluation result rather than a live visitor-editable counter — a product decision made with the user, not merely a style choice, but recorded here because it changes what "admin-only" means for AI QA surfaces (§12.2).
- **Affected surfaces:** `main.py` (new tour section: screen builders, callback handlers `tour:1`–`tour:5`, `tour:inject`, `tour:skip`, `tour:replay`, `tour_fb:*`; `main_menu_keyboard()` dropped its `is_admin` parameter and always includes `🛠 Admin`; `send_admin_panel` no longer gates on `_is_admin_user`; `_admin_keyboard()` gained a `Replay the tour` row; `/help` gained a `Start the tour` button; `run_ai_qa_demo_reviews` refactored to share a new `_ephemeral_ai_qa_review_from_result` helper with no behavior change), `flatfeed/ai_qa.py` (`AI_QA_TRIGGER_TOUR_FAULT`, `AI_QA_HISTORY_IS_REAL_MODEL_RUN`, `AI_QA_HISTORY_SOURCE_CAPTION` constants — the caption is pre-run/mock-provider today and must be flipped in the same change as the day a real GPT-5.4-mini history run replaces it), `tests/test_guided_tour.py` (new), `tests/test_admin_ui.py` (updated for the `main_menu_keyboard()` signature change and the new `Replay the tour` button), `README.md` (Demo Script), `docs/PROJECT_CONTEXT.md` (new "Guided tour" subsection). The dashboard (`flatfeed/dashboard/streamlit_app.py`) is unchanged in this pass — its own `-demo`-suffix exclusion and funnel-first reordering is tracked as follow-up work, not part of this entry.
- **Compatibility impact:** `main_menu_keyboard(is_admin=...)` callers all updated in the same change (no remaining call sites pass `is_admin`). The two `test_admin_ui.py` tests asserting a non-admin's reply keyboard excludes `🛠 Admin` no longer describe real behavior and were replaced with one test asserting the button is always present; `test_admin_panel_contains_task_oriented_buttons` updated to expect `Replay the tour` first. No listing-card, WBS, or matching semantics changed. No AI QA prompt, risk threshold, or persisted-review schema changed.
- **Migration consideration:** fixed now, no grandfathering needed — this is new surface, not a rewrite of an existing rule's meaning. Follow-up (not yet done, tracked for a later change): reorder the dashboard to lead with the same funnel shown on tour screen 5, add the `qa_prompt_version`-based exclusion filter there explicitly (screen 5 already has it; the dashboard's version-comparison table does not yet), and flip `AI_QA_HISTORY_IS_REAL_MODEL_RUN` once a real provider run + human triage exists.

### 2026-07-09 hero-lede voice, numbered-kicker emphasis, footer positioning line

- **Problem:** a design review against an external reference landing (a paid-acquisition application page) surfaced three small, low-risk gaps on `docs/case-study.html`, and one non-gap. (1) The hero lede was the only hero element still in third person ("FlatFeed collects…") while the H1 was already a first-person outcome statement (§22) — a register mismatch inside one section. (2) §6.3 already names the numbered mono kicker (`01`–`07`) "the page's navigation motif," but the numeral rendered at the same 11px size as its label, under-weighted for a motif the doc calls load-bearing. (3) The footer carried the honesty/provenance line only ("© 2026 — prototype · synthetic data · demo metrics") with no short line stating the product's AI-boundary thesis, the closest thing the page has to a one-line positioning statement. (4) Non-gap, checked and closed: a prose line-length audit across `.case-lede`, all seven `.case-prose` blocks, `.case-cta p`, and `.case-sibling p`, measured by rendering the page and probing actual character width per element (not estimated) at the widest fluid-root viewport — every block landed at 54–72ch, inside the 60–75ch target, so no width changes were made; this is a completed audit with a "no change" result, not a skipped check.
- **Rationale:** (1) First person is already sanctioned for the case study (§24) and already used in the H1; the lede was rewritten to close the register gap while staying inside §24's verb discipline — "I designed the pipeline to pull listings through source adapters, normalize messy listing text into one catalog, and match them against user filters — then added AI QA to review parser quality, without letting it mutate user-facing results." uses "designed"/"added" (candidate delivery/judgment verbs, and "designed… the source-collection and matching flow" directly echoes the canonical ownership sentence in §24/section 03) for what the candidate did, and keeps the pipeline/AI QA as the grammatical actor for what the system does ("to pull…, normalize…, and match…", "to review…, without letting it mutate…") — avoiding the earlier draft's mistake of making "I" the direct subject of collect/normalize/match/use, which would have blurred candidate-judgment verbs into system-behavior verbs (the exact category-swap §24 prohibits). All five facts in the original lede (source-adapter collection, text normalization into one catalog, filter matching, AI QA review, AI never mutates) are preserved meaning-identical; checked CASE_STUDY.md and README.md for a verbatim duplicate of the old lede first — none existed, so no cross-surface sync was needed (§27). (2) Enlarging only the numeral (`.case-section .kicker span`, not `.kicker` itself) reinforces an already-approved pattern (§6.3, §28 "numbered mono kicker… keep it") rather than adding a new one, and the selector's containment in `.case-section` means it cannot reach the hero, boundary, or sibling kickers — verified those three have no `<span>` child in the markup at all, so they were structurally unreachable by this rule even before checking the rendered result. Reused the existing `--accent` token (already AA-verified 5.4:1 per §15) rather than a new color. (3) The footer line condenses the canonical AI-boundary meaning (§2's canonical sentence, already rendered verbatim as the page's pull-quote in `#boundary`) into a short mono caption — wording ("AI QA reviews — it never mutates listings") stays verbatim-close to README's existing "AI never mutates listings" (§21) rather than inventing new phrasing, uses only canonical terms (§20: AI QA, matching, listings), and reuses the existing `.case-foot span` mono-caption style and `--ink-3` color (already AA-verified ≈4.9:1) instead of introducing a new token or a new contrast pair to verify. The existing honesty/provenance span was kept byte-for-byte and wrapped, not replaced, so no §23 evidence label was touched.
- **Affected surfaces:** `docs/case-study.html` (hero lede text; footer markup — new `.case-foot-meta` wrapper holding the existing honesty span plus a new `.case-foot-line`), `docs/styles.css` (`.case-section .kicker span` rule; `.case-foot-meta` rule), this file (§34). `CASE_STUDY.md`, `README.md`, `main.py`, the dashboard, tests, and eval numbers are untouched — verified no eval-affecting or ownership-changing content was in scope. The sibling Opsqora landing was **not** touched in this change; the numbered-kicker emphasis and the footer positioning-line pattern are candidates for the same treatment there for cross-portfolio parity (§5: "when one landing's system evolves, consider whether the other should receive the same pattern"), left for a separate change.
- **Compatibility impact:** None breaking. The lede change is copy-only inside the existing `.case-lede` style rules (no new claims, no evidence label changed). The kicker change only enlarges an inline numeral already present in the markup — no new breakpoint overrides, no markup restructuring; verified at 375px and 1440px viewports via rendered computed styles (numeral 18px/375px root, 19.89px/1440px root, both scoped correctly) with no console errors. The footer change is additive — the honesty span's text and position in the DOM are unchanged, only newly wrapped; verified the two-line stack wraps cleanly under the footer's existing `flex-wrap` at 375px and sits in one row at 1440px, no overflow or clipping at either width.
- **Migration consideration:** Fixed now, docs-only (`docs/case-study.html` + `docs/styles.css`); per the §31 matrix this required `git diff --check` (clean) plus a browser render/computed-style check at the touched viewports, not the heavier tests/eval suite — no code, eval numbers, or claims were touched, so `unittest`/`eval.run_eval`/`check_eval_numbers` were out of scope and skipped. Explicitly considered and rejected in the same review, recorded here so it is not re-proposed without a new decision: adopting the reference site's warm/cream monochrome palette (`#faf8f4`/`#161514`/`#e2ddd3`) — it conflicts with FlatFeed's teal-calibrated neutrals (`--bg`/`--line`/`--accent-wash` all carry a cool/green undertone) and would force a paired recalibration of Opsqora's ultramarine system to avoid a three-way temperature clash; the accent-free monochrome approach itself was also rejected as it would remove the teal/amber two-accent system's scannability role (§5.1).

### 2026-07-09 demo-frame chrome label + overflow fix

- **Problem:** the browser-chrome URL label in both demo frames carried a descriptive suffix (`flatfeed.local — Telegram bot · QA dashboard`, `mich-mayer.github.io/flatfeed — AI QA dashboard`) that added no reader value over the plain host, and `.demo-frame-chrome em` had no `min-width`/overflow handling, so at mid-range viewports the long string wrapped and pushed `.demo-frame-live` ("Demo · synthetic data") past the frame's right border — a visible layout break, not a copy nuance.
- **Rationale:** the chrome label's job is to look like an address bar, not to caption the mockup (the figcaption already does that); a bare host reads cleaner and never overflows regardless of content length. Structurally, flex children need `min-width: 0` to shrink below content size — adding that plus `overflow: hidden; white-space: nowrap; text-overflow: ellipsis` on the label and `flex: none` on the dots/live-label makes the frame overflow-proof for any future URL length, not just the current one.
- **Affected surfaces:** `docs/case-study.html` (both `<em>` labels), `docs/styles.css` (`.demo-frame-chrome em`, `.demo-frame-dots`, `.demo-frame-live`), this file (§34). Sibling Opsqora received the identical CSS fix and an equivalent label simplification (`${LIVE_URL_LABEL} — AI eval` → `LIVE_URL_LABEL`) in its own `src/case-study.tsx` and `src/styles.css`.
- **Compatibility impact:** none — the provenance marker (`Demo · synthetic data`) is unchanged and still carries the synthetic qualifier; only the address-bar text and its container's overflow behavior changed. The existing mobile rule hiding `em` entirely (`max-width: 38.75em`) is unchanged and still applies below that width.
- **Migration consideration:** fixed now on both demo-frame instances; bot, dashboard app, README, CASE_STUDY.md, and eval numbers untouched.

### 2026-07-09 converge catalog-browse button wording

- **Problem:** §29 carried a known, low-priority duplication: the reply-keyboard button and help text both said "📂 All listings" (`main.py:98`, `:2042`) while the inline no-matches-found button said "📂 Browse all listings" (`main.py:379`) — one action, two wordings, tolerated only until either was next touched (§19/§29).
- **Rationale:** §19's copy order (correct meaning → clear action → comprehension → project terminology) favors one name per action; the short form was the majority form (two call sites) and matches the persistent keyboard, so it was cheaper and lower-risk to converge the single inline call site to it rather than lengthen the two existing ones.
- **Affected surfaces:** `main.py:379` (inline `_no_matches_keyboard`); this file (§§19, 29, 34). No test asserted the old string (verified by search).
- **Compatibility impact:** none — same `callback_data="settings:catalog"`, same destination; only the button's visible text changed.
- **Migration consideration:** fixed now, one line; bot tests, dashboard, README, CASE_STUDY.md, and eval numbers untouched.

### 2026-07-09 automated eval-number sync check

- **Problem:** §27 already required every eval result number (golden-set size, parser field/exact accuracy, misses by tag, false alert fields, QA cost) to stay identical across `CASE_STUDY.md` and `docs/case-study.html`, but the only enforcement was a documented `rg` search a human had to run and eyeball — nothing failed loudly if a number drifted after a real eval run, and §30 carried this as an open "numbers updated by hand" risk.
- **Rationale:** for a portfolio piece whose central claim is measured-not-claimed evidence (§23), a silently stale metric is a factual-integrity defect, not a cosmetic one (§4 conflict order: factual integrity outranks convenience). A verification script closes the enforcement gap without taking on the larger, still-undecided commitment of generating the prose from JSON (§30) — it only checks what's already hand-written.
- **Affected surfaces:** new `scripts/check_eval_numbers.py`; `README.md` (Eval section + Development Checks), `docs/agent-workflow.md` (Build and Verification), this file (§§27, 30).
- **Compatibility impact:** none — no case-page or CASE_STUDY.md prose changed; the script currently passes against the live eval run (15 listings, 100.0%/100.0% accuracy, 0 misses, 0 false alerts, $0.000000). Verified it also fails correctly: a deliberately introduced mismatch (97.3% vs 100.0%) was caught and reported with file-level detail before being reverted.
- **Migration consideration:** fixed now; run the script (baseline command in README/agent-workflow) any time eval numbers or their surrounding prose change, before handoff.

### 2026-07-09 browser-window chrome parity with Opsqora

- **Problem:** FlatFeed had the shared browser-window pattern in the hero, but the `What I built` dashboard preview remained a bare `product-shot`; the hero dots were square outlines while Opsqora used recognizable macOS-style traffic lights. That made the two case-study landings feel less like one portfolio system and made FlatFeed's second product proof read as a static table rather than an intentional product window.
- **Rationale:** the browser-window chrome is an evidence wrapper, not decoration: it labels provenance ("Demo · synthetic data"), scopes mockups as product evidence, and matches the sibling Opsqora case-study pattern while preserving FlatFeed's teal accent and product-specific content. The traffic-light dot radius is now the one sanctioned radius exception because it belongs to window chrome, not cards, buttons, or content panels.
- **Affected surfaces:** `docs/case-study.html` (dashboard preview wrapped in `demo-frame demo-frame--product`), `docs/styles.css` (`.demo-frame-dots`, `.demo-frame--product`, `.product-shot` border), this file (§§5, 6.3, 34).
- **Compatibility impact:** the previous square-dot chrome and bare built-section product shot are superseded; square corners remain mandatory everywhere except `.demo-frame-dots`.
- **Migration consideration:** fixed now for both demo-frame instances on the case-study page; bot, dashboard app, README, CASE_STUDY.md, and eval numbers untouched.

### 2026-07-09 fluid rem scale (sync with Opsqora)

- **Problem:** the sibling Opsqora landing migrated its type/spacing system to a fluid rem scale (`fix(design): adopt fluid rem scale`, 2026-07-07) for accessibility (user font-size preferences, browser zoom) and to use wide-viewport space instead of leaving it as margin; FlatFeed still authored all 227 size/spacing declarations in fixed px with no root `font-size`, so the two "one shared system" landings had diverged on a foundational mechanism, not just the accent split §4 already permits.
- **Rationale:** consistency across the portfolio outranks either page's prior implementation detail (§4 conflict order); rem sizing also directly serves §15's WCAG 2.2 AA target (1.4.4/1.4.10) in a way fixed px cannot. Adopted the identical mechanism Opsqora already validated (one root `clamp()`, 1rem==16px authoring convention, hairlines/effects ≤2px stay px, breakpoints in em) rather than inventing a second approach.
- **Affected surfaces:** `docs/styles.css` (full file — every font-size, padding, margin, gap, width/height, and max-width converted px→rem except 1–2px hairlines/outline and the `--demo-shadow`/`backdrop-filter` effect values; the three responsive breakpoints converted px→em), this file (§§5.2, 5.3, 5.4, 14).
- **Compatibility impact:** none visually — every value converts via px÷16 so the page renders pixel-identical at the default 16px root; the only *behavior* change is that the root now scales to 18px above a 1600px viewport (previously fixed) and the whole system now responds to browser zoom/user font-size settings, which it did not before.
- **Migration consideration:** fixed now, whole file in one pass; bot, dashboard, README, and CASE_STUDY.md untouched (no px/rem usage there).

### 2026-07-08 cross-portfolio 7-part unification

- **Problem:** the FlatFeed and Opsqora landings shared a visual system but not a structural one: different nav sets (5 vs 6 items, different labels) and section placements meant the two-project portfolio did not read as one deliberate case framework, and neither page carried the guide-required what-I'd-do-differently reflection; the H1's "trusted, measurable matching workflow" was also the page's most abstract line.
- **Rationale:** both landings now follow the canonical 7-part AI PM case framework with an identical 7-item nav mirroring the numbered sections; Build/Buy/Wrapper moved from 02 (Why AI?) to 04 (The Approach) because it is model-strategy reasoning, leaving 02 to the negative-decision judgment signal (kept per §22); the Results H2 and a "Measured — synthetic golden-set eval" group-label row lift the synthetic qualifier to scan level; the author approved the first-person H1 rewrite and the unified AI-agent disclosure in section 03 on 2026-07-08 (§24). A quiet sibling cross-link after the CTA frames the two projects as opposite AI-boundary placements.
- **Affected surfaces:** case page and docs: `docs/case-study.html`, `docs/styles.css` (`.case-results-group`, `.case-sibling`), `CASE_STUDY.md`, this file (§§6.3, 22, 24, 25).
- **Compatibility impact:** §6.3's previous 5-item nav snapshot and §22's previous H1 example are superseded; eval numbers, mockup panels, the boundary quote, and the workflow band are unchanged.
- **Migration consideration:** fixed now across page, CASE_STUDY.md, and this standard in one change; bot, dashboard, README, and eval numbers untouched.

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
| Should renters ever see match reasons (`MatchDecision.reasons`) in cards? | Product | Author |
| Automate eval-number propagation into CASE_STUDY.md / case-study.html from `run_eval --json`? | Implementation | Author |
| Converge the `All listings` / `Browse all listings` label pair on one form | Content | Author |
| Any live source adapter rollout — requires terms review and a documented scope change before any rule here extends to it | Product/legal | Author |

---

*This document defines standards; it changes no code. Sources: `main.py`, `flatfeed/` (bot, matching, AI QA, dashboard), `synthetic/` + `eval/` (golden set and eval), `docs/case-study.html` + `docs/styles.css` (case page), `README.md`, `docs/PROJECT_CONTEXT.md`, `CASE_STUDY.md` (product intent and claims). WCAG 2.2 AA, Telegram bot conventions, GOV.UK/GDS and Microsoft writing guidance, and AI PM portfolio evidence standards serve as references only.*
