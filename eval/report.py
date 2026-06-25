from __future__ import annotations

import json
from typing import Any


def format_text_report(report: dict[str, Any]) -> str:
    parser = report["parser"]
    qa = report["qa"]
    lines = [
        "FlatFeed eval report",
        "",
        f"Golden set size: {report['listing_count']}",
        f"Parser field accuracy: {parser['field_accuracy']:.1%}",
        f"Parser exact listing accuracy: {parser['exact_listing_accuracy']:.1%}",
        "",
        "Parser accuracy by field:",
    ]
    for field, value in parser["by_field"].items():
        lines.append(f"- {field}: {value:.1%}")
    lines.extend(
        [
            "",
            "Parser misses by tag:",
        ]
    )
    if parser["misses_by_tag"]:
        for tag, count in sorted(parser["misses_by_tag"].items()):
            lines.append(f"- {tag}: {count}")
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "AI QA controller:",
            f"- caught error fields: {qa['caught_error_fields']}",
            f"- missed error fields: {qa['missed_error_fields']}",
            f"- false alert fields: {qa['false_alert_fields']}",
            f"- quiet correct fields: {qa['quiet_correct_fields']}",
            f"- caught error rate: {qa['caught_error_rate']:.1%}",
            f"- false alert rate: {qa['false_alert_rate']:.1%}",
            f"- alert precision: {qa['alert_precision']:.1%}",
            "",
            f"Provider: {report['qa_provider']}",
            f"Total QA cost: ${report['total_cost_usd']:.6f}",
        ]
    )
    return "\n".join(lines)


def format_json_report(report: dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
