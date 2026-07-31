from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from decimal import Decimal, ROUND_CEILING
from pathlib import Path
from typing import Any, Mapping

from eval.ai_qa_prompt import (
    MODEL_OUTPUT_JSON_SCHEMA as BASELINE_OUTPUT_SCHEMA,
)
from eval.ai_qa_prompt import (
    TERRA_V1_PROMPT_VERSION,
    TERRA_V1_SYSTEM_INSTRUCTIONS,
)
from eval.ai_qa_prompt import render_case_input as render_baseline_input
from eval.ai_qa_review_contract import (
    MODEL_OUTPUT_JSON_SCHEMA as CANDIDATE_OUTPUT_SCHEMA,
)
from eval.ai_qa_review_contract import (
    REVIEW_PROMPT_VERSION,
    SYSTEM_INSTRUCTIONS as CANDIDATE_SYSTEM_INSTRUCTIONS,
)
from eval.ai_qa_review_contract import (
    render_case_input as render_candidate_input,
)
from eval.ai_qa_review_development import (
    DEFAULT_OUTPUT_DIR as DEFAULT_DATASET_DIR,
)
from eval.ai_qa_review_development import (
    MANIFEST_FILE,
    MODEL_INPUTS_FILE,
    TRUTH_FILE,
    verify_review_development,
)


RUNNER_VERSION = "review-plan-v1"
MODEL = "gpt-5.6-terra"
REASONING_EFFORT = "high"
SERVICE_TIER = "default"
RETRIES = 0
TIMEOUT_SECONDS = 60.0
STORE = False

INPUT_PRICE_PER_1M = Decimal("2.50")
CACHED_INPUT_PRICE_PER_1M = Decimal("0.25")
OUTPUT_PRICE_PER_1M = Decimal("15.00")
PRICING_OBSERVED_DATE = "2026-07-30"
PRICING_SOURCE = "https://developers.openai.com/api/docs/pricing"

DEFAULT_PLAN_PATH = (
    Path(__file__).with_name("runs")
    / "review-v1-development-dry-run.json"
)

_FORBIDDEN_REQUEST_KEYS = (
    "case_type",
    "corrupted_field",
    "expected_value",
    "corrupted_value",
    "corruption_type",
    "truth",
)

_PROFILES = {
    "baseline": {
        "prompt_version": TERRA_V1_PROMPT_VERSION,
        "system_instructions": TERRA_V1_SYSTEM_INSTRUCTIONS,
        "schema": BASELINE_OUTPUT_SCHEMA,
        "render": render_baseline_input,
        "max_output_tokens": 256,
        "future_output_dir": "eval/runs/review-v1-development-baseline",
    },
    "candidate": {
        "prompt_version": REVIEW_PROMPT_VERSION,
        "system_instructions": CANDIDATE_SYSTEM_INSTRUCTIONS,
        "schema": CANDIDATE_OUTPUT_SCHEMA,
        "render": render_candidate_input,
        "max_output_tokens": 512,
        "future_output_dir": "eval/runs/review-v1-development-candidate",
    },
}


class ReviewRunnerError(RuntimeError):
    """The review-v1 development runner cannot proceed safely."""


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as artifact:
        for chunk in iter(lambda: artifact.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
    ]


def _round_up_cents(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_CEILING)


def _cost_usd(
    *,
    input_tokens: int,
    output_tokens: int,
) -> Decimal:
    return (
        Decimal(input_tokens) * INPUT_PRICE_PER_1M
        + Decimal(output_tokens) * OUTPUT_PRICE_PER_1M
    ) / Decimal(1_000_000)


def _verify_request_hygiene(
    *,
    case: Mapping[str, object],
    rendered_input: str,
) -> None:
    if str(case["case_id"]) in rendered_input:
        raise ReviewRunnerError("case ID leaked into model input")
    for forbidden in _FORBIDDEN_REQUEST_KEYS:
        if f'"{forbidden}"' in rendered_input:
            raise ReviewRunnerError(
                f"hidden answer field leaked into model input: {forbidden}"
            )


def _profile_plan(
    *,
    profile: str,
    cases: list[dict[str, Any]],
) -> dict[str, object]:
    config = _PROFILES[profile]
    system_instructions = str(config["system_instructions"])
    render = config["render"]
    max_output_tokens = int(config["max_output_tokens"])

    rendered_inputs: list[str] = []
    for case in cases:
        rendered = render(case)
        _verify_request_hygiene(case=case, rendered_input=rendered)
        rendered_inputs.append(rendered)

    system_bytes_per_request = len(system_instructions.encode("utf-8"))
    user_input_bytes = sum(
        len(rendered.encode("utf-8"))
        for rendered in rendered_inputs
    )
    input_token_upper_bound = (
        system_bytes_per_request * len(cases)
        + user_input_bytes
    )
    output_token_upper_bound = max_output_tokens * len(cases)
    worst_case_cost = _cost_usd(
        input_tokens=input_token_upper_bound,
        output_tokens=output_token_upper_bound,
    )

    return {
        "profile": profile,
        "configuration": {
            "model": MODEL,
            "reasoning_effort": REASONING_EFFORT,
            "prompt_version": config["prompt_version"],
            "max_output_tokens": max_output_tokens,
            "retries": RETRIES,
            "service_tier": SERVICE_TIER,
            "timeout_seconds": TIMEOUT_SECONDS,
            "store": STORE,
            "strict_structured_outputs": True,
        },
        "hashes": {
            "prompt_sha256": _sha256_bytes(
                system_instructions.encode("utf-8")
            ),
            "output_schema_sha256": _sha256_bytes(
                _canonical_json(config["schema"]).encode("utf-8")
            ),
            "rendered_inputs_sha256": _sha256_bytes(
                "\n".join(rendered_inputs).encode("utf-8")
            ),
        },
        "requests": {
            "case_requests": len(cases),
            "retry_requests_reserved": RETRIES * len(cases),
            "maximum_responses_api_requests": (
                len(cases) * (RETRIES + 1)
            ),
        },
        "preflight": {
            "method": (
                "UTF-8 bytes as a conservative input-token upper bound; "
                "maximum output tokens reserved for every case; no cache "
                "discount assumed"
            ),
            "input_token_upper_bound": input_token_upper_bound,
            "output_token_upper_bound": output_token_upper_bound,
            "worst_case_cost_usd": str(worst_case_cost.quantize(Decimal("0.000001"))),
            "hard_budget_limit_usd": str(_round_up_cents(worst_case_cost)),
        },
        "future_output_dir": config["future_output_dir"],
    }


def build_review_development_dry_run(
    *,
    dataset_dir: Path = DEFAULT_DATASET_DIR,
) -> dict[str, object]:
    """Build a deterministic paired request plan without network access."""

    manifest = verify_review_development(dataset_dir)
    input_path = dataset_dir / MODEL_INPUTS_FILE
    truth_path = dataset_dir / TRUTH_FILE
    cases = _read_jsonl(input_path)
    truth = _read_jsonl(truth_path)

    profiles = {
        name: _profile_plan(profile=name, cases=cases)
        for name in ("baseline", "candidate")
    }
    combined_hard_budget = sum(
        Decimal(profile["preflight"]["hard_budget_limit_usd"])
        for profile in profiles.values()
    )
    focus_counts = Counter(
        str(row["corruption_type"])
        for row in truth
        if row["case_type"] == "corrupted"
        and row["corruption_type"]
        in {"rooms_neighbor_value", "postal_code_substitution"}
    )

    return {
        "runner_version": RUNNER_VERSION,
        "mode": "dry_run",
        "network_calls_made": 0,
        "credential_read": False,
        "dataset": {
            "split": manifest["split"],
            "case_count": len(cases),
            "model_inputs_file": MODEL_INPUTS_FILE,
            "model_inputs_sha256": _sha256_file(input_path),
            "truth_file": TRUTH_FILE,
            "truth_sha256": _sha256_file(truth_path),
            "manifest_file": MANIFEST_FILE,
            "manifest_sha256": _sha256_file(dataset_dir / MANIFEST_FILE),
            "focus_cases": dict(sorted(focus_counts.items())),
        },
        "paired_comparison": {
            "same_cases": True,
            "same_model": True,
            "same_reasoning_effort": True,
            "profiles": profiles,
            "responses_api_requests": sum(
                profile["requests"]["maximum_responses_api_requests"]
                for profile in profiles.values()
            ),
            "model_availability_checks": 1,
            "maximum_total_api_calls": (
                1
                + sum(
                    profile["requests"][
                        "maximum_responses_api_requests"
                    ]
                    for profile in profiles.values()
                )
            ),
        },
        "pricing": {
            "input_per_1m_usd": str(INPUT_PRICE_PER_1M),
            "cached_input_per_1m_usd": str(CACHED_INPUT_PRICE_PER_1M),
            "output_per_1m_usd": str(OUTPUT_PRICE_PER_1M),
            "observed_date": PRICING_OBSERVED_DATE,
            "source": PRICING_SOURCE,
            "must_refresh_before_execute": True,
        },
        "combined_hard_budget_limit_usd": str(combined_hard_budget),
        "development_targets": {
            "candidate": {
                "successful_checks": "at least 119/120",
                "errors_detected": "at least 68/70",
                "correct_fields": "at least 67/70",
                "clean_false_alerts": "at most 1/50",
                "rooms_correct_field": "at least 19/20",
                "wbs_correct_field": "10/10",
                "rent_kalt_correct_field": "10/10",
                "address_postal_code_correct_field": "10/10",
                "district_correct_field": "8/8",
                "floor_correct_field": "6/6",
                "rent_warm_correct_field": "6/6",
            },
            "comparison": {
                "total_correct_regressions_allowed": 0,
                "clean_false_alert_regressions_allowed": 0,
                "focus_rule": (
                    "Candidate must not score below baseline on rooms plus "
                    "postal-code cases; if baseline misses any focus case, "
                    "candidate must produce at least one net recovery."
                ),
            },
        },
        "execution_guard": {
            "status": "blocked",
            "reason": (
                "No development execution freeze exists. This dry run does "
                "not authorize an API call."
            ),
            "next_required_artifact": (
                "eval/runs/review-v1-development-configuration-freeze.json"
            ),
        },
        "boundaries": {
            "development_only": True,
            "final_600_case_evidence": False,
            "product_runtime_modified": False,
            "old_holdout_reused": False,
        },
    }


def write_dry_run_plan(
    path: Path = DEFAULT_PLAN_PATH,
) -> dict[str, object]:
    if path.exists():
        raise FileExistsError("review-v1 dry-run plan already exists")
    plan = build_review_development_dry_run()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    verify_dry_run_plan(path)
    return plan


def verify_dry_run_plan(
    path: Path = DEFAULT_PLAN_PATH,
) -> dict[str, object]:
    stored = json.loads(path.read_text(encoding="utf-8"))
    expected = build_review_development_dry_run()
    if stored != expected:
        raise ValueError("review-v1 dry-run plan does not match current inputs")
    return stored


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plan the paired review-v1 development run without a network call.",
    )
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument(
        "--plan-path",
        type=Path,
        default=DEFAULT_PLAN_PATH,
    )
    args = parser.parse_args()

    if args.execute:
        raise ReviewRunnerError(
            "API execution is disabled until a separate configuration freeze exists"
        )
    if args.write and args.verify_only:
        parser.error("--write and --verify-only are mutually exclusive")

    if args.write:
        plan = write_dry_run_plan(args.plan_path)
    elif args.verify_only:
        plan = verify_dry_run_plan(args.plan_path)
    else:
        plan = build_review_development_dry_run()
    print(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
