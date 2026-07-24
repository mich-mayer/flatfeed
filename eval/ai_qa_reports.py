from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from eval.ai_qa_scorer import ERROR_FIELDS


REPORT_FILENAMES = {
    "json_report": "report.json",
    "markdown_report": "report.md",
    "false_positives": "false_positives.jsonl",
    "false_negatives": "false_negatives.jsonl",
    "field_breakdown": "field_breakdown.json",
}

_METRIC_LABELS = (
    ("error_recall", "Error recall"),
    ("missed_error_rate", "Missed-error rate"),
    ("false_alert_rate", "False-alert rate"),
    ("challenge_set_precision", "Challenge-set precision"),
    ("field_localization_accuracy", "Field-localization accuracy"),
    ("structured_output_coverage", "Structured-output coverage"),
    ("technical_failure_rate", "Technical failure rate"),
)


def _format_percentage(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2%}"


def _format_interval(metric: Mapping[str, Any]) -> str:
    interval = metric["wilson_95_ci"]
    if interval["low"] is None:
        return "n/a"
    return (
        f"{_format_percentage(interval['low'])}–"
        f"{_format_percentage(interval['high'])}"
    )


def format_markdown_report(report: Mapping[str, Any]) -> str:
    lines = [
        "# Synthetic offline AI QA evaluation",
        "",
        (
            "Engineering evaluation artifact. Results apply only to this "
            "synthetic challenge set and are not production precision or "
            "user-impact evidence."
        ),
        (
            "This offline scorer does not integrate OpenAI or AI QA into the "
            "Telegram bot or product runtime."
        ),
        "",
        f"- Split: `{report['split']}`",
        f"- Run label: `{report.get('run_label') or 'not set'}`",
        f"- Cases: {report['counts']['total_cases']}",
        (
            f"- Clean / corrupted: {report['counts']['clean_cases']} / "
            f"{report['counts']['corrupted_cases']}"
        ),
        "",
        "## Metrics",
        "",
        "| Metric | Estimate | Wilson 95% CI | Count |",
        "|---|---:|---:|---:|",
    ]
    for key, label in _METRIC_LABELS:
        metric = report["metrics"][key]
        lines.append(
            f"| {label} | {_format_percentage(metric['value'])} | "
            f"{_format_interval(metric)} | "
            f"{metric['numerator']}/{metric['denominator']} |"
        )

    lines.extend(
        [
            "",
            "## Field breakdown",
            "",
            (
                "| Field | Corrupted | Alerted | Correct field | "
                "Localized recall | Wilson 95% CI |"
            ),
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for field in ERROR_FIELDS:
        breakdown = report["field_breakdown"][field]
        localized = breakdown["localized_recall"]
        lines.append(
            f"| {breakdown['label']} | {breakdown['total_corrupted']} | "
            f"{breakdown['alerted']} | {breakdown['correctly_localized']} | "
            f"{_format_percentage(localized['value'])} | "
            f"{_format_interval(localized)} |"
        )

    counts = report["counts"]
    gates = report["acceptance_gates"]
    lines.extend(
        [
            "",
            "## Acceptance gates",
            "",
            (
                "These are eval-contract targets. Status is calculated from "
                "unrounded estimates."
            ),
            "",
            "| Gate | Rule | Estimate | Status |",
            "|---|---:|---:|---:|",
        ]
    )
    for name, gate in gates["gates"].items():
        operator = ">=" if gate["comparison"] == "min" else "<="
        lines.append(
            f"| `{name}` | {operator} {_format_percentage(gate['threshold'])} | "
            f"{_format_percentage(gate['value'])} | {gate['status']} |"
        )
    lines.extend(
        [
            "",
            "## Output and failure diagnostics",
            "",
            f"- Invalid JSON: {counts.get('outcome_invalid_json', 0)}",
            f"- Invalid schema: {counts.get('outcome_invalid_schema', 0)}",
            f"- Technical failures: {counts.get('technical_failures', 0)}",
            f"- False positives: {counts.get('false_positives', 0)}",
            f"- False negatives: {counts.get('false_negatives', 0)}",
            (
                "- Wrong field localizations: "
                f"{counts.get('wrong_field_localizations', 0)}"
            ),
            "",
            "## Operational measurements",
            "",
        ]
    )
    operational = report["operational"]
    lines.extend(
        [
            f"- Case result records: {operational['case_result_records']}",
            f"- Completed cases: {operational['completed_cases']}",
            f"- Request count (including retries): {operational['request_count']}",
            f"- Retries: {operational['retry_count']}",
        ]
    )
    usage = operational.get("token_usage")
    if usage is None:
        lines.append("- Token usage: not recorded")
    else:
        lines.append(
            "- Token usage: "
            f"{usage['input_tokens']} input, "
            f"{usage['cached_input_tokens']} cached input, "
            f"{usage['output_tokens']} output, "
            f"{usage['reasoning_tokens']} reasoning "
            f"(n={usage['records_with_usage']}/"
            f"{usage['total_case_records']}, "
            f"{'partial' if usage['is_partial'] else 'complete'})"
        )
    cost = operational.get("cost")
    if cost is None:
        lines.append("- Cost: not recorded")
    else:
        lines.append(
            f"- Total recorded cost: ${cost['total_usd']:.6f} "
            f"(n={cost['records_with_cost']}/"
            f"{cost['total_case_records']}, "
            f"{'partial' if cost['is_partial'] else 'complete'})"
        )
        per_request = cost["cost_per_completed_case_usd"]
        lines.append(
            "- Cost per completed case: "
            + (
                "n/a"
                if per_request is None
                else f"${per_request:.6f}"
            )
        )
    latency = operational.get("latency_by_mode")
    if latency is None:
        lines.append("- Latency: not recorded")
    else:
        for mode, values in latency.items():
            lines.append(
                f"- Latency `{mode}`: p50 {values['p50_ms']:.2f} ms, "
                f"p95 {values['p95_ms']:.2f} ms "
                f"(n={values['sample_count']}/"
                f"{values['total_case_records']}, "
                f"{'partial' if values['is_partial'] else 'complete'})"
            )

    lines.extend(
        [
            "",
            "## Diagnostic artifacts",
            "",
            "- `false_positives.jsonl`",
            "- `false_negatives.jsonl`",
            "- `field_breakdown.json`",
            "",
        ]
    )
    return "\n".join(lines)


def _write_jsonl(
    path: Path,
    rows: Sequence[Mapping[str, object]],
) -> None:
    serialized = "".join(
        json.dumps(
            row,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
        for row in rows
    )
    path.write_text(serialized, encoding="utf-8")


def write_report_bundle(
    report: Mapping[str, Any],
    output_dir: Path,
) -> dict[str, Path]:
    """Write the machine report, summary, and diagnostic artifacts."""

    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        key: output_dir / filename
        for key, filename in REPORT_FILENAMES.items()
    }
    paths["json_report"].write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    paths["markdown_report"].write_text(
        format_markdown_report(report),
        encoding="utf-8",
    )
    diagnostics = report["diagnostics"]
    _write_jsonl(
        paths["false_positives"],
        diagnostics["false_positives"],
    )
    _write_jsonl(
        paths["false_negatives"],
        diagnostics["false_negatives"],
    )
    paths["field_breakdown"].write_text(
        json.dumps(
            report["field_breakdown"],
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return paths
