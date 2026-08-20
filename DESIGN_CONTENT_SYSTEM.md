# FlatFeed — Design & Content System

**Status:** Normative. Single source of truth for UI, layout, components, copy, terminology, and case-study content.
**Date:** 2026-08-13 (case-study linear narrative compressed from seven sections to five; see §34 history for earlier decisions).
**Basis:** source code inspection (`main.py`, `flatfeed/`, `synthetic/`, `eval/`), an evidence/claim audit, desktop and mobile browser renders of the case-study page, and the project docs (`README.md`, `docs/PROJECT_CONTEXT.md`, `CASE_STUDY.md`). No user research or usability study has been run; product-value statements remain hypotheses.

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
| Bot UI or user copy | §§7, 10, 17–20, 31 | One message = one purpose; sanctioned emoji only; listing-card field order unchanged; destructive actions confirm with consequence-named buttons; no public admin/model-eval controls |
| Parser, matching, WBS, transit, or eval | §§2–3, 10–13, 20, 23, 27, 31 | Deterministic matching owns user-facing decisions; fail closed; WBS semantics live in `flatfeed/wbs_rules.py`; eval numbers update everywhere together |
| AI QA | §§2–3, 11–12, 21, 23, 31 | Admin-only, budgeted, versioned, non-mutating; ground truth and case tags never enter prompts |
| Case-study landing page | §§4–6, 13–15, 22–27, 32–34 | Synthetic/mock qualifiers stay at reading depth; ownership language preserved; hiring-first five-section structure and preview honesty preserved |
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
1. **Telegram bot UI** — `main.py` (aiogram): saved-filter setup and editing, on-demand deterministic matching, conditional background notifications, compatibility handling for retired tour controls, and listing cards (formatted in `flatfeed/matching.py`).
2. **Case-study landing page** — `docs/case-study.html` + `docs/styles.css`: the public AI PM portfolio, captured Telegram evidence, and model-evaluation evidence page.
3. **Public repo docs** — `README.md`, `CASE_STUDY.md`, `docs/PROJECT_CONTEXT.md`: reader-facing evidence; they follow the content rules in §§16–26.

**Not covered:** `LOCAL_CONTEXT.md` (local-only, git-ignored — operational server/bot details MUST NOT leak into any covered surface); test internals; build tooling; future live source adapters (out of current demo scope).

**Source-of-truth order:** this file → `docs/PROJECT_CONTEXT.md` (product semantics detail) → `README.md` (commands and setup). For behavior, code constants win over any document: `flatfeed/wbs_rules.py` (WBS semantics), `flatfeed/matching.py` (card format), `flatfeed/ai_qa.py` (`CURRENT_AI_QA_PROMPT_VERSION`, risk thresholds), `eval/run_eval.py` (metrics). If this file is silent, follow the closest approved pattern in §28.

---

## 2. Product Context

Confirmed by `README.md`, `docs/PROJECT_CONTEXT.md`, `CASE_STUDY.md`:

- **Category:** working Telegram product prototype for a saved Berlin WBS apartment filter. The multi-source ingestion layer is implemented; the public demo enables one synthetic source adapter. Model evaluation is documented separately in the case study and `eval/` artifacts.
- **Primary users:** (a) a user testing the normal saved-filter workflow against a synthetic catalog; (b) case-study readers — recruiters, hiring managers, AI PMs. Configured admins may receive direct QA alerts outside the public flow, but there is no public admin surface. The target portfolio role is **AI Product Manager in a corporate environment**: reliability, explainability, privacy, defensibility, measurable AI quality, and cost control matter more than feature count.
- **Unit of work:** the *listing*. It flows through: source adapter → deterministic parsing → local transit enrichment → deterministic matching against the user's saved filter → Telegram card. Matches are available on demand; the same card is sent automatically when background delivery is enabled.
- **Role of AI:** the accepted hosted-model result is an offline evaluation surface, not part of the public Telegram runtime. Optional runtime AI QA can be enabled only for direct admin alerts. Listing parsing and user-facing matching are fully deterministic and make no LLM calls. AI findings cannot replace or mutate parsing rules, listing data, matching, or user-facing cards automatically.
- **Role of the human:** the admin triages every alerted finding as `Parser error` / `Parser correct` / `Borderline / unsure`; parser improvements are made by a human editing `flatfeed/parser.py` / `flatfeed/wbs_rules.py`.
- **Honesty constraint (product-level):** everything measurable is a *synthetic/demo* result unless a real production measurement exists. Demo metrics MUST be visibly labeled as synthetic evaluation metrics, never as production user-impact numbers.
- **Privacy constraint:** the product flow stores one filter keyed by Telegram user ID until the user resets or deletes it. `/delete` is a published command and confirmed destructive action; it does not delete Telegram chat history or unrelated admin-review records. No real listings are scraped or redistributed; listing photos are licensed prototype assets (`assets/listing_photos/LICENSES.md`).

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
*Implications:* the authored synthetic regression-case count stays in README and runnable eval artifacts as development evidence; the public HTML and Markdown case studies do not present it as a product outcome. After a frozen hosted-model evaluation completes and passes the evidence-review contract, the landing may report the permitted result under the same-depth synthetic label defined in §13 and §23. Detailed field diagnostics remain in the case study or runnable eval artifacts; transit minutes are geometric estimates; demo photos disclose whether they are illustrative or location-aligned, while apartment terms remain synthetic.
*Anti-pattern:* turning 100% on authored cases, zero mock cost, or zero false alerts into a product result.

**P4 — Ground truth is eval-only.**
*Why:* the eval is only meaningful if the parser and AI QA cannot see the answers.
*Implications:* synthetic case tags and hidden truth fields MUST never appear in listing text, listing URLs, parser input, or AI QA prompts. They live in `synthetic/case_catalog.py` / `synthetic/golden_set.py` and are read only by `eval/run_eval.py`.
*Anti-pattern:* "helpfully" enriching a prompt with golden-set metadata.

**P5 — The cost of a misleading prototype result is high; fail quiet, fail closed.**
*Why:* presenting an inactive or mismatched synthetic listing as proof weakens trust in the whole case.
*Implications:* every returned candidate passes the current adapter's activity check before card delivery; the implemented synthetic adapter checks local catalog state, not a live network source. An on-demand request returns up to three matches. Background delivery starts only with `BOT_BACKGROUND_ENABLED=true`, verifies candidates and sends each listing once.
*Anti-pattern:* sending unverified candidates to hit a count.

**P6 — Domain terms are kept, glossed, never translated away.**
*Why:* WBS, Kaltmiete, Bezirk are the domain; removing them removes correctness.
*Implications:* the product is English-facing; WBS (Wohnberechtigungsschein) and Kaltmiete keep short plain-language explainers at the point of use (wizard hints in Telegram; accessible hover, keyboard-focus and tap tooltips at first use on the case page's `Save one filter` step); the visible filter label is `District` while the semantic unit is the Bezirk (12 Berlin Bezirke; Ortsteil/Kiez names normalize to a Bezirk).
*Anti-pattern:* renaming WBS to "housing certificate"; translating Kaltmiete to "cold rent" in UI.

**P7 — Destructive actions confirm; everything else flows.**
*Why:* the working product stores a saved filter and delivery-related user data.
*Implications:* `/delete` asks for explicit confirmation with `Yes, delete saved data` / `No, keep my data`; reset and edit actions do not require destructive confirmation.
*Anti-pattern:* one-tap destructive actions; trapping the user in a setup flow.

**P8 — Product interaction and evaluation evidence stay separate.**
*Why:* users need one short matching flow; portfolio readers need the experiment protocol and results. Combining them made the bot feel like an operations console instead of a product.
*Implications:* the public bot contains no dashboard, admin panel, model metrics, or fault-injection demo. The case study and `eval/` artifacts carry hosted-model evidence. Direct admin alerts remain private operational messages when optional runtime QA is explicitly enabled.
*Anti-pattern:* duplicating scorecards inside Telegram; exposing QA controls or parser jargon in the user flow.

---

## 4. Benchmark Map

References inform rules; they are never templates. Deviation from a reference is not itself a defect.

| Area | Primary reference | Project-specific rule |
|---|---|---|
| Bot conversation UX | Telegram Bot API / official bot design conventions | Persistent reply keyboard for the main story; inline keyboards for choices; commands published in the menu (§7) |
| Saved-filter flow | GOV.UK "one thing per page" | Four focused setup questions, one purpose per message, then canonical listing cards (§7.6) |
| Listing card | Project (`flatfeed/matching.py`) | Fixed field order, bold HTML labels, canonical fallback strings (§10) |
| Case-study page | Repo-local "Swiss International" rules in §5; the sibling Opsqora landing is a comparison example when available, not a required dependency | Hand-written HTML/CSS, token palette in `docs/styles.css`, hiring-first five-section case framework (§6.3, §22); accent split: FlatFeed teal, Opsqora ultramarine |
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

These tokens apply to `docs/case-study.html` / `docs/styles.css` only. The bot has no visual tokens (§7).

The page uses the repo-local **"Swiss International" system** documented in this section: flat 1px-bordered panels, square corners, mono uppercase kickers, five numbered case-study sections, one seven-screen product carousel, and a dark final summary. The sibling Opsqora project is a useful comparison implementation when it is available, but this file is the source of truth for FlatFeed. The deliberate difference between the two sites is the accent: FlatFeed is teal, Opsqora is ultramarine.

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
| `--brand` | `#6247ea` | FlatFeed logo purple | Header Repository button only | Content accents, evidence status, long text |
| `--accent` | `#08766e` | Single accent — FlatFeed teal | Kicker numbers, state dots, button hovers, selection, focus rings | Long text |
| `--accent-deep` | `#055d57` | Accent text/links | Link hovers and demo-state label | — |
| `--accent-wash` | `#e3f2ee` | Accent wash | Role note and quiet accent fills | Text backgrounds needing contrast |

Rules:
- **One-accent system:** teal is the only content accent. Evidence is distinguished by labels and filled/outlined square markers, not by a second result color. The header Repository button is the sole brand-purple exception and matches the logo asset; purple carries no evidence or status meaning.
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
| Hero h1 | display 600 | clamp(36px → 64px), lh 1.02, ls −0.04em | first-person outcome statement |
| Section h2 | display 600 | clamp(28px → 48px), lh 1.06 | takeaway statements |
| Hero lede | ui 400 | clamp(16px → 20px) / 1.6 | `--ink-2` |
| Body prose (`.case-prose p`) | ui 400 | 16px / 1.65, max-width 680px | `--ink-2` |
| Supporting prose | ui 400 | 15px / 1.65, measure `--measure-prose` | `--ink-2`; section ledes, panel intros, callout bodies, slide commentary |
| Card / cell copy | ui 400 | 13.5px / 1.6 | `--ink-2`; every card, grid cell and evidence bullet |
| Sub-block heading, major | display 600 | clamp(21.6px → 32px) / 1.15, ls −0.025em | scorecard, boundary and carousel intro headings |
| Sub-block heading, minor | display 600 | clamp(18.4px → 24px) / 1.2, ls −0.02em | subheadings, findings, comparison-panel titles |
| Cell / step title | display 600 | 18px / 1.3, ls −0.015em | workflow, decision and selection cells |
| Slide title | display 600 | clamp(24px → 36px) / 1.08, ls −0.03em | carousel figcaption; stays below the section h2 |
| CTA heading | display 600 | clamp(28px → 44px) / 1.08, ls −0.03em | dark case-study CTA; measure `--measure-heading` |
| Kicker (`.kicker`) | mono 500 | 11px uppercase, ls 0.07em | `--ink-3`; index number span in `--accent` 600 |
| Block label (`.preview-label`, `.evidence-status`) | mono 600 | 11px uppercase, ls 0.07em | `--ink-3`; `--ink-2` on `--accent-wash` for AA contrast |
| Step / item number | mono 600 | 11px, ls 0.07em | `--accent`; only colour varies, and only where it carries meaning |
| Buttons (`.btn`) | ui 600 | 13px, padding 11×18 | square corners; the header Repository action uses compact 12px text, 11px horizontal padding and the same 26px authored height as the logo mark |
| Labels / dt | mono 500 | 10–11px uppercase, ls 0.07em | `--ink-3` |
| Product-preview fields | ui/mono | 9–12px | compact product evidence only |

Rules:
- Base body is 15px/1.5 `--font-ui`; long-form prose measure stays ≤680px (reference px at the 16px root; authored as 0.9375rem/42.5rem).
- Display sizes use `clamp()` — do not add per-breakpoint font overrides.
- New text styles SHOULD reuse a role above rather than introduce a new size; do not add weights above 700.
- **One letter-spacing for every mono/uppercase label: `0.07em`.** Kickers,
  block labels, `dt`s, table headers and step numbers share it.
- **One line height per prose role.** Supporting prose is 1.65, card/cell copy is
  1.6. Do not fork a per-component line height.
- Display letter-spacing follows size monotonically: −0.04em (h1) → −0.035em
  (section h2) → −0.03em (slide title, CTA) → −0.025em (major) → −0.02em (minor)
  → −0.015em (cell title).

### 5.3 Borders, Radius, Elevation — ADOPT

- **Square corners throughout: border-radius 0.** Status dots and carousel controls are literal squares.
- 1px `--line` hairlines divide and border; 1px `--ink` rules open sections and label groups.
- **The `--ink` rule marks exactly two things: a `.case-section` boundary and a
  label group (`.case-meta`, `.evidence-status`).** Every
  divider *inside* a section is `--line`, so a sub-block can never read as a new
  numbered section. The two `--ink`-bordered panels (`.product-carousel__stage`,
  `.qa-scorecard`) are the only major-evidence containers.
- **One construction for repeated equal-weight cells:** `gap: 1px` over a
  `--line` ground, cells on `--surface`, a 1px `--line` frame. Do not reintroduce
  separated bordered cards with a gap, or per-cell `border-right`/`border-bottom`.
  Within each workflow or decision-grid row, item marker, title and body occupy
  shared subgrid rows so every body begins on the same visual baseline even when
  one title wraps.
- **One accent-emphasis idiom:** `border-left: 2px solid var(--accent)`
  (`.role-note`, `.qa-stop`,
  `.product-journey__panel--with`, `.demo-listing-disclosure`). Do not draw an
  accent bar with an inset shadow or a fully tinted border.
- Elevation: one shadow only — on `.product-carousel__image-frame`. Everything else is flat.
- No gradients anywhere. The sticky header uses `color-mix` transparency + `backdrop-filter: blur(10px)`, not a gradient; the blur radius stays fixed px.

### 5.4 Grid and Width — ADOPT

- One centered column: `.case` width `min(100% - 3rem, 75rem)`.
- Hero is a text-led proposition with no screenshot. The seven-screen carousel follows the hero copy at full content width. On desktop, each slide centers a portrait capture and a bounded 25rem caption column as one composition inside the framed stage, and a compact joined previous/next pair aligns to the commentary's left edge. **The carousel heading sits on the page's left content edge like every other section and sub-block heading** — the framed stage is the object whose contents are centred, not the heading above it. The slide's visible `01 / 07` label carries position, while a visually hidden live region announces changes for screen readers. **At 56rem and below the slide becomes the vertical stack ordered capture → commentary → controls.** The two-column composition is only kept while the commentary column can hold its bounded measure; below 56rem it would be squeezed to roughly 200px, which breaks both the measure and the reserved caption height.
- The caption height reserved to keep the carousel controls from moving is
  **measured, per breakpoint, against the longest approved slide copy in that
  column** — `13.5rem` on desktop, `16.5rem` in the stack, `18.5rem` below 23rem,
  `20rem` below 21.5rem — and is authored as `min-height` so longer copy can
  never be clipped. Verify the reserve by stepping through all seven slides at
  the breakpoint edges and confirming the controls do not move; re-measure
  whenever slide copy or caption type changes. In the stack the caption is
  top-aligned so leftover reserve falls between the comment and the controls,
  never between the screenshot and its own comment.
- **The slide title takes one `clamp()` across all widths.** A second,
  viewport-relative `clamp` inside a media query made the caption height depend
  on both the column width and the viewport, so no fixed reserve could hold —
  which is the concrete reason §5.2 forbids per-breakpoint font overrides.
- Numbered mono kickers (`01`–`05`) are the section motif. Product and Next use four-step grids, Decisions uses a three-up grid, and AI Evaluation uses a two-by-two aggregate grid; each collapses per §14.
- The dark CTA spans the content width and uses `--pad-panel`.

### 5.5 Icons and Imagery — ADOPT

- Icons are inline hand-written SVG strokes, stroke `currentColor`, width 2: 14px inside buttons (arrows, git-branch), 16px in panel headers. No icon library at runtime, no emoji on the page.
- Brand: `assets/flatfeed-logo-mark.png` at 26px in the header wordmark, `alt=""` (decorative next to the visible name).
- Imagery: seven real Telegram captures document the working product flow in order: start, WBS tier, district, Kaltmiete, rooms, saved filter, and the canonical synthetic listing card. The carousel-level copy states that the catalog is synthetic; each slide adds only a short title and one orienting sentence rather than repeating the visible interface. Do not add a screenshot to the hero, dashboard mockups, or decorative illustrations.
- Any photo of a building MUST keep alt text disclosing its demo context. Source, author, license, and modifications stay documented in `assets/listing_photos/LICENSES.md`; attribution for a licensed public-preview image also appears in the adjacent figcaption.

### 5.6 Spacing and Structural Tokens — ADOPT

Rhythm, box padding and measure are authored as `:root` tokens in
`docs/styles.css`. New page styles MUST use these tokens; a new literal value
MUST NOT be introduced without updating this table.

| Token | Value | Role |
|---|---|---|
| `--space-section-top` / `--space-section-bottom` | `2.75rem` / `clamp(2.75rem, 2vw + 1.45rem, 3.5rem)` | `.case-hero` and `.case-section` insets, one value at every width with no breakpoint override. The top inset stays **fixed**: with `scroll-padding-top: 0` it is the only thing clearing the sticky header above an anchored section's kicker (§14), so reducing it clips the kicker. |
| `--space-heading-block` | `clamp(2.75rem, 0.8vw + 2.3rem, 3.125rem)` | section heading → first block, applied once via `.section-heading + *` |
| `--space-block` | `2.5rem` | block → block inside a section |
| `--space-panel` | `2rem` | block → block inside a panel |
| `--space-subrule` | `2rem` | padding after an in-section `--line` divider |
| `--space-caption` | `1rem` | content → footnote/caption |
| `--pad-box` | `1.5rem` | every card and grid cell |
| `--pad-panel` | `3rem` | full-width panel (dark CTA); always `2 × --pad-box` |
| `--label-col` | `10rem` | label column in every label/content row |
| `--measure-prose` | `48rem` | prose measure |
| `--measure-heading` | `42rem` | sub-block and CTA heading measure |

Rules:
- **The rhythm is one descending ladder** — section boundary
  (`top` + `bottom`) > `--space-heading-block` > `--space-block` >
  `--space-panel` / `--space-subrule` > `--space-caption`. A step MUST NOT
  overtake the one above it at any width; check the resolved pixel values, not
  the authored units, when changing any of them.
- The largest steps separate fluid display type (`h2` is
  `clamp(1.75rem, 4vw, 3rem)`), so they are authored as `clamp()` and scale with
  the viewport like that type. The steps below them separate fixed body-size
  content and stay fixed. This is why the section insets need no breakpoint
  override. `--space-section-top` is the one exception — it is pinned by the
  sticky-header clearance above, not by the type it separates.
- Micro gaps use one family: `0.75rem` (label/title → text), `1rem`
  (label → figure, content → caption), `1.5rem` (kicker → heading, everywhere
  including the dark CTA).
- Standard controls use `2.625rem`; short-viewport carousel arrows use
  `2.25rem`. The header Repository action is a deliberate `1.625rem` brand
  lockup exception matching the adjacent logo-mark height.
- Do not add a component-specific spacing value when a token expresses the same
  relationship.

---

## 6. Layout Systems per Surface

### 6.1 Telegram bot shell — ADOPT
**Purpose:** let a user configure one filter and inspect deterministic results without demo-specific framing.
**Anatomy:** a persistent two-action reply keyboard exposes `⚙ Filter` and `🔎 Show matches`. `/start` introduces the product, discloses the synthetic/no-live boundary once, and shows the saved-filter status. The published command menu contains `/start`, `/filter`, `/matches`, `/help`, and `/delete`; contextual inline buttons handle setup, editing, reset, and deletion.
**Rules:** the public bot MUST expose the saved-filter and on-demand matching path and MAY send automatic matches when background delivery is enabled. It MUST NOT expose unfiltered catalog browsing, a notification toggle, admin controls, or model metrics. Retired tour callbacks redirect to the current filter status without writing tour state.

### 6.2 Saved filter card — ADOPT
The status card shows whether a filter exists and, when configured, lists WBS, District, Max Kaltmiete, and Rooms in that order. It offers `Show matches`, `Edit filter`, `Reset filter`, and `Delete my data`. The setup wizard asks one field at a time and persists only after all four answers are complete.

### 6.3 Case-study page shell — ADOPT
Skip link → compact sticky top bar (above 56rem, FlatFeed brand with `Product case study` subtitle, the centered five-item nav Problem · Product · Decisions · AI Evaluation · Next, and one proportionally compact Repository action share one row) → text-led Problem hero (plain-language proposition and first-use WBS tooltip) → **hiring-first five-section case study**: 01 Problem · 02 Product · 03 Decisions · 04 AI Evaluation · 05 Next → dark concluding summary → sibling case cross-link. The sibling cross-link is the final page block; there is no separate footer.

The page MUST answer in order: what user problem the product simplifies, what was built, what the candidate owned and decided, how the bounded AI check was evaluated, and what should be tested next. Product combines the solution, four-stage workflow and seven-screen Telegram proof. Decisions combines the three consequential trade-offs. AI Evaluation opens with a concise prose boundary between rule-based matching and the separate offline parser-quality check, then keeps the aggregate results and one unusable result visible; field-level results, configuration and cost assumptions sit in closed-by-default details so they do not interrupt the hiring scan. Dashboard mockups, mock-cost, legal analysis, scripted-demo history and historical iteration tables do not belong in the main public narrative. At ≤56rem the header is not sticky and the nav moves to a second row as a two-column grid; the brand and Repository action remain in the first row without creating an implicit third column.

### 6.4 No separate dashboard — ADOPT
The prototype has no dashboard or public operations console. The case study demonstrates the Telegram product only through captured screens and MUST NOT link to or invite readers to open the bot. Final hosted-model evidence lives in the case study and frozen `eval/` artifacts. A new stats command, admin page, or dashboard would be a new phase and requires an explicit product decision rather than a replacement implementation.

---

## 7. Telegram UI System

The bot's "design system" is message structure, keyboards, and formatting discipline — there is no CSS.

### 7.1 Message formatting — ADOPT
- Parse mode is HTML. Allowed tags: `<b>` for labels and step prefixes, `<i>` for hints/explainers, `<a>` for the single `Open listing` link. No other markup, no code blocks in user-facing messages.
- One message = one purpose. A listing card is the complete user-facing result; do not send a separate explanation of why it matched. An on-demand request may return up to three verified matches.
- Emoji do not appear in prose. The two persistent menu actions retain their established magnifying-glass and gear prefixes; destructive deletion retains the trash prefix in its inline action.

### 7.2 Keyboards — ADOPT
- Persistent reply keyboard: `⚙ Filter` and `🔎 Show matches`.
- No filter: `Set up filter`.
- Saved filter: `Show matches`, `Edit filter`, `Reset filter`, `Delete my data`.
- Field editing: WBS, District, Max Kaltmiete, Rooms, plus Back/Cancel where applicable.
- `/delete` keeps consequence-named confirmation labels.

### 7.3 Public filter wizard — ADOPT
The four-step WBS → District → Max Kaltmiete → Rooms wizard is the current public product path. It writes one completed filter, supports individual field edits, and can be cancelled without changing the saved filter. Old `tour:*` callbacks MUST redirect to the current filter status without writing user state.

### 7.4 No public admin panel — ADOPT
The reply keyboard and command menu expose no admin, QA, refresh, backfill, or metrics controls. Optional runtime QA may send a direct private alert to configured `ADMIN_TELEGRAM_USER_IDS`; that alert keeps the three triage labels `Parser error` / `Parser correct` / `Borderline / unsure`. These labels are operational vocabulary, never a public-demo interaction.

### 7.5 Failure and timeout messages — ADOPT principle
Failures never expose internals. Empty results explicitly belong to the limited synthetic catalog and suggest loosening the saved filter; transport or processing failures invite a retry. Apologies, exclamation marks, and blame are out of register (§17).

### 7.6 Saved-filter product flow — ADOPT
`/start` introduces the normal product flow and immediately shows the current filter status. A user can create or edit a four-field filter, then request results with `Show matches` or `/matches`. The request runs `is_listing_match` over the synthetic catalog and applies the adapter's local activity check. For each result, the bot sends only the exact canonical listing card; a request returns up to three cards. When `BOT_BACKGROUND_ENABLED=true`, the runtime starts the collection loop and sends each newly collected matching card once.

The first-use message states that the prototype uses a synthetic catalog. Empty states repeat the limited-catalog boundary where it explains the outcome. `/help` explains that automatic notification delivery is conditional on background mode. The public flow contains no evidence scorecard, model call, mock QA, fault injection, triage, admin view, or notification-settings control.

---

## 8. Evidence Surface Boundary

- Captured Telegram screens document the interaction: saved filter → deterministic match → canonical listing card.
- The case-study narrative explains the implemented notification loop: collect → match → verify → send once.
- The case study documents the product decisions and reports the accepted synthetic hosted-model experiment. Product behavior is shown through the seven captured Telegram screens; no live-prototype CTA appears.
- Frozen `eval/` artifacts hold detailed protocol, field diagnostics, cost, and reproducibility evidence.
- Do not reintroduce a dashboard, Telegram stats command, mock QA interaction, or hand-typed runtime metrics. A new operational surface is a new product phase.

---

## 9. Action Hierarchy

| Level | Treatment | Placement | Wording |
|---|---|---|---|
| Product entry | Persistent reply keyboard + filter status card | `Filter`, `Show matches` | Verb + object |
| Filter management | Inline buttons under the filter status | `Set up filter`, `Edit filter`, `Reset filter` | One clear action |
| Destructive | Published `/delete` + inline status action | `Yes, delete saved data` | Consequence named in the confirm labels |
| Case-study CTA | `.btn--primary` in the top bar | Header only | `View repository` |

Rules:
- One primary action per surface: the bot uses `Show matches` after a filter exists; the case page uses `View repository` in the header. The final summary is editorial, with no button.
- Catalog browsing, admin controls, model metrics, and QA simulation are intentionally absent from the public bot.
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
- Every product result uses this exact formatter output. Do not send a separate match-reason message, prepend explanatory copy, or attach a management keyboard to the card.
- The photo (when present) is a deterministic prototype asset. The showcase card is the only address-aligned exception: its photo, displayed address, district, and coordinates refer to the same real location, while availability and apartment terms remain explicitly synthetic. Other catalog photos MUST NOT imply that they depict their listing address.

---

## 11. Status and Semantic Vocabulary

One concept = one canonical vocabulary. Do not merge concepts because they sound similar.

| Concept | Canonical values | Where | Notes |
|---|---|---|---|
| **Listing activity** | active / inactive (removed listings stay in history, excluded from delivery) | DB + delivery logic | A failed activity check marks inactive; partial collection never mass-marks removals |
| **Admin QA triage** | `Parser error` / `Parser correct` / `Borderline / unsure` | Direct private QA alerts | The decision of record; exactly three values |
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
2. **Admin-only.** Optional runtime AI QA findings and triage exist only in direct private alerts to configured admins. Users never see AI output; the public bot has no QA controls.
3. **Budgeted and optional.** `AI_QA_PROVIDER=mock` is the default (local, deterministic, free). `openai` is opt-in, requires an API key and explicit budget settings; daily count and dollar budgets stop excessive usage. Copy MUST NOT present AI QA as required for matching — it isn't.
4. **Versioned and deduplicated.** Each listing gets at most one review per prompt version; the version constant lives in `flatfeed/ai_qa.py` and is displayed, not duplicated, elsewhere.
5. **Risk is a thresholded number.** `risk_score` 0–100; alert at ≥ the configured threshold (default 75); an alerting review must contain at least one concrete issue. Never render risk without its threshold context in admin surfaces.
6. **Source data vs AI output separated.** Raw listing text and the parser snapshot remain distinct from AI findings in direct alert copy and eval artifacts. Never blend them into one paragraph.
7. **Prompt hygiene.** Ground-truth fields and synthetic case tags MUST NOT enter prompts (P4). The prompt is also product policy — e.g. it encodes that "no WBS mention → No WBS required" is *correct*; prompt changes are product changes and bump the version.
8. Hard prohibitions: anthropomorphism ("the AI thinks/wants"); presenting the mock provider as a live model; "AI-powered" as a feature adjective; implying AI does the matching; any capability claim not traceable to `flatfeed/` behavior.

---

## 13. Data Visualization (case page)

- The case page has no charts. Evidence remains a labeled Demonstrated / Not demonstrated split plus the accepted evaluation scorecard and field table.
- Before frozen hosted-model validation, the public HTML and Markdown case studies show no quantitative AI result. The authored regression-case count remains a technical README/eval check, verified by `scripts/check_eval_numbers.py`.
- After the one-time final locked holdout completes and passes a separate
  evidence review, the AI Evaluation section MAY report its result whether the
  configuration passed or failed. It MUST show the four aggregate product
  metrics and all seven field results with a visible
  synthetic-data qualifier in the scorecard method prose.
- The landing reports only the final independent 600-listing result; development
  and earlier validation scores stay out of public surfaces. The four aggregate
  metrics explain overall behavior. The field table separately distinguishes
  the four matching-critical filters from the three diagnostic listing fields
  so an aggregate cannot hide a weak matching-critical field.
- The final-evaluation narrative MAY explain the qualitative configuration path:
  lower-cost model and reasoning settings first, escalation only after a
  predefined gate is missed, and the final shift from model judgment to exact
  quote extraction plus deterministic comparison. It MUST NOT expose scores
  from development screens, calibration, or earlier validation runs.
- One clearly labeled inference-cost scenario MAY follow the final result. It
  MUST name its volume proxy, formula, pricing date, assumptions, and exclusions
  and MUST NOT read as measured production cost. Historical engineering
  metrics, confidence intervals, and latency remain in eval artifacts.

---

## 14. Responsive System (case-study page)

Breakpoints are authored in rem/em-like units: **68rem** (tighter desktop grids), **56rem** (non-sticky two-row header and linear hero), and **40rem** (single-column metadata/workflow and full-width CTA buttons).

- Desktop is the primary reading surface; mobile is a supported viewing mode, not a separately designed product.
- Section kickers start after a compact top inset: `--space-section-top` (`2.75rem`), one value at every width. The Problem section hero uses the same inset so the first viewport prioritizes content over shell spacing. Desktop anchor navigation scrolls each section divider beneath the single-row sticky header; the section's own top inset places its kicker below the shell.
- Nothing needed for the 10-second scan (§22) may disappear at any width: kicker, H1, boundary-aware lede, CTA and metadata. The section nav remains visible and becomes a two-column grid on narrow screens.
- Telegram handles bot responsiveness — do not add custom viewport logic there.

---

## 15. Accessibility Baseline (case-study page) — WCAG 2.2 AA target

- Landmarks and labels exist and MUST be preserved: the skip link, `aria-label` on nav ("Case study sections"), evidence panels, the workflow band, and the scope-figures list; decorative SVGs carry `aria-hidden` and the brand image an empty alt; the demo photo has a descriptive alt disclosing it is a demo image.
- Contrast: current `--ink-2`, `--ink-3`, and `--accent` are chosen for readable text on white; verify any retint instrumentally and keep normal text ≥4.5:1.
- Keyboard: a global `:focus-visible` outline (2px `--accent`) covers all interactive elements — any new interactive element MUST keep a visible focus state.
- `scroll-behavior: smooth` exists only inside `prefers-reduced-motion: no-preference`; the reduced-motion block keeps behavior neutral. New animation MUST be gated the same way.
- Telegram accessibility rides on the platform; the project's obligation there is text clarity (§16) and never encoding meaning in emoji alone.

---

## 16. Content Principles

1. **Frontload the point.** The first clause carries the message ("Finding WBS-eligible apartments in Berlin is fragmented and time-sensitive: …").
2. **Concrete over abstract.** "shows one verified synthetic card", "three consecutive failures trigger an admin alert" — numbers with units and denominators, mechanisms over adjectives.
3. **State facts, not self-praise.** Surfaces never grade themselves ("robust", "seamless" do not appear — protect this). Quality is demonstrated by the eval, the boundary, and the confirmations.
4. **Precision is credibility.** WBS semantics are exact (`WBS 141-220` excludes 140); "estimates" stay estimates ("walking-time estimates", "not calculated"); one imprecise claim taxes every accurate one.
5. **Explain domain terms at first use, keep the term.** "WBS (Wohnberechtigungsschein) is a Berlin eligibility certificate…", "Kaltmiete is the base rent, excluding operating and heating costs." Don't translate the term away; gloss it (P6).
6. **Every claim carries its evidence status.** "These are synthetic evaluation metrics, not production user-impact numbers" — the qualifier is part of the sentence, not a footnote (§23).
7. **Write for the working reader.** The user wants the next apartment; the recruiter wants the judgment. Private operational alerts serve configured admins without becoming a public product surface.
8. **Explain the action before the system term.** On the public case study, say
   what happens in plain verbs (`puts every listing into the same format`, `AI
   returns an exact quote`, `code compares the values`) before using an internal
   term such as schema, parser snapshot, deterministic comparison or runtime
   QA. Keep a technical term only when it carries evidence, product-boundary or
   reproducibility meaning. Plain language must remain professional and exact;
   it is not permission to remove synthetic qualifiers, ownership or limits.

---

## 17. Voice and Tone

**Bot voice (ADOPT):** a competent first-person guide — plain, brief, helpful, never cute. It may accurately describe the user's saved filter, but MUST distinguish synthetic-catalog results from live-market monitoring. No exclamation marks, no small talk, no personality bits.

**Case study / docs voice (ADOPT):** professional, evidence-led, first person where ownership is claimed ("I defined the product scope…"), never salesy. Judgment is shown by trade-offs ("I deliberately limited live source coverage to make the demo privacy-safe, defensible, and measurable"), not by adjectives.

Voice is stable; tone flexes by context:

| Context | Tone | Example / rule |
|---|---|---|
| Normal bot flow | Plain, task-forward | "Which WBS should match?" |
| Success | Plain explanation, no celebration | "Found 1 active listing that matches your filter." |
| No results | Honest + what the filter was | State that nothing active matches; never pad with near-misses |
| Destructive confirm | Consequence named, neutral | "Yes, delete saved data" / "No, keep my data" |
| Session loss | Own the cause, restart cleanly | "Your setup session expired (the bot restarted), so I lost the earlier answers. Let's start again." |
| User-facing failure | Outcome + retry, no internals | "One or more sources may have returned an error or timed out." |
| Private admin alert | Finding + concrete decision request | Keep source evidence separate from the AI finding |
| Case-study limitation | Matter-of-fact, unhedged | "These are synthetic evaluation metrics, not production user-impact numbers." |

---

## 18. Product Copy System

| Category | Pattern | Length | Examples (current, approved) | Anti-pattern |
|---|---|---|---|---|
| Product entry buttons | Verb + object | 2 words | `Set up filter`, `Show matches` | "Start tour", "Try it" |
| Inline action buttons | Verb + object, plain text | 2–5 words | `Edit filter`, `Reset filter`, `Delete my data` | "OK", "Click here" |
| Confirmation buttons | Consequence in the label | ≤5 words | `Yes, delete saved data` / `No, keep my data` | Bare Yes/No for destructive actions |
| Wizard questions | Direct question, one thing | 1 sentence | "How many rooms do you need?" | Multi-question messages |
| Wizard hints | `<i>` gloss at the point of use | 1–2 sentences | the WBS and Kaltmiete explainers | Glossary dumps in /help |
| Card labels | `<b>Label:</b>` fixed vocabulary | 1 word | `District:`, `Kalt:`, `Warm:` | Renaming card fields |
| Unknowns | Canonical fallback strings | — | `not specified`, `not calculated` | "n/a", "—", "unknown" |
| Bot statements | One purpose | 1–2 sentences | "Tap Show matches to check the synthetic catalog now." | Paragraph messages; implying live monitoring |
| Failure copy | Outcome + retry | 1–2 clauses | "Try loosening the filter." | Apologies, exclamations, stack traces |
| Commands | Single lowercase words | 1 word | `/start /filter /matches /help /delete` | Advertising retired tour commands |

Capitalization: sentence case everywhere; card labels and proper/domain nouns (WBS, Kaltmiete, S-Bahn, U-Bahn, Bezirk names) keep their canonical forms. Terminal periods on sentences, none on button labels.

---

## 19. Action Language

| Action | Canonical wording | Prohibited alternatives | Scope |
|---|---|---|---|
| Create or change criteria | **Filter** / **Set up filter** / **Edit filter** | "Preferences", "Subscription" | Main menu, status card, `/filter` |
| Request results | **Show matches** | "Recommendations", "Find flats" | Main menu, status card, `/matches` |
| Reset criteria | **Reset filter** | "Replay", "Start over" | Status card |
| Remove saved product data | `/delete` (+ consequence-named confirm pair) | "Unsubscribe", "Forget me" | Published command and status card |
| Admin: triage a finding | **Parser error** / **Parser correct** / **Borderline / unsure** | Any fourth label; abbreviations | QA reports |
| Open a listing | **Open listing** (the card's only link) | "More", "Details" | Listing card |
| Case-study CTA | **View repository** | "Open prototype", "Try the demo", "Review the walkthrough", "GitHub" (as a button label) | Header only |

Actions that have no product function (subscribe, bookmark, share, export, language switch, pause notifications) MUST NOT appear in UI or copy as if they did. If a phase adds one, define its canonical verb here first.

---

## 20. Terminology System

| Concept | Canonical term | Definition | User-facing form | Case study / docs form | Avoid |
|---|---|---|---|---|---|
| Unit of work | listing | One apartment offer normalized into the catalog | listing | listing | "ad", "flat" (as the entity), "object" |
| Eligibility certificate | WBS | Wohnberechtigungsschein; tiers 100/140/160/180/220 | WBS (+ wizard gloss) | WBS (glossed at first use) | Translating it; removing tiers |
| Rent basis | Kaltmiete | Base rent excluding operating and heating costs; the only matching basis | Kaltmiete / card `Kalt:` | Kaltmiete (glossed) | "cold rent", matching on Warmmiete |
| Total rent | Warmmiete | Rent incl. utilities; display only | card `Warm:` | Warmmiete | Using it for matching |
| Location unit | Bezirk | One of the 12 Berlin Bezirke | label `District` | Bezirk / district | Treating Ortsteil/Kiez as the unit |
| Person using the product | user | The person configuring a filter or reviewing matches | user | user | Alternative audience nouns outside the dedicated Audience metadata |
| Matching criteria | saved filter | Four stored fields (WBS type, district, max Kaltmiete, rooms) keyed by Telegram user ID | your filter | saved filter | "subscription", "example filter" for the current product |
| Getting results | match / matching | Deterministic rule comparison of listings vs the saved filter | matching listing | deterministic matching | "recommendations", "AI matching" |
| Collection layer | source adapter | Per-source ingestion module with activity checks and health | Source (card field) | source-adapter architecture | "scraper" (the demo doesn't scrape) |
| Demo source | FlatFeed Synthetic | The synthetic catalog adapter | Source: FlatFeed Synthetic | synthetic source adapter | Implying live sources exist |
| Parsing | deterministic parsing | Rule-based field extraction at ingestion; no LLM | — (internal) | deterministic parsing | "AI parsing" |
| AI surface | AI QA | Offline hosted-model evaluation plus optional private runtime alerts | — | AI QA | "AI assistant", "autopilot" |
| AI QA input | parser snapshot | The parsed-field record a review evaluates | — | parser snapshot | "the data" |
| AI QA output | finding / review | Versioned review with risk score and issues | flagged report | finding, review | "verdict", "decision" |
| Risk number | risk score | 0–100 likelihood the parser result is materially wrong | — | risk score + threshold | "confidence" (inverted meaning) |
| Human QA label | triage label | Parser error / Parser correct / Borderline / unsure | the three buttons | admin feedback | "rating" |
| Eval dataset | golden set | Synthetic cases with hidden ground truth | — | golden set / synthetic golden-set eval | "test data" (vague) |
| Hidden answers | ground truth | Eval-only truth fields and case tags | — | hidden ground truth | Putting it anywhere near prompts |
| Quality numbers | field accuracy / exact listing accuracy | Parser vs golden set | — | with "synthetic" scope attached | Unscoped "accuracy" |
| Transit estimate | walking-time estimate | Geometric estimate from bundled station CSV | `S-Bahn:`/`U-Bahn:` minutes, `not calculated` | local walking-time estimates | Implying routing/geocoding services |
| User notifications | automatic notification | Background delivery verifies a newly collected match, sends its canonical card once and records delivery | new matching listing | implemented; controlled by `BOT_BACKGROUND_ENABLED` | "instant" or implying continuous push from provider systems |
| Admin alerts | admin alert | Source-health or high-risk QA alert to admins | — | admin alert | Mixing with user notifications |
| Provenance | synthetic / demo / mock / estimated | Not from live systems or production | demo catalog | synthetic, demo-only, mock provider | "sample data" (vague), unlabeled values |

Audience adaptation is allowed (gloss depth, sentence length) — mechanical word-for-word identity between surfaces is not required. Meaning identity is (§27).

The dedicated `Audience` metadata value on the landing is the sole exception to
the canonical person noun. Everywhere else — landing copy, bot UI, Markdown,
technical docs, research language, outcomes and tests — use `user` / `users`.

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

**10-second scan** (brand label + Problem kicker + H1 + lede) must answer: What is FlatFeed, where is it used and which repeated task does it replace?
Mechanics: above 56rem the header brand, five centered navigation labels and Repository action share one compact row; at narrower widths the nav remains visible in a second-row two-column grid. Every numbered section has a matching navigation item using exactly the same words, capitalization and punctuation. The kicker establishes only `01 Problem`; do not repeat the case-study type beside it. The H1 names the repeated cross-website search problem without introducing FlatFeed's solution. The lede explicitly states that several real-estate portals offer alerts, that each alert is limited to its own platform, and that, meanwhile, housing providers are a primary WBS-listing source whose own websites may publish before portals; it also states that some providers offer only email alerts while others offer none. It then introduces the intended Telegram flow without claiming live aggregation. Product status appears at the beginning of Product; the AI method and its synthetic-evaluation label appear in AI Evaluation. Direct ownership and the self-directed project context appear in Decisions. No name, role label or contact data is required.

**45-second scan** (+ Product, Decisions, aggregate AI Evaluation and Next) must answer: how FlatFeed changes the user workflow, which trade-offs the candidate made, what was implemented, why AI does not match listings, what was measured and what remains unvalidated.
Mechanics: the hiring-first sequence is Problem → Product → Decisions → AI Evaluation → Next. Product starts with the implemented save → normalize → match → return flow, then shows the seven-screen carousel. Decisions presents three consequential choices. AI Evaluation introduces the boundary in prose: the Telegram flow remains rule-based, while a separate offline check asks AI for source evidence and lets code compare parsed values. It keeps the four aggregate metrics, synthetic qualifier, unusable result and runtime boundary visible; field results and cost assumptions are secondary details.

**Deep read** must answer: problem without invented metrics, product mechanism, ownership, decisions, implemented product, AI rationale, measured evidence, limitations and the next validation question. AI Evaluation contains one plain-language final-evaluation narrative plus closed details for field-level results, final configuration and a bounded cost scenario. Only the final 600-listing run may appear as quantitative evidence; the synthetic qualifier, one unusable check and no-runtime-integration boundary stay visible at the same depth as the strongest aggregate metrics.

Element rules:
- **Problem hero:** numbered `01 Problem` kicker → plain proposition H1 with the first-use WBS tooltip → one-paragraph problem and product lede. The brand already labels the page `Product case study`; direct ownership and self-directed context belong in Decisions.
- **Product carousel:** seven real Telegram captures document setup through result in the author-supplied order. The hero remains text-only. The carousel does not auto-advance; previous/next buttons, arrow keys, and touch swipe expose the sequence. On desktop the capture and its bounded caption form one centered two-column block, with the heading aligned over the caption and a compact joined pair of arrow buttons immediately below the commentary, aligned to its left edge. Every capture sits in the same fixed-ratio frame with `object-fit: contain`, and every caption uses the same reserved height, sized for the longest approved slide copy. Together these keep the buttons fixed while screens change without cropping screenshots or allowing copy to overlap the controls. The buttons share one internal border so they read as a single navigator rather than two floating actions. Do not show a second visual `Screen N of 7` label because the caption already shows `NN / 07`; retain a visually hidden live region for assistive technology. On mobile, commentary remains adjacent in reading order, retains the shared reserved height, and controls follow it with the same left alignment. Carousel-level copy describes the product sequence without repeating demo setup. Each slide uses a step number, short title, and one orienting sentence. Photo credit remains adjacent to the relevant image in a smaller 11px utility style with 1.5 line height and readable `--ink-3` contrast. No dashboard, mock metrics, fabricated runtime data or browser imitation.
- **Product:** combine the solution and implementation proof. Begin with a compact product-status line, then the four-stage implemented flow—save, put listings into one format, match with rules, return matches in Telegram—and the seven-screen carousel. The `Save one filter` step gives the first accessible Kaltmiete tooltip. Qualify the architecture with the one present synthetic source adapter. Explain the user-visible action before technical architecture. Do not repeat the workflow in comparison or capability cards.
- **Decisions:** use a full-width heading, then a full-width `My role` note before the three decision cards. The note names direct ownership, coding collaborators and the absence of a live rollout without competing with the heading. Show three choices in reader language: use AI to audit the parser rather than decide matches, use synthetic data to test product mechanics while source access and reuse terms remain unvalidated, and fail closed when critical data is missing. Scripted-demo history does not belong in the linear case.
- **AI Evaluation:** begin after the `04 AI Evaluation` kicker with one heading and one prose paragraph that describe the check as an implemented product capability: it runs on every new listing, AI returns source quotes, code compares them with parsed values, differences go to a configured admin, and matching stays rule-based. State the reporting boundary as a design decision, never as an apology. Follow that paragraph with a stacked `role-note` in plain reader language: AI finds the relevant source values, code compares them with the parser output, and an admin resolves differences as wrong, correct or unclear. The scope label carries the ingestion-level, admin-only and switched-off status; detailed guardrails, review versioning, cost caps and risk thresholds remain in the durable project documentation. Caveats belong in the Next prototype limits, not in this introduction. Follow with one compact three-row worked example under a field-neutral heading: the first row identifies the synthetic German `Listing text` and contains all four matching values, followed by aligned `Parser output` and `AI evidence` rows that show values only. Treat every source label as a bordered table cell and keep all three rows equal in height at each viewport. Highlight the differing value, explain the resulting risk to a user and state the admin-review step at the same visible depth: AI points out the conflict, while only a configured admin checks the original listing and decides whether the parser is wrong before any data changes. Users never see or act on AI flags. The example may use a WBS range without implying that WBS is the only field that can be wrong. Then move to the question of planted conflicts between listing text and structured data. Describe the frozen set as 300 agreeing pairs and 300 with one deliberately altered structured value; retain its synthetic qualifier, no-retry/no-tuning setup, 599/600 limitation and no-runtime-integration boundary at visible depth. Present that boundary as a full-width stacked `role-note`, matching `My role` and the Next data-quality gate, then place field-level results, final configuration, unusable-case detail and cost scenario in closed details. These values are controlled evaluation evidence, never user or production outcomes. No score from an earlier model iteration appears.
- **Next:** show the four next product metrics, the admin-review requirement and controlled prototype limits. The prototype limits carry every AI caveat together: the check ships off with a mock provider, the reported results come from an offline evaluation harness rather than the runtime path, and live-source accuracy plus the review loop at production volume are unmeasured. The introductory copy and data-quality gate explain the planned feedback loop at a general level: only configured admins review AI flags, users never see them, reviewed parser errors become test cases and parser fixes, false AI alerts improve the next QA version, and no review changes listings or matching automatically. Configuration detail belongs in a closed block. Do not imply a committed user study, live-source pilot or production rollout.
- **Conclusion:** explicitly synthesize the hiring signal in a dark concluding summary: a working apartment-search workflow, rules making user-facing matches, a built AI data-quality check that flags parser risks for admin review without touching a match, and the validation required before testing with real listings. Do not add a kicker above its headline. The final summary has no button; product behavior is demonstrated through screenshots.

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
| PLANNED | Future phase | "provider-specific adapter", "where terms allow it" |
| LIMITATION | Known gap | Stated in Results/Learned or PROJECT_CONTEXT, unhedged |

Hard constraints (non-negotiable):
- Synthetic eval numbers MUST NOT read as production evidence at any reading depth.
- Eval numbers MUST come from an actual run and update **all** their occurrences together (§27); never round 99.x to 100, never keep stale numbers because they look better.
- A hosted-model result MUST come only from the final one-time locked holdout and
  MUST show a synthetic-data qualifier, absolute counts and the real-world
  manual-audit limitation at the same reading depth. Calibration,
  development-screen, and earlier frozen-validation scores MUST NOT appear on
  the landing or public Markdown case study.
- Public cost calculations are ESTIMATE, not MEASURED: show the final run's
  recorded per-check cost separately from a conservative no-cache scenario,
  cite the workload proxy, and disclose that inference cost excludes source
  access, hosting, monitoring, duplicates, pricing changes, real-listing length,
  and human review.
- A real product limitation MUST say that human review is still required for every AI alert and for an independent random sample of listings receiving no alert. This is PLANNED, not implemented; the prototype uses no housing-provider data without permission.
- Multi-source orchestration, per-source activity checks and source health are implemented architecture. The public case MUST state that the demo exercises them through FlatFeed Synthetic only; a live provider-specific adapter and its source-access validation remain out of scope.
- $0 QA cost MUST stay attributed to the mock provider.
- Hiring signal MUST NOT be improved by inventing evidence. Ever.

---

## 24. Candidate Ownership Language

- The canonical ownership statement says: "I defined the WBS user problem and product scope; chose which fields determine a match and how missing data is handled; set the AI boundary; and designed the evaluation plan and acceptance criteria. I implemented the Telegram prototype with Claude Code and Codex as coding collaborators." Keep the HTML and Markdown versions in sync in *meaning*.
- Verb discipline: **defined/designed/scoped/chose** = candidate judgment; **implemented/built/wrote** = delivery; **the bot/the parser/the eval does X** = system behavior; **demo/mock/synthetic** = illustrative outcome. Do not swap categories.
- The author approved the agent-collaboration disclosure; it lives in the Decisions contribution note and `CASE_STUDY.md` §2 and MUST NOT be removed or softened without the author.
- First person ("I", "my") is correct on the case study and in CASE_STUDY.md. In the bot, "I" is the *bot* speaking about bot actions (§17) — never the candidate. README uses no first person for ownership except CASE_STUDY-quoted material.

---

## 25. Professional Language Rules

**Prefer:** concrete user-visible mechanisms tied to artifacts — "four-field saved filter", "source adapter", "estimated walks to the nearest S- and U-Bahn stations", and "Telegram listing summary". State whether each mechanism is implemented, disabled, synthetic, or unvalidated. Keep authored regression-case counts, activity checks, fail-closed behavior, and disabled notification deduplication in technical documentation unless they explain a specific reader-facing risk.

**Buzzword register.** Current status: *leverage, seamless, robust, cutting-edge, intelligent, actionable insights, AI-powered, end-to-end (as a boast), scalable, production-ready, enterprise-grade* appear on no surface as self-praise. Protect this. Rules rather than blanket bans:
- *production-ready / enterprise-grade*: MUST NOT appear — the demo explicitly is neither.
- *end-to-end*: acceptable only in the literal sense already used ("an end-to-end AI PM case: problem framing, trade-off definition, prototype delivery, evaluation, and honest documentation") — a scoped list, not a boast.
- *scalable*: only about a specific mechanism with its limit stated (e.g. "SQLite is appropriate for this local portfolio prototype" is the model — a fitness claim, not a scale claim).
- Self-praise adjectives about our own output ("reliable", "trusted", "honest") SHOULD NOT be used as feature labels. Name the user job or the concrete mechanism instead.

---

## 26. Scannability Rules

- Headings state the takeaway or the question; a heading-only read of the case page must be coherent.
- Case-study paragraphs ≤5 sentences, one idea each; bot messages are 1–2 sentences.
- Lists for parallel mechanisms (README "What It Shows", workflow, decisions, evidence); tables only for enumerable facts.
- The case page uses no public metric cards before hosted-model validation.
  After the §13 final-result review, one evaluation block may contain the four
  aggregate metrics, the seven-row field table, and one inference-cost
  scenario. Aggregate metrics remain visible; the field table, configuration
  and cost scenario use closed-by-default details. These elements remain
  subordinate to the product story and cannot be split into repeated
  promotional number strips.
- Technical explanations follow "term (plain gloss)" on first use — the WBS and Kaltmiete hints are the models.
- Review gates: the 10s/45s scan tests (§22) for any case-page change; for the bot, "can a new user save a filter, receive or request matching cards, and manage saved data?".

---

## 27. Cross-Surface Consistency

**MUST remain consistent (meaning-identical) across bot, case page, and docs:**
- The meaning of listing, filter, WBS tiers, Kaltmiete-only matching, district/Bezirk, golden set, risk score, triage labels (§20).
- The AI boundary sentence pattern: parsing/matching deterministic; AI QA admin-only, budgeted, never mutating (§2, §12).
- **Public eval numbers.** The authored synthetic regression-case count remains
  in README and runnable eval artifacts, not in `docs/case-study.html` or
  `CASE_STUDY.md`. After the §13 final-result review, those two case-study
  surfaces contain only the final 600-listing holdout numbers: four aggregate
  metrics, seven field results, the recorded run cost, and the explicitly
  estimated 15,000-check cost scenario. Historical model-iteration numbers,
  confidence intervals, and latency stay in runnable engineering artifacts.
- **Eval sync check.** `scripts/check_eval_numbers.py` re-runs
  `eval.run_eval --json`, verifies the authored-case count in `README.md`, and
  checks both public case-study surfaces against the final locked-holdout
  scorecard, field report, and run cost.
- The five-part Problem / Product / Decisions / AI Evaluation / Next structure stays meaning-aligned between HTML and Markdown.
- WBS semantics: `flatfeed/wbs_rules.py` is the single source; documents give examples, the module defines truth.
- The card field contract (§10) between `flatfeed/matching.py`, README's card sketch, PROJECT_CONTEXT's card sketch, and any case-page mockup.
- Copy changes propagate across bot UI, tests, case-study surfaces, and documentation together (a stated Known Constraint in PROJECT_CONTEXT).

**MAY adapt by audience:**
- Gloss depth (case page glosses WBS for recruiters; the bot glosses it for users).
- Register (bot conversational first person; docs technical; case page editorial).
- German domain-term density (cards say `Kalt:`/`Warm:`; prose says Kaltmiete/Warmmiete).

---

## 28. Approved Patterns

Working well; reuse as-is; do not "improve" for uniformity's sake.

| Pattern | Location | Why approved | Reuse guidance |
|---|---|---|---|
| Deterministic core + AI-as-QA boundary | whole product | The portfolio thesis, implemented | Any new AI use starts admin-only, budgeted, non-mutating |
| Two-action product home | bot shell | Makes the normal repeat-use loop immediately visible | Keep `Filter` and `Show matches` as the only persistent global actions |
| One saved filter per user | setup + status card | Keeps the prototype narrow while demonstrating real state | Persist only after all four fields are complete |
| Consequence-named confirmation pair | `/delete` | Lets users remove saved product data safely | Keep published and explicit |
| Fixed listing-card contract with canonical fallbacks | `flatfeed/matching.py` | Predictable, scannable, honest about unknowns | Never fork per-context card variants |
| Fail-closed matching on unknown values | matching rules | Wrong sends are the costliest error | Default for any new matching field |
| Adapter state check before each card | on-demand delivery path | Names the implemented boundary precisely | Do not imply live-network verification |
| Source-health alerting with cooldown | ingestion | Detects silent failure without alert spam | Any new background job |
| Deduplicated automatic delivery | background pipeline | New matches reach users without requiring repeated manual checks | Gate with `BOT_BACKGROUND_ENABLED`; verify activity and record each successful send |
| Ground-truth quarantine | `synthetic/` ↔ prompts | Makes the eval meaningful | Absolute; no exceptions |
| Version-stamped QA reviews (one per listing per version) | `flatfeed/ai_qa.py` | Enables version comparison, caps cost | Any new AI artifact gets a version field |
| Hiring-first story sequence | case study §§01–05 | Lets hiring managers identify the product, ownership, judgment and evaluation evidence without repeated sections | Keep Problem → Product → Decisions → AI Evaluation → Next in that order |
| Demonstrated / Not demonstrated split | case study §03 | Prevents prototype completion from reading as market validation | Every future evidence claim |
| Teal-only structure accent | case page | Keeps weak evidence from gaining visual weight | Use labels and filled/outlined markers for evidence status |
| Licensed demo photos with attribution file | `assets/listing_photos/` | Defensibility | Any new third-party asset gets the same treatment |

---

## 29. Deprecated / Do-Not-Copy

Exists in the codebase today; MUST NOT be reused in new work; migrate when touching the area. (No formal audits exist yet — this list comes from direct inspection and is expected to grow when audits run.)

| Pattern | Current location | Reason | Replacement | Priority |
|---|---|---|---|---|
| ~~Guided demo as the only public mode (`Try the demo`, `tour:*`)~~ | compatibility handlers remain in `main.py` | It showed portfolio framing instead of the normal product a user would operate | Saved filter + on-demand matching | Retired 2026-08-06; old tour callbacks redirect to filter status |
| ~~Unfiltered catalog browsing (`📂 All listings`)~~ | (removed — `main.py`) | It bypassed the focused demo and added a competing global action | Replay the guided scenario | Done — don't reintroduce without a new phase decision |
| Case-page GitHub links hard-coded to `github.com/mich-mayer/flatfeed` (×4) | `docs/case-study.html` — top bar and evaluation evidence | Static page, no build step: a URL can't be single-sourced in markup without JS-only links (breaks no-JS on the page's key "view my code" CTA) or introducing a build/template; the 4 real hrefs are the correct static pattern | VERIFIED 2026-07-08 against `git origin` — canonical = `mich-mayer/flatfeed`, treat as FACT. A canonical-URL comment at `<body>` top is the documented source of truth; keep the 4 links in sync on any repo move/rename | Resolved-verified |

---

## 30. Unresolved Decisions

Insufficient evidence for a rule — do not invent one; use the temporary default.

| Decision | Why unresolved | Evidence needed | Temporary default |
|---|---|---|---|
| Localization (German or Russian bot copy) | Product is English-facing by decision (PROJECT_CONTEXT Known Constraints) | An explicit product decision to localize | English only; keep German domain terms glossed |
| Live source adapters | Legal/terms review pending; demo is synthetic-only | Author's go-ahead + terms-compatible sources | Synthetic adapter only; describe others as PLANNED |
| Eval-metrics *generation* into docs (vs. verification) | Numbers are still written by hand; only checked automatically now (§27, `scripts/check_eval_numbers.py`, 2026-07-09) | A decision to template/generate the result blocks from `run_eval --json` instead of hand-editing them | Hand-edit numbers, then run the §27 sync check before handoff; do not build a generator without this decision |

---

## 31. Agent Instructions

For Claude/Fable, Codex, and other coding agents.

**Before changing bot UI or copy, an agent MUST:**
1. Read §§7, 17–19 and match the existing register (plain product voice, HTML tags `<b>/<i>/<a>` only, no decorative emoji).
2. Keep the listing-card contract (§10) and canonical fallback strings intact.
3. Add a consequence-named confirmation to anything destructive or costly (§7.2).
4. Propagate copy changes across bot, tests, case-study surfaces, and docs together (§27).

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
4. Run the 10s/45s scan tests (§22) on the changed section.

**Verification matrix.** Choose the required row by the riskiest touched surface; run broader checks when uncertain or when a change crosses surfaces.

| Change type | Required checks | Add when |
|---|---|---|
| Documentation-only, no claims or numbers changed | `git diff --check`; targeted `rg` for changed terminology/evidence labels | Run tests/eval only if docs assert behavior that may have drifted |
| Case-study HTML/CSS only | `git diff --check`; 10s/45s scan review (§22); browser/render check for the touched viewport(s); `rg` for non-token colors when CSS changes | Run unit tests if code examples, eval numbers, or generated artifacts are touched |
| Eval numbers or result prose | `PYTHONPYCACHEPREFIX=/tmp/flatfeed-pycache .venv/bin/python -m eval.run_eval`; eval sync search (§27); `git diff --check` | Run full tests if parser/generator/AI QA code changed |
| Parser, matching, WBS, synthetic catalog, transit, or DB behavior | `PYTHONPYCACHEPREFIX=/tmp/flatfeed-pycache .venv/bin/python -m unittest discover -s tests`; `PYTHONPYCACHEPREFIX=/tmp/flatfeed-pycache .venv/bin/python -m eval.run_eval`; `git diff --check` | Add focused manual smoke checks for changed source adapters or delivery paths |
| Bot UI or AI QA behavior | Full tests; focused runtime/manual check of the changed flow; `git diff --check` | Run eval if parser snapshots, AI QA prompt policy, or documented result numbers changed |
| Deployment/public URL changes | Relevant tests from above; Pages/GitHub status check; `curl -I` and content check for the published URL | Re-check after cache delay if headers still show old content |

**Always:**
- Use the matrix above; if you skip a heavier check that the old blanket rule would have run, state why in the final/handoff.
- Keep the product catalog synthetic: no real scraping, no network geocoding, no image reuploading, no live-source claims.
- Operational/server details belong in `LOCAL_CONTEXT.md` (local-only) and MUST NOT enter any committed or public surface.
- Don't overwrite others' uncommitted work.

---

## 32. Design Review Checklist

- [ ] Bot: message = one purpose; HTML tags within the allowed set; emoji only in sanctioned button labels (§7.1).
- [ ] Bot: `/start` exposes `Filter` and `Show matches`, discloses the synthetic/no-live boundary, and shows current filter status (§§6.1, 7.6).
- [ ] Bot: destructive/costly actions have consequence-named confirmations (§7.2).
- [ ] Card: field order, labels, grouping, and fallback strings match §10 exactly.
- [ ] Delivery: adapter state check, up to three on-demand cards, no separate match-reason message, conditional deduplicated notifications, and fail-closed matching intact (§3 P5).
- [ ] Case page: tokens only, square corners, shadow only on the active carousel image frame, one teal content accent (§5).
- [ ] Case page: hiring-first five-section structure, numbered-kicker motif, text-led hero, seven-screen carousel, and clear mobile linear flow (§6.3, §14).
- [ ] Accessibility: aria labels/alt preserved; new text colors checked ≥4.5:1; new motion gated (§15).
- [ ] Product/evidence separation intact: no QA controls or metrics in user-facing surfaces (§3 P8).

## 33. Content Review Checklist

- [ ] Audience identified: user, case-study reader, or private alert recipient; register matches §17.
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
3. **Affected surfaces** — bot, case page, eval artifacts, docs; list the files.
4. **Compatibility impact** — which existing messages/screens/copy now violate the new rule.
5. **Migration consideration** — fix now, fix-when-touched (add to §29), or explicitly grandfather.

Update this file in the same change. External references inform; project needs decide. Keep tests, the eval, and `git diff --check` green.

### 2026-08-20 simplify the AI-check runtime note

- **Problem:** the runtime note in the AI Evaluation section condensed review versioning, post-model guardrails, the daily cost cap, risk threshold, alert triage and disabled-by-default state into one dense paragraph. Readers could not quickly understand the implemented path.
- **Rationale:** the case page now states the operational sequence in plain language: AI finds source values, code compares them, and an admin resolves a difference. The nearby scope label retains the implementation boundary; versioning and budget controls remain documented in `docs/PROJECT_CONTEXT.md` for technical readers.
- **Affected surfaces:** `docs/case-study.html`, `CASE_STUDY.md`, and this file (§22).
- **Compatibility impact:** the previous long runtime-note copy no longer conforms; the AI boundary, admin-only review, deterministic matching, and disabled-by-default scope remain unchanged.
- **Migration consideration:** verify the revised note at desktop and mobile widths and keep the HTML and Markdown case studies meaning-aligned.

### 2026-08-19 describe the AI check as an implemented capability

- **Problem:** the case study described the admin AI data-quality check as a
  separate offline experiment that "never changed listings, matches or Telegram
  cards", and deferred its actual product status to a closed `<details>` in
  Next. The check is in fact built into ingestion (`flatfeed/ai_qa.py`, the
  `ai_qa_reviews` table, `run_ai_qa_for_unreviewed_active_listings`), with a
  daily cost cap, a risk threshold, deterministic guardrails and a three-state
  admin resolution loop. The page therefore understated shipped work and read
  as a disclaimer rather than a capability.
- **Rationale:** lead section 04 with what the product does, then show the
  evidence that it works. The reporting boundary — AI flags, code compares, an
  admin decides, matching stays rule-based — is an architectural decision and
  is stated as one. A stacked `role-note` after the introduction carries the
  runtime specifics that prove integration. The evaluation is framed as
  pre-enablement validation with the real model on a frozen synthetic set. All
  caveats consolidate in the Next prototype limits, which now separate the
  switched-off default, the offline harness, and the unmeasured live-source
  accuracy. This matches how the already-built background delivery feature is
  described one line above.
- **Affected surfaces:** `docs/case-study.html`, `CASE_STUDY.md`, and this file
  (§§22 and 34).
- **Compatibility impact:** an AI Evaluation introduction that presents the
  check as an experiment detached from the product, a product status line that
  omits it, or prototype limits that state the switched-off default without the
  harness and live-source boundaries, no longer conforms. The frozen dataset,
  metrics, field results, model configuration and product runtime remain
  unchanged.
- **Migration consideration:** verify the new `role-note` spacing inside
  section 04 at desktop and mobile widths, and confirm the closed evaluation
  details still open correctly beneath it.

### 2026-08-18 show the AI check through one compact source comparison

- **Problem:** the AI Evaluation introduction explained source evidence and
  deterministic comparison in prose, but did not let a general reader see what
  the model and simulated parser output were being compared on. The initial
  example separated the listing text from the comparison, used a service-style
  synthetic-example label and named WBS in the heading, which made the source
  less obvious and the risk look field-specific.
- **Rationale:** use a compact three-row comparison whose first row is labelled
  `Listing text` and contains one German synthetic listing with WBS, district,
  Kaltmiete and rooms. Two identically ordered value-only rows show `Parser
  output` and `AI evidence`, so the differing WBS range stays easy to compare
  while the field-neutral heading makes clear that any parsed value may be
  wrong. Each source label is a bordered cell and the three rows share the
  height required by the longest row, so the source reads as part of the same
  table rather than as a separate quote. The result also makes the operating
  boundary explicit: AI flags a difference, while a person reviews the source
  and decides whether the parser is wrong before any data changes. The
  surrounding copy preserves the experiment's actual boundary:
  structured values simulate parser output, AI returns source evidence, code
  compares them, and nothing can change product output.
- **Affected surfaces:** `docs/case-study.html`, `docs/styles.css`,
  `CASE_STUDY.md`, and this file (§§22 and 34), plus the shared stylesheet cache
  key in `docs/demo-listing.html`.
- **Compatibility impact:** an AI Evaluation introduction made only of prose,
  a listing quote visually detached from the comparison, a field-specific
  example heading, or comparison rows that repeat field names beside every
  value no longer conforms. The frozen dataset, metrics, field results, model
  configuration and product runtime remain unchanged.
- **Migration consideration:** updated now across the public HTML and Markdown
  case studies. Verify the comparison at desktop and mobile widths, ensure the
  values remain aligned without overflow, and exercise the existing closed
  evaluation details after the change.

### 2026-08-18 connect human review to controlled parser improvement

- **Problem:** the worked example stated that a person decides whether the
  parser is wrong, but Next did not explain how that decision improves the
  product after review.
- **Rationale:** keep the feedback loop in Next rather than adding another
  component to AI Evaluation. At a general, planned-workflow level, explain
  that only configured admins review AI flags, confirmed parser errors become
  test cases and parser fixes, false AI alerts improve the next QA version,
  and no review directly changes listing data or matching.
- **Affected surfaces:** `docs/case-study.html`, `CASE_STUDY.md` and this file
  (§§22 and 34).
- **Compatibility impact:** a case study that suggests users see or act on AI
  flags, or a Next review gate that omits the controlled use of review
  decisions, no longer conforms. The prototype's non-mutating AI boundary,
  synthetic evidence and runtime scope remain unchanged.
- **Migration consideration:** update the HTML and Markdown case studies
  together; validate that the longer gate remains readable at desktop and
  mobile widths.

### 2026-08-18 remove the conclusion kicker

- **Problem:** the dark concluding summary repeated `What this demonstrates`
  as a visual kicker before a headline that already stated the takeaway.
- **Rationale:** remove the redundant kicker and let the headline and summary
  copy carry the conclusion directly.
- **Affected surfaces:** `docs/case-study.html`, `docs/styles.css`, the shared
  stylesheet cache key in `docs/demo-listing.html`, and this file (§§6, 22 and
  34).
- **Compatibility impact:** the dark conclusion must not render a kicker above
  its headline. Its content, position and sibling case link remain unchanged.
- **Migration consideration:** verify the conclusion at desktop and mobile
  widths after removing the label.

### 2026-08-18 make the conclusion name the hiring signal

- **Problem:** the conclusion headline used broad phrases such as `clear
  decisions` and `evidence for the next step`, which did not tell a hiring
  manager what FlatFeed demonstrated.
- **Rationale:** name the concrete product and boundary in the headline and
  copy: an apartment-search workflow, deterministic matching, and AI limited to admin
  review of parser risks. Retain the honest next validation step.
- **Affected surfaces:** `docs/case-study.html`, `CASE_STUDY.md` and this file
  (§§22 and 34).
- **Compatibility impact:** the conclusion must state the concrete workflow
  and rule/AI boundary rather than rely on generic portfolio language.
- **Migration consideration:** verify readable wrapping and the unchanged dark
  conclusion layout at desktop and mobile widths.

### 2026-08-18 recalibrate the vertical rhythm's two largest steps

- **Problem:** the 2026-08-12 pass unified heading→block spacing to a single
  `3.5rem` but never re-tuned the resulting density. Measured on the rendered
  page at 1440px, a section boundary opened a 138–163px optical void and a
  section `h2` sat 79–82px above the block it introduces, so a headline read as
  detached from its own supporting copy. Empty bands of 40px or more totalled
  1745px — 29% of the page. Nothing in the rhythm scaled: every step was a fixed
  `rem` while the display type it separates is `clamp()`-fluid, and below 40rem
  the section insets were hardcoded to `3rem`/`4rem`, bypassing the tokens
  entirely so the scale had two sources of truth.
- **Rationale:** consistency over visual preference (§4), applied to density
  rather than to naming. Only the two oversized top steps were changed;
  `--space-block`, `--space-panel`, `--space-subrule`, `--space-caption` and
  `--pad-box` are untouched, because the measurement showed the lower half of
  the ladder was already correct. The binding constraint is the descending
  ladder now written into §5.6: `--space-heading-block` cannot fall much further
  without overtaking `--space-block` beneath it, so the bulk of the reduction
  comes from the section boundary, which has no such floor. Spacing that
  separates fluid display type is now fluid for the same reason the type is —
  which also removes the need for the breakpoint override, collapsing the scale
  back to one source. Rejected: cutting the steps to a uniform smaller value,
  which inverted the ladder (`heading-block` fell below `block`) and made a
  headline bind less tightly to its own block than two sibling blocks bind to
  each other.
- **Affected surfaces:** `docs/styles.css` (the `:root` rhythm tokens and the
  removed `max-width: 40rem` section-inset override), the stylesheet cache keys
  in `docs/case-study.html` and `docs/demo-listing.html`, and this file
  (§§5.6, 14, 34). Copy, product behaviour, evaluation evidence and Markdown are
  unchanged.
- **Compatibility impact:** at 1440px the section boundary drops from 132px to
  100px and heading→block from 59.5px to 50.6px; at 375px the boundary drops
  from 112px to 88px and heading→block from 56px to 44px. The ladder stays
  strictly descending at 375, 640, 896, 1088 and 1440px. `--space-section-top`
  was deliberately left fixed at `2.75rem`: making it fluid resolved it to
  36.8px at 1440px, below the 40.5px sticky header, and a verified anchor click
  clipped the destination kicker by 3px. That coupling — `scroll-padding-top: 0`
  plus the section's own inset (§14) — is now recorded in §5.6 so the token is
  not "simplified" into the fluid pair later.
- **Migration consideration:** fixed now. Verify by resolved pixel value, not
  authored unit: the ladder must descend at every tested width, and anchor
  navigation must leave the destination kicker below the sticky header at
  widths above 56rem.

### 2026-08-18 align body-copy starts across repeated card rows

- **Problem:** workflow and decision cards used identical margins but independent
  title heights. A wrapped title therefore pushed only its own paragraph down,
  producing visibly uneven body starts inside one equal-weight row.
- **Rationale:** marker, title and body are shared structural roles. CSS subgrid
  lets each row adopt the tallest title without fixed heights, manual line breaks
  or viewport-specific exceptions, and preserves natural height after cards
  collapse to one column.
- **Affected surfaces:** `docs/styles.css`, `docs/case-study.html` (stylesheet
  cache version only), and this file (§§5.3, 34). Copy, product behaviour,
  evaluation evidence and Markdown are unchanged.
- **Compatibility impact:** Product workflow, Decisions cards and Next metric
  cards now synchronize body starts within each rendered row. Browsers without
  subgrid support retain the previous readable layout through `@supports`.
- **Migration consideration:** updated now. Verify desktop, intermediate and
  single-column widths, plus browser console and the carousel interaction.

### 2026-08-18 make contextual role notes consistent in width and structure

- **Problem:** after Evidence boundary adopted the stacked role-note pattern,
  it remained inset by the scorecard padding, while `My role` was full width.
  The Next data-quality gate still used the older side-by-side label layout,
  and only `My role` carried a quiet scope line.
- **Rationale:** these are the same label-plus-explanation component in three
  contexts. A shared label, body and scope structure makes their reading order,
  inner spine and evidence boundary consistent without changing the surrounding
  scorecard evidence. Scope lines only restate limits already present in body
  copy; they introduce no new claims.
- **Affected surfaces:** `docs/case-study.html`, `docs/styles.css`, and this
  file (§§22, 34), plus `CASE_STUDY.md` for narrative parity. Product
  behaviour and evaluation data are unchanged.
- **Compatibility impact:** the scorecard's Evidence boundary now bleeds only
  through its own inner padding to align with section-level notes; scorecard
  borders, metrics and closed details remain contained. The Next gate stacks
  its label above the explanatory text. All three notes end with the same quiet
  uppercase scope metadata role.
- **Migration consideration:** updated now. Verify all three notes at desktop
  and mobile widths for matching width and no horizontal overflow.

### 2026-08-18 reuse the stacked role-note pattern for the AI evidence boundary

- **Problem:** the Evidence boundary used a side-by-side evaluation-outcome
  layout while the closely related `My role` note used the clearer stacked
  contribution-note pattern. The different treatments made equivalent
  label-plus-explanation blocks feel unrelated.
- **Rationale:** both blocks are contextual evidence, not scorecards. Reusing
  the stacked `role-note` component preserves the accent boundary while giving
  the label and explanation one direct reading order.
- **Affected surfaces:** `docs/case-study.html`, `docs/styles.css`, and this
  file (§§5.3, 22, 34). User-facing wording, product behaviour, evaluation
  evidence and Markdown are unchanged.
- **Compatibility impact:** the Evidence boundary no longer uses the retired
  `.qa-outcome` component. Its label, emphasis and visible limitation remain in
  the same location ahead of the closed evaluation details.
- **Migration consideration:** updated now, including the existing Decisions
  note, through the reusable stacked modifier. Verify desktop and mobile layout
  with no horizontal overflow.

### 2026-08-18 give AI Evaluation the same heading role as numbered sections

- **Problem:** the heading directly below the `04 AI Evaluation` kicker used
  the major sub-block type role despite being the section's sole reader-facing
  takeaway. It therefore appeared materially smaller and looser than Product,
  Decisions and Next.
- **Rationale:** a numbered section's first and only takeaway is a section
  heading, regardless of the local wrapper used to keep its explanatory prose
  together. Applying the shared section role restores the scan hierarchy and
  leaves major sub-block type for the scorecard and carousel introductions.
- **Affected surfaces:** `docs/styles.css`, `docs/case-study.html` (stylesheet
  cache version only), and this file (§§34). User-facing copy, product behaviour,
  evaluation evidence and Markdown are unchanged.
- **Compatibility impact:** the AI Evaluation takeaway now uses the same fluid
  size, line height, letter spacing and 48rem measure as other numbered section
  headings; its following paragraph and all scorecard subheadings are unchanged.
- **Migration consideration:** updated now and verified at desktop and mobile
  widths. No application code or eval data changed.

### 2026-08-18 align every case-study heading role with the type scale

- **Problem:** the case page's hero, section and carousel-title CSS had drifted
  from the approved role table. The section H2 could grow beyond its documented
  maximum, the carousel title began too large on narrow screens, and a
  breakpoint-specific hero override contradicted the one-clamp rule. The dark
  CTA used an intentional display role that was not specified in the table.
- **Rationale:** the approved type scale is the source of truth. One fluid clamp
  per display role preserves readable mobile minima and stable hierarchy without
  exceptions; documenting the existing CTA role makes its deliberate prominence
  reviewable rather than implicit.
- **Affected surfaces:** `docs/styles.css`, `docs/case-study.html` (stylesheet
  cache version only), and this file (§§5.2, 34). User-facing case-study copy,
  product behaviour, evaluation evidence and Markdown are unchanged.
- **Compatibility impact:** the hero now uses its standard fluid clamp at every
  breakpoint; section H2s and slide titles may be smaller at narrow and very
  wide widths, while major/minor sub-block and cell-title roles are unchanged.
- **Migration consideration:** updated now and verified in the browser at
  desktop and mobile widths. No eval data or application code changed.

### 2026-08-18 make Decisions ownership a full-width contribution note

- **Problem:** the ownership copy sat in the narrow right column of the Decisions
  heading, where it competed with the takeaway and read as a generic aside rather
  than evidence of the candidate's judgment and delivery.
- **Rationale:** keep direct ownership in Decisions, but place it before the
  three choices in a vertically stacked `My role` note. The note first names the
  candidate's concrete product and evaluation decisions, then implementation and
  coding-collaborator disclosure, with the no-live-rollout boundary in a quieter
  scope line.
- **Affected surfaces:** `docs/case-study.html`, `docs/styles.css`,
  `CASE_STUDY.md`, and this file (§§22 and 34).
- **Compatibility impact:** the Decisions heading no longer carries supporting
  prose in its second desktop column; direct ownership remains in the same
  section and keeps the approved collaborator disclosure.
- **Migration consideration:** updated now across the public HTML and Markdown
  case studies. Product scope, evaluation evidence and the three decisions are
  unchanged.

### 2026-08-17 remove the redundant AI Evaluation method line

- **Problem:** after the `Two separate paths` boundary moved into AI Evaluation,
  the compact `Method:` line immediately repeated the same AI-evidence and
  code-comparison explanation.
- **Rationale:** let the boundary establish the operating model, then move
  directly to the question the offline test asks. Removing the duplicate keeps
  the evaluation introduction concise without weakening the AI boundary.
- **Affected surfaces:** `docs/case-study.html`, `docs/styles.css`,
  `CASE_STUDY.md`, and this file (§§22 and 34).
- **Compatibility impact:** a standalone `Method: AI extracts source evidence;
  code checks it.` line no longer belongs below the two-path boundary.
- **Migration consideration:** removed now across public HTML and Markdown.
  The boundary, method semantics and measured evaluation evidence are unchanged.

### 2026-08-17 move the two-path boundary into AI Evaluation

- **Problem:** the `Two separate paths` explanation sat below Decisions even
  though it explains the architecture and scope of the subsequent AI
  effectiveness evaluation.
- **Rationale:** begin AI Evaluation with the boundary between deterministic
  user matching and offline AI evidence extraction. Readers can then understand
  what the 600-listing test evaluates before seeing its method, question and
  scorecard.
- **Affected surfaces:** `docs/case-study.html`, `docs/styles.css`,
  `CASE_STUDY.md`, and this file (§§22 and 34).
- **Compatibility impact:** Decisions now ends after its three product choices;
  the user/offline path explanation no longer belongs there.
- **Migration consideration:** moved now across public HTML and Markdown. The
  text, AI boundary, evaluation evidence and section destinations are unchanged.

### 2026-08-17 remove redundant AI Evaluation labels

- **Problem:** the opening outcome heading and the `Two separate paths` label
  repeated information conveyed by the evaluation evidence and boundary itself.
- **Rationale:** begin the section with the `04 AI Evaluation` kicker and the
  boundary's explanatory heading, leaving the scorecard to present the measured
  result.
- **Affected surfaces:** `docs/case-study.html`, `CASE_STUDY.md`, and this file
  (§§22 and 34).
- **Compatibility impact:** the content hierarchy remains intact; only duplicate
  labels are removed.
- **Migration consideration:** removed now across public HTML and Markdown.
  The boundary, explanatory copy and measured evaluation evidence remain.

### 2026-08-17 give the AI boundary its full heading measure

- **Problem:** after its label was removed, the boundary retained the old
  two-column header grid and top rule. The heading occupied the narrow label
  column while the empty rule added a visual interruption.
- **Rationale:** remove the redundant divider and render the explanatory
  heading across the normal heading measure before the two path cards.
- **Affected surfaces:** `docs/styles.css` and this system (§§14 and 34).
- **Compatibility impact:** the AI Evaluation boundary no longer uses the
  label-column layout or top rule; its cards and evidence footnote are unchanged.
- **Migration consideration:** updated now in the rendered case study.

### 2026-08-17 turn the AI boundary into a testing introduction

- **Problem:** two path cards, a runtime footnote and a separate product-proof
  paragraph repeated the same boundary without forming a clear transition into
  the evaluation scorecard.
- **Rationale:** condense the material into one heading and one prose paragraph:
  matching remains rule-based, AI supplies source evidence offline, code checks
  it, and the setup cannot affect product output. The evaluation question now
  follows directly.
- **Affected surfaces:** `docs/case-study.html`, `docs/styles.css`,
  `CASE_STUDY.md`, and this system (§§6.3, 22 and 34).
- **Compatibility impact:** the public AI Evaluation introduction no longer
  uses separate user-path and offline-path cards.
- **Migration consideration:** consolidated now across public HTML and Markdown.
  The AI boundary and evaluation evidence are unchanged.

### 2026-08-17 simplify the AI Evaluation introduction heading

- **Problem:** the word `offline` in the introduction heading duplicated the
  explanation immediately below it and made the heading less direct.
- **Rationale:** state the product boundary in the heading — parser quality
  versus rule-based matching — and retain the separate offline-evaluation detail
  in the body copy where it explains the method.
- **Affected surfaces:** `docs/case-study.html`, `CASE_STUDY.md`, and this
  system (§34).
- **Compatibility impact:** content meaning and evaluation scope are unchanged.
- **Migration consideration:** updated now across public HTML and Markdown.

### 2026-08-17 streamline the AI Evaluation method sentence

- **Problem:** `without influencing matches` repeated the rule-based boundary
  already established by the heading and closing sentence of the introduction.
- **Rationale:** remove the repetition while retaining the explicit statement
  that the setup cannot change listing data, match decisions or Telegram cards.
- **Affected surfaces:** `docs/case-study.html`, `CASE_STUDY.md`, and this
  system (§34).
- **Compatibility impact:** method, AI boundary and evaluation scope are unchanged.
- **Migration consideration:** updated now across public HTML and Markdown.

### 2026-08-17 remove the AI QA scorecard label

- **Problem:** the all-caps AI QA label repeated the evaluation context without
  helping the reader reach the test question.
- **Rationale:** remove the label and let the question lead. Keep `synthetic`
  in the first method sentence so the result retains its visible scope qualifier.
- **Affected surfaces:** `docs/case-study.html`, `docs/styles.css`,
  `CASE_STUDY.md`, and this system (§§13, 27 and 34).
- **Compatibility impact:** the scorecard heading uses the main content width;
  the frozen 600-case evidence, its result and its limits are unchanged.
- **Migration consideration:** updated now across public HTML and Markdown.

### 2026-08-17 remove the AI QA decision callout

- **Problem:** the prominent `Passed the synthetic benchmark` callout repeated
  the four metric cards immediately below it.
- **Rationale:** let the individual results and their predeclared targets carry
  the evidence, rather than adding a summary decision panel.
- **Affected surfaces:** `docs/case-study.html`, `CASE_STUDY.md`, and this
  system (§§13, 27 and 34).
- **Compatibility impact:** no standalone pass/fail callout appears above the
  metrics; all metric counts, targets and evidence limits remain visible.
- **Migration consideration:** updated now across public HTML and Markdown.

### 2026-08-17 make the AI Evaluation heading describe the full boundary

- **Problem:** the prior heading named parser quality and rule-based matching,
  but did not explain the distinct roles of AI and code.
- **Rationale:** name the complete chain in reader order: AI provides source
  evidence, code checks parser output, and fixed rules decide matches. Remove
  the duplicate rule-based statement from the paragraph below it.
- **Affected surfaces:** `docs/case-study.html`, `CASE_STUDY.md`, and this
  system (§34).
- **Compatibility impact:** the AI boundary is clearer; evaluation method and
  product behavior are unchanged.
- **Migration consideration:** updated now across public HTML and Markdown.

### 2026-08-17 describe the AI experiment as controlled discrepancy checking

- **Problem:** the previous copy implied that FlatFeed had parsed live listing
  sources and that the evaluation checked that parser's output. In fact, the
  final evaluation paired generated listing text with structured values that
  simulate parser output, then planted one value conflict in half the cases.
- **Rationale:** name the controlled mechanism directly: AI quotes generated
  listing text, code compares those quotes with structured values, and the test
  measures planted text–data conflicts rather than live ingestion or
  production-parser accuracy.
- **Affected surfaces:** `docs/case-study.html`, `CASE_STUDY.md`,
  `scripts/check_eval_numbers.py`, and this system (§§13, 22, 27 and 34).
- **Compatibility impact:** public AI evidence no longer calls simulated values
  FlatFeed's parsed values or calls the controlled benchmark parser quality.
- **Migration consideration:** updated now across public HTML and Markdown.
  The frozen 600-case data, metrics, limitation and runtime boundary are
  unchanged.

### 2026-08-17 order Decisions as AI boundary, synthetic scope, then matching trade-off

- **Problem:** the prior three-card order placed the fail-closed matching
  trade-off before the synthetic-data scope decision, despite the intended
  reader sequence being explicitly AI boundary → synthetic-data scope →
  matching trade-off.
- **Rationale:** preserve the bounded AI decision as the section lead, then
  establish why generated listings are used before ending with the deterministic
  matching trade-off. This is the author-selected reading order.
- **Affected surfaces:** `docs/case-study.html`, `CASE_STUDY.md`, and this file
  (§§22 and 34).
- **Compatibility impact:** the prior A/B/C and 1/2/3 ordering of the synthetic
  scope and fail-closed decisions no longer conforms. Card content and product
  boundaries are unchanged.
- **Migration consideration:** reordered now across public HTML and Markdown.
  No product behavior, evaluation result or source-access claim changed.

### 2026-08-17 make source-access due diligence visible in Decisions

- **Problem:** the synthetic-data card explained what the prototype could and
  could not test, but did not make clear that generated listings were also a
  deliberate choice while access to and reuse of provider data remain
  unvalidated.
- **Rationale:** name `source access and reuse terms` rather than make a legal
  claim. The phrase communicates the product decision to avoid using provider
  data prematurely, while leaving open the factual paths of permission, a feed,
  an API or an agreement.
- **Affected surfaces:** `docs/case-study.html`, `CASE_STUDY.md`, and this
  file (§§22 and 34).
- **Compatibility impact:** the card must not imply that synthetic data was
  selected only for convenience, or that permission for provider data is
  impossible or already resolved.
- **Migration consideration:** updated now across public HTML and Markdown.
  Source scope, evaluation evidence and the requirement for permitted live
  sources remain unchanged.

### 2026-08-17 distinguish synthetic mechanics from real-world validation

- **Problem:** the third Decisions card said the generated-listing prototype
  tested the workflow before source coverage. Without a permitted live source,
  that wording could imply an end-to-end test of collection, freshness or
  renter value that has not occurred.
- **Rationale:** state exactly what generated listings can validate — filter
  setup, normalization, matching and Telegram delivery — and name what they
  cannot validate: source coverage, listing freshness and renter value. Those
  require permitted live sources and a real-user pilot.
- **Affected surfaces:** `docs/case-study.html`, `CASE_STUDY.md`, and this file
  (§§22 and 34).
- **Compatibility impact:** describing the synthetic prototype as testing the
  live-source workflow or market value no longer conforms.
- **Migration consideration:** corrected now across public HTML and Markdown.
  Implemented mechanics, source scope and evaluation evidence are unchanged.

### 2026-08-17 balance Decisions across AI, reliability and user workflow

- **Problem:** the three Decisions cards were all framed as technical or
  delivery constraints. They underplayed the product choice to test a saved
  filter and normalized Telegram results, while the AI card foregrounded
  prompt iteration rather than the user-facing boundary.
- **Rationale:** make the section's three choices legible as a balanced product
  strategy: deterministic user-facing matching with a separate AI
  parser-quality check; fail-closed matching when critical data is unknown; and
  validating the saved-filter workflow before live-source coverage. The source
  access limit remains explicit in the final card and Next, while the detailed
  synthetic experiment remains in AI Evaluation.
- **Affected surfaces:** `docs/case-study.html`, `CASE_STUDY.md`, and this
  file (§§22 and 34).
- **Compatibility impact:** the earlier `Give AI a narrow, checkable task`,
  `Do not match a listing when required data is missing`, and `Do not promise
  coverage before source access is clear` card copy no longer conforms. The
  deterministic-matching, no-live-coverage and AI-runtime boundaries are
  unchanged.
- **Migration consideration:** rewritten now across public HTML and Markdown.
  The Decisions headline now names the artifact as a prototype, consistent with
  the no-live-rollout context.

### 2026-08-17 lead Decisions with the bounded AI choice

- **Problem:** the decision that explains FlatFeed's distinct AI boundary was
  third in the three-card sequence, after matching and source-coverage limits.
- **Rationale:** lead with the most differentiating product decision — AI checks
  parser evidence while deterministic code compares values — then present the
  matching and coverage constraints it supports. This preserves the exact
  boundaries and claims while improving the section's scan order.
- **Affected surfaces:** `docs/case-study.html`, `CASE_STUDY.md`, and this file
  (§§22 and 34).
- **Compatibility impact:** the former A/B/C and 1/2/3 order for the three
  Decisions cards no longer conforms; card copy and the user/offline boundary
  remain unchanged.
- **Migration consideration:** reordered now across public HTML and Markdown.
  No product behavior, evaluation result or source-coverage claim changed.

### 2026-08-17 name the AI parser-quality review in Product status

- **Problem:** the Product status named the Telegram prototype, generated test
  listings and rule-based matching, but omitted the separate AI review used to
  check parser quality.
- **Rationale:** add the compact label `AI parser-quality review` to the same
  status line. It makes the product's bounded AI use visible without implying
  that AI decides user-facing matches.
- **Affected surfaces:** `docs/case-study.html`, `CASE_STUDY.md`, and this
  file (§§22 and 34).
- **Compatibility impact:** a Product status that describes deterministic
  matching but omits the AI parser-quality review is incomplete.
- **Migration consideration:** updated now across the public HTML and Markdown
  case-study surfaces. Matching, source coverage and AI-runtime boundaries are
  unchanged.

### 2026-08-17 hide section dividers beneath the sticky header on desktop anchor navigation

- **Problem:** clicking a desktop section-navigation link stopped with the
  section divider visibly separated below the sticky header, making the target
  feel misaligned with the page shell.
- **Rationale:** let the divider pass beneath the opaque blurred header while
  preserving the existing 2.75rem section inset, so the destination's kicker
  and heading remain readable immediately below the shell. Narrow layouts keep
  their 1rem scroll padding because their header is not sticky.
- **Affected surfaces:** `docs/styles.css`, the stylesheet cache keys in
  `docs/case-study.html` and `docs/demo-listing.html`, and the anchor-navigation
  rule in §14 of this file.
- **Compatibility impact:** a desktop `3rem` root scroll offset that leaves a
  visible gap between the header and a targeted section divider no longer
  conforms.
- **Migration consideration:** updated now for the shared case-study stylesheet.
  Section order, link destinations, content and mobile header behavior are
  unchanged.

### 2026-08-17 keep narrow section navigation inside the page spine

- **Problem:** at a narrow mobile viewport, the first-row brand subtitle plus
  Repository action forced the header grid wider than the page spine, carrying
  the two-column section navigation with it.
- **Rationale:** retain the required FlatFeed brand and Repository action, but
  hide the supplementary `Product case study` subtitle below 40rem. This keeps
  every section link reachable within the viewport without changing its label,
  destination or two-column layout.
- **Affected surfaces:** `docs/styles.css` and this file (§§6.3, 14 and 34).
- **Compatibility impact:** the brand subtitle is no longer required to remain
  visible below 40rem; the brand name, action and all section links remain
  visible.
- **Migration consideration:** fixed now in the shared case-study header. No
  product copy, section order or desktop header behavior changed.

### 2026-08-17 remove the duplicated Product introduction

- **Problem:** the Product introduction restated the same four criteria,
  normalization, rule-based matching and Telegram-card outcome that the status
  line and four workflow steps immediately below already show.
- **Rationale:** let the heading establish the product proposition, then move
  directly to status and the workflow. The first step now owns the Kaltmiete
  explanation, so the reader still sees the domain-term gloss at the point of
  use.
- **Affected surfaces:** `docs/case-study.html`, `CASE_STUDY.md`, and the
  Product element rule in §§3, 22 and 34 of this file.
- **Compatibility impact:** a prose paragraph between the Product heading and
  status line no longer conforms.
- **Migration consideration:** removed now across both public case-study
  surfaces. Product behavior, source coverage, evidence and terminology are
  unchanged.

### 2026-08-17 repeat the Kaltmiete tooltip in the setup workflow

- **Problem:** the `Save one filter` step named Kaltmiete without an English
  gloss. A reader scanning the workflow independently could miss the meaning
  of the matching field.
- **Rationale:** reuse the existing accessible tooltip, with the same
  `Base rent, excluding operating and heating costs.` explanation, rather than
  introducing a second term treatment.
- **Affected surfaces:** `docs/case-study.html` and the Kaltmiete-tooltip rules
  in §§3, 22 and 34 of this file.
- **Compatibility impact:** an unglossed Kaltmiete in the `Save one filter`
  workflow step no longer conforms.
- **Migration consideration:** updated now in the rendered case study.
  Product behavior, evidence and terminology are unchanged.

### 2026-08-17 make the Product workflow name its Telegram-card outcome

- **Problem:** the first step did not name the four saved fields, the status
  line added a redundant `Product:` label, and the final workflow step focused
  on one-time delivery without naming the user-visible Telegram card.
- **Rationale:** name WBS type, district, maximum Kaltmiete and rooms in the
  setup step; let the status facts stand without a label; and make the final
  step state the actual outcome — a match returned in Telegram.
- **Affected surfaces:** `docs/case-study.html`, `CASE_STUDY.md`, and the
  Product element rule in §§22 and 34 of this file.
- **Compatibility impact:** `Set the four matching criteria once`, `Product:`,
  and `Return each new match once` no longer conform in the public Product
  workflow.
- **Migration consideration:** updated now across both public case-study
  surfaces. Product behavior, source coverage, evidence and implementation
  status are unchanged.

### 2026-08-17 keep disabled-mode detail out of the Product workflow

- **Problem:** the fourth workflow step added that background delivery is
  switched off in the demo. This implementation-state detail interrupted the
  user-facing explanation after its complete delivery behavior was already
  clear.
- **Rationale:** retain the implemented behavior — users can request matches,
  and background delivery records successful sends to prevent duplicates — but
  do not repeat its demo-mode configuration in the Product workflow. The
  synthetic source and no-live-provider boundary remain explicit elsewhere.
- **Affected surfaces:** `docs/case-study.html`, `CASE_STUDY.md`, and the
  Product element rule in §§22 and 34 of this file.
- **Compatibility impact:** the sentence `It is built but switched off in this
  demo.` no longer belongs in the public Product workflow.
- **Migration consideration:** removed now from both public case-study
  surfaces. Product behavior, source coverage, evidence and implementation
  status are unchanged.

### 2026-08-17 explain why housing-provider sites require direct monitoring

- **Problem:** the Problem lede said only that housing providers publish on
  their own websites. It did not explain that these sites are a primary source
  of WBS listings, may publish before real-estate portals, and do not consistently
  provide alerts.
- **Rationale:** state the observed search context directly: some providers
  offer only email alerts and others offer none, so users still need to monitor
  provider websites alongside portals. Keep the wording conditional and retain
  the explicit no-live-aggregation boundary elsewhere on the page.
- **Affected surfaces:** `docs/case-study.html`, `CASE_STUDY.md`, and the
  10-second-scan mechanics in §§22 and 34 of this file.
- **Compatibility impact:** Problem copy that mentions provider websites
  without explaining their timing and notification gap no longer carries the
  complete product context.
- **Migration consideration:** updated now across the rendered case study and
  its Markdown counterpart. Product behavior, source coverage, evidence and
  implementation status are unchanged.

### 2026-08-14 keep the Problem hero focused on the user problem

- **Problem:** the `Project ownership` panel sat in the Problem hero after the
  problem explanation. It interrupted the Problem → Product → Decisions
  narrative and repeated information that the Decisions section already states.
- **Rationale:** a fast reader should first understand the user's repeated
  search and the implemented prototype. Ownership remains important, but its
  natural place is Decisions, where the concrete choices substantiate it.
- **Affected surfaces:** `docs/case-study.html`, `CASE_STUDY.md`, and the
  case-study structure rules in §§6.3, 14 and 22 of this file.
- **Compatibility impact:** the hero no longer contains an ownership panel.
  Decisions remains the page's direct statement that the project was
  self-directed and that the candidate made the product and evaluation
  decisions.
- **Migration consideration:** removed now from both public case-study
  surfaces. Product scope, evidence labels and ownership claims are unchanged.

### 2026-08-14 place status with the section it describes

- **Problem:** Product and Evaluation status lines appeared below the Problem
  lede, mixing implementation and experiment evidence into the user-problem
  section.
- **Rationale:** place the product-status line at the start of Product, before
  the workflow and screenshots. Place the AI method at the start of AI
  Evaluation, while retaining the synthetic 600-listing label with the
  scorecard to avoid repeating the same evidence.
- **Affected surfaces:** `docs/case-study.html`, `CASE_STUDY.md`, and the
  case-study structure rules in §§6.3, 14 and 22 of this file.
- **Compatibility impact:** the Problem hero carries no implementation or
  evaluation status line. The facts and their evidence labels are unchanged.
- **Migration consideration:** moved now on both public case-study surfaces;
  no product behavior, evaluation result or scope changed.

### 2026-08-14 use plain professional language across the case study

- **Problem:** the final hiring summary used short, concrete verbs, while the
  rest of the case still asked readers to decode internal phrases such as
  `bounded AI-and-code check`, `shared import pipeline`, `parser snapshots`,
  `review-required result` and `runtime admin-QA path`. The facts were correct,
  but the writing style changed between sections and slowed a hiring-manager
  scan.
- **Rationale:** apply the final summary's pattern across the page: state what
  happens in plain verbs first, then retain a technical term only when it is
  needed for evidence, product boundaries or reproducibility. Keep the tone
  professional by preserving exact ownership, synthetic qualifiers, metrics,
  trade-offs and limitations rather than replacing them with vague claims.
- **Affected surfaces:** rendered case study, Markdown case study and the
  public-copy rules (`docs/case-study.html`, `CASE_STUDY.md`, §§16, 22 and 34).
- **Compatibility impact:** unexplained internal terminology in public
  headings, linear copy, paths, details labels or prototype-limit text no
  longer conforms when a shorter action-led explanation carries the same fact.
  Technical terms remain allowed where the detail is necessary.
- **Migration consideration:** migrated now across all five case-study
  sections and the sibling-case handoff. Evaluation values, evidence labels,
  ownership, product scope and behavior are unchanged.

### 2026-08-14 state the multi-portal baseline explicitly

- **Problem:** the generic sentence `Portal alerts cover only listings on that
  platform` used a singular portal without an antecedent, so the problem could
  read as if Berlin had only one property portal.
- **Rationale:** state that several property portals offer saved-search alerts,
  while making the actual fragmentation precise: each alert is limited to its
  own platform and housing providers also publish on their own websites. This
  clarifies the existing market baseline without implying that FlatFeed already
  aggregates live sources.
- **Affected surfaces:** rendered case study, Markdown case study and the
  10-second-scan mechanics (`docs/case-study.html`, `CASE_STUDY.md`, §§22 and
  34).
- **Compatibility impact:** singular or generic portal-alert copy that can be
  read as describing one portal no longer conforms.
- **Migration consideration:** migrated now across the rendered case study and
  its Markdown counterpart. Product scope, evidence and implementation status
  are unchanged.

### 2026-08-14 make the hiring summary concrete

- **Problem:** the final summary relied on abstract portfolio phrases such as
  `bounded product`, `probabilistic checks` and `evidence before expansion`.
  They were accurate but made the reader translate the hiring signal back into
  the product decisions already shown on the page.
- **Rationale:** name the demonstrated work directly: a working Telegram
  prototype, rules deciding matches, AI kept in a separate quality check and
  validation before real-listing testing. This keeps the professional signal
  while making each claim understandable on its own.
- **Affected surfaces:** `docs/case-study.html`, `CASE_STUDY.md`, and this file
  (§§22 and 34).
- **Compatibility impact:** conclusion copy that summarizes the case only with
  abstract product-management terminology no longer conforms.
- **Migration consideration:** migrated now across the rendered case study and
  Markdown counterpart. Product scope, evidence and behavior are unchanged.

### 2026-08-14 reduce the carousel photo credit hierarchy

- **Problem:** the required photo attribution used nearly the same visual size
  as the orienting slide sentence, so utility metadata competed with product
  explanation.
- **Rationale:** keep the complete credit adjacent to the image, but render it
  at 11px with a 1.5 line height and the existing readable secondary text color.
  The disclosure stays legible while its lower information priority becomes
  visible.
- **Affected surfaces:** `docs/case-study.html`, `docs/styles.css`, stylesheet
  cache key in `docs/demo-listing.html`, and this file (§§5.5, 22 and 34).
- **Compatibility impact:** carousel photo credits styled like primary slide
  commentary no longer conform.
- **Migration consideration:** migrated now for the single licensed carousel
  image. Credit wording, adjacency, license disclosure and synthetic boundary
  are unchanged.

### 2026-08-14 make the first-screen language more concrete

- **Problem:** the first screen used abstract portfolio language such as
  `separate sources`, `explores a simpler flow`, `problem framing`, `AI
  boundary` and `evaluation gates`. The facts were accurate, but a fast reader
  had to translate them into websites, a prototype test and concrete ownership.
- **Rationale:** name the visible context directly (`multiple websites`), make
  the prototype status the subject of the proposed flow, use the established
  `rule-based matching` term and express ownership with plain verbs. Keep the
  synthetic, implementation and evaluation boundaries unchanged.
- **Affected surfaces:** `docs/case-study.html`, `CASE_STUDY.md`, and this file
  (§§22, 24 and 34).
- **Compatibility impact:** the previous abstract first-screen phrases and
  `fixed-rule matching` label no longer conform on the active case-study
  surfaces.
- **Migration consideration:** migrated now across the rendered case study and
  its Markdown counterpart. Product behavior, evidence and scope are unchanged.

### 2026-08-14 align desktop navigation with the brand row

- **Problem:** the desktop navigation occupied a separate 36px row even though
  the brand, five links and Repository action fit comfortably on one line. The
  extra shell height delayed the Problem content and ownership signal during a
  fast first-viewport scan. On narrow widths, the inherited desktop third
  column also let the Repository action create horizontal overflow.
- **Rationale:** above 56rem, use equal outer grid columns around the centered
  navigation so the nav stays geometrically centered while the brand and action
  sit at opposite edges. Symmetric block padding centers all three elements
  vertically without restoring the removed navigation row. At 56rem and below,
  retain the readable two-column nav with its own vertical padding on a second
  non-sticky row and explicitly place the action in column two.
- **Affected surfaces:** `docs/styles.css`, stylesheet cache keys in
  `docs/case-study.html` and `docs/demo-listing.html`, and this file (§§6.3, 14,
  22 and 34).
- **Compatibility impact:** a separate desktop nav row, one-sided desktop
  header padding, a 5.5rem desktop anchor offset, or a narrow header with an
  implicit third action column no longer conforms.
- **Migration consideration:** migrated now for the shared case-study shell.
  Navigation labels, destinations, product copy, evidence and behavior are
  unchanged.

### 2026-08-13 make the hero headline problem-led

- **Problem:** the `01 Problem` kicker was followed by a solution-led headline
  about one saved filter. During a fast scan, the two labels described different
  stages of the case-study narrative.
- **Rationale:** the H1 now names the repeated cross-source search itself. The
  product proposition remains in the lede and Product section, preserving fast
  comprehension without presenting a solution as the problem.
- **Affected surfaces:** `docs/case-study.html`, `CASE_STUDY.md`, and this file
  (§§22 and 34).
- **Compatibility impact:** a hero H1 that leads with `One saved filter` or
  another FlatFeed mechanism no longer conforms under the Problem kicker.
- **Migration consideration:** migrated now across the rendered case study and
  its Markdown counterpart. Product scope, evidence and behavior are unchanged.

### 2026-08-13 name the evaluation section `AI Evaluation`

- **Problem:** the generic navigation label `Evidence` described the rigor of
  the section but hid its actual subject during a fast scan. Nearly all of the
  section's linear content evaluates the bounded AI-and-code data-quality
  check, while the implemented product proof already lives in Product.
- **Rationale:** use `AI Evaluation`, not `AI Evidence`. The former is
  idiomatic, names the activity precisely and makes the AI PM relevance visible
  in navigation. `AI Evidence` could be read as evidence produced by AI rather
  than evidence about the evaluated system. Internal labels such as `Evidence
  boundary` and evidence-link terminology remain unchanged because they name
  their local function accurately.
- **Affected surfaces:** `docs/case-study.html`, `CASE_STUDY.md`,
  `LANDING_CONTENT_FINAL.md`, `docs/CURRENT_STATUS.md`, and this file (§§5.4,
  6.3, 13, 22, 27–28, 34).
- **Compatibility impact:** `Evidence` as the fourth navigation item, numbered
  section label or structural section name no longer conforms. The section's
  claims, scorecard, evidence boundary, evaluation artifacts and metrics are
  unchanged.
- **Migration consideration:** migrated now across the visible HTML label,
  anchor, Markdown heading and active content-system rules. No runtime code,
  evaluation number or product behavior changed.

### 2026-08-13 compress the hiring narrative to five sections

- **Problem:** the seven-section landing repeated the saved-filter workflow in
  Problem, Solution, Product and Evidence and repeated the AI boundary in
  Decisions, AI, Evidence, Next and the conclusion. A hiring manager could
  understand the project but still reach the strongest evidence and candidate
  synthesis only after a long linear read.
- **Rationale:** preserve every fact needed for trust at visible depth while
  removing repeated explanations. Product now combines solution, mechanism and
  Telegram proof; Decisions combines three consequential trade-offs and the
  two-path AI boundary; Evidence combines the evaluation question, four
  aggregates, the unusable result and its limitation. Technical depth remains
  available in closed details. This follows the case-study conflict hierarchy:
  fast comprehension improves only after factual integrity and ownership are
  preserved.
- **Affected surfaces:** `docs/case-study.html`, `docs/styles.css`,
  `CASE_STUDY.md`, `LANDING_CONTENT_FINAL.md`,
  `scripts/check_eval_numbers.py`, `docs/CURRENT_STATUS.md`, and this file
  (§§0, 5–6, 22, 27–28, 31–34).
- **Compatibility impact:** the separate Solution and AI sections,
  Without/FlatFeed comparison, scripted-demo decision, repeated capability
  cards, learning-card recap and architecture-first closing summary no longer
  conform. The public metric labels are now `Errors detected`, `Unnecessary
  review flags`, `Correct field identified` and `Usable results`; the evidence
  values are unchanged.
- **Migration consideration:** migrated now across both public case-study
  sources and the verification contract. The Telegram product, screenshots,
  evaluation artifacts, cost assumptions, synthetic/no-live qualifiers and
  repository links are unchanged.

### 2026-08-13 adopt the hiring-first case-study sequence

- **Problem:** the product-first sequence delayed candidate ownership and
  product decisions until after the implementation walkthrough. A hiring
  manager scanning quickly could understand the product and technical depth but
  still miss who made the decisions and why the work demonstrates product
  judgment.
- **Rationale:** use Problem → Solution → Decisions → Product → AI → Evidence →
  Next. The first viewport now carries product stage and ownership; Decisions
  makes trade-offs scannable; detailed evaluation configuration, field results
  and cost assumptions remain available without dominating the linear read.
- **Affected surfaces:** `docs/case-study.html`, `docs/styles.css`,
  `CASE_STUDY.md`, `LANDING_CONTENT_FINAL.md`, and this file (§§6.3, 14, 22,
  26–28, 34).
- **Compatibility impact:** the former What I Built / My Role / How AI Fits /
  Results / What I Learned labels and order no longer conform. The old rule
  that ownership appears only after the product walkthrough is superseded.
- **Migration consideration:** migrated now. Evidence numbers, product
  behavior, screenshots, AI boundaries and synthetic/live qualifiers are
  unchanged; only the reading hierarchy and public wording changed.

### 2026-08-12 move the implementation flow into What I Built

- **Problem:** the four-stage workflow in Solution repeated the product
  mechanism after the consolidated product statement, while What I Built began
  with screenshots without first showing the implemented system that produces
  them.
- **Rationale:** Solution should establish the user value through the concise
  product statement and Without/FlatFeed comparison. Starting What I Built with
  save → prepare → match → notify creates a clear mechanism-to-proof sequence:
  readers see the implemented flow before its Telegram screens. The existing
  four-column workflow and single-column mobile treatment remain unchanged.
- **Affected surfaces:** workflow markup in `docs/case-study.html`; its
  narrative location in `CASE_STUDY.md`; this file (§§22, 34).
- **Compatibility impact:** a four-stage workflow inside Solution no longer
  conforms. It belongs immediately after the What I Built heading and before
  the product carousel.
- **Migration consideration:** moved now without changing workflow copy,
  product behavior, screenshots, evidence or responsive layout.

### 2026-08-12 consolidate the product essence in Solution

- **Problem:** the Solution opening repeated the product across a headline,
  supporting paragraph and separate `Product in one sentence` block. Each
  version added a different detail, forcing readers to assemble the product
  proposition from three competing texts.
- **Rationale:** keep Problem focused on the user need, then consolidate the
  complete product essence into one bold, full-width Solution statement. Place
  Audience and Product metadata directly after it. Role and Scope belong in My Role;
  removing them here prevents the Solution from previewing the next section.
  This removes repetition without removing the four criteria, normalized
  format, fixed rules or Telegram-alert behavior.
- **Affected surfaces:** Solution copy and markup in `docs/case-study.html` and
  `CASE_STUDY.md`; statement width and retired product-summary rules in
  `docs/styles.css`; stylesheet cache keys in both public HTML files; this file
  (§§5.3, 6.3, 22, 34).
- **Compatibility impact:** separate Solution supporting copy, a `Product in one
  sentence` block, product metadata inside Problem, or Role / Scope metadata in
  Solution no longer conform. The approved order is one product statement →
  Audience / Product metadata → four-step workflow.
- **Migration consideration:** consolidated now. The retained metadata values,
  workflow, tooltips, product claims, evaluation evidence and product behavior
  are unchanged; ownership detail remains in My Role.

### 2026-08-12 first-use domain-term tooltips

- **Problem:** the separate WBS/Kaltmiete glossary block interrupted the Problem
  section's reading flow and visually competed with the product metadata.
- **Rationale:** keep each German domain term and move its explanation to its
  first use. A visible dotted underline plus a tooltip available on hover,
  keyboard focus and tap preserves discoverability and accessibility without a
  permanent explanatory block.
- **Affected surfaces:** tooltip markup and script in `docs/case-study.html` and
  `docs/terms.js`; tooltip styles and retired `.term-note` rules in
  `docs/styles.css`; stylesheet cache keys in both public HTML files; this file
  (§§3, 6.3, 17, 33, 34).
- **Compatibility impact:** a separate case-page glossary block or a tooltip
  that works only on hover no longer conforms. Telegram wizard hints remain
  inline and unchanged.
- **Migration consideration:** fixed now for the first WBS and Kaltmiete uses
  on the case page. Later repetitions remain plain text; product behavior,
  evaluation evidence and domain semantics are unchanged.

### 2026-08-12 remove the final repository button

- **Problem:** the final summary repeated the same Repository action already
  available in the header, weakening the summary's role as a closing statement.
- **Rationale:** retain one repository handoff in the persistent header and
  leave the dark summary panel as editorial content only.
- **Affected surfaces:** CTA markup in `docs/case-study.html`; retired CTA
  button/action rules in `docs/styles.css`; this file (§§9, 19, 22, 29, 34).
- **Compatibility impact:** `View repository`, `.btn--inverse`, or a
  `.case-actions` group in the final summary no longer conform.
- **Migration consideration:** removed now. The header Repository action,
  summary copy, sibling case link, evidence links and product behavior are
  unchanged.

### 2026-08-12 remove the case-study footer

- **Problem:** after the final CTA and sibling-case link, the repeated FlatFeed
  wordmark and positioning tagline added a separate 100px closing zone without
  introducing a new action or piece of evidence.
- **Rationale:** end the page on the sibling-case cross-link, which is the last
  useful reader action. Removing the entire footer also removes its divider and
  vertical padding, matching the author-selected browser region exactly.
- **Affected surfaces:** footer markup and stylesheet cache key in
  `docs/case-study.html`; footer rules and responsive overrides in
  `docs/styles.css`; shared stylesheet cache key in `docs/demo-listing.html`;
  this file (§§5.2, 5.5, 6.3, 29, 34).
- **Compatibility impact:** a separate footer, footer wordmark, footer tagline,
  footer navigation, or footer divider no longer conform on the case-study page.
- **Migration consideration:** removed now. The header brand, Repository
  actions, sibling-case link, product copy, evidence and evaluation results are
  unchanged.

### 2026-08-12 logo-aligned header action

- **Problem:** the header Repository button was taller than the adjacent logo
  mark and used the page ink color, so the two brand-side actions did not read
  as one compact lockup.
- **Rationale:** match the button's authored height to the 26px logo mark and
  use the logo asset's measured dominant purple (`#6247ea`). Keep teal as the
  content and evidence accent; purple is confined to this single brand action
  and carries no semantic status.
- **Affected surfaces:** `docs/styles.css`; stylesheet cache keys in
  `docs/case-study.html` and `docs/demo-listing.html`; this file (§§5.1, 5.2,
  5.6, 34).
- **Compatibility impact:** header Repository buttons taller than the logo or
  using ink/teal as their resting fill no longer conform.
- **Migration consideration:** fixed now for the case-study header only. Other
  buttons, evidence colors, content accents, copy, product behavior and
  evaluation results are unchanged.

### 2026-08-12 landing consistency pass (tokens, label role, divider hierarchy)

- **Problem:** the page had been refined section by section, so components with
  one role had drifted apart. `.preview-label` — the block label used 14 times
  across seven sections — had no style definition at all and rendered as body
  text next to real mono labels. The 1px `--ink` rule marked both a
  `.case-section` boundary and five in-section sub-blocks, so a sub-block read
  as a new numbered section. Repeated equal-weight cells were built three
  different ways (1px-gap grid, per-cell `border-right`/`border-bottom`,
  separated cards with a 1.5rem gap). Heading→block spacing was 3.75 / 3 / 1.5 /
  clamp(3.5–5)rem, card padding 1.25 / 1.5 / 1.75–2rem, cell copy 12.5 / 13 /
  13.5px at four line heights, label letter-spacing 0.04 / 0.045 / 0.06 / 0.07 /
  0.08em, and step numbers existed in four variants. The carousel slide title
  (max 2.75rem) rivalled the section h2 (max 3.5rem), and the caption reserve of
  18rem — calibrated for the desktop 25rem column — left up to 193px of dead
  space between a screenshot and its own comment below 56rem. Read top to
  bottom, the page felt like a set of separately designed sections rather than
  one product.
- **Rationale:** consistency over visual preference (§4). Every difference was
  tested against "is this element intentionally different, or accidentally
  different?", and only accidental variation was normalized. Nothing was
  redesigned: the Swiss International system, the one-accent rule, square
  corners, the seven-section motif and the single shadow are unchanged, and no
  new colour, family, weight or component was introduced. The fixes are
  systematic rather than local — a `:root` spacing/measure scale (§5.6), one
  label role and one letter-spacing (§5.2), one meaning per rule weight and one
  grid construction (§5.3), and a per-breakpoint caption reserve (§5.4) — so a
  future change inherits the rule instead of re-deriving a value. The reserved
  caption height keeps the 2026-08-12 fixed-navigation guarantee: the controls
  sit at an identical offset on all seven slides at every width, verified in the
  browser. Removing `box-shadow: inset 3px 0 0` from the comparison panel makes
  the existing "one shadow only" rule literally true.
- **Affected surfaces:** `docs/styles.css` (1729 → 1613 lines);
  `docs/case-study.html` and `docs/demo-listing.html` (stylesheet cache key
  only); this file (§§5.2–5.6, 34). **No copy, markup, evidence label or number
  changed on any surface** — the two HTML files differ from their previous
  version by the `?v=` query string alone.
- **Carousel breakpoint correction (part of this pass):** measuring the reserve
  across the full width range exposed a defect that predates it. Between 40rem
  and 56rem the two-column stage left the commentary about 200px wide, and the
  seventh slide's attribution needed 18.02rem — more than the reserve. The
  original fixed `height` therefore overflowed the arrows in that band, which is
  exactly what the 2026-08-12 fixed-navigation entry set out to prevent, and a
  `min-height` alone only converted the overlap into a moving control. The
  vertical stack now starts at 56rem instead of 40rem, so the two-column
  composition is kept only where the commentary can hold its bounded measure.
  Under §4 this is correctness over visual preference: the recorded guarantee
  was unmet, and the composition it protected had already failed at that width.
  Verified by stepping all seven slides at 344 / 360 / 375 / 390 / 430 / 500 /
  660 / 700 / 890 / 900 / 1000 / 1280 / 1600px — the controls hold one offset at
  every width.
- **Carousel heading alignment (author-approved, second review pass):** the
  carousel introduction was aligned to the caption column, so the media column
  above the stage stood empty and the block looked accidental rather than
  composed. It now sits on the page's left content edge, which makes the block
  read like every other sub-block on the page: rule → heading → panel. This
  supersedes the alignment half of the 2026-08-11 "centered carousel
  composition" entry; the centred capture-and-commentary composition *inside*
  the framed stage is unchanged.
- **Second review pass — remaining defects found and fixed:** a later
  `.section-heading > p` rule silently overrode the shared prose role, so all
  seven section paragraphs stayed at line-height 1.7 while every other prose
  block moved to 1.65; `.hero-ai-note` copy sat at 1.55 and `.term-note` at
  0.8125rem, outside the card-copy role; header and footer nav links used two
  sizes; the field table used two sizes for `th` and `td` where weight already
  carries the distinction; the comparison lists kept a trailing hairline the
  evidence lists did not; the 1px accent-bar compensation was placed before the
  rules it had to override, so the cascade discarded it; the dark CTA and the
  small-screen panels each carried their own inner spine. The page now resolves
  to **one outer spine and one inner spine at every width**, verified by
  measuring the left edge of every panel and its first child.
- **Compatibility impact:** an unstyled or sentence-case `.preview-label`, an
  `--ink` divider inside a section, a second grid construction for repeated
  cells, a literal spacing/padding/measure value where §5.6 has a token, a mono
  label at any letter-spacing other than `0.07em`, an accent bar drawn as an
  inset shadow, a desktop-only carousel caption reserve, a two-column carousel
  stage below 56rem, a carousel heading aligned to the caption column, a
  per-breakpoint font-size override, and any second inner spine no longer
  conform.
  Dead selectors that duplicated a live pattern (`.btn--ghost`, `.btn--accent`,
  `.top-link`, `.evidence-card--open`, `.qa-table__miss`, `.qa-explainer`,
  `.reliability-boundary__note`) were removed so they cannot seed a divergent
  variant; the `.demo-listing-*` rules were kept because they belong to the
  separate demo surface.
- **Migration consideration:** fixed now, in one pass. Carousel behaviour,
  keyboard and swipe support, the `aria-live` position region, disabled states,
  focus rings, slide order, screenshots, evidence and the seven-section
  structure are unchanged. The carousel heading alignment was raised as an open
  item in the first pass, approved by the author, and folded into this entry.

### 2026-08-12 fixed carousel navigation position

- **Problem:** slide comments have different lengths, so the navigation moved
  vertically when readers switched screens. On narrow layouts the movement was
  large enough to interrupt the reading rhythm and could make long copy feel
  crowded against the controls.
- **Rationale:** reserve one caption height based on the longest approved slide
  copy and bottom-align every comment inside it. Normalize the near-identical
  source captures inside one non-cropping frame because their source dimensions
  differ by a few pixels. The shared control then follows the same fixed text
  and media boundaries on every slide, while the reserved space prevents the
  seventh slide's longer attribution from overlapping the arrows.
- **Affected surfaces:** `docs/styles.css`; `docs/case-study.html` (stylesheet
  cache key); this file (§§5.4, 22, 34).
- **Compatibility impact:** content-sized carousel captions that move navigation
  between slides no longer conform.
- **Migration consideration:** implemented locally. Slide copy, screenshots,
  controls, keyboard support, swipe support, evidence and production deployment
  are unchanged.

### 2026-08-12 joined carousel arrow control

- **Problem:** the separate arrows aligned to the far right of the commentary
  looked detached from the reading flow and made two related actions resemble
  independent buttons.
- **Rationale:** join the square buttons with one shared internal border and
  align the pair to the commentary's left edge. This creates one compact
  navigator at the natural end of the text path: slide number → title → note →
  navigation. Keep disabled buttons in place so the control does not shift at
  the first or last screen.
- **Affected surfaces:** `docs/styles.css`; `docs/case-study.html` (stylesheet
  cache key); this file (§§5.4, 15, 22, 34).
- **Compatibility impact:** separated or right-aligned carousel arrow pairs no
  longer conform.
- **Migration consideration:** implemented locally. Button labels, disabled
  states, arrow-key support, swipe support, screenshots, copy, evidence and
  production deployment are unchanged.

### 2026-08-12 arrow-only carousel navigation

- **Problem:** the visible `Screen N of 7` inside the navigation duplicated the
  `NN / 07` label immediately above each slide title and made a simple two-action
  control feel like a wide status bar.
- **Rationale:** show only a compact previous/next arrow pair, aligned to the
  right edge of the commentary. Keep the dynamic position text as a visually
  hidden `aria-live` region so screen-reader users still receive the slide
  change announcement.
- **Affected surfaces:** `docs/styles.css`; `docs/case-study.html` (stylesheet
  cache key); this file (§§5.4, 15, 22, 34).
- **Compatibility impact:** a second visible carousel position label and
  full-width three-cell control bars no longer conform.
- **Migration consideration:** implemented locally. Button labels, disabled
  states, arrow-key support, swipe support, screenshot order, evidence and
  production deployment are unchanged.

### 2026-08-12 carousel controls integrated with commentary

- **Problem:** controls below the screenshot visually separated navigation from
  the slide explanation. Readers had to move between the left and right
  columns to understand a screen and then advance it.
- **Rationale:** place the shared previous / position / next controls directly
  below the active commentary in the right column. Center the commentary and
  controls together against the screenshot. On narrow screens keep a linear
  capture → commentary → controls order so the explanation is read before the
  reader advances.
- **Affected surfaces:** `docs/styles.css`; `docs/case-study.html` (stylesheet
  cache key); this file (§§5.4, 14, 22, 34).
- **Compatibility impact:** carousel layouts with navigation under the
  screenshot no longer conform.
- **Migration consideration:** implemented locally. Carousel behavior,
  screenshot order, copy, keyboard support, swipe support, evidence and
  production deployment are unchanged.

### 2026-08-11 centered carousel composition

- **Problem:** the carousel figure was mathematically centered, but its second
  grid column expanded to fill the remaining width while the caption itself
  stopped at 25rem. The visible screenshot-and-copy composition therefore felt
  left-heavy and made repeated slide navigation less comfortable.
- **Rationale:** center an explicit two-column composition using the bounded
  screenshot width and a 25rem copy column. Align the carousel introduction
  with the caption column and keep controls below the screenshot. Retain a
  fluid copy column below 56rem and the established vertical stack below 40rem
  so comments remain readable without horizontal overflow.
- **Affected surfaces:** `docs/styles.css`; `docs/case-study.html` (stylesheet
  cache key); this file (§§5.4, 14, 22, 34).
- **Compatibility impact:** desktop carousel layouts with a full-width flexible
  caption cell or an introduction misaligned from the caption no longer
  conform.
- **Migration consideration:** implemented locally. Screenshot order, copy,
  controls, accessibility behavior, product evidence and production deployment
  are unchanged.

### 2026-08-11 remove `only` from the closing AI clause

- **Problem:** `uses AI only to check data quality` added emphasis the closing
  proposition did not need and made the sentence less natural.
- **Rationale:** use the direct clause `uses AI to check data quality`. The
  preceding fixed-rules clause still keeps matching ownership explicit, so the
  AI boundary remains clear without the extra limiter.
- **Affected surfaces:** `docs/case-study.html`; `CASE_STUDY.md`; this file
  (§§21–22, 34).
- **Compatibility impact:** the word `only` no longer belongs in this closing
  AI clause; historical §34 entries retain their recorded wording.
- **Migration consideration:** implemented locally. Product behavior,
  evaluation evidence, runtime configuration and production deployment are
  unchanged.

### 2026-08-11 plain-language closing proposition

- **Problem:** the accurate closing summary read like an architecture inventory:
  `deterministic matching`, `multi-source ingestion` and `bounded, admin-only AI
  QA` competed in one sentence, weakening the user outcome and making the final
  scan harder to remember.
- **Rationale:** lead with two short benefits—`One filter. Timely apartment
  alerts.`—then explain the system in plain verbs: sources come into one flow,
  fixed rules match apartments and AI only checks data quality. The word `only`
  preserves the AI boundary without internal QA terminology in the headline.
- **Affected surfaces:** `docs/case-study.html`; `CASE_STUDY.md`; this file
  (§§21–22, 34).
- **Compatibility impact:** architecture-first final summaries and unexplained
  `AI QA` terminology no longer conform in the closing proposition.
- **Migration consideration:** implemented locally. Product behavior,
  evaluation evidence, runtime configuration and production deployment are
  unchanged.

### 2026-08-11 AI boundary in the final case-study summary

- **Problem:** the final CTA summarized saved filters, alerts, deterministic
  matching and multi-source architecture but omitted the bounded AI QA work,
  leaving one of the case study's central product decisions out of the closing
  scan.
- **Rationale:** add `bounded, admin-only AI QA` after the user product and
  deterministic matching. This keeps AI visible without implying that it
  selects apartments or changes user-facing data.
- **Affected surfaces:** `docs/case-study.html`; `CASE_STUDY.md`; this file
  (§§21–22, 34).
- **Compatibility impact:** closing summaries that omit the AI boundary or
  describe AI as part of matching no longer conform.
- **Migration consideration:** implemented locally. Product behavior,
  evaluation evidence, runtime configuration and production deployment are
  unchanged.

### 2026-08-11 article-free Problem and Solution labels

- **Problem:** `The Problem` and `The Solution` were grammatically valid but
  longer than the other compact navigation labels, while the definite article
  did not add information in this case-study taxonomy.
- **Rationale:** use the article-free category labels `Problem` and `Solution`
  in both navigation and section kickers. Keep the remaining labels unchanged
  because they are first-person or verb phrases rather than parallel noun
  categories.
- **Affected surfaces:** `docs/case-study.html`; `CASE_STUDY.md`; this file
  (§§6.3, 14, 22, 34).
- **Compatibility impact:** current navigation, section kickers and Markdown
  headings using `The Problem` or `The Solution` no longer conform. Historical
  §34 entries retain the wording they documented at the time.
- **Migration consideration:** implemented locally. Anchors, section order,
  copy, product claims, evaluation evidence and production deployment are
  unchanged.

### 2026-08-11 compact case-study header and section starts

- **Problem:** the two-row desktop header occupied about 109px and the first
  section content began another 68px below it; regular sections used more than
  90px of top padding. Together they hid too much case-study content in the
  first viewport.
- **Rationale:** keep the complete seven-item navigation and Repository action,
  but reduce the header row gap, header top inset, nav padding and the
  Repository button in proportion. Align the Problem hero and regular section
  starts to a tighter editorial rhythm while retaining more bottom spacing to
  separate complete sections.
- **Affected surfaces:** `docs/styles.css`; `docs/case-study.html` (stylesheet
  cache key); this file (§§5.2, 6.3, 14, 34).
- **Compatibility impact:** desktop headers around 109px tall, the 42px header
  Repository button, 7rem anchor offset, 4rem Problem top padding and 5.5rem
  regular-section top padding no longer conform.
- **Migration consideration:** implemented locally for desktop and narrow
  layouts. Product copy, section order, screenshots, evaluation evidence,
  runtime behavior and production deployment are unchanged.

### 2026-08-11 product-first case-study sequence

- **Problem:** the landing introduced `Why AI?` before readers had seen how
  FlatFeed solved the repeated-monitoring problem or what the working product
  looked like. The formal framework therefore made the case read like an AI QA
  project instead of a Berlin WBS apartment-alert product.
- **Rationale:** reorder the seven sections to The Problem → The Solution →
  What I Built → My Role → How AI Fits → Results → What I Learned. Move the
  four-step product path and Without/FlatFeed comparison into The Solution,
  keep the product screenshots before candidate and AI detail, move model
  selection into How AI Fits, separate implemented product evidence from
  measured synthetic AI QA in Results, and integrate current limitations into
  What I Learned.
- **Affected surfaces:** `docs/case-study.html`; `docs/styles.css`;
  `CASE_STUDY.md`; `docs/CURRENT_STATUS.md`; this file (§§0, 4–6, 14, 22,
  27–28, 32, 34).
- **Compatibility impact:** the earlier Problem → Why AI → Role → Approach →
  Built order, a standalone Approach section, and a separate unnumbered
  Prototype Setup and Limitations section no longer conform. Historical §34
  entries retain their original wording as decision history.
- **Migration consideration:** implemented locally without changing product
  behavior, screenshots, evaluation numbers or production deployment.

### 2026-08-11 first-person role section label

- **Problem:** `Your Role` addressed the case-study author in the second person,
  while the section itself describes the author's contribution in the first
  person and the Markdown case study already used `My Role`.
- **Rationale:** use `My Role` in both the navigation and numbered section so
  the label matches the narrative voice and remains identical across HTML and
  Markdown surfaces.
- **Affected surfaces:** `docs/case-study.html`; this file (§§6.3, 22, 34).
- **Compatibility impact:** `Your Role` is no longer the current section label;
  historical governance entries retain the wording they documented at the time.
- **Migration consideration:** implemented locally. Section content, anchor,
  product claims, evidence and production deployment are unchanged.

### 2026-08-11 compact landing navigation and restored brand subtitle

- **Problem:** distributing seven section labels across the full navigation row
  made the header feel visually fragmented, while the FlatFeed wordmark alone
  did not identify the page as a case study.
- **Rationale:** group the exact section labels in a compact centered row and
  restore `Product case study` beside the FlatFeed wordmark at every viewport;
  all seven navigation links remain visible below it.
- **Affected surfaces:** `docs/case-study.html`; `docs/styles.css`; this file
  (§§6.3, 22, 34).
- **Compatibility impact:** full-width `space-between` navigation and the
  subtitle-free desktop brand no longer conform. The prior §34 entry remains a
  historical record of the earlier direction.
- **Migration consideration:** implemented locally. Product copy, section
  names, screenshots, evaluation evidence, runtime behavior and production
  deployment are unchanged.

### 2026-08-11 exact section names in landing navigation

- **Problem:** the header used shortened labels for five of seven sections and
  omitted Why AI? and Your Role, so the navigation did not represent the page
  structure. The brand also repeated the generic `Product case study` subtitle.
- **Rationale:** show all seven sections in the header and make every label
  match its numbered section exactly. Keep the desktop header compact with a
  dedicated navigation row. On narrow screens the header stops being sticky
  and the links use a two-column grid so every section name remains visible.
- **Affected surfaces:** `docs/case-study.html`; `docs/styles.css`; this file
  (§§5, 6.3, 22, 34).
- **Compatibility impact:** abbreviated `Problem`, `Approach`, `Product` and
  `Learnings` labels, the five-item nav, hidden mobile nav and the `Product case
  study` brand subtitle no longer conform.
- **Migration consideration:** implemented locally. Product copy, screenshots,
  evaluation evidence, runtime behavior and production deployment are unchanged.

### 2026-08-11 seven-part hiring-manager case-study structure

- **Problem:** the Product / Decisions / Evidence narrative made the working
  product visible but buried the problem, AI rationale, candidate ownership and
  learnings. The live-prototype CTA also invited readers into an artifact the
  author now wants to demonstrate only through controlled screenshots.
- **Rationale:** use the InstitutePM seven-part framework as a scan-friendly
  case-study backbone. Lead with the time spent repeatedly checking several
  housing-provider websites, state early that rules own matching and AI owns
  only parser QA, give role and approach their own sections, keep the existing
  seven-screen carousel as product proof, and separate measured synthetic
  results from conditional next-test learning. Remove every live-prototype CTA.
- **Affected surfaces:** `docs/case-study.html`; `docs/styles.css`;
  `CASE_STUDY.md`; this file (§§5, 6, 8, 9, 19, 22, 27, 34).
- **Compatibility impact:** the three-section header navigation, Product hero,
  combined Decisions contribution note, Evidence opening cards and `Open
  prototype` action no longer conform. Historical §34 entries remain records of
  earlier states rather than current instructions.
- **Migration consideration:** implemented as a local landing-page and Markdown
  restructure. Existing screenshots, product behavior, evaluation artifacts,
  final metrics and production deployment are unchanged.

### 2026-08-10 evidence-led AI QA configuration selection story

- **Problem:** the public case named only the final Terra-high configuration,
  so a reader could see the destination but not the product judgment behind
  model tier, reasoning effort, cost control, and the final AI boundary.
- **Rationale:** explain the progression without publishing historical scores.
  The story starts with lower-cost Luna settings, moves to Terra and higher
  reasoning only after predefined gates are missed, and makes clear that the
  accepted result also required narrowing AI to source-quote extraction while
  deterministic code made the comparison.
- **Affected surfaces:** `docs/case-study.html`; `docs/styles.css`;
  `CASE_STUDY.md`; this file (§§13, 22, 34).
- **Compatibility impact:** a final-configuration-only explanation no longer
  provides enough ownership context. Intermediate experiment scores, latency,
  and calibration tables still do not belong on public surfaces.
- **Migration consideration:** implemented in the local review sandbox as a
  three-step configuration-selection sequence. Evaluation artifacts, product
  runtime, final metrics, and production deployment are unchanged.

### 2026-08-10 canonical listing-only result and conditional notifications

- **Problem:** the bot sent a separate field-level explanation before every listing card, adding conversational noise the author does not want. At the same time, public copy underplayed the implemented notification loop even though fast delivery is central when high-demand listings may disappear quickly.
- **Rationale:** make the canonical listing card the complete user-facing result. Keep deterministic reasons internal to matching and tests, but never send them as a separate user message. Present deduplicated notifications as a core capability: when `BOT_BACKGROUND_ENABLED=true`, the runtime collects, verifies and sends each newly matched listing once; on-demand matching remains available in either mode.
- **Affected surfaces:** `main.py`; `.env.example`; `tests/test_bot_ui.py`; `tests/test_guided_tour.py`; `docs/case-study.html`; `CASE_STUDY.md`; `README.md`; `docs/PROJECT_CONTEXT.md`; `docs/CURRENT_STATUS.md`; this file (§§2–3, 6–10, 20, 22, 27–34).
- **Compatibility impact:** `Why this listing matched`, reason bullets, reason screenshots, `criteria → reasons → card`, and any requirement to explain each match in a separate message no longer conform. Copy saying background delivery cannot start also no longer conforms; the feature is conditional, not absent.
- **Migration consideration:** removed the separate message from on-demand and legacy-tour delivery, restored the existing background-task lifecycle behind its configuration flag, and updated active tests and public/docs surfaces. Internal `MatchDecision.reasons` remain available for deterministic diagnostics and are not a user-facing feature. Historical §34 entries and frozen assets remain evidence of prior iterations, not current requirements.

### 2026-08-10 canonical user noun with one Audience exception

- **Problem:** the product's audience noun drifted between two terms across the hero, bot, evidence, research language and technical documentation, making otherwise identical roles sound like different actors.
- **Rationale:** use `user` / `users` for every product action, workflow, outcome and research reference. Preserve the established audience label only in the dedicated landing metadata value, where it names the market segment rather than an actor in the flow.
- **Affected surfaces:** `docs/case-study.html`; `CASE_STUDY.md`; `main.py`; `docs/CURRENT_STATUS.md`; active files under `eval/`; this file (§§17, 20, 22, 24, 34).
- **Compatibility impact:** alternative person nouns outside the landing's `Audience` value no longer conform, including compounds such as `-facing`, `-flow`, `-outcome` and `-research`.
- **Migration consideration:** fixed across current public, runtime, normative and active evaluation sources. Frozen artifacts under `eval/runs/` retain their recorded wording because changing them would rewrite historical evidence; they are not active product copy.

### 2026-08-10 product-first landing narrative with consolidated disclosure

- **Problem:** the hero named WBS listings but did not clearly state that FlatFeed helps people find apartments in Berlin, while repeated synthetic-adapter and disabled-runtime qualifiers made the product read like a technical disclaimer before its value was understood.
- **Rationale:** describe category, geography, audience and implemented functionality at the point where each capability appears. Collect current demo source, disabled runtime paths, offline-model integration status and unvalidated outcomes in one final disclosure block. Keep synthetic labels beside evaluation metrics and the photo credit beside its image because those qualifiers define the evidence itself rather than the general prototype setup.
- **Affected surfaces:** `docs/case-study.html`; `docs/styles.css`; `CASE_STUDY.md`; this file (§§6, 22, 23, 34).
- **Compatibility impact:** the previous hero, carousel intro, decision cards and opening Evidence split no longer conform because they repeat setup limitations before the reader reaches the product story. The AI evaluation must still retain its synthetic label and real counts at the metric level.
- **Migration consideration:** implemented in the local review sandbox. All product setup and unvalidated outcomes now appear immediately before the final CTA; the Schlangenbader Straße 91 attribution stays adjacent to the screenshot. No product behavior, evaluation result, deployment or production surface changed.

### 2026-08-10 landing hierarchy and workflow comparison refinement

- **Problem:** the header presented two competing actions, the carousel repeated a provenance kicker already explained in adjacent copy, the screenshot was slightly too small at common desktop sizes, and the workflow comparison overstated the demo as a live-source handoff.
- **Rationale:** keep one visually primary Repository action in the header, retain the synthetic boundary in the carousel description, and size the portrait capture from both viewport height and a bounded width so the image plus controls remains visible on short desktop screens. Rewrite the comparison around repeated filters, WBS/rent comparison, consistent Telegram formatting and fixed-rule reasons. Disclose the address-aligned showcase photo directly beside its screenshot. Describe the implemented multi-source architecture separately from the single enabled synthetic adapter, and frame hosted-model work as offline prototype experiments rather than a user-facing feature.
- **Affected surfaces:** `docs/case-study.html`; `CASE_STUDY.md`; `README.md`; this file (§§2, 5, 6, 9, 14, 19, 22, 23, 34).
- **Compatibility impact:** the top-bar `Open prototype` action and unfilled Repository link no longer conform. The carousel provenance kicker is removed, while the adjacent sentence still states that the captures come from the working prototype and the catalog is synthetic. The showcase photo now has required Bodo Kubrak / CC0 attribution and synthetic-terms disclosure. No copy may claim that the synthetic demo opens a live source or application flow.
- **Migration consideration:** implemented in the local review sandbox. Product runtime, screenshot assets, matching behavior, evaluation metrics, and the final summary CTA are unchanged; publication remains a separate approval step.

### 2026-08-07 text-only hero and seven-screen product carousel

- **Problem:** one listing screenshot in the hero showed only the final output and competed with the product proposition. The newly captured working flow contains the stronger proof: setup, saved state, on-demand search, and the resulting listing in one sequence.
- **Rationale:** keep the hero focused on the user problem and move visual evidence into one accessible, non-automatic carousel immediately after it. Seven short numbered captions orient an external reader without repeating the Telegram copy; a single carousel-level statement preserves the synthetic-catalog boundary at the same reading depth.
- **Affected surfaces:** `docs/case-study.html`; `docs/styles.css`; `docs/carousel.js`; seven `docs/assets/flatfeed-flow-*.png` captures; this file (§§5, 6, 14, 15, 22, 32, 34).
- **Compatibility impact:** the two-column hero, macOS-style screenshot frame, three-capture walkthrough, and hidden demo-era walkthrough no longer conform. The product proposition, working-prototype status, synthetic-data boundary, deterministic matching story, and Telegram implementation remain unchanged.
- **Migration consideration:** implemented as a local review sandbox. Publication remains a separate approval step; the previous screenshot assets stay in the repository but are no longer referenced by the case page.

### 2026-08-07 carousel controls below the screenshot

- **Problem:** centering the existing previous / position / next controls under the complete two-column slide separated them from the screenshot they control.
- **Rationale:** place the three-part control row in the left column directly below the screenshot and inside the carousel frame. Remove the separate position-indicator row so the screenshot has one clear control system. This follows the supplied reference without introducing additional navigation.
- **Affected surfaces:** `docs/case-study.html`; `docs/styles.css`; `docs/carousel.js`; this file (§§5, 15, 22, 34).
- **Compatibility impact:** previous/next behavior, accessible names, keyboard navigation, and swipe gestures remain unchanged. The seven direct-position indicators are removed; on narrow screens the control row remains directly below the screenshot in the same single-column reading flow.
- **Migration consideration:** fixed in the local review sandbox. No product copy, image assets, matching behavior or evaluation evidence changed.

### 2026-08-06 restored saved-filter product prototype

- **Problem:** the guided scenario presented FlatFeed as a portfolio demo rather than the normal product a user would operate. A working saved-filter flow already existed, so demo framing hid stronger evidence: personal criteria, persisted state, on-demand matching, and field-level reasons.
- **Rationale:** restore the narrow user-facing workflow while keeping every honesty boundary. The user can save and edit four criteria, request up to three deterministic matches, see reasons before each canonical card, reset the filter, or delete saved data. The catalog remains synthetic, background notifications remain disabled, and AI QA remains outside the public user path.
- **Affected surfaces:** `main.py`; `tests/test_bot_ui.py`; `tests/test_guided_tour.py`; `README.md`; `CASE_STUDY.md`; `docs/PROJECT_CONTEXT.md`; `docs/CURRENT_STATUS.md`; `docs/agent-workflow.md`; `docs/case-study.html`; Telegram capture assets under `docs/assets/`; this file (§§1–3, 5–11, 17–22, 25–34).
- **Compatibility impact:** demo-only `/start`, `Try the demo`, `Replay the demo`, `Demo 1/2`, `Demo 2/2`, no-persistence rules, and a case-study-only walkthrough no longer describe the current product. Old `tour:*` callbacks remain safe compatibility routes but redirect to the current filter status and do not restore tour state.
- **Migration consideration:** fixed now in code, tests, active documentation, and landing copy. Replace all three Telegram captures with current working-product screens before publication. Do not reintroduce the dashboard, public admin/model controls, unfiltered catalog browsing, live-source claims, or background user notifications.

### 2026-08-06 captured walkthrough as the public product surface

- **Problem:** a live Telegram handoff adds app-switching and account friction to a portfolio reader who only needs to understand the implemented flow. It also lets the tiny synthetic scenario be mistaken for a public product entry point.
- **Rationale:** the case study itself now carries the complete public walkthrough through a captured Telegram session. Telegram remains a working implementation artifact and source of the capture, but the page contains no Telegram CTA or deep link. This keeps the proof inspectable without hiding its synthetic boundary.
- **Affected surfaces:** `docs/case-study.html`; `README.md`; `docs/PROJECT_CONTEXT.md`; `docs/CURRENT_STATUS.md`; this file (§§6, 8–9, 19, 22, 34).
- **Compatibility impact:** `Open in Telegram`, `Explore the replay`, and copy that frames the bot as the public surface no longer conform on the case page or public documentation. Bot-local `Try the demo` and `/start` remain unchanged.
- **Migration consideration:** fixed now in the public case-study source and documentation. The bot runtime, matching logic, screenshot asset, evaluation data, and results are unchanged.

### 2026-08-06 three-screen Telegram walkthrough

- **Problem:** the hero listing-card capture proved the normalized output but did not show the preceding filter contract or the deterministic reasons, so a reader could not reconstruct the two-step experience from the landing alone.
- **Rationale:** keep the final card as the strongest hero proof and add two real Telegram captures below the product comparison: Demo 1/2 for the four criteria and Demo 2/2 for the field-level match reasons. The page now documents criteria → reasons → card without a Telegram link or simulated interaction.
- **Affected surfaces:** `docs/case-study.html`; `docs/styles.css`; `docs/assets/flatfeed-telegram-filter.png`; `docs/assets/flatfeed-telegram-match-reasons.png`; `docs/assets/flatfeed-telegram-showcase.png`; `docs/CURRENT_STATUS.md`; this file (§§5, 6, 22, 34).
- **Compatibility impact:** the earlier one-capture Product layout no longer represents the complete public walkthrough. The hero frame, synthetic labeling, Telegram runtime and deterministic matching contract remain unchanged.
- **Migration consideration:** implemented now with author-supplied captures. The two walkthrough frames are equal-width on desktop, stack at ≤56rem, and crop only the Telegram composer area; product code and evaluation evidence are unchanged.

### 2026-08-05 product-value-first Telegram story

- **Problem:** the demo repeatedly disclosed synthetic data but did not first explain the repeated manual work FlatFeed is designed to replace. The browser replay then looked like a second product interface rather than evidence from the Telegram prototype. AI quality evidence was visible only as a scorecard, without a compact explanation of its bounded relationship to the user-facing path.
- **Rationale:** product value must precede prototype limitations. `/start` now contrasts the manual task with the intended flow, then demonstrates one fixed scenario. The case study uses captured Telegram evidence and a non-interactive product walkthrough so it remains available without a running bot. The optional reliability explanation and a case-study boundary block show AI as separately evaluated admin QA, never as a user-facing decision-maker.
- **Affected surfaces:** `main.py`; `tests/test_guided_tour.py`; `docs/case-study.html`; `docs/styles.css`; `docs/demo-listing.html`; `README.md`; `CASE_STUDY.md`; `docs/PROJECT_CONTEXT.md`; `docs/CURRENT_STATUS.md`; this file (§§1, 5, 6, 7, 9, 22, 34).
- **Compatibility impact:** `Try the demo`, `Temporary filter`, `Find matches`, `Why this matched`, `How matching works`, browser replay, and per-listing browser detail are no longer the public product narrative. `user` is the canonical noun for product behavior and benefits.
- **Migration consideration:** implemented in code and local case-study source. Replace the existing hero capture with current Telegram screenshots before publication; until then the locally rendered case study uses the existing truthful result capture rather than a fabricated replacement.

### 2026-08-05 browser replay and synthetic listing details

- **Problem:** the Telegram bot was the only interactive proof, yet it requires an externally hosted process and a Telegram account. The case-study hero showed a static screenshot, so a hiring manager could not inspect the two-step flow without leaving the portfolio. `Open listing` then led to a generic disclosure rather than the specific synthetic card they had just seen.
- **Rationale:** make the reproducible, no-account replay the primary portfolio interaction while keeping Telegram as an optional proof of the same flow. The browser version is explicitly a static replay: it contains one fixed authored scenario and no backend, user state, live collection, notifications, or model call. A detail view can make the synthetic card inspectable without pretending it is a landlord or application page.
- **Affected surfaces:** `docs/case-study.html`; `docs/replay.js`; `docs/demo-listing.html`; `docs/demo-listing.js`; `docs/styles.css`; `main.py`; `README.md`; `CASE_STUDY.md`; `docs/PROJECT_CONTEXT.md`; `docs/CURRENT_STATUS.md`; this file (§§1, 5, 6, 7, 22, 34).
- **Compatibility impact:** the hero screenshot is superseded by the browser replay; `Explore the replay` is the primary CTA and `Open in Telegram` is secondary. Demo 2/2 no longer reports an active-match count, which did not add decision value in a single guaranteed scenario. `docs/demo-listing.html?id=0001` now renders the actual fixed synthetic detail fields instead of a generic disclosure.
- **Migration consideration:** fixed now in the source tree. GitHub Pages remains on the prior version until this work is reviewed, committed, and deployed. The static replay is not a substitute for a live bot deployment and must not be described as one.

### 2026-08-05 demo-only public prototype

- **Problem:** the public bot combined a tightly authored guided scenario with a second saved-filter mode over the same tiny synthetic catalog. Arbitrary filters could return empty or artificial-looking results, while persistence and `Show matches` suggested a usable housing product even though there is no live ingestion or real notification service.
- **Rationale:** make the public artifact do one job well. `/start` now removes legacy reply keyboards and leads into one guaranteed, non-persistent scenario that executes the real deterministic matcher, local activity check, field-level reasons, and canonical card. The product concept may still describe a future saved-filter feed, but the implemented Telegram evidence is explicitly the guided scenario.
- **Affected surfaces:** `main.py`; `tests/test_guided_tour.py`; `tests/test_bot_ui.py`; `README.md`; `CASE_STUDY.md`; `docs/case-study.html`; `docs/PROJECT_CONTEXT.md`; `docs/CURRENT_STATUS.md`; this file (§§1–3, 6–9, 17–22, 28–34).
- **Compatibility impact:** `Show matches`, `Filter`, `Set up my filter`, `Set up my own filter`, `Use this demo filter`, `/filter`, and `/matches` are retired public actions. The command menu contains only `/start` and `/help`; old commands and callbacks redirect to the demo without writing state. Background user notifications never start. `/delete` remains unadvertised only to remove legacy records.
- **Migration consideration:** public migration completed now. Legacy filter/storage/delivery helpers remain in code for safe backward compatibility but are not reachable as a current product mode. A future personalized or live-feed phase requires a new product decision, permitted sources, and new evidence; it must not be re-enabled by exposing the dormant helpers.

### 2026-08-04 guided-tour notification boundary

- **Problem:** Demo 2/2 repeated the three-card limit immediately after the user had already requested matches, but did not explain that a synthetic prototype cannot provide real alerts about newly listed apartments. The optional pipeline explainer could then imply the opposite by describing automatic delivery without the live-source boundary.
- **Rationale:** replace redundant capacity copy with the missing product limitation at the moment a visitor sees the result. The bot now states that the example is synthetic and that the prototype does not monitor live housing sources or send notifications about real new listings. The optional synthetic background-delivery implementation remains unchanged and stays documented as a technical capability.
- **Affected surfaces:** `main.py`; `tests/test_guided_tour.py`; `tests/test_bot_ui.py`; `README.md`; `docs/PROJECT_CONTEXT.md`; this file (§§7.6, 34).
- **Compatibility impact:** the Demo 2/2 sentence `In the regular flow, Show matches can return up to three active listings.` is no longer approved tour copy. The `How matching works` explainer and `/help` must not imply that synthetic background delivery is live housing monitoring.
- **Migration consideration:** fixed now across bot copy, focused tests, and active technical documentation. The three-card limit, matching behavior, optional background-delivery code, case-study evidence, and evaluation numbers are unchanged.

### 2026-07-31 bot-only prototype and two-step demo

- **Problem:** the public Telegram experience exposed four competing global actions (`Show matches`, `Filter`, unfiltered catalog browsing, and a public Admin view), then duplicated model evidence through a deterministic mock QA branch and a separate Streamlit dashboard. The accepted 600-case hosted-model result already lives on the case-study surface, so the extra operations UI made the user workflow slower to understand and created multiple evidence surfaces that could drift.
- **Rationale:** the portfolio now separates proof by job. Telegram demonstrates the implemented user interaction in two taps — temporary filter, then a card produced by the real deterministic matching and activity-check path. The case study and frozen eval artifacts demonstrate the hosted-model experiment. `Show matches` and `Filter` are the only persistent product actions; unfiltered browsing, public admin controls, mock fault injection, Telegram metrics, and the dashboard are removed. Optional background notifications and direct private admin alerts remain implementation capabilities, but UI copy only says notifications are on when `BOT_BACKGROUND_ENABLED=true`.
- **Affected surfaces:** `main.py`; `flatfeed/config.py`; `flatfeed/ai_qa.py`; removed `flatfeed/dashboard/`; `.env.example`; `requirements.txt`; `tests/test_bot_ui.py`; `tests/test_guided_tour.py`; `tests/test_ai_qa.py`; removed `tests/test_admin_ui.py` and `tests/test_dashboard.py`; `README.md`; `CASE_STUDY.md`; `docs/PROJECT_CONTEXT.md`; `docs/CURRENT_STATUS.md`; `docs/agent-workflow.md`; this file.
- **Compatibility impact:** old keyboards carrying `tour:4`, `tour:5`, `tour:inject`, `tour_fb:*`, `settings:catalog`, `settings:dashboard`, or `settings:ai_qa_*` no longer have handlers. `/listings` and `/aiqa_status` are removed. The guided path changes from three required steps plus optional QA to `Try the demo` → `Find matches`; `How matching works` becomes optional after the result. Saved-filter requests return at most three cards instead of ten.
- **Migration consideration:** completed in this change. Dashboard code, configuration, dependencies, and tests are deleted; active docs now describe the bot-only boundary. Historical §34 entries remain unchanged as decision history and MUST NOT be read as current behavior. Public evaluation numbers and frozen run artifacts are unchanged.

### 2026-07-31 canonical tour card and one-way listing disclosure

- **Problem:** Demo 2/2 prepended matching explanation to the listing caption and attached tour actions to that same message, so the portfolio visitor did not see the product's canonical listing card as a normal user would. Its `1 of N` wording also failed to explain that the walkthrough intentionally shows one example while `Show matches` can return up to three. The static synthetic-listing disclosure then linked back into the Telegram tour even though the visitor had just arrived from a Telegram card.
- **Rationale:** one message now has one purpose. Step 2 explains the count and deterministic reasons, sends the exact canonical card, then sends follow-up actions. The disclosure page remains a one-way honesty surface with one useful next action: the case study. Empty custom-filter results explicitly belong to the limited synthetic catalog, not the live Berlin market. The authored catalog is not expanded to fabricate coverage of every possible filter combination.
- **Affected surfaces:** `main.py`; `docs/demo-listing.html`; `tests/test_guided_tour.py`; `tests/test_bot_ui.py`; `tests/test_demo_listing_page.py`; `README.md`; `docs/PROJECT_CONTEXT.md`; `docs/CURRENT_STATUS.md`; this file.
- **Compatibility impact:** `send_match_to_chat` no longer accepts `text_prefix`; Demo 2/2 now emits explanation, card, and actions as separate messages. The synthetic-listing page no longer contains `Try the guided tour` or a `t.me` link. Matching rules, the three-card regular limit, the 15-case parser regression set, and evaluation numbers are unchanged.
- **Migration consideration:** completed in this change. Tests enforce the canonical-card separation, limited-catalog empty-state wording, and removal of the circular bot CTA. Historical §34 entries remain unchanged.

### 2026-07-30 feasible next-test boundary

- **Problem:** the public Next test proposed a permitted live-source pilot even
  though the prototype has no permitted live dataset or source integration.
- **Rationale:** stop synthetic AI tuning after the accepted 600-case result
  and test the user-flow hypothesis with the existing synthetic Telegram
  demo. Keep real-source access visible as a separate feasibility risk instead
  of presenting it as the next executable step.
- **Affected surfaces:** `docs/case-study.html`, `CASE_STUDY.md`,
  `docs/CURRENT_STATUS.md`, and this document (§§22, 34).
- **Compatibility impact:** Next test no longer includes real-source freshness,
  notification timing, or live AI review metrics. It measures understanding and
  usability of the current synthetic flow.
- **Migration consideration:** updated now across both case-study surfaces and
  the current-status handoff. Product code and evaluation artifacts are
  unchanged.

### 2026-07-30 extraction-v1 final evidence update

- **Problem:** the public case and current-status docs still described the
  earlier failed rooms result after a new frozen 600-case extraction-v1
  evaluation completed.
- **Rationale:** replace stale public evidence with the latest final run while
  preserving its limits. Show the accepted synthetic decision, every aggregate
  and field result, the one invalid check, exact run cost, and the explicit
  boundary that no product integration or real-source accuracy was proven.
- **Affected surfaces:** `README.md`, `CASE_STUDY.md`,
  `docs/case-study.html`, `docs/CURRENT_STATUS.md`,
  `docs/PROJECT_CONTEXT.md`, `eval/AI_QA_EVAL_PLAN.md`,
  `eval/AI_QA_FAILURE_ANALYSIS.md`, `scripts/check_eval_numbers.py`, and this
  document (§§13, 22, 34).
- **Compatibility impact:** the canonical public result is now 300/300 planted
  errors found and localized, 0/300 false alerts, and 599/600 usable checks.
  Earlier rooms-failure results remain only as experiment history.
- **Migration consideration:** local public and technical sources were updated
  together and are verified from the final run artifacts. Deployment remains a
  separate action.

### 2026-07-29 product-flow and evidence clarity pass

- **Problem:** the public workflow elevated activity checks and notification
  deduplication—expected delivery controls—above the actual user value. The
  Decisions heading claimed trust without source-completeness evidence, the
  first decision framed missing data as a product achievement, and the
  Demonstrated list omitted both the synthetic qualifier and the strongest
  hosted-model result. The next-test signals mixed several unexplained metrics.
- **Rationale:** describe the intended flow as Filter → Collect → Prepare →
  Match → Deliver, while stating the current source is synthetic at the same
  reading depth. Surface the implemented S-/U-Bahn walking-time estimates,
  frame the saved filter as an initial shortlist rather than a final
  eligibility decision, and summarize the strong overall AI result together
  with its failed rooms target. Explain the pilot through direct value and
  measurable timings instead of abstract trust language.
- **Affected surfaces:** `docs/case-study.html`, `CASE_STUDY.md`, `README.md`,
  the guided-tour copy in `main.py`, `tests/test_guided_tour.py`, and this
  document (§§20, 22, 25, 28, 34).
- **Compatibility impact:** public filter lists use `WBS type`; hero metadata
  says that AI flags suspected parser errors for admin review; the public
  workflow no longer presents activity checks or notification deduplication as
  features. Those controls remain implemented and documented in
  `docs/PROJECT_CONTEXT.md`.
- **Migration consideration:** updated now across the case page, Markdown case,
  README summary, and guided tour. Parser, matching, source-activity, delivery
  deduplication, transit calculations, datasets, and final evaluation numbers
  are unchanged.

### 2026-07-29 public regression-count removal

- **Problem:** the Demonstrated block presented the 15 authored synthetic
  parser cases as product evidence. The count describes a development safety
  check, but does not establish performance on real listing formats or value
  for users.
- **Rationale:** retain the deterministic regression suite because it catches
  parser regressions cheaply, but keep its authored-case count in technical
  documentation. Public case-study evidence should focus on the runnable user
  flow, explicit limitations, and the separately labelled final AI evaluation.
- **Affected surfaces:** `docs/case-study.html`, `CASE_STUDY.md`, `README.md`,
  and this document (§§3, 13, 25, 27, 34).
- **Compatibility impact:** the HTML and Markdown Demonstrated lists no longer
  mention the authored regression count. README and the runnable eval remain
  responsible for recording and checking that count.
- **Migration consideration:** fixed now across the two public case-study
  surfaces and their governing copy rules. Parser code, synthetic fixtures,
  tests, and eval behavior are unchanged.

### 2026-07-29 hero role-metadata removal

- **Problem:** the hero metadata value `Product lead & builder` did not explain
  a concrete responsibility, repeated ownership information available deeper
  in the case, and implied team leadership in a solo prototype.
- **Rationale:** keep the hero metadata limited to facts that help a reader
  decode the product immediately: audience, prototype status, and the bounded
  AI role. Preserve the detailed, artifact-linked ownership statement in the
  Decisions contribution note and `CASE_STUDY.md`.
- **Affected surfaces:** `docs/case-study.html` and this document (§§6, 22,
  34).
- **Compatibility impact:** the hero metadata now contains three items and no
  candidate-role label. Candidate ownership language itself is unchanged.
- **Migration consideration:** fixed now on the public case page. The Telegram
  prototype, dashboard, Markdown case, eval artifacts, and numerical evidence
  are unchanged.

### 2026-07-27 reader-language and source-aggregation narrative pass

- **Problem:** browser comments from the author identified public copy that was
  technically defensible but hard to understand without repository context:
  `fail closed`, `evaluation contract`, `test harness`, `field-level
  guardrails`, and `model inference only`. The hero repeated `Product case
  study`, the secondary CTA skipped Product, the Product heading and its
  explanation were bottom-aligned, and the third decision elevated
  notification deduplication from a baseline control into a portfolio-level
  product choice. The unvalidated list also framed source risk as one-source
  performance even though the product ambition is a complete Berlin WBS feed.
- **Rationale:** keep the four-question Product / Decisions / Evidence / Next
  test structure, but explain mechanisms in reader language. Move `Product case
  study` beside the brand and keep the prototype boundary in the hero kicker;
  route the secondary CTA to Product; top-align section-heading columns; use
  `user` for product actions and target-audience references
  group. Replace the weak reliability decision with the more material choice
  of one normalized user flow across permitted source adapters, while stating
  that only one synthetic adapter is implemented. Replace public `cards` jargon
  with listings, summaries, or a consistent Telegram format. The AI result
  remains a separate synthetic evaluation with the same final rejection,
  counts, thresholds, and stopping decision.
- **Affected surfaces:** `docs/case-study.html`, `docs/styles.css`,
  `CASE_STUDY.md`, `scripts/check_eval_numbers.py`, and this document (§§13,
  16, 20, 22–24, 28, 34).
- **Compatibility impact:** the current canonical evidence label is `AI QA
  evaluation · synthetic data · 600 listings`; `Offline` is no longer part of
  the public label, while the adjacent text explicitly says the model was not
  integrated into the product. The ownership note no longer lists the
  supporting dashboard or test harness as primary product outputs, but keeps
  the approved Claude Code and Codex collaborator disclosure. The canonical
  third public decision is now one normalized product flow across sources, not
  reliability-before-source-count.
- **Migration consideration:** HTML and Markdown were updated together. The
  eval-number checker accepts either direct rejection wording (`configuration
  not accepted`) or the equivalent sentence (`did not accept the
  configuration`) and still verifies every final metric, field result, cost,
  and stopping rationale. Product runtime, dashboard code, datasets, eval
  artifacts, and numerical evidence are unchanged.

### 2026-07-24 final-result public case-study narrative

- **Problem:** the landing led with a stronger 280-case validation scorecard and
  reduced the final 600-listing holdout to a footnote. A first-time reader could
  not see how the metrics were calculated, why both aggregate and field-level
  gates existed, or why rooms made the final decision a fail.
- **Rationale:** the final independent run is the most honest public result.
  Present it as a complete PM case rather than a promotional scorecard:
  experiment setup, metric purpose and calculation, all field results, failure
  analysis, stopping decision, and a bounded inference-cost scenario. Strong
  aggregate numbers remain visible, but cannot override the rejected rooms
  guardrail. Earlier iteration scores stay out of public surfaces.
- **Affected surfaces:** `docs/case-study.html`, `docs/styles.css`,
  `CASE_STUDY.md`, `scripts/check_eval_numbers.py`,
  `docs/CURRENT_STATUS.md`, and this document (§§13, 22–23, 26–27, 34).
- **Compatibility impact:** the public `Synthetic frozen validation` block and
  its 280-case numbers are superseded. The current canonical evidence label is
  `Offline AI QA evaluation · synthetic data · 600 listings`. The landing may
  now show the seven field results and one explicitly bounded inference-cost
  scenario; this is not permission for historical run tables or production-cost
  claims.
- **Migration consideration:** migrate the HTML and Markdown case studies
  together, validate every number from final locked-holdout artifacts, keep the
  user-approved stopping paragraph verbatim, and verify desktop/mobile reading
  order before handoff. Product runtime and experiment artifacts remain
  unchanged.

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
- **Rationale:** name the user problem, matching and AI guardrails, and
  evaluation contract as the candidate's decisions while preserving the
  approved coding-collaborator disclosure. Invite the reader to try the user
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
  Learn / Measure / Decide signals to include user adoption, source
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
  live-source coverage, freshness, and user outcomes as open questions.
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
  field guardrail passed. Keep the user workflow ahead of the QA evidence,
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
  Product Scorecard gates. Keep the product promise and user workflow first;
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

- **Problem:** a copy review against the hiring-manager goals found three defect groups. (a) Rule violations and defects: workflow step 01 said `maximum cold rent` although §20 prohibits "cold rent" and the hero glosses Kaltmiete; the tour's plural suffix `"es"` would render "matching listing**es**" for any 2+ match count (latent today — the current catalog yields exactly 1 match); the meta description said "explicit user filters" (plural) against the one-filter H1; one action carried three CTA labels (`Try the demo` / `Try the guided demo`); README said "failure controls" where CASE_STUDY.md said "reliability controls". (b) Residual specification language on reader-facing surfaces: noun chains ("synthetic-adapter state check", "background-delivery deduplication", "hosted-model AI QA" on a page that never mentions the mock provider), passive "are implemented", and `A → B · C` chains in tour step 3/3. (c) Wording a reader could challenge: H1 "tested as" reads as user-tested (which the Evidence section denies), "useful listing opens" names an undefined metric, "One matcher result" and "QA control" are insider terms.
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

- **Problem:** the public case and guided tour gave internal parser/AI QA mechanics, mock metrics, and a seven-part strategy narrative more weight than the user-facing product. Several phrases also exceeded the implementation boundary: four-field matching read as full eligibility, the synthetic adapter's local state check read as live-source verification, and optional background deduplication read as a guarantee for every card.
- **Rationale:** hiring-manager comprehension and factual defensibility take priority over feature count. The public story now centers on one temporary filter, one actual matcher result from the synthetic catalog, three product decisions, a Demonstrated / Not demonstrated evidence split, and one next validation. AI QA is a bounded optional branch, not the user path. Detailed eval diagnostics remain runnable engineering evidence instead of public product outcomes.
- **Affected surfaces:** `docs/case-study.html`, `docs/styles.css`, `CASE_STUDY.md`, `README.md`, `docs/demo-listing.html`, `docs/PROJECT_CONTEXT.md`, `main.py`, `tests/test_guided_tour.py`, and `scripts/check_eval_numbers.py`. This document's current rules in §§2–7 and 22–28 were updated to match.
- **Compatibility impact:** the guided tour's required path changed from five screens to three; `tour:3` remains a compatibility explainer, while the main step-2 button now routes directly to `tour:5`, rendered as Step 3/3. The QA simulation remains available from the final keyboard. Public 100%/exact-accuracy/mock-cost blocks and the dashboard mockup were removed. The delete confirmation now names its actual database scope.
- **Migration consideration:** fixed across current public and normative surfaces. Historical §34 entries and local plan files remain historical records and are not current requirements. A live-source test and user study remain future validation, not implementation claims.

### 2026-07-11 product-first demo rework: tour v2, dashboard restructure, case-study honesty fixes

- **Problem:** two independent audits (an internal tour walkthrough and Codex's `docs/PRODUCT_DEMO_AUDIT.md`) converged on the same diagnosis after the 2026-07-10 tour shipped: the demo told the story of "parser + AI QA" more strongly than the story of a complete product, which undersells the author as a Product Manager rather than an engineer. Specifics found and fixed: (1) the tour opened with product mechanics before the user's problem, and AI occupied roughly 3 of 5 beats; (2) step 2 built its listing card by directly formatting a pre-selected listing (`_listing_match_from_model`) instead of running the real matching predicate, so "this is what FlatFeed found" was a stronger claim than the tour actually demonstrated; (3) step 1 saved the demo filter to `users` immediately on `Start the tour`, before the visitor made any explicit choice; (4) the tour's closing screen showed a same-session-empty AI QA funnel (`Checked by AI: 0` etc.) — worse than no screen, since it promised measurability and delivered zeros; (5) `AI confidence: 70%` in the tour alert and the dashboard's demo block read as a calibrated model probability when the mock provider always returns a fixed 0.7/0.8 (`flatfeed/ai_qa.py`); (6) the case-study hero mockup showed a listing card (`District: Wedding`, `Demo street 12`, `610 EUR`/`760 EUR`) that does not match any real synthetic catalog case — Wedding normalizes to Bezirk `Mitte`, and no case has those values — while a second mockup in "What I built" showed dashboard tabs (`Overview` / `QA Review` / `Sources`) that have never existed in the real one-scroll Streamlit page; (7) `Open listing` pointed at `https://demo.flatfeed.local/...`, a domain that has never resolved publicly, so the card's only link looked broken to an external viewer; (8) the dashboard's own heading was "FlatFeed parser AI QA" with no product-pipeline or evidence/limitations framing.
- **Rationale:** the central thesis adopted for this pass — *FlatFeed turns Berlin's chaotic WBS-flat hunt into one reliable feed: filter once, get every active match once; reliability is the product, AI is one bounded quality control inside it* — governs every change below, and was chosen over Codex's more generic "FlatFeed solves a repeated user task" because it names the actual urgency (listings vanish within hours) and the actual mechanism (one filter, one-time delivery), which a generic phrasing loses. Two Codex recommendations were adopted with a **narrower scope** than proposed, for reasons recorded here so they are not silently re-widened: (a) Codex's "remove the fault-injection mini-game, replace with a static labeled case" was rejected — the interactive fault injection is the tour's only moment where a visitor *does* rather than reads the human-in-the-loop model, and removing it would have made "AI as a bounded control" a claim instead of a demonstration; it was compressed into one step (4/5) instead, which independently achieves Codex's stated goal (a 3-product/1-AI/1-evidence balance) without losing the interaction. (b) Codex's "any triage selection should proceed neutrally, never grade the visitor" was adopted, but the specific wording avoids both grading ("Correct —") and false neutrality that hides the ground truth: the new unified response opens with "Recorded for this demo only — nothing you tap is stored" for every label, then states as fact (not judgment) that the corrupted snapshot did contradict the listing text, so `Parser error` is the label an admin would confirm — informative without commenting on what the visitor personally chose. Screen 2's "Why it matched" reasons are a deliberate, scoped exception to the §30 default that user-facing match reasons stay internal (recorded in §30's row) — chosen because proving the *real* `is_listing_match` predicate ran (not a hand-picked result) is the single highest-value fix Codex's audit identified for trust in the tour, and the reasons are read-only, already-computed `MatchDecision.reasons` output, not a new explanation feature. The empty funnel is not backfilled with seeded numbers (an option considered and rejected in an earlier working session): a mock-provider self-check trivially catches its own injected faults, so seeded metrics would read as circular, not measured. Screenshots replacing HTML mockups (author decision, resolves the §30 "Real screenshots vs HTML mockups" row — that row is removed from §30 as resolved) ship in two phases: this change corrects the mockup *values* to the real, current Lichtenberg tour-catalog listing (interim truthful state, since the mockups are what ships today) and removes the fabricated dashboard tabs; real screenshots replace the HTML mockups entirely once the author captures them from a live tour session and a live dashboard render (tracked as follow-up, not done here — an agent cannot drive a Telegram client to capture bot screenshots). The real OpenAI QA run (which would let the funnel return with genuine, non-circular numbers) and moving "Why AI?" after the product sections plus adding the two-path (main-flow vs. AI-QA-loop) diagrams are explicitly deferred by the author — nothing in this entry claims or depends on either.
- **Affected surfaces:**
  - `main.py` — tour rewritten step-by-step: step 1 no longer calls `save_fixed_preferences` (ephemeral filter); a new `_tour_candidate_matches()` runs `is_listing_match` over every active/parsed listing and step 2 runs it through the same `_verified_active_matches` activity-check path production delivery uses; step 3 is a new "Rules make the decision" pipeline explainer (replaces the old raw-text parsing deep-dive, which moved to the dashboard); step 4 is a new AI-framing screen whose button triggers the existing `tour:inject` fault flow (fault-note header now reads `Simulated parser fault`; `_format_ai_qa_review` gained an `include_confidence` parameter mirroring `include_cost`, both `False` for the tour); the triage response function collapsed from a graded Correct/Noted split into one neutral response for all three labels; step 5 replaced the AI QA funnel with `Working now` / `Measured on synthetic data` (a live `len(load_golden_set())` count) / `Not yet proven`, and gained `tour:save_filter` (writes the derived preferences only now, on explicit request) alongside the existing wizard entry point (`settings:filter`, reused rather than duplicated); `_load_tour_funnel`/`_tour_rate_line` were deleted (dead code, no remaining caller). A latent bug was found and fixed in the same change: `_select_tour_listing()` requires transit enrichment data that a fresh `scripts/ingest_synthetic.py` run does not populate (enrichment is normally lazy, triggered by the bot's own matches/listings handlers) — `_send_tour_screen_1` now calls `enrich_missing_transport_walk` itself so the tour is not silently broken as the very first interaction after a catalog refresh.
  - `synthetic/generator.py`, `flatfeed/ingestion/synthetic.py`, `flatfeed/db/seed.py`, `docs/demo-listing.html` (new) — the synthetic listing URL moved from the never-resolving `https://demo.flatfeed.local/listings/<id>` to `https://mich-mayer.github.io/flatfeed/demo-listing.html?id=<id>`, a real static page (linked from `case-study.html`'s hero figcaption) disclosing that the listing is synthetic and pointing back to the case study and the tour. `SYNTHETIC_BASE_URL` is now defined once in `synthetic/generator.py` (the URL's actual point of construction) and imported by `flatfeed/ingestion/synthetic.py` instead of being duplicated as a second literal — the two constants had silently matched by coincidence before this change, which is exactly the kind of drift this consolidation prevents. `check_synthetic_listing_active`'s prefix check was updated for the new query-string URL shape. The local DB was re-ingested (upsert-by-URL: old-URL rows are marked `removed_from_source` and preserved in history, matching the product's own reliability semantics; the `users` table is untouched by ingestion).
  - `flatfeed/dashboard/streamlit_app.py` — restructured into the five product-operations sections listed in §8, added `fmt_share`, added a live `eval.run_eval`-backed parsing-accuracy section with a raw-text→fields worked example (reusing the same tour-listing selection heuristic as `main.py`, duplicated locally since the dashboard cannot import `main.py` without triggering bot router registration), added the `-demo`-suffix exclusion filter to `_load_review_rows` (defense in depth, per §7.6), labeled mock `AI confidence` as illustrative, added an `if __name__ == "__main__":` guard (harmless under `streamlit run`, makes pure helpers safely importable — `tests/test_dashboard.py`, new) and fixed a pre-existing rendering bug where two unescaped `$..$` amounts in one caption made Streamlit render the text between them as LaTeX math.
  - `docs/case-study.html` — kicker changed so "AI" is not the first word (`Product case study · working prototype · synthetic data · 2026`); hero lede rewritten from pipeline-mechanics to the user-outcome thesis above, keeping §24 verb discipline (`I scoped` = candidate judgment; `rules... decide` = system behavior); hero mockup listing-card values corrected to the real Lichtenberg tour-catalog listing (`Rosenfelder Str. 12`, `Kalt 512,40 EUR`, etc.) instead of the invented Wedding/610/760 values; hero figcaption now links `t.me/FlatFeedBot?start=tour` as "the guided tour" — the one place this deep link appears on the page, deliberately not duplicated into a competing hero CTA (§9 one-primary-action-per-surface); the "What I built" dashboard mockup's fabricated tabs were removed and its table headers changed to match the dashboard's real "Where the parser is most at risk" columns, with a new figcaption disclosing it is a stylized illustration, not tabbed navigation. The 7-part structure, the `Why AI?` section and its position, the Results table and numbers, the footer, and `CASE_STUDY.md` were **not** touched — moving `Why AI?` and adding the two-path diagrams are explicitly out of scope for this change (see Migration consideration).
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

- **Problem:** a copy audit against GOV.UK/GDS, the Microsoft Writing Style Guide, and ONS metric guidance found (a) one concept with several names across surfaces — the catalog QA run was called "Run catalog QA" / "Parser check", the QA demo was called "QA demo" / "error demo", admin-confirmed errors were "Confirmed errors" / "Real parser errors" / "Real errors", pending triage was "Pending decision" / "Pending review" / "Pending alert feedback", the source column was "Catalog" vs the card's "Source", and single-field edits confirmed with "Done, settings updated." although the object is the *filter*; (b) AI-transparency drift — `risk_score` (0–100) rendered as a percentage, alert header "AI QA: review parser" and section header "Mismatch" reading as facts, "the model believes / AI decided" anthropomorphism, and mock-provider cost shown under an "OpenAI model" label; (c) user-flow defects — the post-save summary claimed "Checking available listings now" although no immediate check runs, the `Set up filter` entry skipped the `Step 1/4` prefix and WBS hint, "Hi!" violated the no-exclamation rule, and "I no longer save filters from free text" referenced product history new users cannot know; (d) raw enum values (`daily_cost_limit_reached`, enabled: "none") shown in admin messages.
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
| Automate eval-number propagation into CASE_STUDY.md / case-study.html from `run_eval --json`? | Implementation | Author |
| Converge the `All listings` / `Browse all listings` label pair on one form | Content | Author |
| Any live source adapter rollout — requires terms review and a documented scope change before any rule here extends to it | Product/legal | Author |

---

*This document defines standards; it changes no code. Sources: `main.py`, `flatfeed/` (bot, matching, AI QA, dashboard), `synthetic/` + `eval/` (golden set and eval), `docs/case-study.html` + `docs/styles.css` (case page), `README.md`, `docs/PROJECT_CONTEXT.md`, `CASE_STUDY.md` (product intent and claims). WCAG 2.2 AA, Telegram bot conventions, GOV.UK/GDS and Microsoft writing guidance, and AI PM portfolio evidence standards serve as references only.*
