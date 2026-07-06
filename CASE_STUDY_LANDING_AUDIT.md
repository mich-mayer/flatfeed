# Case-Study Landing Audit (docs/case-study.html + docs/styles.css)

**Date:** 2026-07-06.
**Benchmark:** `DESIGN_CONTENT_SYSTEM.md` (section references below).
**Method:** line-by-line review of `docs/case-study.html` and `docs/styles.css` against the benchmark; cross-check against `CASE_STUDY.md`; metric verification via an actual `ENV_FILE=.env.local .venv/bin/python -m eval.run_eval` run on 2026-07-06.
**Scope:** findings only — no code was changed. Each finding: priority (P1 = fix before next publish, P2 = fix soon, P3 = improvement/author decision), benchmark section, location, recommendation.

**Verified first:** the landing's eval numbers are reproducible. The 2026-07-06 run reports: golden set size 15, parser field accuracy 100.0%, parser exact listing accuracy 100.0%, parser misses by tag: none, false alert fields: 0. No stale-number defect exists (§23, §13). The findings below are about labeling, consistency, and presentation — not about fabricated data.

---

## P1 — Evidence and honesty at reading depth

### CSL-01 — Hero QA panel shows eval metrics with no synthetic qualifier at the same reading depth
- **Benchmark:** §23 hard constraint ("Synthetic eval numbers MUST NOT read as production evidence at any reading depth"), §3 P3, §13.
- **Location:** `docs/case-study.html:87-122` (`dashboard-panel`: "15 Golden listings / 100% Field accuracy / 0 Parser misses / $0 Mock QA cost").
- **Problem:** a 10-second scanner sees "100% Field accuracy" in the hero with nothing nearby saying these are synthetic golden-set demo metrics. "Golden listings" and "Mock QA cost" hint at it only for readers who already know the vocabulary. The panel header says just "QA Dashboard".
- **Recommendation:** add a visible one-line qualifier inside the panel (e.g. a muted caption under the metric grid or in the panel header: "Synthetic golden-set eval — demo metrics, not production numbers"). Keep it at the same visual level as the numbers.
- **Status:** Fixed in `docs/case-study.html` by adding a visible synthetic golden-set eval qualifier inside the hero dashboard panel.

### CSL-02 — The 10-second scan never discloses the demo/synthetic status of the project
- **Benchmark:** §22 (10-second scan must answer what this is), §23, §2 honesty constraint.
- **Location:** `docs/case-study.html:29-52` (hero copy: kicker, H1, `hero-summary`, `role-list`).
- **Problem:** kicker, H1, summary, and the Role/Domain/Prototype-type list all describe the product with no mention that the demo runs on a synthetic catalog. Phase honesty first appears in the proof strip ("explicit demo-only metrics") and Results — below the fold of the scan.
- **Recommendation:** add one honest clause at hero depth. Cheapest structural fix: a fourth `role-list` row — `<dt>Data</dt><dd>Synthetic Berlin catalog with hidden ground truth</dd>` — which also strengthens the spec-sheet pattern. Alternatively end `hero-summary` with a demo-status clause.
- **Status:** Fixed in `docs/case-study.html` by adding the Data row to the hero role list.

### CSL-03 — Metric naming drift across hero, Results cards, and CASE_STUDY.md
- **Benchmark:** §27 (eval numbers and their meaning consistent across surfaces), §20.
- **Location:** `docs/case-study.html:108-110` ("0 Parser misses"), `docs/case-study.html:309-311` ("0 Parser misses by tag"), `CASE_STUDY.md:64-65` ("0 false alert fields").
- **Problem:** three surfaces highlight what looks like the same "0" but is not: `misses_by_tag` (a parser metric) and `false_alert_fields` (an AI QA controller metric) are different measurements in `eval/run_eval.py`. The hero's unscoped "Parser misses" could be either. A careful reader comparing surfaces finds an apparent contradiction; a careless one merges two metrics into one claim.
- **Recommendation:** pick the canonical pair from the eval vocabulary and use it consistently: "Parser misses by tag: 0" (parser) and "False alert fields: 0" (AI QA). Scope the hero card to one of them explicitly. Do not rename the metrics away from `eval/run_eval.py` output terms.
- **Status:** Fixed in `docs/case-study.html` by aligning the hero metric caption with the Results card: "Parser misses by tag".

### CSL-04 — Same numbers formatted differently within one page (hero vs Results)
- **Benchmark:** §27, §13 (units and denominators stay with the number), §16.4 precision.
- **Location:** `docs/case-study.html:104` ("100%") vs `:301-306` ("100.0%"); `:112` ("$0") vs `:313` ("$0.000000").
- **Problem:** the hero rounds the same measured values that Results states precisely. Two formats for one measurement on one page weaken the "measured, not claimed" signal.
- **Recommendation:** use the eval-output form ("100.0%") in both places. For cost, choose one form (the run-output "$0.000000" or a deliberate "$0.00") and use it in both the hero panel and the Results card; keep "Mock" attached to it wherever it appears.
- **Status:** Fixed in `docs/case-study.html` by using "100.0%" and "$0.000000" in both hero and Results, with "Mock QA cost" retained.

---

## P2 — Content

### CSL-05 — "Multi-source ready" proof point is a capability self-grade
- **Benchmark:** §23 (capabilities exercised only through the synthetic adapter must be described as such), §25.
- **Location:** `docs/case-study.html:127-130`.
- **Problem:** "ready" grades an untested capability; no live source adapter has ever exercised the architecture. The supporting span ("Source-adapter architecture with per-source activity checks") is the honest part.
- **Recommendation:** demote the heading to the mechanism, e.g. **"Source-adapter architecture"** with span "Registry, per-source activity checks, and health monitoring — exercised through the synthetic adapter in this demo." (mirrors the README's approved phrasing).
- **Status:** Fixed in `docs/case-study.html` by retitling the proof point and tying the architecture to the synthetic adapter demo.

### CSL-06 — HTML "What I Built" (05) omits the AI QA sentence present in CASE_STUDY.md §5
- **Benchmark:** §27 (7-part structure and meaning sync between `CASE_STUDY.md` and the HTML page).
- **Location:** `docs/case-study.html:249-251` vs `CASE_STUDY.md:55-57`.
- **Problem:** the Markdown version describes the AI QA system inside "What I Built" ("reviews parser snapshots, logs cost and token usage, flags high-risk issues for an admin, and keeps human feedback separate from automatic matching"); the HTML section stops after source health. The HTML deep-read of section 05 therefore under-describes what was built relative to the canonical Markdown.
- **Recommendation:** append the existing CASE_STUDY.md sentence (verbatim or meaning-identical) to the HTML section 05 paragraph.
- **Status:** Fixed in `docs/case-study.html` by appending the existing AI QA sentence from `CASE_STUDY.md` section 5.

### CSL-07 — Results prose in HTML drops the mock-QA sentence that anchors the "$0.000000" card
- **Benchmark:** §27, §23 ("$0 QA cost MUST stay attributed to the mock provider").
- **Location:** `docs/case-study.html:292-294` vs `CASE_STUDY.md:63-65`.
- **Problem:** the HTML Results paragraph verifies the parser numbers but never mentions the mock AI QA provider; the "$0.000000 Mock QA cost" card floats with only its two-word caption as provenance. The Markdown version carries the full sentence ("The mock AI QA provider produced 0 false alert fields and $0.000000 total QA cost in that demo run").
- **Recommendation:** add the mock-provider sentence to the HTML Results paragraph, keeping the "synthetic evaluation metrics, not production user-impact numbers" qualifier in the same paragraph as it is now.
- **Status:** Fixed in `docs/case-study.html` by adding the mock AI QA provider sentence while keeping the synthetic qualifier in the same paragraph.

### CSL-08 — "Transit context" mockup card doesn't correspond to a real product state
- **Benchmark:** §22 ("Mockup panels depict only states the real product produces"), §10 card contract.
- **Location:** `docs/case-study.html:75-84`.
- **Problem:** the real bot renders transit inside the listing card as `S-Bahn: <minutes>` / `U-Bahn: <minutes>` lines; there is no standalone "Transit context" card, and the "9 min walk" phrasing is not the card's rendering. The mini-map is fine as an illustration, but the card it decorates invents a message type.
- **Recommendation:** either fold the transit lines into the listing-card mockup above it (matching §10 field order: District → … → S-Bahn → U-Bahn → WBS → Kalt) or relabel the second panel as an explanatory illustration rather than a bot message (e.g. caption text instead of a fake card `h2`).
- **Status:** Fixed in `docs/case-study.html` by merging transit lines into the listing-card mockup and leaving the mini-map decorative.

---

## P2 — Design / CSS

### CSL-09 — Non-token color literals throughout `styles.css`
- **Benchmark:** §5.1 (tokens only; no new hex literals), §29 (the `#263545` entry).
- **Location:** `docs/styles.css:434` (`#263545` body-text color), `:261` (`#ddf3dc` user bubble), `:264` (`#f2f5f6` bot bubble), `:556` (`#f0d5ad` results border), plus repeated `#ffffff` where `var(--surface)` exists (`:174,178,333,389,471,580,624`) and header rgba literals (`:65-66`).
- **Problem:** the token set in `:root` is bypassed in ~10 places; future palette changes will miss them.
- **Recommendation:** map `#ffffff` → `var(--surface)`; promote the message-bubble pair and the results border to named tokens (e.g. `--bubble-user`, `--bubble-bot`, `--amber-border`) or derive them from existing tokens; replace `#263545` with `var(--ink)` or a new `--ink-soft` token. Update §5.1 of the benchmark in the same change (§34).
- **Status:** Fixed in `docs/styles.css` and `DESIGN_CONTENT_SYSTEM.md` by promoting the literal colors to named tokens and replacing non-root literals with token references.

### CSL-10 — `scroll-behavior: smooth` not gated on `prefers-reduced-motion`
- **Benchmark:** §15, §29 (known gap, Medium).
- **Location:** `docs/styles.css:21-23`.
- **Recommendation:** wrap in `@media (prefers-reduced-motion: no-preference)`.
- **Status:** Fixed in `docs/styles.css` by gating smooth scrolling behind `prefers-reduced-motion: no-preference`.

### CSL-11 — CTA buttons have no `:hover`/`:focus` styling
- **Benchmark:** §15 (visible focus state), §9 (primary action affordance).
- **Location:** `docs/styles.css:157-178` (`.button-primary`, `.button-secondary`); compare nav links which do get `:hover/:focus` at `:104-107`.
- **Problem:** the page's two most important interactive elements give no hover feedback; keyboard focus falls back to the browser default ring only (not suppressed — so not a WCAG failure, but below the page's own standard set by the nav).
- **Recommendation:** add hover (e.g. `--teal-dark` background for primary, border/ink shift for secondary) and a `:focus-visible` outline consistent with the nav treatment. Same for footer links.
- **Status:** Fixed in `docs/styles.css` by adding hover and `:focus-visible` treatments to CTA buttons and footer links.

---

## P3 — Structure and polish (author judgment where noted)

### CSL-12 — Mockup content uses `<h2>` headings inside the hero
- **Benchmark:** §15 (semantics), §26.
- **Location:** `docs/case-study.html:69,80` (`listing-card h2`: "2-room WBS listing", "Transit context").
- **Problem:** fake listing titles enter the document outline at the same level as the real case-study sections ("The Problem", "Results"); a heading-only read (§26 gate) surfaces mockup noise.
- **Recommendation:** demote to `<p><strong>` (or `<h3>` at minimum) with the same visual style.
- **Status:** Fixed in `docs/case-study.html` and `docs/styles.css` by demoting the listing mockup title to `p > strong` while preserving its visual styling.

### CSL-13 — Sticky header with a 104px brand mark costs ~140px of every viewport — author decision
- **Benchmark:** no rule; flagged as judgment (§34 would govern a rule change).
- **Location:** `docs/styles.css:55-94`.
- **Recommendation (optional):** keep the large mark at top, shrink it in the sticky state (or unstick the header above 900px too). Do not change without the author's aesthetic sign-off.

### CSL-14 — GitHub URLs hard-coded to `github.com/mich-mayer/flatfeed` — needs author verification
- **Benchmark:** §29 (existing Medium item), §35.
- **Location:** `docs/case-study.html:23,37,348-349`.
- **Recommendation:** author confirms the canonical public repo URL before the next publish; then the links become FACT-status claims. An agent must not guess or change these unilaterally.

### CSL-15 — 5-card Results band leaves an orphan card at ≤900px
- **Benchmark:** §14 (polish level).
- **Location:** `docs/styles.css:683-687` (`.result-cards` → `1fr 1fr` at ≤900px; 5 items = 2-2-1).
- **Recommendation:** acceptable as-is; if touched, prefer `repeat(auto-fit, minmax(150px, 1fr))` or a 3+2 arrangement.

### CSL-16 — No social-sharing meta (Open Graph / Twitter card) — improvement, not a violation
- **Benchmark:** none (portfolio-reach improvement).
- **Location:** `docs/case-study.html:3-9` (head).
- **Recommendation (optional):** add `og:title`, `og:description`, `og:image` (an existing licensed asset only). Author decides whether to invest.

---

## What passed (no action)

- **Numbers integrity:** all published eval values reproduce from a real run (see header). §23's worst failure mode is absent.
- **"Why AI?" negative-decision-first framing** (`case-study.html:162-165`) — intact, matches §22.
- **Workflow band** (Collect → Normalize → Match → Review → Notify) — matches the implemented pipeline (§22).
- **Results prose qualifier** ("synthetic evaluation metrics, not production user-impact numbers") — present in-paragraph (§23).
- **7-part structure** and section order — in sync with `CASE_STUDY.md` (§6.3), apart from CSL-06/07 sentence-level gaps.
- **Ownership language** in sections 03/05 — meaning-identical to `CASE_STUDY.md` (§24).
- **Accessibility basics:** nav/panels/workflow `aria-label`s, decorative `aria-hidden`, demo-photo alt disclosure, real `th` headers, no suppressed focus outlines, `lang="en"` (§15).
- **Amber containment:** amber appears only in the Results cards (§5.1).
- **Buzzword register:** zero self-praise buzzwords on the page apart from CSL-05's "ready" (§25); "trusted, measurable" in the H1 is sanctioned by §25 (anchored by the eval and boundary sections).
- **Card vocabulary in the phone mockup** ("District:", "WBS:", "Kalt:", relative field order) — conforms to §10, apart from the CSL-08 transit card.

---

## Suggested fix order

1. CSL-01, CSL-02 (honesty at scan depth — the benchmark's hard constraints).
2. CSL-03, CSL-04 (metric naming and formatting consistency).
3. CSL-05, CSL-06, CSL-07 (content sync and self-grading).
4. CSL-10, CSL-11, CSL-09 (CSS: motion gate, focus/hover, tokens).
5. CSL-08, CSL-12, CSL-15 (mockup fidelity and semantics).
6. CSL-13, CSL-14, CSL-16 — author decisions; do not implement without sign-off.

*Findings only; no code changed in this audit. Verification for any fix: reload `docs/case-study.html` locally, re-run the §22 10s/30s scan tests on changed sections, and run `git diff --check`.*
