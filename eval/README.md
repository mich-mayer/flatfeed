# Evaluation guide

Start with the [final synthetic report](runs/extraction-v1-final-600/report.md)
or [its protocol](AI_QA_EVAL_PLAN.md). The accepted result belongs to the separate
offline `extraction-v1` checker. It is not a validation of optional runtime QA
and is not integrated into the Telegram product.

## Accepted final evidence

| Artifact | What it establishes |
|---|---|
| [Report](runs/extraction-v1-final-600/report.md) / [JSON](runs/extraction-v1-final-600/report.json) | Gates, results, the unusable check and limitations |
| [Run manifest](runs/extraction-v1-final-600/run_manifest.json) | Executed configuration, dataset hashes, cost and completion |
| [Configuration freeze](runs/extraction-v1-final-600-configuration-freeze.json) | Pre-run model, prompt, schema, budget and acceptance gates |
| [Predictions](runs/extraction-v1-final-600/predictions.jsonl) | Recorded per-case outputs and check outcomes |
| [Dataset manifest](datasets/extraction_v1_final_600/dataset_manifest.json) | Composition, seed, hashes and isolation |
| [Inputs](datasets/extraction_v1_final_600/model_inputs.jsonl) / [truth](datasets/extraction_v1_final_600/truth.jsonl) | Separate model-input and scoring records |

The model receives raw text only. Code compares extracted quotes with the
parser snapshot. The 600-case set contains 300 clean cases and 300 cases with
one planted error; results do not estimate natural production error prevalence.

## How the final check works

1. [Extraction contract](ai_qa_extraction_contract.py): exact quotes or null,
   strict schema, and validation against raw text.
2. [Comparator](ai_qa_extraction_compare.py): normalization, field comparison
   and deterministic `review_required`.
3. [Final execution and scorer](ai_qa_extraction_final.py): frozen configuration,
   evidence recording and acceptance gates.
4. [Public-evidence check](../scripts/check_eval_numbers.py): verifies README and
   case-study claims against saved artifacts without a hosted-model rerun.

The separate [runtime QA implementation](../flatfeed/ai_qa.py) instead asks for
a risk assessment from text and a parser snapshot. Its default is disabled.

## Historical experiments

Historical results are retained to explain decisions and verify dataset
isolation. They are not additional final acceptance runs. Start with the
[chronological protocol](archive/AI_QA_EVAL_HISTORY.md) and
[analysis of the earlier holdout misses](AI_QA_FAILURE_ANALYSIS.md).

| Run family under `runs/` | Purpose and status |
|---|---|
| `development-smoke-*`, `development-100-*` | Initial development, prompt and reasoning screens |
| `luna-effort-screen-*`, `luna-v1-calibration`, `luna-v2-validation`, `luna-low-calibration`, `luna-v3-*`, `luna-v4-calibration`, `luna-v5-calibration` | Luna configuration development, calibration and frozen validation history |
| `terra-effort-screen-*`, `terra-2x2-*`, `terra-v2-screen-*` | Terra model/prompt/reasoning comparisons |
| `terra-calibration`, `terra-validation`, `terra-high-screen-*`, `terra-high-calibration`, `terra-high-validation` | Terra configuration selection and validation history |
| [terra-high-locked-holdout](runs/terra-high-locked-holdout/) | Consumed earlier holdout with silent misses; not the accepted final result |
| `review-v1-development-*` | Separate follow-up development after failure analysis |
| [extraction-v1-development](runs/extraction-v1-development/) | Development of the quote-extraction contract before the final freeze |
| [extraction-v1-final-600](runs/extraction-v1-final-600/) | Accepted final run; consumed and immutable |

Browse [all run artifacts](runs/) and [dataset families](datasets/). Freeze,
dry-run and comparison files document their adjacent run family. Old data and
failed iterations remain because the final isolation checks refer to them.
Do not remove them to simplify the file tree or improve the apparent results.

## Local regression checks

[run_eval.py](run_eval.py) checks the small authored synthetic parser regression
set; it is separate from the hosted-model experiment. Follow the
[fresh-checkout instructions](../README.md#development-checks) to reconstruct
ignored local test fixtures and run tests without model calls.

Do not rerun, tune, regenerate or rescore consumed model evaluations. Keep
frozen evidence bytes and experiment paths unchanged; add navigation here
instead of editing hashed artifacts.
