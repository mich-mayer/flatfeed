from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol

import openai
from dotenv import dotenv_values
from openai import OpenAI

from eval.ai_qa_corruptions import MODEL_PARSER_SNAPSHOT_FIELDS
from eval.ai_qa_datasets import DEFAULT_DATASET_DIR
from eval.ai_qa_luna_calibration import DEFAULT_LUNA_DATASET_DIR
from eval.ai_qa_luna_v3_cycle import DEFAULT_LUNA_V3_DATASET_DIR
from eval.ai_qa_luna_v4_cycle import DEFAULT_LUNA_V4_DATASET_DIR
from eval.ai_qa_luna_v5_cycle import DEFAULT_LUNA_V5_DATASET_DIR
from eval.ai_qa_luna_effort_screen import DEFAULT_LUNA_EFFORT_SCREEN_DIR
from eval.ai_qa_luna_low_cycle import DEFAULT_LUNA_LOW_DATASET_DIR
from eval.ai_qa_terra_effort_screen import DEFAULT_TERRA_EFFORT_SCREEN_DIR
from eval.ai_qa_terra_prompt_reasoning_screen import (
    DEFAULT_TERRA_PROMPT_REASONING_SCREEN_DIR,
)
from eval.ai_qa_terra_calibration_cycle import (
    DEFAULT_TERRA_CALIBRATION_DATASET_DIR,
)
from eval.ai_qa_terra_high_cycle import DEFAULT_TERRA_HIGH_DATASET_DIR
from eval.ai_qa_terra_high_screen import DEFAULT_TERRA_HIGH_SCREEN_DIR
from eval.ai_qa_terra_v2_screen import DEFAULT_TERRA_V2_SCREEN_DIR
from eval.ai_qa_holdout_readiness import audit_locked_holdout_readiness
from eval.ai_qa_prompt import (
    EVAL_PROMPT_VERSION,
    PROMPT_INSTRUCTIONS,
    MODEL_OUTPUT_JSON_SCHEMA,
    RESPONSES_TEXT_FORMAT,
    get_system_instructions,
    render_case_input,
)
from eval.ai_qa_reports import REPORT_FILENAMES
from eval.ai_qa_scorer import EXPERIMENT_LABEL, load_jsonl


RUNNER_VERSION = "1.5"
RUN_MANIFEST_SCHEMA_VERSION = "1.0"
DEFAULT_MODEL = "gpt-5.4-mini-2026-03-17"
DEFAULT_REASONING_EFFORT = "none"
DEFAULT_MAX_OUTPUT_TOKENS = 64
DEFAULT_RETRIES = 2
DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_SERVICE_TIER = "default"

REPO_ROOT = Path(__file__).resolve().parents[1]
EVAL_ROOT = Path(__file__).resolve().parent
EVAL_ENV_PATH = REPO_ROOT / ".env.eval.local"
DATASET_MANIFEST_PATH = DEFAULT_DATASET_DIR / "dataset_manifest.json"
LUNA_DATASET_MANIFEST_PATH = DEFAULT_LUNA_DATASET_DIR / "dataset_manifest.json"
LUNA_V3_DATASET_MANIFEST_PATH = (
    DEFAULT_LUNA_V3_DATASET_DIR / "dataset_manifest.json"
)
LUNA_V3_FREEZE_PATH = EVAL_ROOT / "runs" / "luna-v3-configuration-freeze.json"
LUNA_V4_DATASET_MANIFEST_PATH = (
    DEFAULT_LUNA_V4_DATASET_DIR / "dataset_manifest.json"
)
LUNA_V4_FREEZE_PATH = EVAL_ROOT / "runs" / "luna-v4-configuration-freeze.json"
LUNA_V4_VALIDATION_RUN_DIR = EVAL_ROOT / "runs" / "luna-v4-validation"
LUNA_V5_DATASET_MANIFEST_PATH = (
    DEFAULT_LUNA_V5_DATASET_DIR / "dataset_manifest.json"
)
LUNA_V5_FREEZE_PATH = EVAL_ROOT / "runs" / "luna-v5-configuration-freeze.json"
LUNA_EFFORT_SCREEN_MANIFEST_PATH = (
    DEFAULT_LUNA_EFFORT_SCREEN_DIR / "dataset_manifest.json"
)
LUNA_EFFORT_SCREEN_RUN_DIRS = {
    "none": EVAL_ROOT / "runs" / "luna-effort-screen-none",
    "low": EVAL_ROOT / "runs" / "luna-effort-screen-low",
}
LUNA_LOW_DATASET_MANIFEST_PATH = (
    DEFAULT_LUNA_LOW_DATASET_DIR / "dataset_manifest.json"
)
LUNA_LOW_CALIBRATION_RUN_DIR = EVAL_ROOT / "runs" / "luna-low-calibration"
LUNA_LOW_VALIDATION_RUN_DIR = EVAL_ROOT / "runs" / "luna-low-validation"
LUNA_LOW_FREEZE_PATH = EVAL_ROOT / "runs" / "luna-low-configuration-freeze.json"
LUNA_LOW_CALIBRATION_HARD_BUDGET_USD = Decimal("1.72")
TERRA_EFFORT_SCREEN_MANIFEST_PATH = (
    DEFAULT_TERRA_EFFORT_SCREEN_DIR / "dataset_manifest.json"
)
TERRA_EFFORT_SCREEN_RUN_DIRS = {
    "none": EVAL_ROOT / "runs" / "terra-effort-screen-none",
    "low": EVAL_ROOT / "runs" / "terra-effort-screen-low",
}
TERRA_EFFORT_SCREEN_HARD_BUDGET_USD = Decimal("0.80")
TERRA_PROMPT_REASONING_SCREEN_MANIFEST_PATH = (
    DEFAULT_TERRA_PROMPT_REASONING_SCREEN_DIR / "dataset_manifest.json"
)
TERRA_PROMPT_REASONING_SCREEN_RUN_DIRS = {
    ("luna-v5", "low"): EVAL_ROOT / "runs" / "terra-2x2-luna-v5-low",
    ("terra-v1", "low"): EVAL_ROOT / "runs" / "terra-2x2-terra-v1-low",
    ("luna-v5", "medium"): EVAL_ROOT / "runs" / "terra-2x2-luna-v5-medium",
    ("terra-v1", "medium"): EVAL_ROOT / "runs" / "terra-2x2-terra-v1-medium",
}
TERRA_PROMPT_REASONING_SCREEN_HARD_BUDGET_USD = Decimal("0.90")
TERRA_CALIBRATION_MANIFEST_PATH = (
    DEFAULT_TERRA_CALIBRATION_DATASET_DIR / "dataset_manifest.json"
)
TERRA_CALIBRATION_RUN_DIR = EVAL_ROOT / "runs" / "terra-calibration"
TERRA_CALIBRATION_FREEZE_PATH = EVAL_ROOT / "runs" / "terra-calibration-configuration-freeze.json"
TERRA_CALIBRATION_HARD_BUDGET_USD = Decimal("5.00")
TERRA_VALIDATION_RUN_DIR = EVAL_ROOT / "runs" / "terra-validation"
TERRA_VALIDATION_HARD_BUDGET_USD = Decimal("5.00")
TERRA_V2_SCREEN_MANIFEST_PATH = (
    DEFAULT_TERRA_V2_SCREEN_DIR / "dataset_manifest.json"
)
TERRA_V2_SCREEN_RUN_DIRS = {
    "terra-v1": EVAL_ROOT / "runs" / "terra-v2-screen-terra-v1-medium",
    "terra-v2": EVAL_ROOT / "runs" / "terra-v2-screen-terra-v2-medium",
}
TERRA_V2_SCREEN_HARD_BUDGET_USD = Decimal("1.50")
TERRA_HIGH_SCREEN_MANIFEST_PATH = (
    DEFAULT_TERRA_HIGH_SCREEN_DIR / "dataset_manifest.json"
)
TERRA_HIGH_SCREEN_RUN_DIRS = {
    "medium": EVAL_ROOT / "runs" / "terra-high-screen-medium",
    "high": EVAL_ROOT / "runs" / "terra-high-screen-high",
}
TERRA_HIGH_SCREEN_HARD_BUDGET_USD = Decimal("1.00")
TERRA_HIGH_DATASET_MANIFEST_PATH = (
    DEFAULT_TERRA_HIGH_DATASET_DIR / "dataset_manifest.json"
)
TERRA_HIGH_CALIBRATION_RUN_DIR = (
    EVAL_ROOT / "runs" / "terra-high-calibration"
)
TERRA_HIGH_VALIDATION_RUN_DIR = EVAL_ROOT / "runs" / "terra-high-validation"
TERRA_HIGH_FREEZE_PATH = (
    EVAL_ROOT / "runs" / "terra-high-configuration-freeze.json"
)
TERRA_HIGH_CALIBRATION_HARD_BUDGET_USD = Decimal("5.00")
LOCKED_HOLDOUT_FREEZE_PATH = (
    EVAL_ROOT / "runs" / "terra-high-locked-holdout-configuration-freeze.json"
)
LOCKED_HOLDOUT_RUN_DIR = EVAL_ROOT / "runs" / "terra-high-locked-holdout"
LOCKED_HOLDOUT_HARD_BUDGET_USD = Decimal("10.40")
TERRA_HIGH_VALIDATION_SCORECARD_PATH = (
    TERRA_HIGH_VALIDATION_RUN_DIR
    / "product-scorecard"
    / "product_scorecard.json"
)

PREDICTIONS_FILENAME = "predictions.jsonl"
RUN_MANIFEST_FILENAME = "run_manifest.json"

# Standard direct-API short-context rates per 1M tokens, observed on
# 2026-07-21. Keep the original constants as compatibility aliases for the
# initial candidate and existing tests; all runner calculations resolve rates
# from the configured model.
INPUT_PRICE_PER_1M = Decimal("0.75")
CACHED_INPUT_PRICE_PER_1M = Decimal("0.075")
OUTPUT_PRICE_PER_1M = Decimal("4.50")
MODEL_PRICING_PER_1M: dict[str, tuple[Decimal, Decimal, Decimal]] = {
    DEFAULT_MODEL: (
        INPUT_PRICE_PER_1M,
        CACHED_INPUT_PRICE_PER_1M,
        OUTPUT_PRICE_PER_1M,
    ),
    "gpt-5.6-luna": (
        Decimal("1.00"),
        Decimal("0.10"),
        Decimal("6.00"),
    ),
    "gpt-5.6-terra": (
        Decimal("2.50"),
        Decimal("0.25"),
        Decimal("15.00"),
    ),
    "gpt-5.6-sol": (
        Decimal("5.00"),
        Decimal("0.50"),
        Decimal("30.00"),
    ),
}
PRICING_SOURCE = "https://developers.openai.com/api/docs/pricing"
PRICING_OBSERVED_DATE = "2026-07-21"

_MODEL_INPUT_KEYS = {"case_id", "raw_text", "parser_snapshot"}
_PARSER_SNAPSHOT_KEYS = set(MODEL_PARSER_SNAPSHOT_FIELDS)
_FORBIDDEN_MODEL_KEYS = {
    "answer_key",
    "case_type",
    "clean",
    "corrupted",
    "corrupted_field",
    "corrupted_value",
    "corruption_type",
    "error_category",
    "expected_value",
    "generation_seed",
    "label",
    "seed",
    "split",
    "truth",
}
_MILLION = Decimal("1000000")


class OfflineRunnerError(RuntimeError):
    """A safe, user-facing runner failure without provider secret details."""


class ResponsesClient(Protocol):
    models: Any
    responses: Any


@dataclass(frozen=True)
class RunnerConfig:
    model: str = DEFAULT_MODEL
    reasoning_effort: str = DEFAULT_REASONING_EFFORT
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS
    retries: int = DEFAULT_RETRIES
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    prompt_version: str = EVAL_PROMPT_VERSION

    def validate(self) -> None:
        if not self.model.strip():
            raise ValueError("model must be a non-empty string")
        _pricing_for_model(self.model)
        if self.reasoning_effort not in {"none", "low", "medium", "high"}:
            raise ValueError(
                "reasoning_effort must be none, low, medium, or high"
            )
        if self.max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be positive")
        if self.retries < 0:
            raise ValueError("retries must be non-negative")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        get_system_instructions(self.prompt_version)


@dataclass(frozen=True)
class RunPlan:
    split: str
    input_path: Path
    input_sha256: str
    dataset_manifest_sha256: str
    cases: tuple[Mapping[str, object], ...]
    config: RunnerConfig
    worst_case_cost_usd: Decimal

    @property
    def case_count(self) -> int:
        return len(self.cases)

    @property
    def max_attempts(self) -> int:
        return self.case_count * (self.config.retries + 1)


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _pricing_for_model(
    model: str,
) -> tuple[Decimal, Decimal, Decimal]:
    try:
        return MODEL_PRICING_PER_1M[model]
    except KeyError:
        raise ValueError(
            f"no verified pricing is configured for model: {model}"
        ) from None


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as artifact:
        for chunk in iter(lambda: artifact.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ensure_inside_eval(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    try:
        resolved.relative_to(EVAL_ROOT)
    except ValueError as exc:
        raise ValueError("runner artifacts must stay inside eval/") from exc
    return resolved


def _forbidden_keys(value: object) -> set[str]:
    found: set[str] = set()
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if isinstance(key, str) and key in _FORBIDDEN_MODEL_KEYS:
                found.add(key)
            found.update(_forbidden_keys(nested))
    elif isinstance(value, list):
        for nested in value:
            found.update(_forbidden_keys(nested))
    return found


def _validate_model_input_rows(
    rows: Sequence[Mapping[str, object]],
) -> None:
    if not rows:
        raise ValueError("model input artifact must not be empty")
    seen_case_ids: set[str] = set()
    for row in rows:
        if set(row) != _MODEL_INPUT_KEYS:
            raise ValueError("model input row does not match the frozen schema")
        case_id = row.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError("model input case_id must be a non-empty string")
        if case_id in seen_case_ids:
            raise ValueError(f"duplicate model input case_id: {case_id}")
        seen_case_ids.add(case_id)
        if not isinstance(row.get("raw_text"), str) or not row["raw_text"]:
            raise ValueError(f"raw_text is missing for {case_id}")
        snapshot = row.get("parser_snapshot")
        if not isinstance(snapshot, Mapping) or set(snapshot) != (
            _PARSER_SNAPSHOT_KEYS
        ):
            raise ValueError(f"parser_snapshot schema mismatch for {case_id}")
        leaked_keys = _forbidden_keys(row)
        if leaked_keys:
            raise ValueError(
                f"answer-key leakage detected for {case_id}: "
                f"{sorted(leaked_keys)}"
            )


def _load_dataset_manifest(path: Path) -> Mapping[str, object]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("dataset manifest is missing or invalid") from exc
    if not isinstance(manifest, Mapping):
        raise ValueError("dataset manifest must be a JSON object")
    return manifest


def _split_input_contract(
    split: str,
) -> tuple[Path, str, str]:
    contracts = {
        "development": (DATASET_MANIFEST_PATH, DEFAULT_DATASET_DIR),
        "locked_holdout": (DATASET_MANIFEST_PATH, DEFAULT_DATASET_DIR),
        "luna_calibration": (
            LUNA_DATASET_MANIFEST_PATH,
            DEFAULT_LUNA_DATASET_DIR,
        ),
        "luna_validation": (
            LUNA_DATASET_MANIFEST_PATH,
            DEFAULT_LUNA_DATASET_DIR,
        ),
        "luna_v3_calibration": (
            LUNA_V3_DATASET_MANIFEST_PATH,
            DEFAULT_LUNA_V3_DATASET_DIR,
        ),
        "luna_v3_validation": (
            LUNA_V3_DATASET_MANIFEST_PATH,
            DEFAULT_LUNA_V3_DATASET_DIR,
        ),
        "luna_v4_calibration": (
            LUNA_V4_DATASET_MANIFEST_PATH,
            DEFAULT_LUNA_V4_DATASET_DIR,
        ),
        "luna_v4_validation": (
            LUNA_V4_DATASET_MANIFEST_PATH,
            DEFAULT_LUNA_V4_DATASET_DIR,
        ),
        "luna_v5_calibration": (
            LUNA_V5_DATASET_MANIFEST_PATH,
            DEFAULT_LUNA_V5_DATASET_DIR,
        ),
        "luna_v5_validation": (
            LUNA_V5_DATASET_MANIFEST_PATH,
            DEFAULT_LUNA_V5_DATASET_DIR,
        ),
        "luna_effort_screen": (
            LUNA_EFFORT_SCREEN_MANIFEST_PATH,
            DEFAULT_LUNA_EFFORT_SCREEN_DIR,
        ),
        "luna_low_calibration": (
            LUNA_LOW_DATASET_MANIFEST_PATH,
            DEFAULT_LUNA_LOW_DATASET_DIR,
        ),
        "luna_low_validation": (
            LUNA_LOW_DATASET_MANIFEST_PATH,
            DEFAULT_LUNA_LOW_DATASET_DIR,
        ),
        "terra_effort_screen": (
            TERRA_EFFORT_SCREEN_MANIFEST_PATH,
            DEFAULT_TERRA_EFFORT_SCREEN_DIR,
        ),
        "terra_prompt_reasoning_screen": (
            TERRA_PROMPT_REASONING_SCREEN_MANIFEST_PATH,
            DEFAULT_TERRA_PROMPT_REASONING_SCREEN_DIR,
        ),
        "terra_calibration": (
            TERRA_CALIBRATION_MANIFEST_PATH,
            DEFAULT_TERRA_CALIBRATION_DATASET_DIR,
        ),
        "terra_validation": (
            TERRA_CALIBRATION_MANIFEST_PATH,
            DEFAULT_TERRA_CALIBRATION_DATASET_DIR,
        ),
        "terra_v2_prompt_screen": (
            TERRA_V2_SCREEN_MANIFEST_PATH,
            DEFAULT_TERRA_V2_SCREEN_DIR,
        ),
        "terra_high_reasoning_screen": (
            TERRA_HIGH_SCREEN_MANIFEST_PATH,
            DEFAULT_TERRA_HIGH_SCREEN_DIR,
        ),
        "terra_high_calibration": (
            TERRA_HIGH_DATASET_MANIFEST_PATH,
            DEFAULT_TERRA_HIGH_DATASET_DIR,
        ),
        "terra_high_validation": (
            TERRA_HIGH_DATASET_MANIFEST_PATH,
            DEFAULT_TERRA_HIGH_DATASET_DIR,
        ),
    }
    if split not in contracts:
        raise ValueError(f"unsupported dataset split: {split}")
    manifest_path, dataset_dir = contracts[split]
    manifest = _load_dataset_manifest(manifest_path)
    try:
        artifact = (
            manifest["model_inputs"]
            if split in {
                "luna_effort_screen",
                "terra_effort_screen",
                "terra_prompt_reasoning_screen",
                "terra_v2_prompt_screen",
                "terra_high_reasoning_screen",
            }
            else manifest["splits"][split]["artifacts"]["model_inputs"]
        )
        filename = artifact["file"]
        expected_sha256 = artifact["sha256"]
    except (KeyError, TypeError) as exc:
        raise ValueError("dataset manifest lacks the requested split") from exc
    if not isinstance(filename, str) or not isinstance(expected_sha256, str):
        raise ValueError("dataset manifest model-input entry is invalid")
    input_path = (dataset_dir / filename).resolve()
    actual_sha256 = _sha256_file(input_path)
    if actual_sha256 != expected_sha256:
        raise ValueError("model input SHA-256 does not match dataset manifest")
    return input_path, actual_sha256, _sha256_file(manifest_path)


def _conservative_input_token_bound(
    case: Mapping[str, object],
    *,
    prompt_version: str,
) -> int:
    request_text = get_system_instructions(prompt_version) + render_case_input(case)
    return len(request_text.encode("utf-8"))


def _request_worst_case_cost(
    case: Mapping[str, object],
    *,
    model: str,
    max_output_tokens: int,
    prompt_version: str,
) -> Decimal:
    input_price, _cached_input_price, output_price = _pricing_for_model(model)
    input_tokens = Decimal(
        _conservative_input_token_bound(
            case,
            prompt_version=prompt_version,
        )
    )
    output_tokens = Decimal(max_output_tokens)
    return (
        input_tokens * input_price
        + output_tokens * output_price
    ) / _MILLION


def build_run_plan(
    *,
    split: str = "development",
    limit: int | None = None,
    config: RunnerConfig | None = None,
) -> RunPlan:
    config = config or RunnerConfig()
    config.validate()
    if limit is not None and limit <= 0:
        raise ValueError("limit must be positive")
    input_path, input_sha256, manifest_sha256 = _split_input_contract(split)
    rows = load_jsonl(input_path)
    _validate_model_input_rows(rows)
    if limit is not None and limit > len(rows):
        raise ValueError("limit exceeds the available cases")
    selected_rows = tuple(rows[:limit] if limit is not None else rows)
    attempts = Decimal(config.retries + 1)
    worst_case_cost = sum(
        (
            _request_worst_case_cost(
                case,
                model=config.model,
                max_output_tokens=config.max_output_tokens,
                prompt_version=config.prompt_version,
            )
            * attempts
            for case in selected_rows
        ),
        Decimal("0"),
    )
    plan = RunPlan(
        split=split,
        input_path=input_path,
        input_sha256=input_sha256,
        dataset_manifest_sha256=manifest_sha256,
        cases=selected_rows,
        config=config,
        worst_case_cost_usd=worst_case_cost,
    )
    if split == "luna_v3_validation":
        _validate_luna_v3_freeze(plan)
    if split == "luna_v4_validation":
        _validate_luna_v4_freeze(plan)
    if split == "luna_v5_validation":
        _validate_luna_v5_freeze(plan)
    if split == "luna_effort_screen":
        _validate_luna_effort_screen_plan(plan)
    if split in {"luna_low_calibration", "luna_low_validation"}:
        _validate_luna_low_plan(plan)
    if split == "luna_low_validation":
        _validate_luna_low_validation_freeze(plan)
    if split == "terra_effort_screen":
        _validate_terra_effort_screen_plan(plan)
    if split == "terra_prompt_reasoning_screen":
        _validate_terra_prompt_reasoning_screen_plan(plan)
    if split == "terra_calibration":
        _validate_terra_calibration_plan(plan)
    if split == "terra_validation":
        _validate_terra_calibration_plan(plan)
        _validate_terra_validation_freeze(plan)
    if split == "terra_v2_prompt_screen":
        _validate_terra_v2_prompt_screen_plan(plan)
    if split == "terra_high_reasoning_screen":
        _validate_terra_high_reasoning_screen_plan(plan)
    if split in {"terra_high_calibration", "terra_high_validation"}:
        _validate_terra_high_cycle_plan(plan)
    if split == "terra_high_validation":
        _validate_terra_high_validation_freeze(plan)
    if split == "locked_holdout":
        _validate_locked_holdout_plan(plan)
    return plan


def _validate_luna_v3_freeze(plan: RunPlan) -> None:
    """Require the exact predeclared configuration before validation."""

    try:
        freeze = json.loads(LUNA_V3_FREEZE_PATH.read_text(encoding="utf-8"))
        frozen_config = freeze["configuration"]
        frozen_validation = freeze["validation"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise OfflineRunnerError("Luna-v3 configuration freeze is invalid") from exc

    expected_config = {
        "model": plan.config.model,
        "reasoning_effort": plan.config.reasoning_effort,
        "prompt_version": plan.config.prompt_version,
        "max_output_tokens": plan.config.max_output_tokens,
        "retries": plan.config.retries,
        "runner_version": "1.2",
        "strict_structured_outputs": True,
        "prompt_sha256": _sha256_bytes(
            get_system_instructions(plan.config.prompt_version).encode("utf-8")
        ),
        "output_schema_sha256": _sha256_bytes(
            _canonical_json(MODEL_OUTPUT_JSON_SCHEMA).encode("utf-8")
        ),
    }
    if frozen_config != expected_config:
        raise OfflineRunnerError("Luna-v3 runner configuration differs from freeze")
    if frozen_validation != {
        "case_count": plan.case_count,
        "dataset_manifest_sha256": plan.dataset_manifest_sha256,
        "hard_budget_limit_usd": 0.813,
        "model_inputs_sha256": plan.input_sha256,
        "prompt_changes_after_run": False,
        "run_count_limit": 1,
        "split": plan.split,
    }:
        raise OfflineRunnerError("Luna-v3 validation input differs from freeze")


def _luna_v4_frozen_configuration(plan: RunPlan) -> dict[str, object]:
    return {
        "model": plan.config.model,
        "reasoning_effort": plan.config.reasoning_effort,
        "prompt_version": plan.config.prompt_version,
        "max_output_tokens": plan.config.max_output_tokens,
        "retries": plan.config.retries,
        "runner_version": RUNNER_VERSION,
        "strict_structured_outputs": True,
        "prompt_sha256": _sha256_bytes(
            get_system_instructions(plan.config.prompt_version).encode("utf-8")
        ),
        "output_schema_sha256": _sha256_bytes(
            _canonical_json(MODEL_OUTPUT_JSON_SCHEMA).encode("utf-8")
        ),
    }


def write_luna_v4_configuration_freeze(
    *,
    calibration_report_path: Path,
    calibration_run_manifest_path: Path,
    validation_budget_limit_usd: Decimal,
    output_path: Path = LUNA_V4_FREEZE_PATH,
) -> Path:
    """Freeze a passing calibration before the one validation run."""

    output_path = _ensure_inside_eval(output_path)
    if output_path.exists():
        raise FileExistsError("Luna-v4 configuration freeze already exists")
    try:
        report = json.loads(calibration_report_path.read_text(encoding="utf-8"))
        run_manifest = json.loads(
            calibration_run_manifest_path.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("calibration evidence is missing or invalid") from exc
    if report.get("split") != "luna_v4_calibration":
        raise ValueError("calibration report has the wrong split")
    if report.get("acceptance_gates", {}).get("overall_status") != "pass":
        raise OfflineRunnerError("Luna-v4 calibration did not pass every gate")
    if run_manifest.get("status") != "completed":
        raise ValueError("calibration run manifest is not completed")
    if (
        run_manifest.get("split") != "luna_v4_calibration"
        or run_manifest.get("case_count") != 240
    ):
        raise ValueError("calibration run manifest has the wrong dataset")

    calibration_config = run_manifest.get("configuration", {})
    config = RunnerConfig(
        model=str(calibration_config.get("model", "")),
        reasoning_effort=str(calibration_config.get("reasoning_effort", "")),
        max_output_tokens=int(calibration_config.get("max_output_tokens", 0)),
        retries=int(calibration_config.get("retries", -1)),
        timeout_seconds=float(calibration_config.get("timeout_seconds", 0)),
        prompt_version=str(calibration_config.get("prompt_version", "")),
    )
    expected = RunnerConfig(
        model="gpt-5.6-luna",
        reasoning_effort="none",
        max_output_tokens=64,
        retries=0,
        timeout_seconds=config.timeout_seconds,
        prompt_version="luna-v4",
    )
    if config != expected or run_manifest.get("runner_version") != RUNNER_VERSION:
        raise OfflineRunnerError("calibration did not use the predeclared config")
    expected_prompt_hash = _sha256_bytes(
        get_system_instructions(config.prompt_version).encode("utf-8")
    )
    expected_schema_hash = _sha256_bytes(
        _canonical_json(MODEL_OUTPUT_JSON_SCHEMA).encode("utf-8")
    )
    if (
        calibration_config.get("prompt_sha256") != expected_prompt_hash
        or calibration_config.get("output_schema_sha256")
        != expected_schema_hash
        or calibration_config.get("strict_structured_outputs") is not True
        or calibration_config.get("responses_api") is not True
        or calibration_config.get("store") is not False
    ):
        raise OfflineRunnerError("calibration prompt or schema evidence differs")

    input_path, input_sha256, manifest_sha256 = _split_input_contract(
        "luna_v4_validation"
    )
    rows = load_jsonl(input_path)
    _validate_model_input_rows(rows)
    validation_plan = RunPlan(
        split="luna_v4_validation",
        input_path=input_path,
        input_sha256=input_sha256,
        dataset_manifest_sha256=manifest_sha256,
        cases=tuple(rows),
        config=config,
        worst_case_cost_usd=sum(
            (
                _request_worst_case_cost(
                    case,
                    model=config.model,
                    max_output_tokens=config.max_output_tokens,
                    prompt_version=config.prompt_version,
                )
                for case in rows
            ),
            Decimal("0"),
        ),
    )
    if validation_plan.worst_case_cost_usd > validation_budget_limit_usd:
        raise OfflineRunnerError("validation budget is below the preflight bound")

    freeze = {
        "schema_version": "1.0",
        "status": "validation_authorized_once",
        "configuration": _luna_v4_frozen_configuration(validation_plan),
        "calibration_evidence": {
            "report_sha256": _sha256_file(calibration_report_path),
            "run_manifest_sha256": _sha256_file(calibration_run_manifest_path),
        },
        "validation": {
            "case_count": validation_plan.case_count,
            "dataset_manifest_sha256": validation_plan.dataset_manifest_sha256,
            "hard_budget_limit_usd": float(validation_budget_limit_usd),
            "model_inputs_sha256": validation_plan.input_sha256,
            "prompt_changes_after_run": False,
            "run_count_limit": 1,
            "split": validation_plan.split,
        },
        "locked_holdout_authorized": False,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(freeze, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_luna_v4_freeze(plan: RunPlan) -> None:
    try:
        freeze = json.loads(LUNA_V4_FREEZE_PATH.read_text(encoding="utf-8"))
        frozen_config = freeze["configuration"]
        frozen_validation = freeze["validation"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise OfflineRunnerError("Luna-v4 configuration freeze is invalid") from exc
    if frozen_config != _luna_v4_frozen_configuration(plan):
        raise OfflineRunnerError("Luna-v4 runner configuration differs from freeze")
    if frozen_validation != {
        "case_count": plan.case_count,
        "dataset_manifest_sha256": plan.dataset_manifest_sha256,
        "hard_budget_limit_usd": frozen_validation.get("hard_budget_limit_usd"),
        "model_inputs_sha256": plan.input_sha256,
        "prompt_changes_after_run": False,
        "run_count_limit": 1,
        "split": plan.split,
    }:
        raise OfflineRunnerError("Luna-v4 validation input differs from freeze")


def _validate_luna_v5_freeze(plan: RunPlan) -> None:
    """Keep validation closed until a passing calibration is frozen."""

    try:
        freeze = json.loads(LUNA_V5_FREEZE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OfflineRunnerError(
            "Luna-v5 validation is disabled until passing calibration freeze"
        ) from exc
    if freeze.get("status") != "validation_authorized_once":
        raise OfflineRunnerError("Luna-v5 validation freeze is not authorized")
    raise OfflineRunnerError(
        "Luna-v5 validation freeze enforcement is not activated in this step"
    )


def _validate_luna_effort_screen_plan(plan: RunPlan) -> None:
    expected = RunnerConfig(
        model="gpt-5.6-luna",
        reasoning_effort=plan.config.reasoning_effort,
        max_output_tokens=256,
        retries=0,
        timeout_seconds=plan.config.timeout_seconds,
        prompt_version="luna-v5",
    )
    if plan.config.reasoning_effort not in {"none", "low"}:
        raise OfflineRunnerError("effort screen supports only none and low")
    if plan.config != expected:
        raise OfflineRunnerError("effort-screen configuration differs from contract")
    if plan.case_count != 24:
        raise OfflineRunnerError("effort screen must use all 24 cases")


def _validate_luna_low_plan(plan: RunPlan) -> None:
    expected = RunnerConfig(
        model="gpt-5.6-luna",
        reasoning_effort="low",
        max_output_tokens=256,
        retries=0,
        timeout_seconds=plan.config.timeout_seconds,
        prompt_version="luna-v5",
    )
    if plan.config != expected:
        raise OfflineRunnerError("Luna-low configuration differs from contract")
    if plan.case_count != 280:
        raise OfflineRunnerError("Luna-low runs must use all 280 cases")


def _validate_luna_low_validation_freeze(plan: RunPlan) -> None:
    try:
        freeze = json.loads(LUNA_LOW_FREEZE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OfflineRunnerError(
            "Luna-low validation is disabled until passing calibration freeze"
        ) from exc
    if freeze.get("status") != "validation_authorized_once":
        raise OfflineRunnerError("Luna-low validation freeze is not authorized")
    raise OfflineRunnerError(
        "Luna-low validation freeze enforcement is not activated in this step"
    )


def _validate_terra_effort_screen_plan(plan: RunPlan) -> None:
    expected = RunnerConfig(
        model="gpt-5.6-terra",
        reasoning_effort=plan.config.reasoning_effort,
        max_output_tokens=256,
        retries=0,
        timeout_seconds=plan.config.timeout_seconds,
        prompt_version="luna-v5",
    )
    if plan.config.reasoning_effort not in {"none", "low"}:
        raise OfflineRunnerError("Terra screen supports only none and low")
    if plan.config != expected:
        raise OfflineRunnerError("Terra-screen configuration differs from contract")
    if plan.case_count != 48:
        raise OfflineRunnerError("Terra screen must use all 48 cases")


def _validate_terra_prompt_reasoning_screen_plan(plan: RunPlan) -> None:
    expected = RunnerConfig(
        model="gpt-5.6-terra",
        reasoning_effort=plan.config.reasoning_effort,
        max_output_tokens=256,
        retries=0,
        timeout_seconds=plan.config.timeout_seconds,
        prompt_version=plan.config.prompt_version,
    )
    if plan.config.reasoning_effort not in {"low", "medium"}:
        raise OfflineRunnerError("Terra 2x2 screen supports only low and medium")
    if plan.config.prompt_version not in {"luna-v5", "terra-v1"}:
        raise OfflineRunnerError("Terra 2x2 screen supports only frozen prompts")
    if plan.config != expected:
        raise OfflineRunnerError("Terra 2x2 configuration differs from contract")
    if plan.case_count != 48:
        raise OfflineRunnerError("Terra 2x2 screen must use all 48 cases")


def _validate_terra_v2_prompt_screen_plan(plan: RunPlan) -> None:
    expected = RunnerConfig(
        model="gpt-5.6-terra",
        reasoning_effort="medium",
        max_output_tokens=256,
        retries=0,
        timeout_seconds=plan.config.timeout_seconds,
        prompt_version=plan.config.prompt_version,
    )
    if plan.config.reasoning_effort != "medium":
        raise OfflineRunnerError("Terra-v2 screen supports only medium reasoning")
    if plan.config.prompt_version not in {"terra-v1", "terra-v2"}:
        raise OfflineRunnerError("Terra-v2 screen supports only frozen prompts")
    if plan.config != expected:
        raise OfflineRunnerError("Terra-v2 screen configuration differs from contract")
    if plan.case_count != 64:
        raise OfflineRunnerError("Terra-v2 screen must use all 64 cases")


def _validate_terra_high_reasoning_screen_plan(plan: RunPlan) -> None:
    expected = RunnerConfig(
        model="gpt-5.6-terra",
        reasoning_effort=plan.config.reasoning_effort,
        max_output_tokens=256,
        retries=0,
        timeout_seconds=plan.config.timeout_seconds,
        prompt_version="terra-v1",
    )
    if plan.config.reasoning_effort not in {"medium", "high"}:
        raise OfflineRunnerError(
            "Terra high screen supports only medium and high reasoning"
        )
    if plan.config != expected:
        raise OfflineRunnerError(
            "Terra high screen configuration differs from contract"
        )
    if plan.case_count != 48:
        raise OfflineRunnerError("Terra high screen must use all 48 cases")


def _validate_terra_high_cycle_plan(plan: RunPlan) -> None:
    expected = RunnerConfig(
        model="gpt-5.6-terra",
        reasoning_effort="high",
        max_output_tokens=256,
        retries=0,
        timeout_seconds=plan.config.timeout_seconds,
        prompt_version="terra-v1",
    )
    if plan.config != expected:
        raise OfflineRunnerError(
            "Terra-high cycle configuration differs from contract"
        )
    if plan.case_count != 280:
        raise OfflineRunnerError("Terra-high cycle must use all 280 cases")


def _validate_terra_high_validation_freeze(plan: RunPlan) -> None:
    try:
        freeze = json.loads(TERRA_HIGH_FREEZE_PATH.read_text(encoding="utf-8"))
        frozen_config = freeze["configuration"]
        frozen_validation = freeze["validation"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise OfflineRunnerError(
            "Terra-high validation is disabled until passing calibration freeze"
        ) from exc
    if freeze.get("status") != "validation_authorized_once":
        raise OfflineRunnerError(
            "Terra-high validation freeze is not authorized"
        )
    if frozen_config != _terra_high_frozen_configuration(plan):
        raise OfflineRunnerError(
            "Terra-high validation configuration differs from freeze"
        )
    expected_validation = {
        "split": "terra_high_validation",
        "case_count": 280,
        "model_inputs_sha256": plan.input_sha256,
        "dataset_manifest_sha256": plan.dataset_manifest_sha256,
        "hard_budget_limit_usd": 5.0,
        "preflight_worst_case_usd": float(plan.worst_case_cost_usd),
        "prompt_changes_after_run": False,
        "run_count_limit": 1,
    }
    if frozen_validation != expected_validation:
        raise OfflineRunnerError(
            "Terra-high validation input differs from freeze"
        )


def _terra_high_frozen_configuration(plan: RunPlan) -> dict[str, object]:
    return {
        "model": plan.config.model,
        "reasoning_effort": plan.config.reasoning_effort,
        "prompt_version": plan.config.prompt_version,
        "max_output_tokens": plan.config.max_output_tokens,
        "retries": plan.config.retries,
        "runner_version": RUNNER_VERSION,
        "strict_structured_outputs": True,
        "prompt_sha256": _sha256_bytes(
            get_system_instructions(plan.config.prompt_version).encode("utf-8")
        ),
        "output_schema_sha256": _sha256_bytes(
            _canonical_json(MODEL_OUTPUT_JSON_SCHEMA).encode("utf-8")
        ),
    }


def _require_terra_high_calibration_gates(
    report: Mapping[str, object],
) -> None:
    if report.get("acceptance_gates", {}).get("overall_status") != "pass":
        raise OfflineRunnerError(
            "Terra-high calibration did not pass every engineering gate"
        )
    counts = report.get("counts", {})
    fields = report.get("field_breakdown", {})
    product_checks = {
        "parser_error_detection": (
            int(counts.get("alerted_corrupted_cases", -1)) >= 133
        ),
        "false_alerts": int(counts.get("false_positives", 999)) <= 4,
        "correct_field_detection": (
            int(counts.get("correctly_localized_alerts", -1)) >= 126
        ),
        "successful_checks": (
            int(counts.get("valid_structured_outputs", -1)) >= 279
        ),
        "wbs": int(fields.get("wbs", {}).get("correctly_localized", -1)) >= 51,
        "district": (
            int(fields.get("district", {}).get("correctly_localized", -1)) >= 9
        ),
        "rent_kalt": (
            int(fields.get("rent_kalt", {}).get("correctly_localized", -1))
            >= 19
        ),
        "rooms": (
            int(fields.get("rooms", {}).get("correctly_localized", -1)) >= 19
        ),
    }
    if not all(product_checks.values()):
        failed = sorted(
            name for name, passed in product_checks.items() if not passed
        )
        raise OfflineRunnerError(
            "Terra-high calibration failed Product Scorecard gates: "
            + ", ".join(failed)
        )


def write_terra_high_calibration_freeze(
    *,
    report_path: Path = (
        TERRA_HIGH_CALIBRATION_RUN_DIR / "reports" / "report.json"
    ),
    run_manifest_path: Path = (
        TERRA_HIGH_CALIBRATION_RUN_DIR / RUN_MANIFEST_FILENAME
    ),
    output_path: Path = TERRA_HIGH_FREEZE_PATH,
) -> Path:
    output_path = _ensure_inside_eval(output_path)
    if output_path.exists():
        raise FileExistsError("Terra-high calibration freeze already exists")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    run_manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))
    _require_terra_high_calibration_gates(report)
    if (
        run_manifest.get("status") != "completed"
        or run_manifest.get("case_count") != 280
    ):
        raise OfflineRunnerError(
            "Terra-high calibration run evidence is incomplete"
        )
    run_config = run_manifest.get("configuration", {})
    expected_run_config = {
        "model": "gpt-5.6-terra",
        "reasoning_effort": "high",
        "prompt_version": "terra-v1",
        "max_output_tokens": 256,
        "retries": 0,
        "strict_structured_outputs": True,
        "responses_api": True,
        "store": False,
        "service_tier": DEFAULT_SERVICE_TIER,
        "prompt_sha256": _sha256_bytes(
            get_system_instructions("terra-v1").encode("utf-8")
        ),
        "output_schema_sha256": _sha256_bytes(
            _canonical_json(MODEL_OUTPUT_JSON_SCHEMA).encode("utf-8")
        ),
    }
    if any(
        run_config.get(key) != value
        for key, value in expected_run_config.items()
    ):
        raise OfflineRunnerError(
            "Terra-high calibration configuration differs from contract"
        )
    if (
        run_manifest.get("split") != "terra_high_calibration"
        or run_manifest.get("input", {}).get("sha256")
        != "5e0906d7fd4158724b23ac9670cc01f575e1d11d6c1aef4999f90d34676a3199"
    ):
        raise OfflineRunnerError(
            "Terra-high calibration input differs from contract"
        )
    config = RunnerConfig(
        model="gpt-5.6-terra",
        reasoning_effort="high",
        max_output_tokens=256,
        retries=0,
        timeout_seconds=float(run_config["timeout_seconds"]),
        prompt_version="terra-v1",
    )
    input_path, input_sha, manifest_sha = _split_input_contract(
        "terra_high_validation"
    )
    rows = load_jsonl(input_path)
    plan = RunPlan(
        split="terra_high_validation",
        input_path=input_path,
        input_sha256=input_sha,
        dataset_manifest_sha256=manifest_sha,
        cases=tuple(rows),
        config=config,
        worst_case_cost_usd=sum(
            (
                _request_worst_case_cost(
                    case,
                    model=config.model,
                    max_output_tokens=256,
                    prompt_version="terra-v1",
                )
                for case in rows
            ),
            Decimal("0"),
        ),
    )
    validation_budget = Decimal("5.00")
    if plan.worst_case_cost_usd > validation_budget:
        raise OfflineRunnerError(
            "Terra-high validation budget is below preflight bound"
        )
    freeze = {
        "schema_version": "1.0",
        "status": "validation_authorized_once",
        "configuration": _terra_high_frozen_configuration(plan),
        "calibration_evidence": {
            "report_sha256": _sha256_file(report_path),
            "run_manifest_sha256": _sha256_file(run_manifest_path),
        },
        "validation": {
            "split": "terra_high_validation",
            "case_count": 280,
            "model_inputs_sha256": input_sha,
            "dataset_manifest_sha256": manifest_sha,
            "hard_budget_limit_usd": float(validation_budget),
            "preflight_worst_case_usd": float(plan.worst_case_cost_usd),
            "prompt_changes_after_run": False,
            "run_count_limit": 1,
        },
        "boundaries": {
            "calibration_passed_engineering_gates": True,
            "calibration_passed_product_gates": True,
            "validation_authorized_once": True,
            "locked_holdout_authorized": False,
            "product_runtime_modified": False,
            "landing_claim_authorized": False,
        },
    }
    output_path.write_text(
        json.dumps(freeze, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _locked_holdout_frozen_configuration(
    plan: RunPlan,
) -> dict[str, object]:
    return {
        "model": plan.config.model,
        "reasoning_effort": plan.config.reasoning_effort,
        "prompt_version": plan.config.prompt_version,
        "max_output_tokens": plan.config.max_output_tokens,
        "retries": plan.config.retries,
        "runner_version": RUNNER_VERSION,
        "strict_structured_outputs": True,
        "prompt_sha256": _sha256_bytes(
            get_system_instructions(plan.config.prompt_version).encode("utf-8")
        ),
        "output_schema_sha256": _sha256_bytes(
            _canonical_json(MODEL_OUTPUT_JSON_SCHEMA).encode("utf-8")
        ),
    }


def _validate_locked_holdout_plan(plan: RunPlan) -> None:
    expected = RunnerConfig(
        model="gpt-5.6-terra",
        reasoning_effort="high",
        max_output_tokens=256,
        retries=0,
        timeout_seconds=plan.config.timeout_seconds,
        prompt_version="terra-v1",
    )
    if plan.config != expected:
        raise OfflineRunnerError(
            "locked holdout configuration differs from contract"
        )
    if plan.case_count != 600:
        raise OfflineRunnerError("locked holdout must use all 600 cases")
    try:
        freeze = json.loads(
            LOCKED_HOLDOUT_FREEZE_PATH.read_text(encoding="utf-8")
        )
        frozen_holdout = freeze["holdout"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise OfflineRunnerError(
            "locked holdout is disabled until its one-run freeze exists"
        ) from exc
    if freeze.get("status") != "holdout_authorized_once":
        raise OfflineRunnerError("locked holdout freeze is not authorized")
    if freeze.get("configuration") != _locked_holdout_frozen_configuration(
        plan
    ):
        raise OfflineRunnerError(
            "locked holdout configuration differs from freeze"
        )
    expected_holdout = {
        "split": "locked_holdout",
        "case_count": 600,
        "model_inputs_sha256": plan.input_sha256,
        "dataset_manifest_sha256": plan.dataset_manifest_sha256,
        "hard_budget_limit_usd": float(LOCKED_HOLDOUT_HARD_BUDGET_USD),
        "preflight_worst_case_usd": float(plan.worst_case_cost_usd),
        "run_count_limit": 1,
        "partial_execution_allowed": False,
        "prompt_changes_after_run": False,
    }
    if frozen_holdout != expected_holdout:
        raise OfflineRunnerError("locked holdout input differs from freeze")


def write_locked_holdout_configuration_freeze(
    *,
    output_path: Path = LOCKED_HOLDOUT_FREEZE_PATH,
    validation_scorecard_path: Path = TERRA_HIGH_VALIDATION_SCORECARD_PATH,
    validation_run_manifest_path: Path = (
        TERRA_HIGH_VALIDATION_RUN_DIR / RUN_MANIFEST_FILENAME
    ),
    validation_freeze_path: Path = TERRA_HIGH_FREEZE_PATH,
) -> Path:
    """Authorize one exact 600-case holdout run after all prior gates pass."""

    output_path = _ensure_inside_eval(output_path)
    if output_path.exists():
        raise FileExistsError("locked holdout configuration freeze already exists")
    if (
        (LOCKED_HOLDOUT_RUN_DIR / PREDICTIONS_FILENAME).exists()
        or (LOCKED_HOLDOUT_RUN_DIR / RUN_MANIFEST_FILENAME).exists()
    ):
        raise FileExistsError(
            "locked holdout run artifacts already exist; refusing release"
        )

    readiness = audit_locked_holdout_readiness()
    if readiness.get("status") != "ready_with_declared_limitations":
        raise OfflineRunnerError("locked holdout readiness audit did not pass")

    scorecard = json.loads(
        validation_scorecard_path.read_text(encoding="utf-8")
    )
    validation_manifest = json.loads(
        validation_run_manifest_path.read_text(encoding="utf-8")
    )
    validation_freeze = json.loads(
        validation_freeze_path.read_text(encoding="utf-8")
    )
    if scorecard.get("decision", {}).get("overall_status") != "pass":
        raise OfflineRunnerError(
            "Terra-high frozen validation did not pass every gate"
        )
    if (
        validation_manifest.get("status") != "completed"
        or validation_manifest.get("split") != "terra_high_validation"
        or validation_manifest.get("case_count") != 280
        or validation_manifest.get("result", {}).get("technical_failures") != 0
    ):
        raise OfflineRunnerError(
            "Terra-high frozen validation evidence is incomplete"
        )
    if validation_freeze.get("status") != "validation_authorized_once":
        raise OfflineRunnerError("Terra-high validation freeze is invalid")

    config = RunnerConfig(
        model="gpt-5.6-terra",
        reasoning_effort="high",
        max_output_tokens=256,
        retries=0,
        prompt_version="terra-v1",
    )
    input_path, input_sha, manifest_sha = _split_input_contract(
        "locked_holdout"
    )
    rows = load_jsonl(input_path)
    _validate_model_input_rows(rows)
    plan = RunPlan(
        split="locked_holdout",
        input_path=input_path,
        input_sha256=input_sha,
        dataset_manifest_sha256=manifest_sha,
        cases=tuple(rows),
        config=config,
        worst_case_cost_usd=sum(
            (
                _request_worst_case_cost(
                    case,
                    model=config.model,
                    max_output_tokens=config.max_output_tokens,
                    prompt_version=config.prompt_version,
                )
                for case in rows
            ),
            Decimal("0"),
        ),
    )
    if plan.case_count != 600:
        raise OfflineRunnerError("locked holdout must contain exactly 600 cases")
    if plan.worst_case_cost_usd > LOCKED_HOLDOUT_HARD_BUDGET_USD:
        raise OfflineRunnerError(
            "locked holdout budget is below the preflight bound"
        )

    freeze = {
        "schema_version": "1.0",
        "status": "holdout_authorized_once",
        "configuration": _locked_holdout_frozen_configuration(plan),
        "prior_evidence": {
            "terra_high_validation_scorecard_sha256": _sha256_file(
                validation_scorecard_path
            ),
            "terra_high_validation_run_manifest_sha256": _sha256_file(
                validation_run_manifest_path
            ),
            "terra_high_configuration_freeze_sha256": _sha256_file(
                validation_freeze_path
            ),
        },
        "readiness": {
            "status": readiness["status"],
            "dataset_manifest_sha256": readiness["source"][
                "dataset_manifest_sha256"
            ],
            "truth_sha256": readiness["source"]["truth_sha256"],
            "comparison_artifact_count": readiness["isolation"][
                "comparison_artifact_count"
            ],
            "all_checks_passed": all(readiness["checks"].values()),
        },
        "holdout": {
            "split": "locked_holdout",
            "case_count": 600,
            "model_inputs_sha256": input_sha,
            "dataset_manifest_sha256": manifest_sha,
            "hard_budget_limit_usd": float(
                LOCKED_HOLDOUT_HARD_BUDGET_USD
            ),
            "preflight_worst_case_usd": float(plan.worst_case_cost_usd),
            "run_count_limit": 1,
            "partial_execution_allowed": False,
            "prompt_changes_after_run": False,
        },
        "source_hashes": {
            "runner_sha256": _sha256_file(Path(__file__)),
            "prompt_module_sha256": _sha256_file(
                EVAL_ROOT / "ai_qa_prompt.py"
            ),
            "scorer_sha256": _sha256_file(EVAL_ROOT / "ai_qa_scorer.py"),
            "scorecard_sha256": _sha256_file(
                EVAL_ROOT / "ai_qa_product_scorecard.py"
            ),
            "readiness_sha256": _sha256_file(
                EVAL_ROOT / "ai_qa_holdout_readiness.py"
            ),
        },
        "boundaries": {
            "validation_passed_all_gates": True,
            "holdout_authorized_once": True,
            "locked_holdout_authorized": True,
            "product_runtime_modified": False,
            "landing_claim_authorized": False,
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(freeze, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_terra_calibration_plan(plan: RunPlan) -> None:
    expected = RunnerConfig(
        model="gpt-5.6-terra",
        reasoning_effort="medium",
        max_output_tokens=256,
        retries=0,
        timeout_seconds=plan.config.timeout_seconds,
        prompt_version="terra-v1",
    )
    if plan.config != expected:
        raise OfflineRunnerError("Terra calibration configuration differs from contract")
    if plan.case_count != 280:
        raise OfflineRunnerError("Terra calibration must use all 280 cases")


def _terra_frozen_configuration(plan: RunPlan) -> dict[str, object]:
    return {
        "model": plan.config.model,
        "reasoning_effort": plan.config.reasoning_effort,
        "prompt_version": plan.config.prompt_version,
        "max_output_tokens": plan.config.max_output_tokens,
        "retries": plan.config.retries,
        "runner_version": RUNNER_VERSION,
        "strict_structured_outputs": True,
        "prompt_sha256": _sha256_bytes(
            get_system_instructions(plan.config.prompt_version).encode("utf-8")
        ),
        "output_schema_sha256": _sha256_bytes(
            _canonical_json(MODEL_OUTPUT_JSON_SCHEMA).encode("utf-8")
        ),
    }


def write_terra_calibration_freeze(
    *,
    report_path: Path = TERRA_CALIBRATION_RUN_DIR / "reports" / "report.json",
    run_manifest_path: Path = TERRA_CALIBRATION_RUN_DIR / RUN_MANIFEST_FILENAME,
    output_path: Path = TERRA_CALIBRATION_FREEZE_PATH,
) -> Path:
    output_path = _ensure_inside_eval(output_path)
    if output_path.exists():
        raise FileExistsError("Terra calibration freeze already exists")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    run_manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))
    if report.get("acceptance_gates", {}).get("overall_status") != "pass":
        raise OfflineRunnerError("Terra calibration did not pass every gate")
    if run_manifest.get("status") != "completed" or run_manifest.get("case_count") != 280:
        raise OfflineRunnerError("Terra calibration run evidence is incomplete")
    run_config = run_manifest.get("configuration", {})
    expected_run_config = {
        "model": "gpt-5.6-terra",
        "reasoning_effort": "medium",
        "prompt_version": "terra-v1",
        "max_output_tokens": 256,
        "retries": 0,
        "strict_structured_outputs": True,
        "responses_api": True,
        "store": False,
        "service_tier": DEFAULT_SERVICE_TIER,
        "prompt_sha256": _sha256_bytes(get_system_instructions("terra-v1").encode("utf-8")),
        "output_schema_sha256": _sha256_bytes(_canonical_json(MODEL_OUTPUT_JSON_SCHEMA).encode("utf-8")),
    }
    if any(run_config.get(key) != value for key, value in expected_run_config.items()):
        raise OfflineRunnerError("Terra calibration configuration differs from contract")
    if run_manifest.get("split") != "terra_calibration" or run_manifest.get("input", {}).get("sha256") != "83474873c20f7d5231ec3523492bdbfc03a9e99364c1933775918a187c0fd335":
        raise OfflineRunnerError("Terra calibration input differs from contract")
    config = RunnerConfig(
        model="gpt-5.6-terra",
        reasoning_effort="medium",
        max_output_tokens=256,
        retries=0,
        timeout_seconds=float(run_config["timeout_seconds"]),
        prompt_version="terra-v1",
    )
    input_path, input_sha, manifest_sha = _split_input_contract("terra_validation")
    rows = load_jsonl(input_path)
    plan = RunPlan(
        split="terra_validation",
        input_path=input_path,
        input_sha256=input_sha,
        dataset_manifest_sha256=manifest_sha,
        cases=tuple(rows),
        config=config,
        worst_case_cost_usd=sum(
            (_request_worst_case_cost(case, model=config.model, max_output_tokens=256, prompt_version="terra-v1") for case in rows),
            Decimal("0"),
        ),
    )
    if plan.worst_case_cost_usd > TERRA_VALIDATION_HARD_BUDGET_USD:
        raise OfflineRunnerError("Terra validation budget is below preflight bound")
    freeze = {
        "schema_version": "1.0",
        "status": "validation_authorized_once",
        "configuration": _terra_frozen_configuration(plan),
        "calibration_evidence": {
            "report_sha256": _sha256_file(report_path),
            "run_manifest_sha256": _sha256_file(run_manifest_path),
        },
        "validation": {
            "split": "terra_validation",
            "case_count": 280,
            "model_inputs_sha256": input_sha,
            "dataset_manifest_sha256": manifest_sha,
            "hard_budget_limit_usd": float(TERRA_VALIDATION_HARD_BUDGET_USD),
            "preflight_worst_case_usd": float(plan.worst_case_cost_usd),
            "run_count_limit": 1,
            "prompt_changes_after_run": False,
        },
        "locked_holdout_authorized": False,
    }
    output_path.write_text(json.dumps(freeze, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_terra_validation_freeze(plan: RunPlan) -> None:
    try:
        freeze = json.loads(TERRA_CALIBRATION_FREEZE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OfflineRunnerError("Terra validation is disabled until passing calibration freeze") from exc
    if freeze.get("status") != "validation_authorized_once":
        raise OfflineRunnerError("Terra validation freeze is not authorized")
    if freeze.get("configuration") != _terra_frozen_configuration(plan):
        raise OfflineRunnerError("Terra validation configuration differs from freeze")
    expected = freeze.get("validation")
    if expected != {
        "split": "terra_validation",
        "case_count": plan.case_count,
        "model_inputs_sha256": plan.input_sha256,
        "dataset_manifest_sha256": plan.dataset_manifest_sha256,
        "hard_budget_limit_usd": float(TERRA_VALIDATION_HARD_BUDGET_USD),
        "preflight_worst_case_usd": float(plan.worst_case_cost_usd),
        "run_count_limit": 1,
        "prompt_changes_after_run": False,
    }:
        raise OfflineRunnerError("Terra validation input differs from freeze")


def load_eval_api_key() -> str:
    """Load the credential only from the repo-local eval environment file."""

    values = dotenv_values(EVAL_ENV_PATH)
    api_key = values.get("OPENAI_API_KEY")
    if not isinstance(api_key, str) or not api_key.strip():
        raise OfflineRunnerError(
            "OPENAI_API_KEY is missing from .env.eval.local"
        )
    return api_key.strip()


def _new_openai_client(api_key: str) -> ResponsesClient:
    return OpenAI(
        api_key=api_key,
        base_url="https://api.openai.com/v1",
    )


def verify_model_availability(
    client: ResponsesClient,
    model: str,
) -> None:
    """Verify the exact snapshot; never route to or choose another model."""

    try:
        model_record = client.models.retrieve(model)
    except Exception as exc:
        category, _retryable = _classify_api_exception(exc)
        raise OfflineRunnerError(
            f"model availability check failed: {category}"
        ) from None
    returned_id = getattr(model_record, "id", None)
    if returned_id != model:
        raise OfflineRunnerError(
            "model availability check returned a different model ID"
        )


def _classify_api_exception(exc: Exception) -> tuple[str, bool]:
    if isinstance(exc, openai.APITimeoutError):
        return "api_timeout", True
    if isinstance(exc, openai.APIConnectionError):
        return "api_connection", True
    if isinstance(exc, openai.RateLimitError):
        return "api_rate_limit", True
    if isinstance(exc, openai.InternalServerError):
        return "api_server", True
    if isinstance(exc, openai.AuthenticationError):
        return "api_authentication", False
    if isinstance(exc, openai.NotFoundError):
        return "model_unavailable", False
    if isinstance(exc, openai.BadRequestError):
        return "api_bad_request", False
    if isinstance(exc, openai.APIStatusError):
        return "api_status", False
    return "unknown_api_error", False


def _response_has_refusal(response: object) -> bool:
    for output_item in getattr(response, "output", []) or []:
        for content_item in getattr(output_item, "content", []) or []:
            if getattr(content_item, "type", None) == "refusal":
                return True
    return False


def _usage_from_response(response: object) -> dict[str, int] | None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    input_tokens = int(getattr(usage, "input_tokens", 0))
    output_tokens = int(getattr(usage, "output_tokens", 0))
    input_details = getattr(usage, "input_tokens_details", None)
    output_details = getattr(usage, "output_tokens_details", None)
    cached_tokens = int(getattr(input_details, "cached_tokens", 0) or 0)
    reasoning_tokens = int(
        getattr(output_details, "reasoning_tokens", 0) or 0
    )
    values = {
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_tokens,
        "output_tokens": output_tokens,
        "reasoning_tokens": reasoning_tokens,
    }
    if any(value < 0 for value in values.values()):
        raise ValueError("response usage contains negative token counts")
    if cached_tokens > input_tokens or reasoning_tokens > output_tokens:
        raise ValueError("response usage detail exceeds its token total")
    return values


def calculate_cost_usd(
    usage: Mapping[str, int],
    *,
    model: str = DEFAULT_MODEL,
) -> Decimal:
    input_price, cached_input_price, output_price = _pricing_for_model(model)
    uncached_input = (
        Decimal(usage["input_tokens"])
        - Decimal(usage["cached_input_tokens"])
    )
    cached_input = Decimal(usage["cached_input_tokens"])
    output = Decimal(usage["output_tokens"])
    return (
        uncached_input * input_price
        + cached_input * cached_input_price
        + output * output_price
    ) / _MILLION


def _completed_prediction(
    *,
    case_id: str,
    response: object,
    retry_count: int,
    latency_ms: float,
    requested_model: str,
) -> dict[str, object]:
    if getattr(response, "status", None) != "completed":
        raise OfflineRunnerError("response_incomplete")
    if getattr(response, "model", None) != requested_model:
        raise OfflineRunnerError("response_model_mismatch")
    if _response_has_refusal(response):
        raise OfflineRunnerError("response_refusal")
    raw_output = getattr(response, "output_text", None)
    if not isinstance(raw_output, str) or not raw_output:
        raise OfflineRunnerError("response_missing_output")

    row: dict[str, object] = {
        "case_id": case_id,
        "status": "completed",
        "raw_output": raw_output,
        "latency_ms": latency_ms,
        "latency_mode": "synchronous_case",
        "retry_count": retry_count,
    }
    try:
        usage = _usage_from_response(response)
    except (TypeError, ValueError, OverflowError):
        raise OfflineRunnerError("response_usage_invalid") from None
    if usage is not None:
        row["usage"] = usage
        row["cost_usd"] = float(
            calculate_cost_usd(usage, model=requested_model)
        )
    return row


def _technical_failure_prediction(
    *,
    case_id: str,
    failure_type: str,
    retry_count: int,
    latency_ms: float,
) -> dict[str, object]:
    return {
        "case_id": case_id,
        "status": "technical_failure",
        "failure": {"type": failure_type},
        "latency_ms": latency_ms,
        "latency_mode": "synchronous_case",
        "retry_count": retry_count,
    }


def _request_case(
    *,
    client: ResponsesClient,
    case: Mapping[str, object],
    config: RunnerConfig,
    sleep_fn: Callable[[float], None],
    monotonic_fn: Callable[[], float],
) -> dict[str, object]:
    case_id = str(case["case_id"])
    started = monotonic_fn()
    retry_count = 0
    for attempt in range(config.retries + 1):
        try:
            response = client.responses.create(
                model=config.model,
                reasoning={"effort": config.reasoning_effort},
                instructions=get_system_instructions(config.prompt_version),
                input=render_case_input(case),
                text={"format": RESPONSES_TEXT_FORMAT},
                max_output_tokens=config.max_output_tokens,
                service_tier=DEFAULT_SERVICE_TIER,
                store=False,
                timeout=config.timeout_seconds,
            )
            latency_ms = (monotonic_fn() - started) * 1000
            try:
                return _completed_prediction(
                    case_id=case_id,
                    response=response,
                    retry_count=retry_count,
                    latency_ms=latency_ms,
                    requested_model=config.model,
                )
            except OfflineRunnerError as exc:
                return _technical_failure_prediction(
                    case_id=case_id,
                    failure_type=str(exc),
                    retry_count=retry_count,
                    latency_ms=latency_ms,
                )
        except Exception as exc:
            failure_type, retryable = _classify_api_exception(exc)
            if retryable and attempt < config.retries:
                retry_count += 1
                sleep_fn(float(2**attempt))
                continue
            latency_ms = (monotonic_fn() - started) * 1000
            return _technical_failure_prediction(
                case_id=case_id,
                failure_type=failure_type,
                retry_count=retry_count,
                latency_ms=latency_ms,
            )
    raise AssertionError("request loop exhausted unexpectedly")


def _write_jsonl_row(path: Path, row: Mapping[str, object]) -> None:
    with path.open("a", encoding="utf-8") as artifact:
        artifact.write(_canonical_json(row) + "\n")
        artifact.flush()


def _base_manifest(
    plan: RunPlan,
    *,
    budget_limit_usd: Decimal,
    status: str,
) -> dict[str, object]:
    input_price, cached_input_price, output_price = _pricing_for_model(
        plan.config.model
    )
    system_instructions = get_system_instructions(plan.config.prompt_version)
    prompt_hash = _sha256_bytes(system_instructions.encode("utf-8"))
    schema_hash = _sha256_bytes(
        _canonical_json(MODEL_OUTPUT_JSON_SCHEMA).encode("utf-8")
    )
    return {
        "schema_version": RUN_MANIFEST_SCHEMA_VERSION,
        "runner_version": RUNNER_VERSION,
        "experiment": EXPERIMENT_LABEL,
        "status": status,
        "split": plan.split,
        "case_count": plan.case_count,
        "case_ids_sha256": _sha256_bytes(
            _canonical_json(
                [str(case["case_id"]) for case in plan.cases]
            ).encode("utf-8")
        ),
        "input": {
            "file": plan.input_path.name,
            "sha256": plan.input_sha256,
            "dataset_manifest_sha256": plan.dataset_manifest_sha256,
        },
        "configuration": {
            "model": plan.config.model,
            "reasoning_effort": plan.config.reasoning_effort,
            "prompt_version": plan.config.prompt_version,
            "prompt_sha256": prompt_hash,
            "output_schema_sha256": schema_hash,
            "strict_structured_outputs": True,
            "responses_api": True,
            "max_output_tokens": plan.config.max_output_tokens,
            "retries": plan.config.retries,
            "timeout_seconds": plan.config.timeout_seconds,
            "service_tier": DEFAULT_SERVICE_TIER,
            "store": False,
        },
        "budget": {
            "hard_limit_usd": float(budget_limit_usd),
            "preflight_worst_case_usd": float(plan.worst_case_cost_usd),
            "input_price_per_1m": float(input_price),
            "cached_input_price_per_1m": float(cached_input_price),
            "output_price_per_1m": float(output_price),
            "pricing_source": PRICING_SOURCE,
            "pricing_observed_date": PRICING_OBSERVED_DATE,
            "estimate_method": (
                "UTF-8 bytes as a conservative input-token upper bound; "
                "max output tokens; all retry attempts reserved"
            ),
        },
        "credential": {
            "source": ".env.eval.local",
            "variable": "OPENAI_API_KEY",
            "value_persisted": False,
        },
        "product_boundary": (
            "Offline eval only; no Telegram bot or product-runtime integration."
        ),
    }


def execute_run_plan(
    plan: RunPlan,
    *,
    output_dir: Path,
    budget_limit_usd: Decimal,
    api_key_loader: Callable[[], str] = load_eval_api_key,
    client_factory: Callable[[str], ResponsesClient] = _new_openai_client,
    sleep_fn: Callable[[float], None] = time.sleep,
    monotonic_fn: Callable[[], float] = time.monotonic,
) -> dict[str, Path]:
    if budget_limit_usd <= 0:
        raise ValueError("budget_limit_usd must be positive")
    if plan.worst_case_cost_usd > budget_limit_usd:
        raise OfflineRunnerError(
            "hard budget is below the preflight worst-case bound"
        )
    output_dir = _ensure_inside_eval(output_dir)
    if plan.split == "luna_effort_screen":
        expected_dir = LUNA_EFFORT_SCREEN_RUN_DIRS[
            plan.config.reasoning_effort
        ].resolve()
        if output_dir != expected_dir:
            raise OfflineRunnerError(
                "effort screen must use its canonical reasoning run directory"
            )
    if plan.split == "luna_low_calibration":
        if output_dir != LUNA_LOW_CALIBRATION_RUN_DIR.resolve():
            raise OfflineRunnerError(
                "Luna-low calibration must use its canonical run directory"
            )
        if budget_limit_usd != LUNA_LOW_CALIBRATION_HARD_BUDGET_USD:
            raise OfflineRunnerError(
                "Luna-low calibration budget differs from contract"
            )
    if plan.split == "terra_effort_screen":
        expected_dir = TERRA_EFFORT_SCREEN_RUN_DIRS[
            plan.config.reasoning_effort
        ].resolve()
        if output_dir != expected_dir:
            raise OfflineRunnerError(
                "Terra screen must use its canonical reasoning run directory"
            )
        if budget_limit_usd != TERRA_EFFORT_SCREEN_HARD_BUDGET_USD:
            raise OfflineRunnerError("Terra screen budget differs from contract")
    if plan.split == "terra_prompt_reasoning_screen":
        expected_dir = TERRA_PROMPT_REASONING_SCREEN_RUN_DIRS[
            (plan.config.prompt_version, plan.config.reasoning_effort)
        ].resolve()
        if output_dir != expected_dir:
            raise OfflineRunnerError(
                "Terra 2x2 screen must use its canonical profile run directory"
            )
        if budget_limit_usd != TERRA_PROMPT_REASONING_SCREEN_HARD_BUDGET_USD:
            raise OfflineRunnerError("Terra 2x2 budget differs from contract")
    if plan.split == "terra_calibration":
        if output_dir != TERRA_CALIBRATION_RUN_DIR.resolve():
            raise OfflineRunnerError(
                "Terra calibration must use its canonical run directory"
            )
        if budget_limit_usd != TERRA_CALIBRATION_HARD_BUDGET_USD:
            raise OfflineRunnerError("Terra calibration budget differs from contract")
    if plan.split == "terra_validation":
        if output_dir != TERRA_VALIDATION_RUN_DIR.resolve():
            raise OfflineRunnerError("Terra validation must use its canonical run directory")
        if budget_limit_usd != TERRA_VALIDATION_HARD_BUDGET_USD:
            raise OfflineRunnerError("Terra validation budget differs from freeze")
    if plan.split == "terra_v2_prompt_screen":
        expected_dir = TERRA_V2_SCREEN_RUN_DIRS[
            plan.config.prompt_version
        ].resolve()
        if output_dir != expected_dir:
            raise OfflineRunnerError(
                "Terra-v2 screen must use its canonical prompt run directory"
            )
        if budget_limit_usd != TERRA_V2_SCREEN_HARD_BUDGET_USD:
            raise OfflineRunnerError("Terra-v2 screen budget differs from contract")
    if plan.split == "terra_high_reasoning_screen":
        expected_dir = TERRA_HIGH_SCREEN_RUN_DIRS[
            plan.config.reasoning_effort
        ].resolve()
        if output_dir != expected_dir:
            raise OfflineRunnerError(
                "Terra high screen must use its canonical reasoning run directory"
            )
        if budget_limit_usd != TERRA_HIGH_SCREEN_HARD_BUDGET_USD:
            raise OfflineRunnerError(
                "Terra high screen budget differs from contract"
            )
    if plan.split == "terra_high_calibration":
        if output_dir != TERRA_HIGH_CALIBRATION_RUN_DIR.resolve():
            raise OfflineRunnerError(
                "Terra-high calibration must use its canonical run directory"
            )
        if budget_limit_usd != TERRA_HIGH_CALIBRATION_HARD_BUDGET_USD:
            raise OfflineRunnerError(
                "Terra-high calibration budget differs from contract"
            )
    if plan.split == "terra_high_validation":
        if output_dir != TERRA_HIGH_VALIDATION_RUN_DIR.resolve():
            raise OfflineRunnerError(
                "Terra-high validation must use its canonical run directory"
            )
        freeze = json.loads(TERRA_HIGH_FREEZE_PATH.read_text(encoding="utf-8"))
        frozen_budget = Decimal(
            str(freeze["validation"]["hard_budget_limit_usd"])
        )
        if budget_limit_usd != frozen_budget:
            raise OfflineRunnerError(
                "Terra-high validation budget differs from freeze"
            )
    if plan.split == "locked_holdout":
        if output_dir != LOCKED_HOLDOUT_RUN_DIR.resolve():
            raise OfflineRunnerError(
                "locked holdout must use its canonical run directory"
            )
        freeze = json.loads(
            LOCKED_HOLDOUT_FREEZE_PATH.read_text(encoding="utf-8")
        )
        frozen_budget = Decimal(
            str(freeze["holdout"]["hard_budget_limit_usd"])
        )
        if budget_limit_usd != frozen_budget:
            raise OfflineRunnerError(
                "locked holdout budget differs from freeze"
            )
    if plan.split == "luna_v4_validation":
        if output_dir != LUNA_V4_VALIDATION_RUN_DIR.resolve():
            raise OfflineRunnerError(
                "Luna-v4 validation must use its single canonical run directory"
            )
        freeze = json.loads(LUNA_V4_FREEZE_PATH.read_text(encoding="utf-8"))
        frozen_budget = Decimal(str(freeze["validation"]["hard_budget_limit_usd"]))
        if budget_limit_usd != frozen_budget:
            raise OfflineRunnerError(
                "Luna-v4 validation budget differs from configuration freeze"
            )
    predictions_path = output_dir / PREDICTIONS_FILENAME
    manifest_path = output_dir / RUN_MANIFEST_FILENAME
    if predictions_path.exists() or manifest_path.exists():
        raise FileExistsError("run artifacts already exist; refusing overwrite")

    api_key = api_key_loader()
    client = client_factory(api_key)
    verify_model_availability(client, plan.config.model)

    output_dir.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now(timezone.utc).isoformat()
    manifest = _base_manifest(
        plan,
        budget_limit_usd=budget_limit_usd,
        status="running",
    )
    manifest["started_at"] = started_at
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )

    completed = 0
    technical_failures = 0
    actual_cost = Decimal("0")
    for case in plan.cases:
        prediction = _request_case(
            client=client,
            case=case,
            config=plan.config,
            sleep_fn=sleep_fn,
            monotonic_fn=monotonic_fn,
        )
        if prediction["status"] == "completed":
            completed += 1
        else:
            technical_failures += 1
        if prediction.get("cost_usd") is not None:
            actual_cost += Decimal(str(prediction["cost_usd"]))
        if actual_cost > budget_limit_usd:
            raise AssertionError("preflight hard-budget invariant was violated")
        _write_jsonl_row(predictions_path, prediction)

    manifest["status"] = "completed"
    manifest["completed_at"] = datetime.now(timezone.utc).isoformat()
    manifest["result"] = {
        "completed_cases": completed,
        "technical_failures": technical_failures,
        "recorded_cost_usd": float(actual_cost),
        "predictions_file": PREDICTIONS_FILENAME,
        "predictions_sha256": _sha256_file(predictions_path),
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return {
        "predictions": predictions_path,
        "run_manifest": manifest_path,
    }


def dry_run_summary(
    plan: RunPlan,
    *,
    budget_limit_usd: Decimal | None = None,
    output_dir: Path | None = None,
) -> dict[str, object]:
    system_instructions = get_system_instructions(plan.config.prompt_version)
    prompt_hash = _sha256_bytes(system_instructions.encode("utf-8"))
    schema_hash = _sha256_bytes(
        _canonical_json(MODEL_OUTPUT_JSON_SCHEMA).encode("utf-8")
    )
    summary: dict[str, object] = {
        "mode": "dry_run",
        "network_calls": 0,
        "split": plan.split,
        "case_count": plan.case_count,
        "selected_case_ids": (
            None
            if plan.split == "locked_holdout"
            else [str(case["case_id"]) for case in plan.cases]
        ),
        "case_ids_sha256": _sha256_bytes(
            _canonical_json(
                [str(case["case_id"]) for case in plan.cases]
            ).encode("utf-8")
        ),
        "model": plan.config.model,
        "reasoning_effort": plan.config.reasoning_effort,
        "prompt": {
            "version": plan.config.prompt_version,
            "sha256": prompt_hash,
            "system_instructions": system_instructions,
        },
        "structured_output": {
            "strict": True,
            "schema_sha256": schema_hash,
            "text_format": RESPONSES_TEXT_FORMAT,
        },
        "request_plan": {
            "case_requests": plan.case_count,
            "retries_per_case": plan.config.retries,
            "maximum_responses_api_requests": plan.max_attempts,
            "model_availability_checks": 1,
            "maximum_total_api_calls": plan.max_attempts + 1,
        },
        "answer_key_leakage_check": {
            "status": "passed",
            "model_input_keys": sorted(_MODEL_INPUT_KEYS),
            "request_input_keys": [
                "raw_listing_text",
                "parser_snapshot",
            ],
            "forbidden_keys_present": [],
        },
        "preflight_worst_case_cost_usd": float(plan.worst_case_cost_usd),
        "input_file": plan.input_path.name,
        "input_sha256": plan.input_sha256,
        "credential_source": ".env.eval.local",
        "credential_read": False,
        "locked_holdout_enabled": plan.split == "locked_holdout",
    }
    if budget_limit_usd is not None:
        summary["hard_budget_limit_usd"] = float(budget_limit_usd)
        summary["budget_sufficient"] = (
            budget_limit_usd >= plan.worst_case_cost_usd
        )
    if output_dir is not None:
        resolved_output_dir = _ensure_inside_eval(output_dir)
        report_dir = resolved_output_dir / "reports"
        artifacts = {
            "predictions": resolved_output_dir / PREDICTIONS_FILENAME,
            "run_manifest": resolved_output_dir / RUN_MANIFEST_FILENAME,
            **{
                name: report_dir / filename
                for name, filename in REPORT_FILENAMES.items()
            },
        }
        summary["future_artifacts"] = {
            "created_by_dry_run": False,
            "paths": {
                name: str(path.relative_to(REPO_ROOT))
                for name, path in artifacts.items()
            },
        }
    return summary


def _decimal_argument(value: str) -> Decimal:
    try:
        parsed = Decimal(value)
    except Exception as exc:
        raise argparse.ArgumentTypeError("must be a decimal number") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive finite number")
    return parsed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the isolated synthetic offline AI QA experiment.",
    )
    parser.add_argument(
        "--split",
        choices=(
            "development",
            "luna_calibration",
            "luna_validation",
            "luna_v3_calibration",
            "luna_v3_validation",
            "luna_v4_calibration",
            "luna_v4_validation",
            "luna_v5_calibration",
            "luna_v5_validation",
            "luna_effort_screen",
            "luna_low_calibration",
            "luna_low_validation",
            "terra_effort_screen",
            "terra_prompt_reasoning_screen",
            "terra_calibration",
            "terra_validation",
            "terra_v2_prompt_screen",
            "terra_high_reasoning_screen",
            "terra_high_calibration",
            "terra_high_validation",
            "locked_holdout",
        ),
        default="development",
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--prompt-version",
        choices=tuple(PROMPT_INSTRUCTIONS),
        default=EVAL_PROMPT_VERSION,
    )
    parser.add_argument(
        "--reasoning-effort",
        choices=("none", "low", "medium", "high"),
        default=DEFAULT_REASONING_EFFORT,
    )
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=DEFAULT_MAX_OUTPUT_TOKENS,
    )
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES)
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--check-model", action="store_true")
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--freeze-luna-v4", action="store_true")
    mode.add_argument("--freeze-locked-holdout", action="store_true")
    parser.add_argument("--max-cost-usd", type=_decimal_argument)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--calibration-report", type=Path)
    parser.add_argument("--calibration-run-manifest", type=Path)
    args = parser.parse_args()

    config = RunnerConfig(
        model=args.model,
        reasoning_effort=args.reasoning_effort,
        max_output_tokens=args.max_output_tokens,
        retries=args.retries,
        timeout_seconds=args.timeout_seconds,
        prompt_version=args.prompt_version,
    )
    try:
        if args.freeze_locked_holdout:
            if args.max_cost_usd != LOCKED_HOLDOUT_HARD_BUDGET_USD:
                parser.error(
                    "--freeze-locked-holdout requires "
                    f"--max-cost-usd {LOCKED_HOLDOUT_HARD_BUDGET_USD}"
                )
            freeze_path = write_locked_holdout_configuration_freeze()
            result = {
                "mode": "freeze_locked_holdout",
                "artifact": str(freeze_path.relative_to(REPO_ROOT)),
                "locked_holdout_authorized_once": True,
                "hard_budget_limit_usd": float(
                    LOCKED_HOLDOUT_HARD_BUDGET_USD
                ),
            }
        elif args.freeze_luna_v4:
            if args.max_cost_usd is None:
                parser.error("--freeze-luna-v4 requires --max-cost-usd")
            if args.calibration_report is None or args.calibration_run_manifest is None:
                parser.error(
                    "--freeze-luna-v4 requires --calibration-report and "
                    "--calibration-run-manifest"
                )
            freeze_path = write_luna_v4_configuration_freeze(
                calibration_report_path=args.calibration_report,
                calibration_run_manifest_path=args.calibration_run_manifest,
                validation_budget_limit_usd=args.max_cost_usd,
            )
            result: Mapping[str, object] = {
                "mode": "freeze_luna_v4",
                "artifact": str(freeze_path.relative_to(REPO_ROOT)),
                "locked_holdout_authorized": False,
            }
        else:
            plan = build_run_plan(
                split=args.split,
                limit=args.limit,
                config=config,
            )
            if args.check_model:
                api_key = load_eval_api_key()
                client = _new_openai_client(api_key)
                verify_model_availability(client, config.model)
                result = {
                    "mode": "model_check",
                    "model": config.model,
                    "available": True,
                    "automatic_substitution": False,
                }
            elif args.execute:
                if args.max_cost_usd is None:
                    parser.error("--execute requires --max-cost-usd")
                if args.output_dir is None:
                    parser.error("--execute requires --output-dir")
                written = execute_run_plan(
                    plan,
                    output_dir=args.output_dir,
                    budget_limit_usd=args.max_cost_usd,
                )
                result = {
                    "mode": "execute",
                    "case_count": plan.case_count,
                    "artifacts": {
                        key: str(path.relative_to(REPO_ROOT))
                        for key, path in written.items()
                    },
                }
            else:
                result = dry_run_summary(
                    plan,
                    budget_limit_usd=args.max_cost_usd,
                    output_dir=args.output_dir,
                )
    except (ValueError, OSError, OfflineRunnerError) as exc:
        parser.error(str(exc))
        return
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
