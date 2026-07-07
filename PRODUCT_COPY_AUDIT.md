# Product Copy Audit and Implementation

**Date:** 2026-07-07
**Scope:** all user-facing product copy — Telegram bot (`main.py`, `flatfeed/matching.py`), Streamlit admin dashboard (`flatfeed/dashboard/streamlit_app.py`), eval CLI report (`eval/report.py`).
**Out of scope (per constraints):** the case-study landing page (`docs/case-study.html`) and public docs, except where the normative standard (`DESIGN_CONTENT_SYSTEM.md`) had to be updated to match copy changes.

---

## 1. Executive Summary

**Before.** The copy base was unusually strong for a prototype: the project ships its own normative content system (`DESIGN_CONTENT_SYSTEM.md`) with canonical terminology, an AI-boundary language policy, and honesty rules — and most surfaces follow it. The listing-card contract, wizard hints, confirmation pairs, and question-form dashboard headings all pass GDS/Microsoft standards as-is.

**Biggest problems found.**

1. **One action, three names.** The admin catalog QA run was labeled `Run catalog QA` (button) but narrated as "Parser check …" in every progress, result, and failure message; the QA demo was labeled `Run QA demo` but narrated as "the error demo".
2. **A false immediate-action claim (P0).** After saving a filter, the bot said "Checking available listings now. Any matching apartments will be sent here right away" — no immediate check runs; delivery happens via the background pipeline or the `Show matches` action.
3. **AI-transparency drift (P0/P1).** The 0–100 `risk_score` was rendered as a percentage ("Risk: high, 85%"), the alert header "AI QA: review parser" and the section header "Mismatch" read as established facts, help texts said "the model believes" / "AI decided", and mock-provider costs sat under an "OpenAI model" label.
4. **Metric-label divergence.** The same admin-confirmed concept appeared as "Confirmed errors", "Real parser errors", and "Real errors"; pending triage as "Pending decision", "Pending review", and "Pending alert feedback"; coverage as "Covered by current AI QA" vs "AI reviewed" / "Still to check" vs "Still to review"; the source column as "Catalog" vs the card's "Source".
5. **Raw internals shown to the admin.** Enum codes (`daily_cost_limit_reached`) and a wrong boolean label (`AI QA enabled: none`) appeared verbatim in admin messages.

**Strongest existing aspects.** Point-of-use WBS/Kaltmiete glosses; consequence-named confirmation buttons; question-form dashboard sections with provenance captions; consistent synthetic/demo labeling; the canonical listing card with honest fallbacks (`not specified`, `not calculated`).

**Highest-impact changes implemented.** Honest post-save filter message; one name per action (catalog QA, QA demo); risk score rendered as "N of 100" with the qualitative label; alert framed as "possible parser error" / "Possible mismatch"; one label per metric concept across bot and dashboard; provider named wherever cost appears; human-readable stop/skip reasons.

**After.** Terminology is now one-to-one with concepts across bot and dashboard, AI output is consistently framed as prediction pending human decision, and every metric label tells a non-specialist what it counts. The product passes the 5–10-second comprehension test on each major surface and reads as the work of someone who takes AI honesty seriously — which is the portfolio's thesis.

---

## 2. Standards Used

- **GOV.UK / GDS Content Design** — primary standard for message clarity: front-loading, plain language, removing insider context ("I no longer save filters…" assumed knowledge of product history), honest statements of what the system does and when.
- **Microsoft Writing Style Guide** — UI copy: action-oriented and consistent labels (one name per action), natural language ("Let's" over "Let us"), correct value vocabulary ("yes/no", not "yes/none"), and metric labels that name the object being counted.
- **ONS content guidance** — metric communication: every quality metric states what it counts and its direction ("Higher is better" / "Lower is better" added to the metric guide), risk scores keep their scale visible ("85 of 100", "Risk score (0–100)"), provenance (provider, prices, synthetic scope) stays attached to the numbers.
- **Repo-local `DESIGN_CONTENT_SYSTEM.md`** — treated as normative on top of the three external standards (terminology §20, AI language §21, voice §17). Where a change touched a rule example, the standard was updated in the same change with a §34 governance record.

---

## 3. Product Copy Inventory

| Page / Area | Copy Types | Main Purpose | Main Risks (before) |
|---|---|---|---|
| Bot: onboarding (`/start`, `/help`) | greeting, glossary, command menu | orient a new renter | "Hi!" exclamation; otherwise sound |
| Bot: filter wizard (4 steps) | questions, hints, nav/confirm buttons | capture WBS/district/rent/rooms | `Set up filter` entry skipped Step 1/4 + hint; "Let us" register |
| Bot: filter card & summary | field labels, status, save confirmation | show saved filter, set expectations | false "Checking available listings now" claim; field order differed between card and summary; "Done, settings updated." |
| Bot: matches / catalog flows | progress, empty states, result intros | deliver listing cards | "fresh" imprecision; otherwise honest |
| Bot: listing card (`matching.py`) | fixed field contract | the core artifact | none — contract intact, untouched |
| Bot: admin panel & QA flows | action buttons, progress, results, alerts, triage | run QA, triage findings | "Parser check"/"error demo" naming; risk as %; fact-style alert headers; raw enums |
| Dashboard (Streamlit) | title, question headings, metrics, tables, demo block | show AI QA health/value/cost | metric-label divergence; "OpenAI model" under mock; "model believes"/"AI decided" |
| Eval CLI (`eval/report.py`) | text report labels | dev-facing eval output | left unchanged — labels are quoted by docs' eval-sync search |

---

## 4. Terminology System

| Concept | Previous Variants | Final Canonical Term | Rationale |
|---|---|---|---|
| Full-catalog AI QA run | Run catalog QA / "Parser check…" | **catalog QA** | Button label is load-bearing (§19); narration must name the same action |
| Fault-injection demo | Run QA demo / "the error demo" | **QA demo** | Same; §29 already flagged "Error demo failed." as deprecated |
| One AI QA pass on a listing | check / review (mixed) | **check** (the act) | "Checks today", "Cost per check" already established |
| Stored QA artifact / coverage state | checked / covered / reviewed | **review / reviewed** | Matches `ai_qa_reviews`, §20 "finding / review" |
| Alerting review | potential-error report / flagged report / potential errors | **flagged report** | §20 user-facing form; matches `Review flagged issues` |
| Admin-confirmed parser error | Confirmed errors / Real parser errors / Real errors | **Confirmed errors** | "Confirmed" names the human decision; matches feedback label and "Cost per confirmed error" |
| Alert awaiting triage | Pending decision / Pending review / Pending alert feedback | **Pending review** | Matches the `Pending review` feedback status label |
| AI risk number | "Risk: high, 85%" / "AI risk: 85%" | **risk score, "N of 100"** | §11/§21: a 0–100 score, not a probability; `%` misstates the scale |
| Model self-estimate | AI confidence / Confidence | **AI confidence** | Distinguishes origin (AI) from observed facts |
| Source company column | Catalog / Source | **Source** | Card field is `Source:`; one concept, one name |
| Prompt/check version | Check version / Current AI QA version | **AI QA version** | Names the versioned thing (the AI QA prompt policy) |
| Saved criteria object | filter / "settings" ("Done, settings updated.") | **filter** | §20 explicitly avoids "settings/preferences" for this object |
| Unchanged (verified consistent) | listing, WBS, Kaltmiete, District, golden set, triage labels, `not specified` / `not calculated` | — | Already canonical; deliberately untouched |

---

## 5. Changes Implemented

### [C1] Honest post-save filter message
- **Severity:** P0
- **Location:** `main.py` → `_filter_summary`
- **Previous copy:** "Checking available listings now. Any matching apartments will be sent here right away. If none are available yet, you'll be notified when new matches appear."
- **New copy:** "I will send new matching listings here automatically, each one only once. To check the catalog right now, tap Show matches."
- **Problem:** claimed an immediate check that does not happen; "apartments" broke the "listing" terminology; buried the real next action.
- **Why better:** states what actually happens (background one-time notifications), surfaces the primary action, and encodes the dedupe guarantee ("each one only once").
- **Standard applied:** GDS (do not mislead about system behavior); §23 evidence rules.

### [C2] Risk score no longer rendered as a percentage
- **Severity:** P0
- **Location:** `main.py` → `_format_ai_qa_review`; dashboard `_review_table`, demo metrics, field table
- **Previous copy:** "Risk: **high, 85%**"; column "AI risk" = "85%"; metric "AI risk" = "85%"; "Average AI risk"
- **New copy:** "Risk score: **85 of 100 (high)**"; column "Risk score (0–100)" = 85; metric "Risk score" = "85 of 100"; "Average risk score (0–100)"
- **Problem:** `risk_score` is a 0–100 score with an alert threshold, not a probability; "%" invited misreading it as one.
- **Standard applied:** ONS (make the scale visible); §11/§21 ("risk is a number with a threshold").

### [C3] Alert framed as prediction, not fact
- **Severity:** P1
- **Location:** `main.py` → `_format_ai_qa_review`
- **Previous copy:** header "AI QA: review parser"; section "Mismatch"
- **New copy:** header "AI QA alert: possible parser error"; section "Possible mismatch"
- **Problem:** "Mismatch" asserted a defect before the human decision; the old header was also garbled English.
- **Standard applied:** §G AI transparency; Microsoft (say what happened and what to do).

### [C4] One name for the catalog QA action
- **Severity:** P1
- **Location:** `main.py` → backfill flow (5 messages) and `_format_ai_qa_backfill_result`
- **Previous copy:** "Parser check is already running…", "Starting parser checks…", "Parser check is taking longer…", "Parser check failed. Check the logs." (×2), "**Parser check completed.**"
- **New copy:** the same messages with **Catalog QA** ("Catalog QA failed. Check the logs.", "**Catalog QA completed.**", "Starting catalog QA for active listings without a review.")
- **Problem:** the button says `Run catalog QA`; the narration named a different-sounding activity, breaking action-to-feedback traceability.
- **Standard applied:** Microsoft (consistent terminology, predictable naming); §19.

### [C5] QA demo naming + deprecated failure message
- **Severity:** P1 (failure string was pre-flagged in §29)
- **Location:** `main.py` → `handle_ai_qa_demo`
- **Previous copy:** "Starting the error demo: I will take active synthetic listings, corrupt one parser field, and check it against the listing."; "Error demo failed. Check the logs."; "…for the error demo."
- **New copy:** "Starting the QA demo: I will corrupt one parser field in each of up to 3 active synthetic listings, then let AI QA check them against the listing text."; "QA demo failed. Check the logs."; "…for the QA demo."
- **Problem:** two names for one action; the old intro was grammatically wrong about what happens (plural listings, one field each); §29 deprecation left unfixed.
- **Standard applied:** Microsoft; §29 migration rule.

### [C6] Confirmed-error and pending-review labels unified
- **Severity:** P2
- **Location:** dashboard `_render_quality`, `_render_field_quality`, `_render_versions`; bot `_format_ai_qa_status`
- **Previous copy:** "Real parser errors" / "Real errors" (×3 tables) / "Confirmed errors"; "Pending decision" / "Pending alert feedback"; "Unsure"
- **New copy:** **"Confirmed errors"** everywhere; **"Pending review"** (dashboard) and "Flagged reports pending review" (bot status); "Borderline / unsure" (matches the triage button verbatim)
- **Problem:** three names for one human decision; triage vocabulary is load-bearing (§7.4) and the status list drifted from it.
- **Standard applied:** §F terminology consistency; Microsoft.

### [C7] Provider named wherever cost appears
- **Severity:** P1
- **Location:** dashboard `_render_costs`; bot `_format_ai_qa_status`
- **Previous copy:** metric "OpenAI model: gpt-5.4-mini" (even in mock mode); status showed "Model: gpt-5.4-mini" with no provider line
- **New copy:** metric "AI QA provider: mock — no API calls" (or "openai · gpt-5.4-mini"), help explaining the mock provider is local, deterministic, free; status gains "Provider: mock" above "Model:"
- **Problem:** $0 figures displayed under an OpenAI label read as an efficiency claim; §21 requires the mock provider named wherever its numbers appear.
- **Standard applied:** §G AI transparency; §21; §23 (MOCK labeling).

### [C8] Human-readable stop/skip reasons and status values
- **Severity:** P2
- **Location:** `main.py` → new `AI_QA_REASON_LABELS` + `_ai_qa_reason_label`; `_format_ai_qa_status`
- **Previous copy:** "Stop reason: daily_cost_limit_reached"; "Skipped: none"; "AI QA enabled: none"
- **New copy:** "Stopped because: daily cost limit reached"; enum codes mapped ("no active listings to check", "OpenAI API key is not configured", …); "AI QA enabled: no"
- **Problem:** raw enum codes in admin prose; "none" as the negative of "yes" is simply wrong.
- **Standard applied:** Microsoft (natural language, no unnecessary technical language); GDS.

### [C9] Backfill/status vocabulary aligned to check vs review
- **Severity:** P2
- **Location:** `main.py` → `_format_ai_qa_backfill_result`, `_format_ai_qa_status`
- **Previous copy:** "Check version:", "Unchecked listings before run", "Listings still unchecked", "Potential errors: N", "Covered by current AI QA", "Still to check", "Total reviews in version", "Pending alert feedback"
- **New copy:** "AI QA version:", "Unreviewed before this run", "Still unreviewed", "Flagged reports: N", "Reviewed by current AI QA version", "Still to review", "Reviews in current version", "Flagged reports pending review"
- **Problem:** check/review/covered used interchangeably; dashboard already said "AI reviewed" / "Still to review".
- **Standard applied:** §F; ONS (denominators and states named consistently).

### [C10] "Filter updated." replaces "Done, settings updated."
- **Severity:** P2
- **Location:** `main.py` (3 occurrences)
- **Problem:** the object is the filter; "settings" is on the §20 avoid-list and collides with the internal `settings:` namespace.
- **Standard applied:** §F; Microsoft (name the affected object).

### [C11] Wizard entry via `Set up filter` now shows Step 1/4 + WBS hint
- **Severity:** P2
- **Location:** `main.py` → `handle_settings_filter`
- **Previous copy:** bare "Which WBS should match?"
- **New copy:** `_wbs_step_text()` — "**Step 1/4** — Which WBS should match?" + the WBS explainer (same as `/filter`)
- **Problem:** the most common wizard entry skipped the progress indicator and the load-bearing gloss (§7.3).
- **Standard applied:** GDS one-thing-per-page with context at the point of the question.

### [C12] Free-text fallback no longer references product history
- **Severity:** P2
- **Location:** `main.py` → `handle_plain_text`
- **Previous copy:** "I no longer save filters from free text, so I do not overwrite them by accident."
- **New copy:** "I only change your filter through the buttons, so free-text messages cannot overwrite it by accident."
- **Problem:** "no longer" required knowing a previous behavior; new users cannot decode it.
- **Standard applied:** GDS (no insider context).

### [C13] Greeting and wizard register
- **Severity:** P3
- **Location:** `main.py` → `handle_start`, `begin_filter_setup`, `SETUP_EXPIRED_TEXT`
- **Previous copy:** "Hi! This is FlatFeed, a demo assistant…"; "Let us set up the filter…"; "Let us start again."
- **New copy:** "This is FlatFeed — a demo assistant…"; "Let's set up the filter…"; "Let's start again."
- **Problem:** exclamation mark violates §17; "Let us" is unnatural register (Microsoft prefers contractions).
- **Standard applied:** Microsoft (natural language); §17.

### [C14] Dashboard anthropomorphism and metric guide
- **Severity:** P2
- **Location:** dashboard `_render_metric_guide`, `_render_quality` help texts, `_render_field_quality` caption
- **Previous copy:** "cases where the model **believes** the parser may have made a material mistake"; "How often AI **decided** the parser may have erred"; "where a human has already confirmed real errors"
- **New copy:** "checks the model **flagged** as a possible material parser error … A flag is a prediction, not a confirmed error."; "How many checks AI flagged as a possible parser error and sent to the admin."; "where the admin has already confirmed errors." Direction notes added: "Higher is better." / "Lower is better."
- **Problem:** review-verbs rule (§21); count metrics described as frequencies; missing direction cues for rates.
- **Standard applied:** §G; ONS (direction of metrics).

### [C15] Source column, admin refresh labels, small renter fixes
- **Severity:** P2–P3
- **Location:** dashboard health + review tables; `main.py` refresh result; matches intro; flagged-reports empty state; budget confirmation; settings card order
- **Changes:** "Catalog" column → "Source" (×2); "Active URLs found" → "Active listings found"; "Updated records" → "Updated"; "up to 10 fresh active listings matching your filter" → "up to 10 active listings that match your filter"; "There are no potential-error reports yet." → "There are no flagged reports yet."; "Run catalog QA may use the OpenAI budget." → "Catalog QA uses a paid provider and may spend the daily OpenAI budget."; filter-card field order now matches the wizard and summary (WBS → District → Kaltmiete → Rooms); dashboard demo button "Run demo AI QA" → "Run QA demo".
- **Standard applied:** §F; Microsoft; GDS.

---

## 6. Page-by-Page Review

### Telegram bot — renter surface
- **Purpose:** set a 4-field filter, receive matching listing cards.
- **Previous issues:** false "checking now" claim; inconsistent wizard entry; "settings" naming; history-referencing fallback.
- **Changes:** C1, C10–C13, C15.
- **5–10-second test:** pass — `/start` shows what the product is, the filter card names its four fields in wizard order, the save confirmation states exactly what will happen and the next action.

### Telegram bot — admin surface
- **Purpose:** run QA, triage flagged reports, monitor coverage/cost.
- **Previous issues:** three names for catalog QA; percentage risk; fact-style alert headers; raw enums; drifted status labels.
- **Changes:** C2–C5, C8, C9.
- **5–10-second test:** pass — every progress/result/failure message names the action that was tapped; an alert reads as "possible parser error … choose a decision", making the AI/human split explicit.

### Streamlit dashboard
- **Purpose:** answer "is AI QA healthy, useful, affordable?" for the admin (and demonstrate evaluation thinking to a reader).
- **Previous issues:** metric-label divergence; "OpenAI model" under mock; anthropomorphic help texts; missing direction cues.
- **Changes:** C2, C6, C7, C14, C15.
- **5–10-second test:** pass — question headings unchanged (already strong), and now each metric label matches the bot's vocabulary, so a reader can follow one concept across surfaces. Verified rendering headlessly via Streamlit AppTest: no exceptions, all sections and new labels present.

### Listing card (`flatfeed/matching.py`)
- **Purpose:** the core artifact.
- **Assessment:** fully compliant with the §10 contract; deliberately untouched.

### Eval CLI report (`eval/report.py`)
- **Assessment:** developer-facing; its exact labels ("false alert fields", "field accuracy") are referenced by the docs' eval-sync search (§27). Left unchanged to avoid breaking documented number-sync tooling. "AI QA controller" heading noted in §10 below.

---

## 7. AI and Evaluation Terminology Review

- **AI outputs:** now consistently *flagged / possible / suggested*; the alert header says "possible parser error"; the mismatch block is "Possible mismatch"; dashboard guide states "A flag is a prediction, not a confirmed error."
- **Confidence:** kept as "AI confidence" (a model self-estimate, %-formatted 0.00–1.00/percent as before); never conflated with risk.
- **Risk:** "risk score N of 100" everywhere; qualitative label (high/medium/low) kept as context; no percentage rendering remains.
- **Recommendations vs decisions:** triage vocabulary (`Parser error` / `Parser correct` / `Borderline / unsure`) untouched and now echoed verbatim in status lists; every alert ends with "Choose a decision with the buttons below."
- **Human review:** "reviewed" now consistently means the stored AI QA review; the admin decision is "confirmed / false alarm / borderline".
- **Quality metrics:** "Useful signal rate" (precision of decisive triage) and "False alarm rate" kept — deliberately *not* renamed to "precision", since the plain names are self-explanatory to non-ML readers and the underlying definition is stated in the metric guide and captions (per the instruction not to replace or rename metric definitions). Direction cues added.
- **Precision / recall / F1 / confusion matrix / drift:** the product's eval reports "caught error rate", "false alert rate", "alert precision", field accuracy — these definitions were not changed. The version-comparison table ("How AI QA quality changed by version") remains the drift-adjacent view; no new metric names were invented.
- **Duplicate detection / SLA risk:** not product concepts in FlatFeed; nothing to audit.
- **Mock provider:** named at every cost surface (dashboard metric, bot status "Provider:", existing demo captions).

---

## 8. Before / After Table

| Location | Previous Copy | Final Copy | Reason | Standard |
|---|---|---|---|---|
| `main.py` `_filter_summary` | "Checking available listings now. Any matching apartments will be sent here right away…" | "I will send new matching listings here automatically, each one only once. To check the catalog right now, tap Show matches." | False immediate-action claim; wrong object noun | GDS, §23 |
| `main.py` `_format_ai_qa_review` | "AI QA: review parser" / "Mismatch" / "Risk: high, 85%" | "AI QA alert: possible parser error" / "Possible mismatch" / "Risk score: 85 of 100 (high)" | Prediction presented as fact; score as % | AI transparency, ONS |
| `main.py` backfill flow | "Parser check failed. Check the logs." (+4 more "Parser check…") | "Catalog QA failed. Check the logs." (+4 more "Catalog QA…") | Button/narration mismatch | Microsoft, §19 |
| `main.py` demo flow | "Starting the error demo…" / "Error demo failed." | "Starting the QA demo…" / "QA demo failed. Check the logs." | Two names for one action; §29 deprecation | Microsoft, §29 |
| `main.py` `_format_ai_qa_status` | "AI QA status." / "Check version" / "AI QA enabled: none" / "Still to check" / "Pending alert feedback" / "Unsure" | "AI QA status" / "AI QA version" / "AI QA enabled: no" / "Still to review" / "Flagged reports pending review" / "Borderline / unsure" (+ "Provider:" line) | Wrong value word; label drift; missing provider | Microsoft, §F, §21 |
| `main.py` `_format_ai_qa_backfill_result` | "Parser check completed." / "Unchecked listings before run" / "Potential errors" / "Stop reason: daily_cost_limit_reached" | "Catalog QA completed." / "Unreviewed before this run" / "Flagged reports" / "Stopped because: daily cost limit reached" | Naming + raw enums | Microsoft, GDS |
| `main.py` edits (×3) | "Done, settings updated." | "Filter updated." | Wrong object; §20 avoid-list | §F, Microsoft |
| `main.py` `handle_settings_filter` | "Which WBS should match?" (bare) | Step 1/4 prefix + question + WBS hint | Missing progress + gloss | GDS, §7.3 |
| `main.py` `handle_plain_text` | "I no longer save filters from free text…" | "I only change your filter through the buttons…" | Insider history reference | GDS |
| `main.py` `handle_start` / wizard | "Hi! …" / "Let us set up…" / "Let us start again." | "This is FlatFeed — …" / "Let's set up…" / "Let's start again." | Register (§17, contractions) | Microsoft, §17 |
| `main.py` matches intro | "…10 fresh active listings matching your filter." | "…10 active listings that match your filter." | "fresh" imprecise | GDS |
| `main.py` refresh result | "Active URLs found" / "Updated records" | "Active listings found" / "Updated" | Internal noun; parallelism | Microsoft |
| `main.py` flagged reports empty | "There are no potential-error reports yet." | "There are no flagged reports yet." | Canonical "flagged report" | §F |
| `main.py` budget confirm | "Run catalog QA may use the OpenAI budget." | "Catalog QA uses a paid provider and may spend the daily OpenAI budget." | Button label used as sentence subject | Microsoft |
| `main.py` `_settings_card` | field order WBS/District/Rooms/Kaltmiete | WBS/District/Kaltmiete/Rooms | Matches wizard + summary order | Microsoft (predictability) |
| Dashboard quality metrics | "Real parser errors" / "Pending decision" | "Confirmed errors" / "Pending review" | One label per concept | §F |
| Dashboard field/version tables | "Real errors" / "Average AI risk" | "Confirmed errors" / "Average risk score (0–100)" | Same + scale visibility | §F, ONS |
| Dashboard review table | "AI risk" = "85%" / "Catalog" | "Risk score (0–100)" = 85 / "Source" | Score-as-%; column naming | ONS, §F |
| Dashboard costs | "OpenAI model: gpt-5.4-mini" | "AI QA provider: mock — no API calls" (or "openai · model") | Mock cost under OpenAI label | §21, §23 |
| Dashboard metric guide / helps | "model believes…" / "AI decided…" | "model flagged… A flag is a prediction, not a confirmed error." + direction cues | Anthropomorphism; missing direction | §21, ONS |
| Dashboard demo | "Run demo AI QA" / "AI risk: 85%" / "Confidence" | "Run QA demo" / "Risk score: 85 of 100" / "AI confidence" | Action + scale + origin naming | Microsoft, ONS |
| `DESIGN_CONTENT_SYSTEM.md` | examples quoting old strings; §29 row | updated examples; §34 governance entry | Standard stays truthful | §34 |
| `tests/test_ai_qa.py` | asserts "<b>Mismatch</b>" | asserts "<b>Possible mismatch</b>" | Copy propagates to tests | §27 |

---

## 9. Final Canonical Voice and Content Rules

- **Voice.** The bot speaks first-person plain ("I will send…", "I only change your filter through the buttons"); the dashboard is a neutral admin register with question headings; no exclamation marks, no apologies, no self-praise anywhere.
- **Sentences.** 1–2 sentences per bot message; the first clause carries the point; contractions are fine ("Let's"), stiff latinate forms are not.
- **Headings.** Dashboard headings are the admin's questions; bot bold headers name the event ("Catalog QA completed.", "AI QA alert: possible parser error") — never generic ("Report", "Info").
- **Buttons.** Verb + object, ≤4 words, consequence named on destructive/costly confirms; feedback messages must repeat the button's noun (tap "Run catalog QA" → hear about "catalog QA").
- **Metric labels.** Name the counted object ("Confirmed errors", "Flagged reports"), keep the scale visible for scores ("Risk score (0–100)", "N of 100"), state direction for rates in the guide, keep denominators in values ("12 of 15").
- **AI transparency.** AI *flags/suggests/reviews*; the admin *confirms/decides*; everything AI-side is "possible" until triaged; risk is a score, never a percentage or an emotion; the provider is named wherever its cost appears; demo results say they are not saved to metrics.
- **Terminology.** One concept = one name: listing, filter, catalog QA, QA demo, check (act) vs review (artifact), flagged report, Confirmed errors, Pending review, Borderline / unsure, Source, AI QA version, risk score, AI confidence. Domain terms (WBS, Kaltmiete, Bezirk/District, S-Bahn/U-Bahn) keep canonical forms with point-of-use glosses.
- **Avoid.** "settings/preferences" for the filter; "real errors"; "%"-rendered risk; raw enum codes in prose; "the model believes/decided"; "AI-powered"; "fresh/robust/seamless"; product-history references ("no longer"); exclamation marks.

---

## 10. Remaining Issues

1. **`/reset` command resets without confirmation** (`main.py` `handle_reset_command`) while the `Reset filter` button confirms. This is product logic, not copy — out of scope per constraints (P7 in the design system; needs a product change, not a rewrite).
2. **`📂 All listings` vs `📂 Browse all listings`** — §35 of the design system explicitly reserves this convergence for an author decision; neither button was otherwise touched.
3. **Eval CLI heading "AI QA controller:"** (`eval/report.py`) — mildly odd naming, but the report's exact labels are pinned by the documented eval-sync search (§27) across CASE_STUDY.md/case-study.html; renaming would require a synchronized docs change and author review of the case-study surface, which is out of scope.
4. **Renter empty-catalog message mentions the admin panel** ("If you are an admin, refresh the synthetic catalog…") — borderline P8 (audience separation), but in this single-operator demo it is the practically correct instruction; changing it would need a product decision on the demo flow.
5. **`Notifications: ON` on the filter card** is static copy (no OFF state exists). Truthful today; if a pause feature ever ships, §19 requires defining its canonical verb first.
6. **Unused `scan_label` computation** in `_settings_card` (dead code, not copy) — left untouched as an unrelated technical change.

---

## 11. Verification

- **Tests:** `python -m unittest discover -s tests` — **107 tests, OK** (one assertion updated in `tests/test_ai_qa.py` to the new "Possible mismatch" header, per §27 copy-propagation).
- **Eval:** `python -m eval.run_eval` — runs clean; golden-set numbers unchanged (100% field accuracy rows, `$0.000000` mock cost), so no doc-number sync was needed.
- **Byte-compile:** `python -m py_compile main.py flatfeed/dashboard/streamlit_app.py` — OK.
- **Dashboard runtime check:** rendered headlessly via `streamlit.testing.v1.AppTest` — no exceptions; all 8 sections and the new metric labels present.
- **Bot formatter smoke test:** `_format_ai_qa_status`, `_format_ai_qa_backfill_result`, `_filter_summary` executed against sample data — output verified.
- **Consistency sweep:** targeted `grep` for all deprecated variants ("Parser check", "error demo", "Real errors", "Pending decision", "Done, settings updated", "Still to check", "Check version", "Let us", "fresh active", "potential-error", "Updated records", "Active URLs") — zero hits outside the historical governance record.
- **`git diff --check`** — clean.
- **Lint/type-check:** no lint or type-check tooling is configured in this repo (unittest + eval are the documented checks in README §Development Checks).
